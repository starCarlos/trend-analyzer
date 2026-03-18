from __future__ import annotations

from datetime import datetime, timedelta
import json
import re
from typing import Protocol
from urllib import error, request

from app.config import Settings, get_settings
from app.models import utcnow
from app.services.mock_providers import generate_github_content, generate_github_history, generate_newsnow_snapshot
from app.services.provider_urls import iter_newsnow_source_endpoints, newsnow_request_headers
from app.services.provider_types import ContentItemInput, TrendPointInput


class ProviderError(RuntimeError):
    pass


class ProviderHttpError(ProviderError):
    def __init__(self, status_code: int, url: str, detail: str):
        self.status_code = status_code
        self.url = url
        self.detail = detail
        super().__init__(f"HTTP {status_code} for {url}: {detail}")


NEWSNOW_RETRY_ATTEMPTS = 2
JUEJIN_DATE_PUBLISHED_RE = re.compile(r'<meta[^>]+itemprop="datePublished"[^>]+content="([^"]+)"')
JUEJIN_TIME_RE = re.compile(r'<time[^>]+datetime="([^"]+)"')
JUEJIN_SCHEMA_DATE_RE = re.compile(r'"datePublished":"([^"]+)"')


class DataProvider(Protocol):
    name: str

    def fetch_github_history(self, target_ref: str) -> list[TrendPointInput]:
        raise NotImplementedError

    def fetch_github_content(self, target_ref: str) -> list[ContentItemInput]:
        raise NotImplementedError

    def fetch_newsnow_snapshot(self, query: str) -> tuple[list[TrendPointInput], list[ContentItemInput]]:
        raise NotImplementedError


class MockDataProvider:
    name = "mock"

    def fetch_github_history(self, target_ref: str) -> list[TrendPointInput]:
        return generate_github_history(target_ref)

    def fetch_github_content(self, target_ref: str) -> list[ContentItemInput]:
        return generate_github_content(target_ref)

    def fetch_newsnow_snapshot(self, query: str) -> tuple[list[TrendPointInput], list[ContentItemInput]]:
        return generate_newsnow_snapshot(query)


