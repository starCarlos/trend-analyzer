from __future__ import annotations

import json
import re
from collections.abc import Mapping


SEARCH_TOKEN_RE = re.compile(r"[a-z0-9]+")
HAS_CJK_RE = re.compile(r"[\u3400-\u9FFF]")
GDELT_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "says",
    "saying",
    "the",
    "to",
    "with",
}
DEFAULT_AMBIGUOUS_QUERY_CONTEXTS = {
    "claude": {
        "ai",
        "agent",
        "agents",
        "anthropic",
        "api",
        "apis",
        "app",
        "apps",
        "artifact",
        "artifacts",
        "assistant",
        "assistants",
        "chatgpt",
        "code",
        "computer",
        "desktop",
        "down",
        "feature",
        "features",
        "haiku",
        "llm",
        "model",
        "models",
        "openai",
        "opus",
        "outage",
        "preview",
        "prompt",
        "prompts",
        "sonnet",
        "status",
        "task",
        "tasks",
    }
}


def _normalize_query_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split()).casefold()


def build_ambiguous_query_contexts(raw_json: str | None = None) -> dict[str, set[str]]:
    contexts = {query: set(tokens) for query, tokens in DEFAULT_AMBIGUOUS_QUERY_CONTEXTS.items()}
    normalized_payload = _normalize_query_text(raw_json)
    if not normalized_payload:
        return contexts

    try:
        payload = json.loads(raw_json)
    except (TypeError, ValueError):
        return contexts
    if not isinstance(payload, dict):
        return contexts

    for query, tokens in payload.items():
        normalized_query = _normalize_query_text(query)
        if not normalized_query:
            continue

        bucket = contexts.setdefault(normalized_query, set())
        candidates = tokens if isinstance(tokens, (list, tuple, set)) else [tokens]
        for token in candidates:
            normalized_token = _normalize_query_text(token)
            if not normalized_token:
                continue
            if HAS_CJK_RE.search(normalized_token):
                bucket.add(normalized_token)
                continue
            token_parts = SEARCH_TOKEN_RE.findall(normalized_token)
            if token_parts:
                bucket.update(token_parts)
            else:
                bucket.add(normalized_token)

    return {query: tokens for query, tokens in contexts.items() if tokens}


def archive_query_tokens(query: str) -> list[str]:
    normalized = _normalize_query_text(query)
    if not normalized:
        return []
    if HAS_CJK_RE.search(normalized):
        return [normalized]

    tokens = []
    for token in SEARCH_TOKEN_RE.findall(normalized):
        if len(token) > 1 or token in {"ai", "vr", "ar", "mcp"}:
            tokens.append(token)
    return tokens or [normalized]


def archive_match_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(SEARCH_TOKEN_RE.findall(value.casefold()))


def archive_text_matches_query(query: str, value: str | None) -> bool:
    normalized_query = _normalize_query_text(query)
    if not normalized_query or not value:
        return False
    if HAS_CJK_RE.search(normalized_query):
        return normalized_query in value.casefold()

    tokens = archive_query_tokens(normalized_query)
    if not tokens:
        return False
    value_tokens = set(SEARCH_TOKEN_RE.findall(value.casefold()))
    return all(token in value_tokens for token in tokens)


def archive_match_strength(
    query: str,
    *,
    title: str | None,
    summary: str | None = None,
    url: str | None = None,
) -> str:
    if archive_text_matches_query(query, title) or archive_text_matches_query(query, url):
        return "strong"
    if archive_text_matches_query(query, summary):
        return "weak"
    return "none"


def gdelt_title_key(title: str) -> str:
    return archive_match_text(title)


def gdelt_title_token_set(title: str, query: str) -> set[str]:
    query_tokens = set(archive_query_tokens(query))
    return {
        token
        for token in SEARCH_TOKEN_RE.findall(title.casefold())
        if len(token) > 2 and token not in query_tokens and token not in GDELT_TITLE_STOPWORDS
    }


def token_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    union = len(left | right)
    return overlap / union if union else 0.0


def gdelt_matches_query(
    query: str,
    *,
    title: str | None,
    url: str | None,
    domain: str | None,
    ambiguous_query_contexts: Mapping[str, set[str]] | None = None,
) -> bool:
    normalized_query = _normalize_query_text(query)
    title_text = archive_match_text(title)
    url_text = archive_match_text(url)
    searchable = " ".join(part for part in (title_text, url_text) if part).strip()
    if not searchable or not normalized_query:
        return False

    if HAS_CJK_RE.search(normalized_query):
        raw_searchable = " ".join(part for part in (title, url) if part).casefold()
        return normalized_query in raw_searchable

    tokens = archive_query_tokens(normalized_query)
    if not tokens:
        return False

    title_tokens = set(title_text.split())
    url_tokens = set(url_text.split())
    matched = normalized_query in searchable or all(token in title_tokens or token in url_tokens for token in tokens)
    if not matched:
        return False

    if len(tokens) != 1:
        return True

    contexts = ambiguous_query_contexts or DEFAULT_AMBIGUOUS_QUERY_CONTEXTS
    context_tokens = contexts.get(tokens[0])
    if not context_tokens:
        return True

    context_text = " ".join(part for part in (title_text, url_text, archive_match_text(domain)) if part).strip()
    if not context_text:
        return False
    available_tokens = set(context_text.split())
    return any(token in available_tokens for token in context_tokens)
