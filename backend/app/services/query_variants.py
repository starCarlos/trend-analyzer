from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from urllib import parse, request

from app.config import Settings, get_settings
from app.models import utcnow
from app.services.archive_relevance import HAS_CJK_RE
from app.services.provider_types import ContentItemInput, TrendPointInput


ASCII_ALPHA_RE = re.compile(r"[A-Za-z]")
WHITESPACE_RE = re.compile(r"\s+")
TRANSLATE_API_URL = "https://translate.googleapis.com/translate_a/single"


def _normalize_query(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", str(value)).strip()


def dedupe_content_inputs(items: list[ContentItemInput]) -> list[ContentItemInput]:
    deduped: list[ContentItemInput] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        identity = (item.source, item.external_key)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(item)
    return deduped


def _newsnow_platform(item: ContentItemInput) -> str | None:
    try:
        payload = json.loads(item.meta_json or "")
    except (TypeError, ValueError):
        payload = None
    if isinstance(payload, dict):
        platform = payload.get("platform")
        if isinstance(platform, str) and platform.strip():
            return platform.strip()
    if item.author and item.author.strip():
        return item.author.strip()
    return None


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
    if target_language.startswith("zh") and not HAS_CJK_RE.search(translated_query):
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

    if HAS_CJK_RE.search(normalized_query):
        if ASCII_ALPHA_RE.search(normalized_query):
            return variants
        add(translate_keyword_variant(normalized_query, target_language="en", settings=settings))
        return variants

    if not ASCII_ALPHA_RE.search(normalized_query):
        return variants

    add(translate_keyword_variant(normalized_query, target_language="zh-CN", settings=settings))
    return variants


def fetch_variant_content_items(
    fetcher: Callable[[str], list[ContentItemInput]],
    query_variants: list[str],
) -> tuple[list[ContentItemInput], list[str]]:
    fetched_items: list[ContentItemInput] = []
    errors: list[str] = []

    for query in query_variants:
        try:
            items = fetcher(query)
        except Exception as exc:
            errors.append(f"{query}: {exc}")
            continue
        fetched_items.extend(items or [])

    return dedupe_content_inputs(fetched_items), errors


def fetch_variant_newsnow_snapshot(
    fetcher: Callable[[str], tuple[list[TrendPointInput], list[ContentItemInput]]],
    query_variants: list[str],
    *,
    provider_name: str,
) -> tuple[list[TrendPointInput], list[ContentItemInput], list[str]]:
    snapshot_items: list[ContentItemInput] = []
    successful_queries: list[str] = []
    errors: list[str] = []
    bucket_start = None

    for query in query_variants:
        try:
            points, items = fetcher(query)
        except Exception as exc:
            errors.append(f"{query}: {exc}")
            continue

        if bucket_start is None:
            hot_hit_point = next((point for point in points if point.metric == "hot_hit_count"), None)
            bucket_start = hot_hit_point.bucket_start if hot_hit_point else (points[0].bucket_start if points else None)
        successful_queries.append(query)
        snapshot_items.extend(items or [])

    if not successful_queries and errors:
        return [], [], errors

    deduped_items = dedupe_content_inputs(snapshot_items)
    resolved_bucket_start = bucket_start or utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    platforms = sorted({platform for item in deduped_items if (platform := _newsnow_platform(item))})
    raw_json = json.dumps(
        {
            "provider": provider_name,
            "query_variants": successful_queries or query_variants,
            "platforms": platforms,
        }
    )

    trend_points = [
        TrendPointInput(
            source="newsnow",
            metric="hot_hit_count",
            source_type="snapshot",
            bucket_granularity="day",
            bucket_start=resolved_bucket_start,
            value=float(len(deduped_items)),
            raw_json=raw_json,
        ),
        TrendPointInput(
            source="newsnow",
            metric="platform_count",
            source_type="snapshot",
            bucket_granularity="day",
            bucket_start=resolved_bucket_start,
            value=float(len(platforms)),
            raw_json=raw_json,
        ),
    ]
    return trend_points, deduped_items, errors
