from __future__ import annotations

import json
from typing import Callable
from urllib import error, parse, request

from app.config import Settings, get_settings


RequestJson = Callable[[str, dict[str, str]], tuple[object, dict[str, str]]]


class _GithubSearchHttpClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        handlers: list[request.BaseHandler] = []
        if settings.http_proxy:
            handlers.append(request.ProxyHandler({"http": settings.http_proxy, "https": settings.http_proxy}))
        self.opener = request.build_opener(*handlers)

    def request_json(self, url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
        req = request.Request(url, headers=headers)
        try:
            with self.opener.open(req, timeout=self.settings.request_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                response_headers = {key: value for key, value in response.info().items()}
                return payload, response_headers
        except error.HTTPError:
            return None, {}
        except error.URLError:
            return None, {}


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _extract_full_name(item: object) -> str | None:
    if not isinstance(item, dict):
        return None

    full_name = str(item.get("full_name") or "").strip().lower()
    if full_name and "/" in full_name:
        return full_name

    name = str(item.get("name") or "").strip().lower()
    owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
    login = str(owner.get("login") or "").strip().lower()
    if not name or not login:
        return None
    return f"{login}/{name}"


def _resolve_direct_self_named_repo(
    query: str,
    *,
    settings: Settings,
    client: RequestJson,
    headers: dict[str, str],
) -> str | None:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return None

    endpoint = f"{settings.github_api_base_url.rstrip('/')}/repos/{parse.quote(normalized_query)}/{parse.quote(normalized_query)}"
    payload, _ = client(endpoint, headers)
    if not isinstance(payload, dict):
        return None

    name = str(payload.get("name") or "").strip()
    if name.casefold() != query.casefold():
        return None

    full_name = _extract_full_name(payload)
    if not full_name or "/" not in full_name:
        return None

    owner_name, repo_name = full_name.split("/", 1)
    if owner_name.casefold() != query.casefold() or repo_name.casefold() != query.casefold():
        return None
    return full_name


def resolve_github_repo_name(
    query: str,
    *,
    settings: Settings | None = None,
    request_json: RequestJson | None = None,
) -> str | None:
    settings = settings or get_settings()
    if settings.provider_mode.strip().lower() == "mock":
        return None
    if not settings.github_api_base_url.strip():
        return None

    encoded_query = parse.quote(f"{query} in:name")
    endpoint = f"{settings.github_api_base_url.rstrip('/')}/search/repositories?q={encoded_query}&per_page=10"
    headers = {
        "User-Agent": "TrendScope/0.1",
        "Accept": "application/vnd.github+json",
    }
    if settings.github_token.strip():
        headers["Authorization"] = f"Bearer {settings.github_token}"

    client = request_json or _GithubSearchHttpClient(settings).request_json
    direct_match = _resolve_direct_self_named_repo(query, settings=settings, client=client, headers=headers)
    if direct_match:
        return direct_match

    payload, _ = client(endpoint, headers)
    if not isinstance(payload, dict):
        return None

    items = payload.get("items")
    if not isinstance(items, list):
        return None

    exact_matches: list[str] = []
    self_named_matches: list[str] = []
    for item in items:
        name = str(item.get("name") or "").strip() if isinstance(item, dict) else ""
        if name.casefold() != query.casefold():
            continue

        full_name = _extract_full_name(item)
        if not full_name or "/" not in full_name:
            continue
        exact_matches.append(full_name)
        owner_name = full_name.split("/", 1)[0]
        if owner_name.casefold() == query.casefold():
            self_named_matches.append(full_name)

    unique_self_named_matches = _unique(self_named_matches)
    if len(unique_self_named_matches) == 1:
        return unique_self_named_matches[0]

    unique_matches = _unique(exact_matches)
    if len(unique_matches) != 1:
        return None
    return unique_matches[0]
