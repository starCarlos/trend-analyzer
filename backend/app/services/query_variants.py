from __future__ import annotations

import json
import re
from functools import lru_cache
from urllib import parse, request

from app.config import Settings, get_settings
from app.services.archive_relevance import HAS_CJK_RE


ASCII_ALPHA_RE = re.compile(r"[A-Za-z]")
WHITESPACE_RE = re.compile(r"\s+")
TRANSLATE_API_URL = "https://translate.googleapis.com/translate_a/single"


def _normalize_query(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", str(value)).strip()


def translate_keyword_variant(
    query: str,
    *,
    target_language: str = "en",
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    normalized_query = _normalize_query(query)
    if not normalized_query:
        return ""

    return _translate_keyword_variant_cached(
        normalized_query,
        target_language,
        resolved_settings.http_proxy or "",
        resolved_settings.request_timeout_seconds,
    )


@lru_cache(maxsize=256)
def _translate_keyword_variant_cached(
    query: str,
    target_language: str,
    http_proxy: str,
    request_timeout_seconds: float,
) -> str:
    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": target_language,
        "dt": "t",
        "q": query,
    }
    url = f"{TRANSLATE_API_URL}?{parse.urlencode(params)}"

    handlers: list[request.BaseHandler] = []
    if http_proxy:
        handlers.append(request.ProxyHandler({"http": http_proxy, "https": http_proxy}))
    opener = request.build_opener(*handlers)
    req = request.Request(
        url,
        headers={
            "User-Agent": "TrendScope/0.1",
            "Accept": "application/json,text/plain,*/*",
        },
    )

    try:
        with opener.open(req, timeout=request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return ""

    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        return ""

    parts: list[str] = []
    for segment in payload[0]:
        if not isinstance(segment, list) or not segment:
            continue
        translated = segment[0]
        if not isinstance(translated, str):
            continue
        parts.append(translated)

    translated_query = _normalize_query("".join(parts))
    if not translated_query or translated_query.casefold() == query.casefold():
        return ""
    if target_language == "en" and (HAS_CJK_RE.search(translated_query) or not ASCII_ALPHA_RE.search(translated_query)):
        return ""
    return translated_query


def keyword_query_variants(query: str, *, settings: Settings | None = None) -> list[str]:
    normalized_query = _normalize_query(query)
    if not normalized_query:
        return []

    variants: list[str] = []
    seen: set[str] = set()

    def add(candidate: str | None) -> None:
        normalized_candidate = _normalize_query(candidate).strip("/")
        if not normalized_candidate:
            return
        identity = normalized_candidate.casefold()
        if identity in seen:
            return
        seen.add(identity)
        variants.append(normalized_candidate)

    add(normalized_query)

    if not HAS_CJK_RE.search(normalized_query) or ASCII_ALPHA_RE.search(normalized_query):
        return variants

    add(translate_keyword_variant(normalized_query, target_language="en", settings=settings))
    return variants
