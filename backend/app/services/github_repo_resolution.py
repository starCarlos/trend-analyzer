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
    payload, _ = client(endpoint, headers)
    if not isinstance(payload, dict):
        return None

    items = payload.get("items")
    if not isinstance(items, list):
        return None

    exact_matches: list[str] = []
    self_named_matches: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name.casefold() != query.casefold():
            continue

        full_name = str(item.get("full_name") or "").strip().lower()
        if not full_name:
            owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
            login = str(owner.get("login") or "").strip().lower()
            if login:
                full_name = f"{login}/{name.lower()}"
        if "/" not in full_name:
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