class RealDataProvider:
    name = "real"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._published_at_cache: dict[str, datetime | None] = {}
        handlers: list[request.BaseHandler] = []
        if settings.http_proxy:
            handlers.append(request.ProxyHandler({"http": settings.http_proxy, "https": settings.http_proxy}))
        self.opener = request.build_opener(*handlers)

    def _headers(self, *, github_stars: bool = False) -> dict[str, str]:
        headers = {
            "User-Agent": "TrendScope/0.1",
            "Accept": "application/vnd.github.star+json" if github_stars else "application/json",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    def _request_json(self, url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
        req = request.Request(url, headers=headers)
        try:
            with self.opener.open(req, timeout=self.settings.request_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                response_headers = {key: value for key, value in response.info().items()}
                return payload, response_headers
        except error.HTTPError as exc:  # pragma: no cover - network dependent
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ProviderHttpError(exc.code, url, detail[:200]) from exc
        except error.URLError as exc:  # pragma: no cover - network dependent
            raise ProviderError(f"Network error for {url}: {exc.reason}") from exc

    def _request_text(self, url: str, headers: dict[str, str]) -> str:
        req = request.Request(url, headers=headers)
        try:
            with self.opener.open(req, timeout=self.settings.request_timeout_seconds) as response:
                return response.read().decode("utf-8", errors="ignore")
        except error.HTTPError as exc:  # pragma: no cover - network dependent
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ProviderHttpError(exc.code, url, detail[:200]) from exc
        except error.URLError as exc:  # pragma: no cover - network dependent
            raise ProviderError(f"Network error for {url}: {exc.reason}") from exc

    @staticmethod
    def _parse_github_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)

    @classmethod
    def _parse_optional_github_datetime(cls, value: str | None) -> datetime | None:
        if not value:
            return None
        return cls._parse_github_datetime(value)

    @staticmethod
    def _parse_link_header(value: str | None) -> dict[str, str]:
        if not value:
            return {}
        links: dict[str, str] = {}
        for part in value.split(","):
            section = part.strip()
            if ";" not in section:
                continue
            url_part, rel_part = section.split(";", 1)
            url = url_part.strip().removeprefix("<").removesuffix(">")
            rel = rel_part.strip().replace('rel="', "").replace('"', "")
            links[rel] = url
        return links

    @staticmethod
    def _truncate_text(value: str | None, limit: int = 240) -> str | None:
        if not value:
            return None
        text = " ".join(value.split())
        if not text:
            return None
        if len(text) <= limit:
            return text
        return f"{text[: limit - 1].rstrip()}…"

    def fetch_github_history(self, target_ref: str) -> list[TrendPointInput]:
        repo_url = f"{self.settings.github_api_base_url}/repos/{target_ref}"
        repo_payload, _ = self._request_json(repo_url, headers=self._headers())
        if not isinstance(repo_payload, dict):
            raise ProviderError("Unexpected GitHub repo payload.")

        created_at = self._parse_github_datetime(repo_payload["created_at"])
        stargazers_count = int(repo_payload.get("stargazers_count", 0))
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        if stargazers_count == 0:
            return [
                TrendPointInput(
                    source="github",
                    metric="star_delta",
                    source_type="backfill",
                    bucket_granularity="day",
                    bucket_start=today,
                    value=0.0,
                    raw_json=json.dumps({"target_ref": target_ref, "provider": self.name, "truncated": False}),
                )
            ]

        next_url = f"{repo_url}/stargazers?per_page=100&page=1"
        page_count = 0
        truncated = False
        starred_dates: dict[datetime, int] = {}

        while next_url and page_count < self.settings.github_history_max_pages:
            payload, headers = self._request_json(next_url, headers=self._headers(github_stars=True))
            if not isinstance(payload, list):
                raise ProviderError("Unexpected GitHub stargazers payload.")

            for item in payload:
                if not isinstance(item, dict) or "starred_at" not in item:
                    continue
                starred_at = self._parse_github_datetime(item["starred_at"]).replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                starred_dates[starred_at] = starred_dates.get(starred_at, 0) + 1

            page_count += 1
            next_url = self._parse_link_header(headers.get("Link")).get("next")

        if next_url:
            truncated = True

        start_day = min(starred_dates) if starred_dates else created_at.replace(hour=0, minute=0, second=0, microsecond=0)
        if not truncated:
            start_day = created_at.replace(hour=0, minute=0, second=0, microsecond=0)

        points: list[TrendPointInput] = []
        cursor = start_day
        while cursor <= today:
            points.append(
                TrendPointInput(
                    source="github",
                    metric="star_delta",
                    source_type="backfill",
                    bucket_granularity="day",
                    bucket_start=cursor,
                    value=float(starred_dates.get(cursor, 0)),
                    raw_json=json.dumps(
                        {
                            "target_ref": target_ref,
                            "provider": self.name,
                            "pages_fetched": page_count,
                            "truncated": truncated,
                        }
                    ),
                )
            )
            cursor += timedelta(days=1)

        return points

    def fetch_github_content(self, target_ref: str) -> list[ContentItemInput]:
        repo_url = f"{self.settings.github_api_base_url}/repos/{target_ref}"
        releases_url = f"{repo_url}/releases?per_page=6"
        issues_url = f"{repo_url}/issues?state=all&sort=updated&direction=desc&per_page=12"

        try:
            releases_payload, _ = self._request_json(releases_url, headers=self._headers())
        except ProviderHttpError as exc:
            if exc.status_code != 404:
                raise
            releases_payload = []
        issues_payload, _ = self._request_json(issues_url, headers=self._headers())

        if not isinstance(releases_payload, list):
            raise ProviderError("Unexpected GitHub releases payload.")
        if not isinstance(issues_payload, list):
            raise ProviderError("Unexpected GitHub issues payload.")

        content_items: list[ContentItemInput] = []

        for item in releases_payload:
            if not isinstance(item, dict):
                continue
            title = str(item.get("name") or item.get("tag_name") or "").strip()
            if not title:
                continue
            release_id = item.get("id") or item.get("tag_name") or title
            author = item.get("author") if isinstance(item.get("author"), dict) else {}
            published_at = self._parse_optional_github_datetime(item.get("published_at") or item.get("created_at"))
            content_items.append(
                ContentItemInput(
                    source="github",
                    source_type="backfill",
                    external_key=f"{target_ref}:release:{release_id}",
                    title=title,
                    url=str(item.get("html_url")) if item.get("html_url") else None,
                    summary=self._truncate_text(str(item.get("body") or "").strip() or None),
                    author=str(author.get("login") or "github"),
                    published_at=published_at,
                    meta_json=json.dumps(
                        {
                            "provider": self.name,
                            "target_ref": target_ref,
                            "content_type": "release",
                        }
                    ),
                )
            )

        for item in issues_payload:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            content_type = "pull" if item.get("pull_request") else "issue"
            github_id = item.get("id") or item.get("number") or title
            user = item.get("user") if isinstance(item.get("user"), dict) else {}
            published_at = self._parse_optional_github_datetime(item.get("updated_at") or item.get("created_at"))
            content_items.append(
                ContentItemInput(
                    source="github",
                    source_type="backfill",
                    external_key=f"{target_ref}:{content_type}:{github_id}",
                    title=title,
                    url=str(item.get("html_url")) if item.get("html_url") else None,
                    summary=self._truncate_text(str(item.get("body") or "").strip() or None),
                    author=str(user.get("login") or "github"),
                    published_at=published_at,
                    meta_json=json.dumps(
                        {
                            "provider": self.name,
                            "target_ref": target_ref,
                            "content_type": content_type,
                            "number": item.get("number"),
                            "state": item.get("state"),
                        }
                    ),
                )
            )

        content_items.sort(key=lambda item: item.published_at or datetime.min, reverse=True)
        return content_items[:20]

    @staticmethod
    def _parse_newsnow_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        candidate = value.strip()
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m-%d %H:%M"):
                try:
                    parsed = datetime.strptime(candidate, fmt)
                    if fmt == "%m-%d %H:%M":
                        parsed = parsed.replace(year=utcnow().year)
                    return parsed
                except ValueError:
                    continue
        return None

    @classmethod
    def _extract_juejin_published_at(cls, html: str) -> datetime | None:
        for pattern in (JUEJIN_DATE_PUBLISHED_RE, JUEJIN_TIME_RE, JUEJIN_SCHEMA_DATE_RE):
            match = pattern.search(html)
            if not match:
                continue
            published_at = cls._parse_newsnow_datetime(match.group(1))
            if published_at:
                return published_at
        return None

    def _resolve_newsnow_published_at(self, platform: str, url: str | None) -> datetime | None:
        if not url:
            return None
        if platform != "juejin":
            return None
        if url in self._published_at_cache:
            return self._published_at_cache[url]

        html = self._request_text(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 TrendScope/0.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        published_at = self._extract_juejin_published_at(html)
        self._published_at_cache[url] = published_at
        return published_at

    def fetch_newsnow_snapshot(self, query: str) -> tuple[list[TrendPointInput], list[ContentItemInput]]:
        query_lc = query.casefold()
        fetched_at = utcnow().replace(microsecond=0)
        bucket_start = fetched_at.replace(hour=0, minute=0, second=0, microsecond=0)
        source_ids = [item.strip() for item in self.settings.newsnow_source_ids.split(",") if item.strip()]

        content_items: list[ContentItemInput] = []
        hit_platforms: set[str] = set()

        for source_id in source_ids:
            payload = self._request_newsnow_source(source_id)

            items = payload.get("items", [])
            if not isinstance(items, list):
                continue

            platform = source_id.split("-", 1)[0]

            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or item.get("name") or "").strip()
                if not title or query_lc not in title.casefold():
                    continue

                url_value = item.get("url") or item.get("link")
                published_at = self._parse_newsnow_datetime(
                    str(item.get("time") or item.get("pubDate") or item.get("published_at") or "").strip()
                )
                if not published_at:
                    published_at = self._resolve_newsnow_published_at(platform, str(url_value) if url_value else None)
                external_key = str(url_value or f"{source_id}:{title}:{index}")
                summary = str(item.get("description") or item.get("digest") or "").strip() or None

                content_items.append(
                    ContentItemInput(
                        source="newsnow",
                        source_type="snapshot",
                        external_key=external_key,
                        title=title,
                        url=str(url_value) if url_value else None,
                        summary=summary,
                        author=str(item.get("author") or item.get("source") or platform),
                        published_at=published_at,
                        meta_json=json.dumps(
                            {
                                "platform": platform,
                                "source_id": source_id,
                                "provider": self.name,
                                "rank": index + 1,
                            }
                        ),
                    )
                )
                hit_platforms.add(platform)

        trend_points = [
            TrendPointInput(
                source="newsnow",
                metric="hot_hit_count",
                source_type="snapshot",
                bucket_granularity="day",
                bucket_start=bucket_start,
                value=float(len(content_items)),
                raw_json=json.dumps(
                    {
                        "query": query,
                        "provider": self.name,
                        "source_ids": source_ids,
                    }
                ),
            ),
            TrendPointInput(
                source="newsnow",
                metric="platform_count",
                source_type="snapshot",
                bucket_granularity="day",
                bucket_start=bucket_start,
                value=float(len(hit_platforms)),
                raw_json=json.dumps(
                    {
                        "query": query,
                        "provider": self.name,
                        "platforms": sorted(hit_platforms),
                    }
                ),
            ),
        ]

        return trend_points, content_items

    def _request_newsnow_source(self, source_id: str) -> dict[str, object]:
        errors: list[str] = []
        for url in iter_newsnow_source_endpoints(self.settings.newsnow_base_url, source_id):
            try:
                payload, _ = self._request_newsnow_with_retry(url)
            except Exception as exc:
                errors.append(str(exc))
                continue

            if isinstance(payload, dict):
                return payload

            errors.append(f"Unexpected NewsNow payload type from {url}: {type(payload).__name__}")

        detail = "；".join(errors) if errors else f"No NewsNow endpoint candidates for {source_id}."
        raise ProviderError(f"NewsNow source fetch failed for {source_id}: {detail}")

    def _request_newsnow_with_retry(self, url: str) -> tuple[object, dict[str, str]]:
        last_exc: Exception | None = None
        for attempt in range(NEWSNOW_RETRY_ATTEMPTS):
            try:
                return self._request_json(url, headers=newsnow_request_headers())
            except Exception as exc:
                last_exc = exc
                if attempt + 1 < NEWSNOW_RETRY_ATTEMPTS and self._is_retryable_newsnow_error(exc):
                    continue
                if attempt > 0 and self._is_retryable_newsnow_error(exc):
                    raise ProviderError(f"{exc} (after {attempt + 1} attempts)") from exc
                raise
        raise ProviderError(f"NewsNow fetch exhausted retries for {url}: {last_exc}")

    @staticmethod
    def _is_retryable_newsnow_error(exc: Exception) -> bool:
        if isinstance(exc, ProviderHttpError):
            return exc.status_code >= 500
        message = str(exc).casefold()
        retryable_tokens = (
            "network error",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "service unavailable",
            "bad gateway",
            "gateway timeout",
            "overloaded",
            "connection reset",
            "connection aborted",
            "remote end closed",
        )
        return any(token in message for token in retryable_tokens)


class AutoDataProvider:
    name = "auto"

    def __init__(self, primary: DataProvider, fallback: DataProvider):
        self.primary = primary
        self.fallback = fallback

    def fetch_github_history(self, target_ref: str) -> list[TrendPointInput]:
        try:
            return self.primary.fetch_github_history(target_ref)
        except ProviderError:
            return self.fallback.fetch_github_history(target_ref)

    def fetch_github_content(self, target_ref: str) -> list[ContentItemInput]:
        try:
            return self.primary.fetch_github_content(target_ref)
        except ProviderError:
            return self.fallback.fetch_github_content(target_ref)

    def fetch_newsnow_snapshot(self, query: str) -> tuple[list[TrendPointInput], list[ContentItemInput]]:
        try:
            return self.primary.fetch_newsnow_snapshot(query)
        except ProviderError:
            return self.fallback.fetch_newsnow_snapshot(query)


def get_data_provider() -> DataProvider:
    settings = get_settings()
    mock_provider = MockDataProvider()
    mode = settings.provider_mode.strip().lower()
    if mode == "mock":
        return mock_provider

    real_provider = RealDataProvider(settings)
    if mode == "real":
        return real_provider
    if mode == "auto":
        return AutoDataProvider(primary=real_provider, fallback=mock_provider)

    raise ValueError("PROVIDER_MODE must be one of: mock, real, auto")
