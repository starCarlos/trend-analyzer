from __future__ import annotations

from urllib import parse


NEWSNOW_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

LEGACY_NEWSNOW_SOURCE_ID_MAP = {
    "weibo-hot": "weibo",
    "zhihu-hot": "zhihu",
    "bilibili-hot": "bilibili",
    "juejin-hot": "juejin",
    "36kr-hot": "36kr",
    "github-trending": "github",
}


def normalize_newsnow_source_id(source_id: str) -> str:
    candidate = source_id.strip()
    return LEGACY_NEWSNOW_SOURCE_ID_MAP.get(candidate, candidate)


def iter_newsnow_source_ids(source_id: str) -> list[str]:
    candidates = [normalize_newsnow_source_id(source_id), source_id.strip()]
    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def build_newsnow_source_endpoint(
    base_url: str,
    source_id: str,
    *,
    legacy: bool = False,
    normalize: bool = True,
) -> str:
    base = base_url.rstrip("/")
    encoded_source_id = parse.quote(normalize_newsnow_source_id(source_id) if normalize else source_id.strip())
    if legacy:
        return f"{base}/api/s/{encoded_source_id}"
    return f"{base}/api/s?id={encoded_source_id}"


def iter_newsnow_source_endpoints(base_url: str, source_id: str) -> list[str]:
    candidates: list[str] = []
    normalized_source_id = normalize_newsnow_source_id(source_id)
    for candidate_id in iter_newsnow_source_ids(source_id):
        should_normalize = candidate_id == normalized_source_id
        for legacy in (False, True):
            endpoint = build_newsnow_source_endpoint(
                base_url,
                candidate_id,
                legacy=legacy,
                normalize=should_normalize,
            )
            if endpoint not in candidates:
                candidates.append(endpoint)
    return candidates


def newsnow_request_headers() -> dict[str, str]:
    return {
        "User-Agent": NEWSNOW_BROWSER_USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
    }
