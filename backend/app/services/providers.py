from __future__ import annotations

from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import hashlib
import html
import json
import re
from typing import Protocol
from urllib import error, parse, request
import xml.etree.ElementTree as ET

from app.config import Settings, get_settings
from app.models import utcnow
from app.services.direct_rss_catalog import iter_direct_rss_feeds
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
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
SEARCH_TOKEN_RE = re.compile(r"[a-z0-9]+")
HAS_CJK_RE = re.compile(r"[\u3400-\u9FFF]")
GOOGLE_NEWS_SOURCE_BLOCKLIST = {"x.com", "twitter.com"}
GDELT_DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}
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
GDELT_AMBIGUOUS_QUERY_CONTEXTS = {
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


class DataProvider(Protocol):
    name: str

    def fetch_github_history(self, target_ref: str) -> list[TrendPointInput]:
        raise NotImplementedError

    def fetch_github_content(self, target_ref: str) -> list[ContentItemInput]:
        raise NotImplementedError

    def fetch_newsnow_snapshot(self, query: str) -> tuple[list[TrendPointInput], list[ContentItemInput]]:
        raise NotImplementedError

    def fetch_google_news_archive(self, query: str) -> list[ContentItemInput]:
        raise NotImplementedError

    def fetch_direct_rss_archive(self, query: str) -> list[ContentItemInput]:
        raise NotImplementedError

    def fetch_gdelt_archive(self, query: str) -> list[ContentItemInput]:
        raise NotImplementedError


class MockDataProvider:
    name = "mock"

    def fetch_github_history(self, target_ref: str) -> list[TrendPointInput]:
        return generate_github_history(target_ref)

    def fetch_github_content(self, target_ref: str) -> list[ContentItemInput]:
        return generate_github_content(target_ref)

    def fetch_newsnow_snapshot(self, query: str) -> tuple[list[TrendPointInput], list[ContentItemInput]]:
        return generate_newsnow_snapshot(query)

    def fetch_google_news_archive(self, query: str) -> list[ContentItemInput]:
        del query
        return []

    def fetch_gdelt_archive(self, query: str) -> list[ContentItemInput]:
        del query
        return []

    def fetch_direct_rss_archive(self, query: str) -> list[ContentItemInput]:
        del query
        return []


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

    @staticmethod
    def _clean_html_text(value: str | None) -> str | None:
        if not value:
            return None
        text = html.unescape(HTML_TAG_RE.sub(" ", value)).replace("\xa0", " ")
        normalized = WHITESPACE_RE.sub(" ", text).strip()
        return normalized or None

    @staticmethod
    def _parse_rfc822_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _parse_feed_datetime(cls, value: str | None) -> datetime | None:
        if not value:
            return None
        candidate = " ".join(value.strip().split())
        if not candidate:
            return None

        parsed = cls._parse_rfc822_datetime(candidate)
        if parsed:
            return parsed

        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass

        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return datetime.strptime(candidate, fmt).replace(tzinfo=None)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_gdelt_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ")
        except ValueError:
            return None

    @staticmethod
    def _direct_rss_feed_order(query: str, extra_feeds: str) -> list:
        feeds = list(iter_direct_rss_feeds(extra_feeds))
        prefer_zh = bool(HAS_CJK_RE.search(query))
        primary_language = "zh" if prefer_zh else "en"
        secondary_language = "en" if prefer_zh else "zh"

        def sort_key(feed) -> tuple[int, str]:
            if getattr(feed, "language", "any") == primary_language:
                return (0, feed.label.casefold())
            if getattr(feed, "language", "any") == secondary_language:
                return (1, feed.label.casefold())
            return (2, feed.label.casefold())

        feeds.sort(key=sort_key)
        return feeds

    @staticmethod
    def _gdelt_tokens(query: str) -> list[str]:
        normalized = " ".join(query.split()).casefold()
        if not normalized:
            return []
        if HAS_CJK_RE.search(normalized):
            return [normalized]
        tokens = []
        for token in SEARCH_TOKEN_RE.findall(normalized):
            if len(token) > 1 or token in {"ai", "vr", "ar", "mcp"}:
                tokens.append(token)
        return tokens or [normalized]

    @staticmethod
    def _gdelt_match_text(value: str | None) -> str:
        if not value:
            return ""
        return " ".join(SEARCH_TOKEN_RE.findall(value.casefold()))

    @classmethod
    def _archive_text_matches_query(cls, query: str, value: str | None) -> bool:
        normalized_query = " ".join(query.split()).casefold()
        if not normalized_query or not value:
            return False
        if HAS_CJK_RE.search(normalized_query):
            return normalized_query in value.casefold()

        tokens = cls._gdelt_tokens(normalized_query)
        if not tokens:
            return False
        value_tokens = set(SEARCH_TOKEN_RE.findall(value.casefold()))
        return all(token in value_tokens for token in tokens)

    @classmethod
    def _archive_match_strength(
        cls,
        query: str,
        *,
        title: str | None,
        summary: str | None = None,
        url: str | None = None,
    ) -> str:
        if cls._archive_text_matches_query(query, title) or cls._archive_text_matches_query(query, url):
            return "strong"
        if cls._archive_text_matches_query(query, summary):
            return "weak"
        return "none"

    @classmethod
    def _gdelt_title_key(cls, title: str) -> str:
        return cls._gdelt_match_text(title)

    @classmethod
    def _gdelt_title_token_set(cls, title: str, query: str) -> set[str]:
        query_tokens = set(cls._gdelt_tokens(query))
        return {
            token
            for token in SEARCH_TOKEN_RE.findall(title.casefold())
            if len(token) > 2 and token not in query_tokens and token not in GDELT_TITLE_STOPWORDS
        }

    @staticmethod
    def _token_jaccard(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        overlap = len(left & right)
        union = len(left | right)
        return overlap / union if union else 0.0

    @classmethod
    def _gdelt_matches_query(cls, query: str, *, title: str | None, url: str | None, domain: str | None) -> bool:
        normalized_query = " ".join(query.split()).casefold()
        title_text = cls._gdelt_match_text(title)
        url_text = cls._gdelt_match_text(url)
        searchable = " ".join(part for part in (title_text, url_text) if part).strip()
        if not searchable or not normalized_query:
            return False
        if HAS_CJK_RE.search(normalized_query):
            raw_searchable = " ".join(part for part in (title, url) if part).casefold()
            return normalized_query in raw_searchable
        tokens = cls._gdelt_tokens(normalized_query)
        if not tokens:
            return False
        title_tokens = set(title_text.split())
        url_tokens = set(url_text.split())
        matched = normalized_query in searchable or all(token in title_tokens or token in url_tokens for token in tokens)
        if not matched:
            return False

        if len(tokens) != 1:
            return True

        context_tokens = GDELT_AMBIGUOUS_QUERY_CONTEXTS.get(tokens[0])
        if not context_tokens:
            return True

        context_text = " ".join(
            part for part in (title_text, url_text, cls._gdelt_match_text(domain)) if part
        ).strip()
        if not context_text:
            return False
        available_tokens = set(context_text.split())
        return any(token in available_tokens for token in context_tokens)

    def _build_gdelt_archive_url(self, query: str) -> str:
        search_query = f'"{query.strip().replace("\"", " ")}"'
        params = {
            "query": search_query,
            "mode": "ArtList",
            "format": "json",
            "sort": "datedesc",
            "maxrecords": str(self.settings.gdelt_max_items),
        }
        if self.settings.gdelt_history_days > 0:
            params["timespan"] = f"{self.settings.gdelt_history_days}d"
        return f"{GDELT_DOC_API_URL}?{parse.urlencode(params)}"

    def fetch_gdelt_archive(self, query: str) -> list[ContentItemInput]:
        if not self.settings.gdelt_enabled:
            return []

        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        url = self._build_gdelt_archive_url(normalized_query)
        raw_text = self._request_text(
            url,
            headers={
                "User-Agent": "TrendScope/0.1",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        stripped = raw_text.lstrip()
        if stripped.startswith("Please limit requests"):
            raise ProviderError(f"GDELT rate limited: {stripped[:160]}")

        try:
            payload = json.loads(raw_text)
        except ValueError as exc:
            raise ProviderError(f"Invalid GDELT payload from {url}: {exc}") from exc

        if not isinstance(payload, dict):
            raise ProviderError(f"Unexpected GDELT payload type from {url}: {type(payload).__name__}")

        articles = payload.get("articles")
        if not isinstance(articles, list):
            raise ProviderError(f"Unexpected GDELT articles payload from {url}.")

        items: list[ContentItemInput] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        kept_title_groups: list[tuple[datetime.date, set[str]]] = []
        for index, article in enumerate(articles):
            if not isinstance(article, dict):
                continue

            title = self._clean_html_text(str(article.get("title") or "").strip())
            article_url = self._clean_html_text(str(article.get("url") or "").strip()) or None
            domain = self._clean_html_text(str(article.get("domain") or "").strip()) or "GDELT"
            if not title:
                continue
            if not self._gdelt_matches_query(normalized_query, title=title, url=article_url, domain=domain):
                continue

            published_at = self._parse_gdelt_datetime(str(article.get("seendate") or "").strip())
            if not published_at:
                continue

            if article_url and article_url in seen_urls:
                continue
            title_key = self._gdelt_title_key(title)
            if title_key in seen_titles:
                continue
            title_tokens = self._gdelt_title_token_set(title, normalized_query)
            is_duplicate_story = any(
                kept_day == published_at.date() and self._token_jaccard(title_tokens, kept_tokens) >= 0.82
                for kept_day, kept_tokens in kept_title_groups
                if title_tokens and kept_tokens
            )
            if is_duplicate_story:
                continue

            if article_url:
                seen_urls.add(article_url)
            seen_titles.add(title_key)
            if title_tokens:
                kept_title_groups.append((published_at.date(), title_tokens))

            identity = article_url or "\0".join((normalized_query, title, domain, published_at.isoformat(), str(index)))
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

            items.append(
                ContentItemInput(
                    source="gdelt",
                    source_type="archive",
                    external_key=f"{normalized_query}:{digest}",
                    title=title,
                    url=article_url,
                    summary=None,
                    author=domain,
                    published_at=published_at,
                    meta_json=json.dumps(
                        {
                            "provider": self.name,
                            "query": normalized_query,
                            "request_url": url,
                            "domain": domain,
                            "language": article.get("language"),
                            "sourcecountry": article.get("sourcecountry"),
                        }
                    ),
                )
            )

        items.sort(key=lambda item: item.published_at or datetime.min, reverse=True)
        return items[: self.settings.gdelt_max_items]

    @staticmethod
    def _strip_google_news_summary(title: str, source_name: str | None, description: str | None) -> str | None:
        cleaned = RealDataProvider._clean_html_text(description)
        if not cleaned:
            return None

        title_lc = title.casefold()
        source_lc = source_name.casefold() if source_name else ""
        candidate = cleaned

        if candidate.casefold().startswith(title_lc):
            candidate = candidate[len(title) :].lstrip(" -|:.")
        if source_name and candidate.casefold().endswith(source_lc):
            candidate = candidate[: -len(source_name)].rstrip(" -|:.")

        normalized = WHITESPACE_RE.sub(" ", candidate).strip()
        return normalized or None

    @staticmethod
    def _google_news_locale_order(query: str) -> list[tuple[str, str, str]]:
        prefer_zh = bool(HAS_CJK_RE.search(query))
        zh_locale = ("zh-CN", "CN", "CN:zh-Hans")
        en_locale = ("en-US", "US", "US:en")
        return [zh_locale, en_locale] if prefer_zh else [en_locale, zh_locale]

    def _build_google_news_archive_url(self, query: str, *, hl: str, gl: str, ceid: str) -> str:
        search_query = f'"{query.strip().replace("\"", " ")}"'
        if self.settings.google_news_history_days > 0:
            search_query = f"{search_query} when:{self.settings.google_news_history_days}d"
        encoded_query = parse.quote_plus(search_query)
        return f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={parse.quote_plus(ceid)}"

    @staticmethod
    def _google_news_is_blocked(source_url: str | None) -> bool:
        if not source_url:
            return False
        domain = parse.urlparse(source_url).netloc.casefold().removeprefix("www.")
        return domain in GOOGLE_NEWS_SOURCE_BLOCKLIST

    def _parse_google_news_archive_feed(self, xml_text: str, query: str, *, request_url: str) -> list[ContentItemInput]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ProviderError(f"Invalid Google News RSS payload from {request_url}: {exc}") from exc

        query_lc = query.casefold()
        items: list[ContentItemInput] = []
        for node in root.findall("./channel/item"):
            title = self._clean_html_text(node.findtext("title"))
            if not title:
                continue

            source_node = node.find("source")
            source_name = self._clean_html_text(source_node.text if source_node is not None else None) or "Google News"
            source_url = source_node.get("url") if source_node is not None else None
            if self._google_news_is_blocked(source_url):
                continue

            description = self._strip_google_news_summary(
                title=title,
                source_name=source_name,
                description=node.findtext("description"),
            )
            searchable_text = " ".join(part for part in (title, description, source_name) if part).casefold()
            if query_lc not in searchable_text:
                continue

            published_at = self._parse_rfc822_datetime(node.findtext("pubDate"))
            if not published_at:
                continue

            link = self._clean_html_text(node.findtext("link"))
            identity = "\0".join((query, source_name, published_at.isoformat(), title))
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

            items.append(
                ContentItemInput(
                    source="google_news",
                    source_type="archive",
                    external_key=f"{query}:{digest}",
                    title=title,
                    url=link,
                    summary=description,
                    author=source_name,
                    published_at=published_at,
                    meta_json=json.dumps(
                        {
                            "provider": self.name,
                            "query": query,
                            "request_url": request_url,
                            "source_url": source_url,
                        }
                    ),
                )
            )

        return items

    def fetch_google_news_archive(self, query: str) -> list[ContentItemInput]:
        if not self.settings.google_news_enabled:
            return []

        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        fetched_items: list[ContentItemInput] = []
        seen_identities: set[tuple[str, str, str]] = set()
        errors: list[str] = []

        for hl, gl, ceid in self._google_news_locale_order(normalized_query):
            url = self._build_google_news_archive_url(normalized_query, hl=hl, gl=gl, ceid=ceid)
            try:
                xml_text = self._request_text(
                    url,
                    headers={
                        "User-Agent": "TrendScope/0.1",
                        "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.1",
                    },
                )
            except Exception as exc:  # pragma: no cover - network dependent
                errors.append(str(exc))
                continue

            for item in self._parse_google_news_archive_feed(xml_text, normalized_query, request_url=url):
                identity = (
                    item.title.casefold(),
                    (item.author or "").casefold(),
                    item.published_at.isoformat() if item.published_at else "",
                )
                if identity in seen_identities:
                    continue
                seen_identities.add(identity)
                fetched_items.append(item)
                if len(fetched_items) >= self.settings.google_news_max_items:
                    break

            if len(fetched_items) >= self.settings.google_news_max_items:
                break

        if fetched_items:
            fetched_items.sort(key=lambda item: item.published_at or datetime.min, reverse=True)
            return fetched_items[: self.settings.google_news_max_items]

        if errors:
            raise ProviderError(f"Google News archive fetch failed: {'；'.join(errors)}")

        return []

    def _parse_direct_rss_feed(self, xml_text: str, query: str, *, request_url: str, source_label: str) -> list[ContentItemInput]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ProviderError(f"Invalid direct RSS payload from {request_url}: {exc}") from exc

        items: list[ContentItemInput] = []

        if root.tag.endswith("rss"):
            nodes = root.findall("./channel/item")
            for index, node in enumerate(nodes):
                title = self._clean_html_text(node.findtext("title"))
                description = self._clean_html_text(node.findtext("description"))
                link = self._clean_html_text(node.findtext("link"))
                author = (
                    self._clean_html_text(node.findtext("author"))
                    or self._clean_html_text(node.findtext("{http://purl.org/dc/elements/1.1/}creator"))
                    or source_label
                )
                if not title:
                    continue
                if self._archive_match_strength(query, title=title, summary=description, url=link) != "strong":
                    continue

                published_at = self._parse_feed_datetime(node.findtext("pubDate") or node.findtext("updated"))
                if not published_at:
                    continue

                digest = hashlib.sha256(
                    "\0".join((query, source_label, published_at.isoformat(), title, str(index))).encode("utf-8")
                ).hexdigest()[:24]
                items.append(
                    ContentItemInput(
                        source="direct_rss",
                        source_type="archive",
                        external_key=f"{query}:{digest}",
                        title=title,
                        url=link,
                        summary=description,
                        author=author,
                        published_at=published_at,
                        meta_json=json.dumps(
                            {
                                "provider": self.name,
                                "query": query,
                                "request_url": request_url,
                                "feed_label": source_label,
                            }
                        ),
                    )
                )
            return items

        if root.tag.endswith("feed"):
            nodes = root.findall("atom:entry", ATOM_NAMESPACE)
            for index, node in enumerate(nodes):
                title = self._clean_html_text(node.findtext("atom:title", namespaces=ATOM_NAMESPACE))
                summary = self._clean_html_text(
                    node.findtext("atom:summary", namespaces=ATOM_NAMESPACE)
                    or node.findtext("atom:content", namespaces=ATOM_NAMESPACE)
                )
                author = self._clean_html_text(
                    node.findtext("atom:author/atom:name", namespaces=ATOM_NAMESPACE)
                ) or source_label

                link_node = next(
                    (
                        candidate
                        for candidate in node.findall("atom:link", ATOM_NAMESPACE)
                        if candidate.get("rel") in {None, "alternate"} and candidate.get("href")
                    ),
                    None,
                )
                link = self._clean_html_text(link_node.get("href")) if link_node is not None else None
                if not title:
                    continue
                if self._archive_match_strength(query, title=title, summary=summary, url=link) != "strong":
                    continue

                published_at = self._parse_feed_datetime(
                    node.findtext("atom:updated", namespaces=ATOM_NAMESPACE)
                    or node.findtext("atom:published", namespaces=ATOM_NAMESPACE)
                )
                if not published_at:
                    continue

                digest = hashlib.sha256(
                    "\0".join((query, source_label, published_at.isoformat(), title, str(index))).encode("utf-8")
                ).hexdigest()[:24]
                items.append(
                    ContentItemInput(
                        source="direct_rss",
                        source_type="archive",
                        external_key=f"{query}:{digest}",
                        title=title,
                        url=link,
                        summary=summary,
                        author=author,
                        published_at=published_at,
                        meta_json=json.dumps(
                            {
                                "provider": self.name,
                                "query": query,
                                "request_url": request_url,
                                "feed_label": source_label,
                            }
                        ),
                    )
                )
            return items

        raise ProviderError(f"Unsupported direct RSS root element from {request_url}: {root.tag}")

    def fetch_direct_rss_archive(self, query: str) -> list[ContentItemInput]:
        if not self.settings.direct_rss_enabled:
            return []

        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        fetched_items: list[ContentItemInput] = []
        seen_identities: set[tuple[str, str, str]] = set()
        errors: list[str] = []

        for feed in self._direct_rss_feed_order(normalized_query, self.settings.direct_rss_extra_feeds):
            try:
                xml_text = self._request_text(
                    feed.url,
                    headers={
                        "User-Agent": "TrendScope/0.1",
                        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.1",
                    },
                )
            except Exception as exc:  # pragma: no cover - network dependent
                errors.append(f"{feed.label}: {exc}")
                continue

            for item in self._parse_direct_rss_feed(
                xml_text,
                normalized_query,
                request_url=feed.url,
                source_label=feed.label,
            ):
                identity = (
                    item.title.casefold(),
                    (item.author or "").casefold(),
                    item.published_at.isoformat() if item.published_at else "",
                )
                if identity in seen_identities:
                    continue
                seen_identities.add(identity)
                fetched_items.append(item)
                if len(fetched_items) >= self.settings.direct_rss_max_items:
                    break

            if len(fetched_items) >= self.settings.direct_rss_max_items:
                break

        if fetched_items:
            fetched_items.sort(key=lambda item: item.published_at or datetime.min, reverse=True)
            return fetched_items[: self.settings.direct_rss_max_items]

        if errors:
            raise ProviderError(f"Direct RSS archive fetch failed: {'；'.join(errors)}")

        return []

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

    def fetch_google_news_archive(self, query: str) -> list[ContentItemInput]:
        primary_fetcher = getattr(self.primary, "fetch_google_news_archive", None)
        fallback_fetcher = getattr(self.fallback, "fetch_google_news_archive", None)

        if not callable(primary_fetcher):
            return fallback_fetcher(query) if callable(fallback_fetcher) else []

        try:
            return primary_fetcher(query)
        except ProviderError:
            return fallback_fetcher(query) if callable(fallback_fetcher) else []

    def fetch_direct_rss_archive(self, query: str) -> list[ContentItemInput]:
        primary_fetcher = getattr(self.primary, "fetch_direct_rss_archive", None)
        fallback_fetcher = getattr(self.fallback, "fetch_direct_rss_archive", None)

        if not callable(primary_fetcher):
            return fallback_fetcher(query) if callable(fallback_fetcher) else []

        try:
            return primary_fetcher(query)
        except ProviderError:
            return fallback_fetcher(query) if callable(fallback_fetcher) else []

    def fetch_gdelt_archive(self, query: str) -> list[ContentItemInput]:
        primary_fetcher = getattr(self.primary, "fetch_gdelt_archive", None)
        fallback_fetcher = getattr(self.fallback, "fetch_gdelt_archive", None)

        if not callable(primary_fetcher):
            return fallback_fetcher(query) if callable(fallback_fetcher) else []

        try:
            return primary_fetcher(query)
        except ProviderError:
            return fallback_fetcher(query) if callable(fallback_fetcher) else []


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
