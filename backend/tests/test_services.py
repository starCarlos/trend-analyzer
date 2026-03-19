import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from fastapi import BackgroundTasks


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"trendscope-test-services-{uuid4().hex}.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DATABASE_PATH}")
os.environ.setdefault("APP_ENV", "test")

from app.config import Settings
from app.database import Base, SessionLocal, engine
from app.main import health, index, provider_smoke, provider_status, provider_verify, tracked_page, web_dir
from app.models import BackfillJob, BackfillJobTask, ContentItem, Keyword, TrendPoint, utcnow
from app.schemas import (
    ProviderCheckPayload,
    ProviderProbePayload,
    ProviderSmokePayload,
    ProviderSmokeRequest,
    ProviderSmokeSearchPayload,
    ProviderStatusPayload,
    ProviderVerifyPayload,
    ProviderVerifyRequest,
)
from app.services.backfill import run_backfill_job
from app.services.collector import collect_tracked_keywords, ensure_tracked, list_tracked_keywords, refresh_keyword
from app.services.direct_rss_catalog import iter_direct_rss_feeds
from app.services.management import list_collect_runs, list_keywords
from app.services.provider_diagnostics import get_provider_status
from app.services.provider_smoke import run_provider_smoke
from app.services.provider_urls import (
    build_newsnow_source_endpoint,
    iter_newsnow_source_endpoints,
    iter_newsnow_source_ids,
    normalize_newsnow_source_id,
)
from app.services.provider_types import ContentItemInput, TrendPointInput
from app.services.github_repo_resolution import resolve_github_repo_name
from app.services.providers import ProviderHttpError, RealDataProvider
from app.services.provider_verification import verify_provider_connectivity
from app.services.query_parser import parse_search_query, resolve_search_query
from app.services.scheduler import CollectionScheduler
from app.services.search import get_backfill_status, search_keyword, set_track_state


class ServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Base.metadata.create_all(bind=engine)

    def setUp(self) -> None:
        self.db = SessionLocal()

    def tearDown(self) -> None:
        self.db.close()

    def test_health_payload(self) -> None:
        payload = health()
        self.assertEqual(payload["status"], "ok")
        self.assertIsInstance(payload["scheduler_enabled"], bool)

    def test_web_entry_assets_exist(self) -> None:
        self.assertTrue(str(index().path).endswith("index.html"))
        self.assertTrue(str(tracked_page().path).endswith("index.html"))
        self.assertTrue((web_dir / "index.html").exists())
        self.assertTrue((web_dir / "app.js").exists())
        self.assertTrue((web_dir / "styles.css").exists())

    def test_web_ui_contains_recent_tracked_collect_and_provider_panels(self) -> None:
        html = (web_dir / "index.html").read_text(encoding="utf-8")
        app_js = (web_dir / "app.js").read_text(encoding="utf-8")
        styles = (web_dir / "styles.css").read_text(encoding="utf-8")
        self.assertIn('<html lang="zh-CN">', html)
        self.assertIn('id="recent-panel"', html)
        self.assertIn('id="tracked-panel"', html)
        self.assertIn('id="operations-shell"', html)
        self.assertIn('id="operations-disclosure"', html)
        self.assertIn('id="collect-form"', html)
        self.assertNotIn('id="collect-runs"', html)
        self.assertIn('id="provider-grid"', html)
        self.assertIn('id="provider-verify-button"', html)
        self.assertIn('id="provider-smoke-form"', html)
        self.assertIn('id="provider-smoke-query-input"', html)
        self.assertIn('id="provider-smoke-button"', html)
        self.assertIn('id="provider-smoke-grid"', html)
        self.assertIn('id="content-disclosure"', html)
        self.assertIn('id="availability-disclosure"', html)
        self.assertIn('value="direct_rss"', html)
        self.assertIn('data-locale-switch="zh"', html)
        self.assertIn('data-locale-switch="en"', html)
        self.assertIn("filter_hint", app_js)
        self.assertIn("return payload?.providers || [];", app_js)
        self.assertIn("function formatChartTimestamp(value)", app_js)
        self.assertIn('sparkline-wrap${singlePoint ? " is-single-point" : ""}', app_js)
        self.assertIn(".sparkline-dot", styles)
        self.assertIn(".sparkline-wrap.is-single-point .sparkline-dot", styles)

    def test_provider_status_reports_mock_mode(self) -> None:
        payload = get_provider_status(
            Settings(
                provider_mode="mock",
                github_api_base_url="",
                newsnow_base_url="",
                newsnow_source_ids="",
            )
        )

        self.assertEqual(payload.resolved_provider, "mock")
        self.assertEqual(payload.github.status, "mock_only")
        self.assertEqual(payload.newsnow.status, "mock_only")
        self.assertEqual(payload.google_news.status, "mock_only")
        self.assertEqual(payload.direct_rss.status, "mock_only")
        self.assertEqual(payload.gdelt.status, "mock_only")
        self.assertIn("mock", payload.summary)

    def test_direct_rss_catalog_appends_extra_feeds(self) -> None:
        feeds = iter_direct_rss_feeds("Custom Feed|https://example.com/custom.xml")

        self.assertTrue(any(feed.label == "Custom Feed" for feed in feeds))
        self.assertTrue(any(feed.url == "https://example.com/custom.xml" for feed in feeds))

    def test_direct_rss_feed_order_prefers_zh_sources_for_cjk_queries(self) -> None:
        ordered = RealDataProvider._direct_rss_feed_order("开源代理", "")

        self.assertGreater(len(ordered), 0)
        self.assertEqual(ordered[0].language, "zh")

    def test_provider_status_route_returns_payload(self) -> None:
        expected = ProviderStatusPayload(
            requested_mode="mock",
            resolved_provider="mock",
            summary="mock summary",
            github=ProviderCheckPayload(
                source="github",
                mode="mock",
                preferred_provider="mock",
                status="mock_only",
                can_use_real_provider=False,
            ),
            newsnow=ProviderCheckPayload(
                source="newsnow",
                mode="mock",
                preferred_provider="mock",
                status="mock_only",
                can_use_real_provider=False,
            ),
        )

        with patch("app.main.get_provider_status", return_value=expected) as loader:
            payload = provider_status()

        loader.assert_called_once_with()
        self.assertEqual(payload.summary, "mock summary")
        self.assertEqual(payload.github.status, "mock_only")

    def test_provider_verify_route_forwards_probe_mode(self) -> None:
        expected = ProviderVerifyPayload(
            probe_mode="real",
            requested_mode="real",
            effective_mode="real",
            summary="verify summary",
            github=ProviderProbePayload(
                source="github",
                attempted_provider="real",
                status="success",
                endpoint="https://api.github.com/rate_limit",
                message="ok",
            ),
            newsnow=ProviderProbePayload(
                source="newsnow",
                attempted_provider="real",
                status="success",
                endpoint="https://newsnow.example.com/api/s?id=weibo-hot",
                message="ok",
            ),
        )

        with patch("app.main.verify_provider_connectivity", return_value=expected) as runner:
            payload = provider_verify(ProviderVerifyRequest(probe_mode="real"))

        runner.assert_called_once_with(probe_mode="real")
        self.assertEqual(payload.summary, "verify summary")
        self.assertEqual(payload.github.status, "success")

    def test_provider_smoke_route_forwards_request_payload(self) -> None:
        expected = ProviderSmokePayload(
            query="anthropic/claude-code",
            period="30d",
            probe_mode="real",
            force_search=True,
            summary="smoke summary",
            provider_status=ProviderStatusPayload(
                requested_mode="real",
                resolved_provider="real",
                summary="status summary",
                github=ProviderCheckPayload(
                    source="github",
                    mode="real",
                    preferred_provider="real",
                    status="ready",
                    can_use_real_provider=True,
                ),
                newsnow=ProviderCheckPayload(
                    source="newsnow",
                    mode="real",
                    preferred_provider="real",
                    status="ready",
                    can_use_real_provider=True,
                ),
            ),
            provider_verify=ProviderVerifyPayload(
                probe_mode="real",
                requested_mode="real",
                effective_mode="real",
                summary="verify summary",
                github=ProviderProbePayload(
                    source="github",
                    attempted_provider="real",
                    status="success",
                    endpoint="https://api.github.com/rate_limit",
                    message="ok",
                ),
                newsnow=ProviderProbePayload(
                    source="newsnow",
                    attempted_provider="real",
                    status="success",
                    endpoint="https://newsnow.example.com/api/s?id=weibo-hot",
                    message="ok",
                ),
            ),
            search=ProviderSmokeSearchPayload(
                query="anthropic/claude-code",
                period="30d",
                status="success",
                message="端到端搜索执行成功。",
                keyword_kind="github_repo",
                normalized_query="anthropic/claude-code",
                trend_series_count=2,
                content_item_count=3,
                availability={"github_history": "ready", "newsnow_snapshot": "ready"},
                backfill_status="success",
            ),
            next_steps=["open tracked page"],
        )

        request_payload = ProviderSmokeRequest(
            query="anthropic/claude-code",
            period="30d",
            probe_mode="real",
            force_search=True,
        )

        with patch("app.main.run_provider_smoke", return_value=expected) as runner:
            payload = provider_smoke(request_payload)

        runner.assert_called_once_with(
            query="anthropic/claude-code",
            period="30d",
            probe_mode="real",
            force_search=True,
        )
        self.assertEqual(payload.summary, "smoke summary")
        self.assertEqual(payload.search.status, "success")
        self.assertEqual(payload.next_steps, ["open tracked page"])

    def test_provider_status_reports_auto_fallback_for_misconfigured_source(self) -> None:
        payload = get_provider_status(
            Settings(
                provider_mode="auto",
                github_token="token",
                github_api_base_url="https://api.github.com",
                github_history_max_pages=10,
                newsnow_base_url="",
                newsnow_source_ids="",
                request_timeout_seconds=8.0,
            )
        )

        self.assertEqual(payload.resolved_provider, "auto")
        self.assertEqual(payload.github.preferred_provider, "real")
        self.assertEqual(payload.github.status, "ready")
        self.assertEqual(payload.newsnow.preferred_provider, "mock")
        self.assertEqual(payload.newsnow.status, "fallback_only")
        self.assertEqual(payload.google_news.status, "ready")
        self.assertEqual(payload.gdelt.status, "ready")

    def test_provider_verify_reports_success_for_real_probe(self) -> None:
        def fake_request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            if url.endswith("/rate_limit"):
                return ({"rate": {"remaining": 4999, "limit": 5000}}, {})
            return ({"items": [{"title": "demo"}]}, {})

        def fake_request_text(url: str, headers: dict[str, str]) -> tuple[str, dict[str, str]]:
            del headers
            if "news.google.com" in url:
                return (
                    """
                    <rss version="2.0">
                      <channel>
                        <item><title>OpenClaw headline</title></item>
                      </channel>
                    </rss>
                    """,
                    {},
                )
            if "api.gdeltproject.org" in url:
                return (json.dumps({"articles": [{"title": "OpenClaw headline"}]}), {})
            return (
                """
                <rss version="2.0">
                  <channel>
                    <item>
                      <title>OpenClaw headline</title>
                      <link>https://example.com/openclaw</link>
                      <pubDate>Tue, 17 Mar 2026 04:42:44 GMT</pubDate>
                    </item>
                  </channel>
                </rss>
                """,
                {},
            )

        payload = verify_provider_connectivity(
            settings=Settings(
                provider_mode="real",
                github_token="token",
                github_api_base_url="https://api.github.com",
                newsnow_base_url="https://newsnow.example.com",
                newsnow_source_ids="weibo-hot",
                request_timeout_seconds=8.0,
            ),
            probe_mode="real",
            request_json=fake_request_json,
            request_text=fake_request_text,
        )

        self.assertEqual(payload.github.status, "success")
        self.assertEqual(payload.newsnow.status, "success")
        self.assertEqual(payload.google_news.status, "success")
        self.assertEqual(payload.gdelt.status, "success")
        self.assertIn("成功", payload.summary)
        self.assertEqual(payload.newsnow.endpoint, "https://newsnow.example.com/api/s?id=weibo")

    def test_provider_verify_newsnow_falls_back_to_legacy_endpoint(self) -> None:
        def fake_request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            if url.endswith("/rate_limit"):
                return ({"rate": {"remaining": 4999, "limit": 5000}}, {})
            if url.endswith("/api/s?id=weibo-hot"):
                raise RuntimeError("HTTP 403")
            if url.endswith("/api/s/weibo-hot"):
                return ({"items": [{"title": "demo"}]}, {})
            raise AssertionError(url)

        payload = verify_provider_connectivity(
            settings=Settings(
                provider_mode="real",
                github_token="token",
                github_api_base_url="https://api.github.com",
                newsnow_base_url="https://newsnow.example.com",
                newsnow_source_ids="weibo-hot",
                google_news_enabled=False,
                gdelt_enabled=False,
                request_timeout_seconds=8.0,
            ),
            probe_mode="real",
            request_json=fake_request_json,
        )

        self.assertEqual(payload.newsnow.status, "success")
        self.assertEqual(payload.newsnow.endpoint, "https://newsnow.example.com/api/s/weibo-hot")

    def test_provider_verify_newsnow_retries_transient_primary_endpoint(self) -> None:
        attempts: dict[str, int] = {}

        def fake_request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            del headers
            if url.endswith("/rate_limit"):
                return ({"rate": {"remaining": 4999, "limit": 5000}}, {})
            attempts[url] = attempts.get(url, 0) + 1
            if url.endswith("/api/s?id=weibo"):
                if attempts[url] == 1:
                    raise RuntimeError("HTTP 500: D1 DB is overloaded")
                return ({"items": [{"title": "demo"}]}, {})
            raise AssertionError(url)

        payload = verify_provider_connectivity(
            settings=Settings(
                provider_mode="real",
                github_token="token",
                github_api_base_url="https://api.github.com",
                newsnow_base_url="https://newsnow.example.com",
                newsnow_source_ids="weibo",
                google_news_enabled=False,
                gdelt_enabled=False,
                request_timeout_seconds=8.0,
            ),
            probe_mode="real",
            request_json=fake_request_json,
        )

        self.assertEqual(payload.newsnow.status, "success")
        self.assertEqual(payload.newsnow.endpoint, "https://newsnow.example.com/api/s?id=weibo")
        self.assertEqual(attempts["https://newsnow.example.com/api/s?id=weibo"], 2)

    def test_provider_verify_skips_when_real_config_is_incomplete(self) -> None:
        payload = verify_provider_connectivity(
            settings=Settings(
                provider_mode="real",
                github_api_base_url="",
                newsnow_base_url="",
                newsnow_source_ids="",
                google_news_enabled=False,
                gdelt_enabled=False,
                request_timeout_seconds=8.0,
            ),
            probe_mode="real",
            request_json=lambda _url, _headers: ({}, {}),
            request_text=lambda _url, _headers: ("", {}),
        )

        self.assertEqual(payload.github.status, "skipped")
        self.assertEqual(payload.newsnow.status, "skipped")
        self.assertEqual(payload.google_news.status, "skipped")
        self.assertEqual(payload.gdelt.status, "skipped")
        self.assertIn("跳过", payload.github.message)

    def test_provider_verify_marks_archive_probe_failures_as_non_blocking(self) -> None:
        def fake_request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            del headers
            if url.endswith("/rate_limit"):
                return ({"rate": {"remaining": 4999, "limit": 5000}}, {})
            return ({"items": [{"title": "demo"}]}, {})

        def fake_request_text(url: str, headers: dict[str, str]) -> tuple[str, dict[str, str]]:
            del headers
            if "news.google.com" in url:
                raise RuntimeError("HTTP 429")
            if "api.gdeltproject.org" in url:
                return (json.dumps({"articles": [{"title": "OpenClaw headline"}]}), {})
            return (
                """
                <rss version="2.0">
                  <channel>
                    <item><title>OpenClaw headline</title></item>
                  </channel>
                </rss>
                """,
                {},
            )

        payload = verify_provider_connectivity(
            settings=Settings(
                provider_mode="real",
                github_token="token",
                github_api_base_url="https://api.github.com",
                newsnow_base_url="https://newsnow.example.com",
                newsnow_source_ids="weibo",
                request_timeout_seconds=8.0,
            ),
            probe_mode="real",
            request_json=fake_request_json,
            request_text=fake_request_text,
        )

        self.assertEqual(payload.github.status, "success")
        self.assertEqual(payload.newsnow.status, "success")
        self.assertEqual(payload.google_news.status, "failed")
        self.assertIn("GitHub 和 NewsNow 已就绪", payload.summary)
        self.assertIn("不会阻塞默认搜索", payload.summary)

    def test_provider_verify_flags_core_probe_failures_as_blocking(self) -> None:
        def fake_request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            del headers
            if url.endswith("/rate_limit"):
                raise RuntimeError("HTTP 403")
            return ({"items": [{"title": "demo"}]}, {})

        def fake_request_text(url: str, headers: dict[str, str]) -> tuple[str, dict[str, str]]:
            del headers
            if "api.gdeltproject.org" in url:
                return (json.dumps({"articles": [{"title": "OpenClaw headline"}]}), {})
            return (
                """
                <rss version="2.0">
                  <channel>
                    <item><title>OpenClaw headline</title></item>
                  </channel>
                </rss>
                """,
                {},
            )

        payload = verify_provider_connectivity(
            settings=Settings(
                provider_mode="real",
                github_token="token",
                github_api_base_url="https://api.github.com",
                newsnow_base_url="https://newsnow.example.com",
                newsnow_source_ids="weibo",
                request_timeout_seconds=8.0,
            ),
            probe_mode="real",
            request_json=fake_request_json,
            request_text=fake_request_text,
        )

        self.assertEqual(payload.github.status, "failed")
        self.assertEqual(payload.newsnow.status, "success")
        self.assertIn("核心实时源", payload.summary)
        self.assertIn("默认真实搜索会继续按策略跳过", payload.summary)

    def test_real_provider_fetch_github_content_tolerates_missing_releases(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                github_api_base_url="https://api.github.com",
                request_timeout_seconds=8.0,
            )
        )

        def fake_request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            del headers
            if url.endswith("/releases?per_page=6"):
                raise ProviderHttpError(404, url, '{"message":"Not Found"}')
            if url.endswith("/issues?state=all&sort=updated&direction=desc&per_page=12"):
                return (
                    [
                        {
                            "id": 42,
                            "number": 7,
                            "title": "Fix startup flow",
                            "html_url": "https://github.com/owner/repo/issues/7",
                            "body": "Ensure the service starts cleanly.",
                            "updated_at": "2026-03-18T00:00:00Z",
                            "state": "open",
                            "user": {"login": "octocat"},
                        }
                    ],
                    {},
                )
            raise AssertionError(url)

        with patch.object(provider, "_request_json", side_effect=fake_request_json):
            items = provider.fetch_github_content("owner/repo")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Fix startup flow")
        self.assertIn(":issue:", items[0].external_key)

    def test_real_provider_fetch_newsnow_snapshot_retries_transient_errors(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                newsnow_base_url="https://newsnow.example.com",
                newsnow_source_ids="weibo",
                request_timeout_seconds=8.0,
            )
        )
        attempts: dict[str, int] = {}

        def fake_request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            del headers
            attempts[url] = attempts.get(url, 0) + 1
            if url.endswith("/api/s?id=weibo"):
                if attempts[url] == 1:
                    raise ProviderHttpError(500, url, '{"message":"D1 DB is overloaded"}')
                return (
                    {
                        "items": [
                            {
                                "title": "mcp is trending",
                                "url": "https://example.com/mcp",
                                "time": "2026-03-18 12:00:00",
                            }
                        ]
                    },
                    {},
                )
            raise AssertionError(url)

        with patch.object(provider, "_request_json", side_effect=fake_request_json):
            trend_points, items = provider.fetch_newsnow_snapshot("mcp")

        self.assertEqual(attempts["https://newsnow.example.com/api/s?id=weibo"], 2)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "mcp is trending")
        self.assertEqual(trend_points[0].metric, "hot_hit_count")
        self.assertEqual(trend_points[0].value, 1.0)

    def test_real_provider_extracts_juejin_published_at_from_article_html(self) -> None:
        html = """
        <html>
          <head>
            <meta itemprop="datePublished" content="2026-03-16T09:01:50.000Z">
          </head>
          <body></body>
        </html>
        """

        published_at = RealDataProvider._extract_juejin_published_at(html)

        self.assertEqual(published_at, datetime.fromisoformat("2026-03-16T09:01:50+00:00").replace(tzinfo=None))

    def test_real_provider_fetch_newsnow_snapshot_enriches_juejin_time_when_missing(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                newsnow_base_url="https://newsnow.example.com",
                newsnow_source_ids="juejin",
                request_timeout_seconds=8.0,
            )
        )

        with patch.object(
            provider,
            "_request_newsnow_source",
            return_value={
                "items": [
                    {
                        "title": "OpenClaw setup notes",
                        "url": "https://juejin.cn/post/7617647693184581658",
                    }
                ]
            },
        ), patch.object(
            provider,
            "_request_text",
            return_value='<meta itemprop="datePublished" content="2026-03-16T09:01:50.000Z">',
        ):
            trend_points, items = provider.fetch_newsnow_snapshot("openclaw")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].published_at, datetime.fromisoformat("2026-03-16T09:01:50+00:00").replace(tzinfo=None))
        self.assertEqual(trend_points[0].metric, "hot_hit_count")
        self.assertEqual(trend_points[0].value, 1.0)

    def test_real_provider_fetch_google_news_archive_parses_and_filters_feed(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                google_news_enabled=True,
                google_news_history_days=365,
                google_news_max_items=10,
                request_timeout_seconds=8.0,
            )
        )

        rss_feed = """
        <rss version="2.0">
          <channel>
            <item>
              <title>OpenClaw 发布新版本</title>
              <link>https://news.google.com/rss/articles/1</link>
              <pubDate>Tue, 17 Mar 2026 04:42:44 GMT</pubDate>
              <description><![CDATA[
                <a href="https://news.google.com/rss/articles/1">OpenClaw 发布新版本</a>&nbsp;&nbsp;<font color="#6f6f6f">51CTO</font>
              ]]></description>
              <source url="https://www.51cto.com">51CTO</source>
            </item>
            <item>
              <title>"spam.openclaw" - Results on X | Live Posts &amp; Updates</title>
              <link>https://news.google.com/rss/articles/2</link>
              <pubDate>Tue, 17 Mar 2026 06:00:00 GMT</pubDate>
              <description><![CDATA[
                <a href="https://news.google.com/rss/articles/2">"spam.openclaw" - Results on X | Live Posts &amp; Updates</a>
              ]]></description>
              <source url="https://x.com">x.com</source>
            </item>
            <item>
              <title>Completely unrelated result</title>
              <link>https://news.google.com/rss/articles/3</link>
              <pubDate>Tue, 17 Mar 2026 08:00:00 GMT</pubDate>
              <description><![CDATA[
                <a href="https://news.google.com/rss/articles/3">Completely unrelated result</a>
              ]]></description>
              <source url="https://example.com">Example</source>
            </item>
          </channel>
        </rss>
        """

        with patch.object(provider, "_request_text", return_value=rss_feed):
            items = provider.fetch_google_news_archive("openclaw")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, "google_news")
        self.assertEqual(items[0].source_type, "archive")
        self.assertEqual(items[0].author, "51CTO")
        self.assertEqual(items[0].published_at, datetime.fromisoformat("2026-03-17T04:42:44+00:00").replace(tzinfo=None))

    def test_real_provider_fetch_gdelt_archive_parses_and_filters_response(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                gdelt_enabled=True,
                gdelt_history_days=90,
                gdelt_max_items=10,
                request_timeout_seconds=8.0,
            )
        )

        payload = json.dumps(
            {
                "articles": [
                    {
                        "url": "https://example.com/openclaw-launch",
                        "title": "OpenClaw launches browser agent mode",
                        "seendate": "20260317T044244Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                    {
                        "url": "https://example.com/unrelated",
                        "title": "Completely unrelated result",
                        "seendate": "20260317T050000Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                ]
            }
        )

        with patch.object(provider, "_request_text", return_value=payload):
            items = provider.fetch_gdelt_archive("openclaw")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, "gdelt")
        self.assertEqual(items[0].source_type, "archive")
        self.assertEqual(items[0].author, "example.com")
        self.assertEqual(items[0].published_at, datetime(2026, 3, 17, 4, 42, 44))

    def test_real_provider_fetch_gdelt_archive_does_not_match_domain_only_noise(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                gdelt_enabled=True,
                gdelt_history_days=90,
                gdelt_max_items=10,
                request_timeout_seconds=8.0,
            )
        )

        payload = json.dumps(
            {
                "articles": [
                    {
                        "url": "https://example.com/story",
                        "title": "Browser agent roundup of the week",
                        "seendate": "20260317T050000Z",
                        "domain": "openclaw-news.example",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                    {
                        "url": "https://example.com/openclaw-launch",
                        "title": "OpenClaw launches browser agent mode",
                        "seendate": "20260317T044244Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                ]
            }
        )

        with patch.object(provider, "_request_text", return_value=payload):
            items = provider.fetch_gdelt_archive("openclaw")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "OpenClaw launches browser agent mode")

    def test_real_provider_fetch_gdelt_archive_deduplicates_near_identical_titles(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                gdelt_enabled=True,
                gdelt_history_days=90,
                gdelt_max_items=10,
                request_timeout_seconds=8.0,
            )
        )

        payload = json.dumps(
            {
                "articles": [
                    {
                        "url": "https://example.com/openclaw-launch-1",
                        "title": "OpenClaw launches browser agent mode beta for desktop automation",
                        "seendate": "20260317T084244Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                    {
                        "url": "https://mirror.example.com/openclaw-launch-1",
                        "title": "OpenClaw launches browser agent mode beta for desktop automation tools",
                        "seendate": "20260317T074244Z",
                        "domain": "mirror.example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                ]
            }
        )

        with patch.object(provider, "_request_text", return_value=payload):
            items = provider.fetch_gdelt_archive("openclaw")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://example.com/openclaw-launch-1")

    def test_real_provider_fetch_gdelt_archive_requires_context_for_ambiguous_query(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                gdelt_enabled=True,
                gdelt_history_days=90,
                gdelt_max_items=10,
                request_timeout_seconds=8.0,
            )
        )

        payload = json.dumps(
            {
                "articles": [
                    {
                        "url": "https://example.com/claude-le-roy",
                        "title": "CAN 2025 : Mustapha Hadji dézingue Claude Le Roy",
                        "seendate": "20260318T231500Z",
                        "domain": "example.com",
                        "language": "French",
                        "sourcecountry": "France",
                    },
                    {
                        "url": "https://example.com/claude-code-security",
                        "title": "Hackers are disguising malware as Claude Code",
                        "seendate": "20260318T173000Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                ]
            }
        )

        with patch.object(provider, "_request_text", return_value=payload):
            items = provider.fetch_gdelt_archive("claude")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Hackers are disguising malware as Claude Code")

    def test_real_provider_fetch_gdelt_archive_uses_configured_ambiguous_contexts(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                gdelt_enabled=True,
                gdelt_history_days=90,
                gdelt_max_items=10,
                archive_ambiguous_query_contexts_json='{"manus":["ai","agent","agents"]}',
                request_timeout_seconds=8.0,
            )
        )

        payload = json.dumps(
            {
                "articles": [
                    {
                        "url": "https://example.com/manus-island",
                        "title": "Storm damages port on Manus island",
                        "seendate": "20260318T150000Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "Australia",
                    },
                    {
                        "url": "https://example.com/manus-ai",
                        "title": "Manus AI launches a new agent workspace",
                        "seendate": "20260318T160000Z",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "United States",
                    },
                ]
            }
        )

        with patch.object(provider, "_request_text", return_value=payload):
            items = provider.fetch_gdelt_archive("manus")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Manus AI launches a new agent workspace")

    def test_real_provider_fetch_direct_rss_archive_parses_rss_and_atom_feeds(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                direct_rss_enabled=True,
                direct_rss_max_items=10,
                request_timeout_seconds=8.0,
            )
        )

        payloads = {
            "https://36kr.com/feed": """
            <rss version="2.0">
              <channel>
                <item>
                  <title>OpenClaw 推出企业功能</title>
                  <link>https://36kr.com/p/1</link>
                  <pubDate>2026-03-18 10:30:00 +0800</pubDate>
                  <description><![CDATA[OpenClaw 企业版开始灰度。]]></description>
                  <author>36Kr</author>
                </item>
                <item>
                  <title>Completely unrelated result</title>
                  <link>https://36kr.com/p/2</link>
                  <pubDate>2026-03-18 09:30:00 +0800</pubDate>
                  <description><![CDATA[Unrelated.]]></description>
                  <author>36Kr</author>
                </item>
              </channel>
            </rss>
            """,
            "https://www.theverge.com/rss/index.xml": """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>OpenClaw ships a new desktop workflow</title>
                <link href="https://www.theverge.com/openclaw" rel="alternate" />
                <updated>2026-03-18T02:15:00+00:00</updated>
                <summary>OpenClaw adds automation controls.</summary>
                <author><name>The Verge</name></author>
              </entry>
            </feed>
            """,
        }

        def fake_request_text(url: str, headers: dict[str, str]) -> str:
            del headers
            if url in payloads:
                return payloads[url]
            raise ProviderError(f"blocked in test: {url}")

        with patch.object(provider, "_request_text", side_effect=fake_request_text):
            items = provider.fetch_direct_rss_archive("openclaw")

        self.assertEqual(len(items), 2)
        self.assertEqual({item.source for item in items}, {"direct_rss"})
        self.assertEqual(items[0].title, "OpenClaw 推出企业功能")
        self.assertEqual(items[1].author, "The Verge")
        self.assertTrue(all(item.published_at is not None for item in items))

    def test_real_provider_fetch_direct_rss_archive_ignores_summary_only_matches(self) -> None:
        provider = RealDataProvider(
            Settings(
                provider_mode="real",
                direct_rss_enabled=True,
                direct_rss_max_items=10,
                request_timeout_seconds=8.0,
            )
        )

        payload = """
        <rss version="2.0">
          <channel>
            <item>
              <title>Daily roundup</title>
              <link>https://example.com/roundup</link>
              <pubDate>2026-03-18 10:30:00 +0800</pubDate>
              <description><![CDATA[OpenClaw appears in the summary only.]]></description>
              <author>Example</author>
            </item>
            <item>
              <title>OpenClaw ships a new desktop workflow</title>
              <link>https://example.com/openclaw</link>
              <pubDate>2026-03-18 11:30:00 +0800</pubDate>
              <description><![CDATA[OpenClaw adds automation controls.]]></description>
              <author>Example</author>
            </item>
          </channel>
        </rss>
        """

        with patch.object(provider, "_request_text", return_value=payload):
            items = provider.fetch_direct_rss_archive("openclaw")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "OpenClaw ships a new desktop workflow")

    def test_provider_smoke_skips_search_when_probe_fails(self) -> None:
        smoke = run_provider_smoke(
            query="anthropic/claude-code",
            period="30d",
            probe_mode="real",
            provider_status_loader=lambda: get_provider_status(Settings(provider_mode="mock")),
            provider_verify_runner=lambda **_: ProviderVerifyPayload(
                probe_mode="real",
                requested_mode="mock",
                effective_mode="real",
                summary="probe failed",
                github=ProviderProbePayload(
                    source="github",
                    attempted_provider="real",
                    status="failed",
                    endpoint="https://api.github.com/rate_limit",
                    message="failed",
                ),
                newsnow=ProviderProbePayload(
                    source="newsnow",
                    attempted_provider="real",
                    status="success",
                    endpoint="https://newsnow.example.com/api/s?id=weibo-hot",
                    message="ok",
                ),
            ),
            search_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("should not run")),
        )

        self.assertEqual(smoke.search.status, "skipped")
        self.assertTrue(any("force_search" in item for item in smoke.next_steps))

    def test_provider_smoke_can_force_end_to_end_search(self) -> None:
        fake_search = type(
            "SearchPayload",
            (),
            {
                "keyword": type("Keyword", (), {"kind": "github_repo", "normalized_query": "anthropic/claude-code"})(),
                "trend": type("Trend", (), {"series": [1, 2]})(),
                "content_items": [1, 2, 3],
                "availability": {"github_history": "ready", "newsnow_snapshot": "ready"},
                "backfill_job": type("BackfillJob", (), {"status": "success"})(),
            },
        )()
        smoke = run_provider_smoke(
            query="anthropic/claude-code",
            period="30d",
            probe_mode="real",
            force_search=True,
            provider_status_loader=lambda: get_provider_status(Settings(provider_mode="real")),
            provider_verify_runner=lambda **_: ProviderVerifyPayload(
                probe_mode="real",
                requested_mode="real",
                effective_mode="real",
                summary="probe failed",
                github=ProviderProbePayload(
                    source="github",
                    attempted_provider="real",
                    status="failed",
                    endpoint="https://api.github.com/rate_limit",
                    message="failed",
                ),
                newsnow=ProviderProbePayload(
                    source="newsnow",
                    attempted_provider="real",
                    status="failed",
                    endpoint="https://newsnow.example.com/api/s?id=weibo-hot",
                    message="failed",
                ),
            ),
            search_runner=lambda *_args, **_kwargs: fake_search,
        )

        self.assertEqual(smoke.search.status, "success")
        self.assertEqual(smoke.search.trend_series_count, 2)
        self.assertEqual(smoke.search.content_item_count, 3)

    def test_provider_smoke_keeps_default_search_when_archive_probe_fails(self) -> None:
        fake_search = type(
            "SearchPayload",
            (),
            {
                "keyword": type("Keyword", (), {"kind": "github_repo", "normalized_query": "openclaw/openclaw"})(),
                "trend": type("Trend", (), {"series": [1]})(),
                "content_items": [1],
                "availability": {"github_history": "ready", "newsnow_snapshot": "ready", "google_news_archive": "failed"},
                "backfill_job": type("BackfillJob", (), {"status": "partial"})(),
            },
        )()

        smoke = run_provider_smoke(
            query="openclaw",
            period="30d",
            probe_mode="real",
            provider_status_loader=lambda: get_provider_status(Settings(provider_mode="real")),
            provider_verify_runner=lambda **_: ProviderVerifyPayload(
                probe_mode="real",
                requested_mode="real",
                effective_mode="real",
                summary="archive probe failed",
                github=ProviderProbePayload(
                    source="github",
                    attempted_provider="real",
                    status="success",
                    endpoint="https://api.github.com/rate_limit",
                    message="ok",
                ),
                newsnow=ProviderProbePayload(
                    source="newsnow",
                    attempted_provider="real",
                    status="success",
                    endpoint="https://newsnow.example.com/api/s?id=weibo",
                    message="ok",
                ),
                google_news=ProviderProbePayload(
                    source="google_news",
                    attempted_provider="real",
                    status="failed",
                    endpoint="https://news.google.com/rss/search?q=openclaw",
                    message="failed",
                ),
                gdelt=ProviderProbePayload(
                    source="gdelt",
                    attempted_provider="real",
                    status="success",
                    endpoint="https://api.gdeltproject.org/api/v2/doc/doc?query=%22openclaw%22",
                    message="ok",
                ),
            ),
            search_runner=lambda *_args, **_kwargs: fake_search,
        )

        self.assertEqual(smoke.search.status, "success")
        self.assertIn("补充历史源仍有失败或跳过", smoke.summary)
        self.assertTrue(any("Google News" in item and "不会阻塞默认搜索" in item for item in smoke.next_steps))

    def test_parse_search_query_normalizes_github_url(self) -> None:
        target = parse_search_query("https://github.com/Anthropic/Claude-Code/")
        self.assertEqual(target.kind, "github_repo")
        self.assertEqual(target.normalized_query, "anthropic/claude-code")
        self.assertEqual(target.target_ref, "anthropic/claude-code")

    def test_resolve_search_query_promotes_unique_bare_repo_name(self) -> None:
        target = resolve_search_query(
            "openclaw",
            repo_lookup=lambda query: "smacker/openclaw" if query == "openclaw" else None,
        )

        self.assertEqual(target.kind, "github_repo")
        self.assertEqual(target.normalized_query, "smacker/openclaw")
        self.assertEqual(target.target_ref, "smacker/openclaw")
        self.assertEqual(target.raw_query, "openclaw")

    def test_resolve_search_query_keeps_keyword_when_repo_lookup_is_missing(self) -> None:
        target = resolve_search_query("openclaw", repo_lookup=lambda _query: None)

        self.assertEqual(target.kind, "keyword")
        self.assertEqual(target.normalized_query, "openclaw")
        self.assertIsNone(target.target_ref)

    def test_github_repo_name_resolver_requires_unique_exact_match(self) -> None:
        settings = Settings(
            provider_mode="real",
            github_api_base_url="https://api.github.com",
            request_timeout_seconds=8.0,
        )

        def unique_request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            del url, headers
            return (
                {
                    "items": [
                        {
                            "name": "OpenClaw",
                            "full_name": "smacker/openclaw",
                        },
                        {
                            "name": "openclaw-cli",
                            "full_name": "someone/openclaw-cli",
                        },
                    ]
                },
                {},
            )

        def ambiguous_request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            del url, headers
            return (
                {
                    "items": [
                        {
                            "name": "OpenClaw",
                            "full_name": "smacker/openclaw",
                        },
                        {
                            "name": "openclaw",
                            "full_name": "another/openclaw",
                        },
                    ]
                },
                {},
            )

        self.assertEqual(
            resolve_github_repo_name("openclaw", settings=settings, request_json=unique_request_json),
            "smacker/openclaw",
        )
        self.assertIsNone(
            resolve_github_repo_name("openclaw", settings=settings, request_json=ambiguous_request_json)
        )

    def test_github_repo_name_resolver_prefers_owner_repo_match_when_exact_name_is_ambiguous(self) -> None:
        settings = Settings(
            provider_mode="real",
            github_api_base_url="https://api.github.com",
            request_timeout_seconds=8.0,
        )

        def request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            del url, headers
            return (
                {
                    "items": [
                        {
                            "name": "openclaw",
                            "full_name": "openclaw/openclaw",
                        },
                        {
                            "name": "OpenClaw",
                            "full_name": "pjasicek/OpenClaw",
                        },
                        {
                            "name": "openclaw",
                            "full_name": "coollabsio/openclaw",
                        },
                    ]
                },
                {},
            )

        self.assertEqual(
            resolve_github_repo_name("openclaw", settings=settings, request_json=request_json),
            "openclaw/openclaw",
        )

    def test_github_repo_name_resolver_uses_direct_self_named_repo_probe_before_search(self) -> None:
        settings = Settings(
            provider_mode="real",
            github_api_base_url="https://api.github.com",
            request_timeout_seconds=8.0,
        )

        def request_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
            del headers
            if url.endswith("/repos/openclaw/openclaw"):
                return (
                    {
                        "name": "OpenClaw",
                        "full_name": "openclaw/openclaw",
                        "owner": {"login": "openclaw"},
                    },
                    {},
                )
            if "/search/repositories?" in url:
                raise AssertionError("search endpoint should not run when direct self-named probe succeeds")
            raise AssertionError(url)

        self.assertEqual(
            resolve_github_repo_name("openclaw", settings=settings, request_json=request_json),
            "openclaw/openclaw",
        )

    def test_newsnow_endpoint_builder_prefers_query_param_and_keeps_legacy_fallback(self) -> None:
        self.assertEqual(
            build_newsnow_source_endpoint("https://newsnow.example.com", "weibo-hot"),
            "https://newsnow.example.com/api/s?id=weibo",
        )
        self.assertEqual(
            iter_newsnow_source_endpoints("https://newsnow.example.com", "weibo-hot"),
            [
                "https://newsnow.example.com/api/s?id=weibo",
                "https://newsnow.example.com/api/s/weibo",
                "https://newsnow.example.com/api/s?id=weibo-hot",
                "https://newsnow.example.com/api/s/weibo-hot",
            ],
        )

    def test_newsnow_source_id_normalizer_maps_legacy_aliases(self) -> None:
        self.assertEqual(normalize_newsnow_source_id("weibo-hot"), "weibo")
        self.assertEqual(normalize_newsnow_source_id("github-trending"), "github")
        self.assertEqual(iter_newsnow_source_ids("weibo-hot"), ["weibo", "weibo-hot"])

    def test_repository_search_backfill_creates_series(self) -> None:
        repo_query = f"owner-{uuid4().hex[:8]}/repo-{uuid4().hex[:8]}"
        background_tasks = BackgroundTasks()
        initial = search_keyword(
            db=self.db,
            background_tasks=background_tasks,
            query=repo_query,
            period="30d",
        )

        self.assertEqual(initial.keyword.kind, "github_repo")
        self.assertIsNotNone(initial.backfill_job)
        self.assertIn(initial.availability["github_history"], {"missing", "pending", "running"})

        self.db.close()
        run_backfill_job(initial.backfill_job.id)
        self.db = SessionLocal()

        refreshed = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=repo_query,
            period="30d",
        )

        self.assertTrue(refreshed.trend.series)
        self.assertTrue(any(item.source == "github" for item in refreshed.content_items))
        self.assertEqual(refreshed.availability["github_history"], "ready")
        self.assertEqual(refreshed.backfill_job.status, "success")

        status = get_backfill_status(self.db, refreshed.keyword.id)
        self.assertIn(status.status, {"success", "partial"})
        self.assertTrue(status.tasks)
        self.assertTrue(any(task.source == "github" and task.task_type == "content" for task in status.tasks))

    def test_search_reuses_failed_backfill_until_explicit_retry(self) -> None:
        query = f"owner-{uuid4().hex[:8]}/repo-{uuid4().hex[:8]}"
        initial = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="30d",
        )

        class FailingProvider:
            name = "failing"

            def fetch_github_history(self, target_ref: str):
                raise RuntimeError(f"probe blocked for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise RuntimeError(f"probe blocked for {target_ref}")

            def fetch_newsnow_snapshot(self, keyword_query: str):
                raise RuntimeError(f"probe blocked for {keyword_query}")

        with patch("app.services.backfill.get_data_provider", return_value=FailingProvider()):
            run_backfill_job(initial.backfill_job.id)

        self.db.close()
        self.db = SessionLocal()

        failed = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="30d",
        )

        self.assertIsNotNone(failed.backfill_job)
        self.assertEqual(failed.backfill_job.id, initial.backfill_job.id)
        self.assertEqual(failed.backfill_job.status, "failed")
        self.assertEqual(failed.availability["github_history"], "failed")
        self.assertTrue(any("probe blocked" in (task.message or "") for task in failed.backfill_job.tasks))

    def test_keyword_search_hides_stale_newsnow_failure_when_history_is_ready(self) -> None:
        query = f"stale-failure-{uuid4().hex[:8]}"
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        initial = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="all",
        )
        job = BackfillJob(keyword_id=initial.keyword.id, status="failed", error_message="probe blocked")
        self.db.add(job)
        self.db.flush()
        self.db.add(
            BackfillJobTask(
                job_id=job.id,
                source="newsnow",
                task_type="snapshot",
                status="failed",
                message="probe blocked",
            )
        )
        self.db.commit()

        self.db.add(
            TrendPoint(
                keyword_id=initial.keyword.id,
                source="keyword_history",
                metric="matched_item_count",
                source_type="timeline",
                bucket_granularity="day",
                bucket_start=today,
                value=3.0,
                raw_json="{}",
            )
        )
        self.db.commit()

        refreshed = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="all",
        )

        self.assertIsNone(refreshed.backfill_job)
        self.assertEqual(refreshed.availability["newsnow_snapshot"], "not_applicable")

    def test_refresh_keyword_retries_failed_backfill_explicitly(self) -> None:
        query = f"owner-{uuid4().hex[:8]}/repo-{uuid4().hex[:8]}"

        class FailingProvider:
            name = "failing"

            def fetch_github_history(self, target_ref: str):
                raise RuntimeError(f"probe blocked for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise RuntimeError(f"probe blocked for {target_ref}")

            def fetch_newsnow_snapshot(self, keyword_query: str):
                raise RuntimeError(f"probe blocked for {keyword_query}")

        with patch("app.services.backfill.get_data_provider", return_value=FailingProvider()):
            first = refresh_keyword(query, run_backfill_now=True)
            second = refresh_keyword(query, run_backfill_now=True)

        self.assertIsNotNone(first.backfill_job)
        self.assertIsNotNone(second.backfill_job)
        self.assertEqual(first.backfill_job.status, "failed")
        self.assertEqual(second.backfill_job.status, "failed")
        self.assertNotEqual(first.backfill_job.id, second.backfill_job.id)
        self.assertTrue(any("probe blocked" in (task.message or "") for task in second.backfill_job.tasks))

    def test_search_can_filter_content_items_by_source(self) -> None:
        repo_query = f"owner-{uuid4().hex[:8]}/repo-{uuid4().hex[:8]}"
        refresh_keyword(repo_query, run_backfill_now=True)

        github_only = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=repo_query,
            period="30d",
            content_source="github",
        )
        newsnow_only = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=repo_query,
            period="30d",
            content_source="newsnow",
        )

        self.assertTrue(github_only.content_items)
        self.assertTrue(newsnow_only.content_items)
        self.assertTrue(all(item.source == "github" for item in github_only.content_items))
        self.assertTrue(all(item.source == "newsnow" for item in newsnow_only.content_items))

    def test_keyword_search_prefetches_history_inline_on_first_lookup(self) -> None:
        query = f"inline-{uuid4().hex[:8]}"
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        class InlineHistoryProvider:
            name = "inline"

            def fetch_github_history(self, target_ref: str):
                raise AssertionError(f"unexpected github history request for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise AssertionError(f"unexpected github content request for {target_ref}")

            def fetch_newsnow_snapshot(self, keyword_query: str):
                raise AssertionError(f"unexpected inline news snapshot request for {keyword_query}")

            def fetch_google_news_archive(self, keyword_query: str):
                self_query = keyword_query
                return [
                    ContentItemInput(
                        source="google_news",
                        source_type="archive",
                        external_key=f"{self_query}:archive:1",
                        title=f"{self_query} archive item 1",
                        url="https://example.com/archive/1",
                        summary="archive-1",
                        author="provider",
                        published_at=today - timedelta(days=2),
                        meta_json="{}",
                    ),
                    ContentItemInput(
                        source="google_news",
                        source_type="archive",
                        external_key=f"{self_query}:archive:2",
                        title=f"{self_query} archive item 2",
                        url="https://example.com/archive/2",
                        summary="archive-2",
                        author="provider",
                        published_at=today - timedelta(days=1),
                        meta_json="{}",
                    ),
                ]

        with patch("app.services.search.get_data_provider", return_value=InlineHistoryProvider()):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query=query,
                period="all",
            )

        history_series = next(
            series
            for series in payload.trend.series
            if series.source == "keyword_history"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual([point.value for point in history_series.points], [1.0, 1.0])
        self.assertTrue(any(item.source == "google_news" for item in payload.content_items))
        self.assertIsNone(payload.backfill_job)
        self.assertEqual(payload.availability["newsnow_snapshot"], "not_applicable")
        self.assertEqual(payload.availability["google_news_archive"], "ready")

    def test_keyword_search_prefetches_direct_rss_inline_on_first_lookup(self) -> None:
        query = f"rss-inline-{uuid4().hex[:8]}"
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        class InlineDirectRssProvider:
            name = "inline-rss"

            def fetch_github_history(self, target_ref: str):
                raise AssertionError(f"unexpected github history request for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise AssertionError(f"unexpected github content request for {target_ref}")

            def fetch_newsnow_snapshot(self, keyword_query: str):
                raise AssertionError(f"unexpected inline news snapshot request for {keyword_query}")

            def fetch_google_news_archive(self, keyword_query: str):
                return []

            def fetch_direct_rss_archive(self, keyword_query: str):
                self_query = keyword_query
                return [
                    ContentItemInput(
                        source="direct_rss",
                        source_type="archive",
                        external_key=f"{self_query}:rss:1",
                        title=f"{self_query} rss item 1",
                        url="https://example.com/rss/1",
                        summary="rss-1",
                        author="publisher",
                        published_at=today - timedelta(days=2),
                        meta_json="{}",
                    ),
                    ContentItemInput(
                        source="direct_rss",
                        source_type="archive",
                        external_key=f"{self_query}:rss:2",
                        title=f"{self_query} rss item 2",
                        url="https://example.com/rss/2",
                        summary="rss-2",
                        author="publisher",
                        published_at=today - timedelta(days=1),
                        meta_json="{}",
                    ),
                ]

            def fetch_gdelt_archive(self, keyword_query: str):
                return []

        with patch("app.services.search.get_data_provider", return_value=InlineDirectRssProvider()):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query=query,
                period="all",
            )

        history_series = next(
            series
            for series in payload.trend.series
            if series.source == "keyword_history"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual([point.value for point in history_series.points], [1.0, 1.0])
        self.assertTrue(any(item.source == "direct_rss" for item in payload.content_items))
        self.assertEqual(payload.availability["direct_rss_archive"], "ready")
        self.assertIsNone(payload.backfill_job)

    def test_keyword_search_prefetches_gdelt_inline_on_first_lookup(self) -> None:
        query = f"gdelt-inline-{uuid4().hex[:8]}"
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        class InlineGdeltProvider:
            name = "inline-gdelt"

            def fetch_github_history(self, target_ref: str):
                raise AssertionError(f"unexpected github history request for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise AssertionError(f"unexpected github content request for {target_ref}")

            def fetch_newsnow_snapshot(self, keyword_query: str):
                raise AssertionError(f"unexpected inline news snapshot request for {keyword_query}")

            def fetch_google_news_archive(self, keyword_query: str):
                return []

            def fetch_gdelt_archive(self, keyword_query: str):
                self_query = keyword_query
                return [
                    ContentItemInput(
                        source="gdelt",
                        source_type="archive",
                        external_key=f"{self_query}:gdelt:1",
                        title=f"{self_query} gdelt item 1",
                        url="https://example.com/gdelt/1",
                        summary=None,
                        author="provider",
                        published_at=today - timedelta(days=2),
                        meta_json="{}",
                    ),
                    ContentItemInput(
                        source="gdelt",
                        source_type="archive",
                        external_key=f"{self_query}:gdelt:2",
                        title=f"{self_query} gdelt item 2",
                        url="https://example.com/gdelt/2",
                        summary=None,
                        author="provider",
                        published_at=today - timedelta(days=1),
                        meta_json="{}",
                    ),
                ]

        with patch("app.services.search.get_data_provider", return_value=InlineGdeltProvider()):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query=query,
                period="all",
            )

        history_series = next(
            series
            for series in payload.trend.series
            if series.source == "keyword_history"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual([point.value for point in history_series.points], [1.0, 1.0])
        self.assertTrue(any(item.source == "gdelt" for item in payload.content_items))
        self.assertEqual(payload.availability["gdelt_archive"], "ready")
        self.assertIsNone(payload.backfill_job)

    def test_keyword_search_prefetches_newsnow_snapshot_inline_when_history_is_missing(self) -> None:
        query = f"newsnow-inline-{uuid4().hex[:8]}"
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        class InlineNewsNowProvider:
            name = "inline-newsnow"

            def fetch_github_history(self, target_ref: str):
                raise AssertionError(f"unexpected github history request for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise AssertionError(f"unexpected github content request for {target_ref}")

            def fetch_google_news_archive(self, keyword_query: str):
                return []

            def fetch_direct_rss_archive(self, keyword_query: str):
                return []

            def fetch_gdelt_archive(self, keyword_query: str):
                return []

            def fetch_newsnow_snapshot(self, keyword_query: str):
                self_query = keyword_query
                return (
                    [
                        TrendPointInput(
                            source="newsnow",
                            metric="hot_hit_count",
                            source_type="snapshot",
                            bucket_granularity="day",
                            bucket_start=today,
                            value=4.0,
                            raw_json=f'{{"query":"{self_query}"}}',
                        ),
                        TrendPointInput(
                            source="newsnow",
                            metric="platform_count",
                            source_type="snapshot",
                            bucket_granularity="day",
                            bucket_start=today,
                            value=2.0,
                            raw_json=f'{{"query":"{self_query}"}}',
                        ),
                    ],
                    [
                        ContentItemInput(
                            source="newsnow",
                            source_type="snapshot",
                            external_key=f"{self_query}:snapshot:1",
                            title=f"{self_query} snapshot item",
                            url="https://example.com/newsnow/1",
                            summary="snapshot",
                            author="provider",
                            published_at=None,
                            meta_json="{}",
                        )
                    ],
                )

        with patch("app.services.search.get_data_provider", return_value=InlineNewsNowProvider()):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query=query,
                period="all",
            )

        newsnow_series = next(
            series for series in payload.trend.series if series.source == "newsnow" and series.metric == "hot_hit_count"
        )
        self.assertEqual([point.value for point in newsnow_series.points], [4.0])
        self.assertTrue(any(item.source == "newsnow" for item in payload.content_items))
        self.assertEqual(payload.availability["newsnow_snapshot"], "ready")
        self.assertIsNone(payload.backfill_job)

    def test_search_filters_stored_gdelt_noise_and_rebuilds_series(self) -> None:
        bucket_start = datetime(2026, 3, 17, 0, 0, 0)
        repo_query = f"owner-{uuid4().hex[:8]}/openclaw"
        keyword = Keyword(
            raw_query=repo_query,
            normalized_query=repo_query,
            kind="github_repo",
            target_ref=repo_query,
        )
        self.db.add(keyword)
        self.db.flush()

        self.db.add_all(
            [
                ContentItem(
                    keyword_id=keyword.id,
                    source="gdelt",
                    source_type="archive",
                    external_key="gdelt-visible",
                    title="OpenClaw launches browser agent mode beta for desktop automation",
                    url="https://example.com/openclaw-launch-1",
                    summary=None,
                    author="example.com",
                    published_at=datetime(2026, 3, 17, 10, 0, 0),
                    meta_json="{}",
                ),
                ContentItem(
                    keyword_id=keyword.id,
                    source="gdelt",
                    source_type="archive",
                    external_key="gdelt-noise",
                    title="Browser agent roundup of the week",
                    url="https://example.com/story",
                    summary=None,
                    author="openclaw-news.example",
                    published_at=datetime(2026, 3, 17, 11, 0, 0),
                    meta_json="{}",
                ),
                ContentItem(
                    keyword_id=keyword.id,
                    source="gdelt",
                    source_type="archive",
                    external_key="gdelt-duplicate",
                    title="OpenClaw launches browser agent mode beta for desktop automation tools",
                    url="https://mirror.example.com/openclaw-launch-1",
                    summary=None,
                    author="mirror.example.com",
                    published_at=datetime(2026, 3, 17, 9, 30, 0),
                    meta_json="{}",
                ),
            ]
        )
        self.db.add(
            TrendPoint(
                keyword_id=keyword.id,
                source="gdelt",
                metric="matched_item_count",
                source_type="timeline",
                bucket_granularity="day",
                bucket_start=bucket_start,
                value=3.0,
                raw_json="{}",
            )
        )
        self.db.commit()

        with (
            patch("app.services.search.get_settings", return_value=Settings(provider_mode="real")),
            patch("app.services.search._prefetch_content_history_inline", return_value=False),
            patch("app.services.search._maybe_schedule_backfill", return_value=None),
        ):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query=repo_query,
                period="all",
                content_source="gdelt",
            )

        self.assertEqual(len(payload.content_items), 1)
        self.assertEqual(payload.content_items[0].title, "OpenClaw launches browser agent mode beta for desktop automation")
        gdelt_series = next(
            series
            for series in payload.trend.series
            if series.source == "gdelt"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual([point.value for point in gdelt_series.points], [1.0])

    def test_keyword_search_dedupes_archive_duplicates_with_direct_rss_priority(self) -> None:
        first_day = datetime(2026, 3, 17, 0, 0, 0)
        second_day = datetime(2026, 3, 18, 0, 0, 0)
        keyword = Keyword(
            raw_query="openclaw",
            normalized_query="openclaw",
            kind="keyword",
        )
        self.db.add(keyword)
        self.db.flush()

        self.db.add_all(
            [
                ContentItem(
                    keyword_id=keyword.id,
                    source="direct_rss",
                    source_type="archive",
                    external_key="direct-rss-primary",
                    title="OpenClaw releases desktop agent",
                    url="https://example.com/rss/openclaw",
                    summary="direct-rss",
                    author="RSS Publisher",
                    published_at=datetime(2026, 3, 17, 10, 0, 0),
                    meta_json="{}",
                ),
                ContentItem(
                    keyword_id=keyword.id,
                    source="google_news",
                    source_type="archive",
                    external_key="google-news-duplicate",
                    title="OpenClaw releases desktop agent!",
                    url="https://news.google.com/rss/articles/1",
                    summary="google-news",
                    author="Google News",
                    published_at=datetime(2026, 3, 17, 11, 0, 0),
                    meta_json="{}",
                ),
                ContentItem(
                    keyword_id=keyword.id,
                    source="newsnow",
                    source_type="snapshot",
                    external_key="newsnow-follow-up",
                    title="OpenClaw follow-up discussion",
                    url="https://example.com/newsnow/openclaw",
                    summary="newsnow",
                    author="NewsNow",
                    published_at=datetime(2026, 3, 18, 9, 0, 0),
                    meta_json="{}",
                ),
            ]
        )
        self.db.add(
            TrendPoint(
                keyword_id=keyword.id,
                source="keyword_history",
                metric="matched_item_count",
                source_type="timeline",
                bucket_granularity="day",
                bucket_start=first_day,
                value=2.0,
                raw_json="{}",
            )
        )
        self.db.commit()

        with (
            patch("app.services.search.get_settings", return_value=Settings(provider_mode="real")),
            patch("app.services.search._prefetch_content_history_inline", return_value=False),
            patch("app.services.search._maybe_schedule_backfill", return_value=None),
        ):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query="openclaw",
                period="all",
            )

        archive_items = [item for item in payload.content_items if item.source in {"google_news", "direct_rss", "gdelt"}]
        self.assertEqual(len(archive_items), 1)
        self.assertEqual(archive_items[0].source, "direct_rss")
        self.assertFalse(any(item.source == "google_news" for item in payload.content_items))

        history_series = next(
            series
            for series in payload.trend.series
            if series.source == "keyword_history"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual(
            [(point.bucket_start, point.value) for point in history_series.points],
            [(first_day, 1.0), (second_day, 1.0)],
        )

    def test_search_filters_summary_only_direct_rss_noise_and_rebuilds_series(self) -> None:
        bucket_start = datetime(2026, 3, 17, 0, 0, 0)
        repo_query = f"owner-{uuid4().hex[:8]}/openclaw"
        keyword = Keyword(
            raw_query=repo_query,
            normalized_query=repo_query,
            kind="github_repo",
            target_ref=repo_query,
        )
        self.db.add(keyword)
        self.db.flush()

        self.db.add_all(
            [
                ContentItem(
                    keyword_id=keyword.id,
                    source="direct_rss",
                    source_type="archive",
                    external_key="direct-rss-strong",
                    title="OpenClaw ships a desktop agent update",
                    url="https://example.com/openclaw-update",
                    summary="strong",
                    author="Publisher",
                    published_at=datetime(2026, 3, 17, 10, 0, 0),
                    meta_json="{}",
                ),
                ContentItem(
                    keyword_id=keyword.id,
                    source="direct_rss",
                    source_type="archive",
                    external_key="direct-rss-weak",
                    title="Daily roundup",
                    url="https://example.com/roundup",
                    summary="OpenClaw is only mentioned in the summary.",
                    author="Publisher",
                    published_at=datetime(2026, 3, 17, 11, 0, 0),
                    meta_json="{}",
                ),
            ]
        )
        self.db.add(
            TrendPoint(
                keyword_id=keyword.id,
                source="direct_rss",
                metric="matched_item_count",
                source_type="timeline",
                bucket_granularity="day",
                bucket_start=bucket_start,
                value=2.0,
                raw_json="{}",
            )
        )
        self.db.commit()

        with (
            patch("app.services.search.get_settings", return_value=Settings(provider_mode="real")),
            patch("app.services.search._prefetch_content_history_inline", return_value=False),
            patch("app.services.search._maybe_schedule_backfill", return_value=None),
        ):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query=repo_query,
                period="all",
                content_source="direct_rss",
            )

        self.assertEqual(len(payload.content_items), 1)
        self.assertEqual(payload.content_items[0].title, "OpenClaw ships a desktop agent update")
        direct_rss_series = next(
            series
            for series in payload.trend.series
            if series.source == "direct_rss"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual([point.value for point in direct_rss_series.points], [1.0])

    def test_keyword_search_filters_ambiguous_gdelt_name_noise_and_rebuilds_series(self) -> None:
        bucket_start = datetime(2026, 3, 18, 0, 0, 0)
        keyword = Keyword(
            raw_query="claude",
            normalized_query="claude",
            kind="keyword",
        )
        self.db.add(keyword)
        self.db.flush()

        self.db.add_all(
            [
                ContentItem(
                    keyword_id=keyword.id,
                    source="gdelt",
                    source_type="archive",
                    external_key="gdelt-noise-claude-name",
                    title="CAN 2025 : Mustapha Hadji dézingue Claude Le Roy",
                    url="https://example.com/claude-le-roy",
                    summary=None,
                    author="example.com",
                    published_at=datetime(2026, 3, 18, 23, 15, 0),
                    meta_json="{}",
                ),
                ContentItem(
                    keyword_id=keyword.id,
                    source="gdelt",
                    source_type="archive",
                    external_key="gdelt-valid-claude-code",
                    title="Hackers are disguising malware as Claude Code",
                    url="https://example.com/claude-code-security",
                    summary=None,
                    author="example.com",
                    published_at=datetime(2026, 3, 18, 17, 30, 0),
                    meta_json="{}",
                ),
            ]
        )
        self.db.add(
            TrendPoint(
                keyword_id=keyword.id,
                source="gdelt",
                metric="matched_item_count",
                source_type="timeline",
                bucket_granularity="day",
                bucket_start=bucket_start,
                value=2.0,
                raw_json="{}",
            )
        )
        self.db.add(
            TrendPoint(
                keyword_id=keyword.id,
                source="keyword_history",
                metric="matched_item_count",
                source_type="timeline",
                bucket_granularity="day",
                bucket_start=bucket_start,
                value=2.0,
                raw_json="{}",
            )
        )
        self.db.commit()

        with (
            patch("app.services.search.get_settings", return_value=Settings(provider_mode="real")),
            patch("app.services.search._prefetch_content_history_inline", return_value=False),
            patch("app.services.search._maybe_schedule_backfill", return_value=None),
        ):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query="claude",
                period="all",
                content_source="gdelt",
            )

        self.assertEqual(len(payload.content_items), 1)
        self.assertEqual(payload.content_items[0].title, "Hackers are disguising malware as Claude Code")
        gdelt_series = next(
            series
            for series in payload.trend.series
            if series.source == "gdelt"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        keyword_history_series = next(
            series
            for series in payload.trend.series
            if series.source == "keyword_history"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual([point.value for point in gdelt_series.points], [1.0])
        self.assertEqual([point.value for point in keyword_history_series.points], [1.0])

    def test_keyword_search_uses_configured_ambiguous_contexts_for_gdelt_read_filter(self) -> None:
        bucket_start = datetime(2026, 3, 18, 0, 0, 0)
        keyword = Keyword(
            raw_query="manus",
            normalized_query="manus",
            kind="keyword",
        )
        self.db.add(keyword)
        self.db.flush()

        self.db.add_all(
            [
                ContentItem(
                    keyword_id=keyword.id,
                    source="gdelt",
                    source_type="archive",
                    external_key="gdelt-manus-noise",
                    title="Storm damages port on Manus island",
                    url="https://example.com/manus-island",
                    summary=None,
                    author="example.com",
                    published_at=datetime(2026, 3, 18, 15, 0, 0),
                    meta_json="{}",
                ),
                ContentItem(
                    keyword_id=keyword.id,
                    source="gdelt",
                    source_type="archive",
                    external_key="gdelt-manus-valid",
                    title="Manus AI launches a new agent workspace",
                    url="https://example.com/manus-ai",
                    summary=None,
                    author="example.com",
                    published_at=datetime(2026, 3, 18, 16, 0, 0),
                    meta_json="{}",
                ),
            ]
        )
        self.db.add(
            TrendPoint(
                keyword_id=keyword.id,
                source="gdelt",
                metric="matched_item_count",
                source_type="timeline",
                bucket_granularity="day",
                bucket_start=bucket_start,
                value=2.0,
                raw_json="{}",
            )
        )
        self.db.add(
            TrendPoint(
                keyword_id=keyword.id,
                source="keyword_history",
                metric="matched_item_count",
                source_type="timeline",
                bucket_granularity="day",
                bucket_start=bucket_start,
                value=2.0,
                raw_json="{}",
            )
        )
        self.db.commit()

        with (
            patch(
                "app.services.search.get_settings",
                return_value=Settings(
                    provider_mode="real",
                    archive_ambiguous_query_contexts_json='{"manus":["ai","agent","agents"]}',
                ),
            ),
            patch("app.services.search._prefetch_content_history_inline", return_value=False),
            patch("app.services.search._maybe_schedule_backfill", return_value=None),
        ):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query="manus",
                period="all",
                content_source="gdelt",
            )

        self.assertEqual(len(payload.content_items), 1)
        self.assertEqual(payload.content_items[0].title, "Manus AI launches a new agent workspace")
        gdelt_series = next(
            series
            for series in payload.trend.series
            if series.source == "gdelt"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        keyword_history_series = next(
            series
            for series in payload.trend.series
            if series.source == "keyword_history"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual([point.value for point in gdelt_series.points], [1.0])
        self.assertEqual([point.value for point in keyword_history_series.points], [1.0])

    def test_repository_search_prefetches_google_news_inline_and_derives_timeline(self) -> None:
        repo_name = f"repo-{uuid4().hex[:8]}"
        query = f"owner-{uuid4().hex[:8]}/{repo_name}"
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        archive_requests: list[str] = []

        class RepoArchiveProvider:
            name = "repo-archive"

            def fetch_github_history(self, target_ref: str):
                raise AssertionError(f"unexpected github history request for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise AssertionError(f"unexpected github content request for {target_ref}")

            def fetch_newsnow_snapshot(self, keyword_query: str):
                raise AssertionError(f"unexpected news snapshot request for {keyword_query}")

            def fetch_google_news_archive(self, keyword_query: str):
                archive_requests.append(keyword_query)
                return [
                    ContentItemInput(
                        source="google_news",
                        source_type="archive",
                        external_key=f"{keyword_query}:archive:1",
                        title=f"{keyword_query} archive item 1",
                        url="https://example.com/archive/1",
                        summary="archive-1",
                        author="provider",
                        published_at=today - timedelta(days=3),
                        meta_json="{}",
                    ),
                    ContentItemInput(
                        source="google_news",
                        source_type="archive",
                        external_key=f"{keyword_query}:archive:2",
                        title=f"{keyword_query} archive item 2",
                        url="https://example.com/archive/2",
                        summary="archive-2",
                        author="provider",
                        published_at=today - timedelta(days=1),
                        meta_json="{}",
                    ),
                ]

        with patch("app.services.search.get_data_provider", return_value=RepoArchiveProvider()):
            payload = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query=query,
                period="all",
            )

        self.assertEqual(archive_requests, [repo_name])
        google_series = next(
            series
            for series in payload.trend.series
            if series.source == "google_news"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual([point.value for point in google_series.points], [1.0, 1.0])
        self.assertTrue(any(item.source == "google_news" for item in payload.content_items))
        self.assertEqual(payload.availability["google_news_archive"], "ready")
        self.assertIsNotNone(payload.backfill_job)
        self.assertIn(payload.backfill_job.status, {"pending", "running"})

    def test_repository_search_default_content_mix_keeps_google_news_visible(self) -> None:
        repo_name = f"repo-{uuid4().hex[:8]}"
        query = f"owner-{uuid4().hex[:8]}/{repo_name}"
        initial = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="all",
        )
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        for index in range(20):
            self.db.add(
                ContentItem(
                    keyword_id=initial.keyword.id,
                    source="github",
                    source_type="backfill",
                    external_key=f"{query}:github:{index}",
                    title=f"github item {index}",
                    url=f"https://example.com/github/{index}",
                    summary="github",
                    author="github",
                    published_at=today - timedelta(minutes=index),
                    meta_json="{}",
                )
            )

        for index in range(2):
            self.db.add(
                ContentItem(
                    keyword_id=initial.keyword.id,
                    source="google_news",
                    source_type="archive",
                    external_key=f"{query}:google:{index}",
                    title=f"{repo_name} news item {index}",
                    url=f"https://example.com/google/{index}",
                    summary="google",
                    author="Google News",
                    published_at=today - timedelta(days=15 + index),
                    meta_json="{}",
                )
            )

        self.db.commit()

        refreshed = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="all",
        )

        self.assertTrue(any(item.source == "google_news" for item in refreshed.content_items))
        self.assertEqual(sum(1 for item in refreshed.content_items if item.source == "google_news"), 2)
        self.assertEqual(refreshed.availability["google_news_archive"], "ready")

    def test_keyword_search_refreshes_google_news_even_when_history_already_exists(self) -> None:
        query = f"refresh-archive-{uuid4().hex[:8]}"
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        initial = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="all",
        )
        job = BackfillJob(keyword_id=initial.keyword.id, status="pending")
        self.db.add(job)
        self.db.flush()
        self.db.add(
            BackfillJobTask(
                job_id=job.id,
                source="newsnow",
                task_type="snapshot",
                status="pending",
            )
        )
        self.db.commit()

        self.db.add(
            TrendPoint(
                keyword_id=initial.keyword.id,
                source="keyword_history",
                metric="matched_item_count",
                source_type="timeline",
                bucket_granularity="day",
                bucket_start=today - timedelta(days=1),
                value=1.0,
                raw_json="{}",
            )
        )
        self.db.commit()

        class ArchiveRefreshProvider:
            name = "archive-refresh"

            def fetch_github_history(self, target_ref: str):
                raise AssertionError(f"unexpected github history request for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise AssertionError(f"unexpected github content request for {target_ref}")

            def fetch_newsnow_snapshot(self, keyword_query: str):
                raise AssertionError(f"unexpected news snapshot request for {keyword_query}")

            def fetch_google_news_archive(self, keyword_query: str):
                return [
                    ContentItemInput(
                        source="google_news",
                        source_type="archive",
                        external_key=f"{keyword_query}:archive:new",
                        title=f"{keyword_query} fresh archive item",
                        url="https://example.com/archive/new",
                        summary="fresh-archive",
                        author="provider",
                        published_at=today - timedelta(days=3),
                        meta_json="{}",
                    )
                ]

        with patch("app.services.search.get_data_provider", return_value=ArchiveRefreshProvider()):
            refreshed = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query=query,
                period="all",
                content_source="google_news",
            )

        self.assertTrue(refreshed.content_items)
        self.assertTrue(all(item.source == "google_news" for item in refreshed.content_items))

    def test_keyword_trend_uses_cumulative_newsnow_curve(self) -> None:
        query = f"keyword-{uuid4().hex[:8]}"
        class EmptyInlineProvider:
            name = "empty-inline"

            def fetch_github_history(self, target_ref: str):
                raise AssertionError(f"unexpected github history request for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise AssertionError(f"unexpected github content request for {target_ref}")

            def fetch_newsnow_snapshot(self, keyword_query: str):
                return ([], [])

            def fetch_google_news_archive(self, keyword_query: str):
                return []

            def fetch_direct_rss_archive(self, keyword_query: str):
                return []

            def fetch_gdelt_archive(self, keyword_query: str):
                return []

        with patch("app.services.search.get_data_provider", return_value=EmptyInlineProvider()):
            initial = search_keyword(
                db=self.db,
                background_tasks=BackgroundTasks(),
                query=query,
                period="all",
            )

        start_day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=2)
        raw_values = [2.0, 3.0, 4.0]
        for offset, value in enumerate(raw_values):
            self.db.add(
                TrendPoint(
                    keyword_id=initial.keyword.id,
                    source="newsnow",
                    metric="hot_hit_count",
                    source_type="snapshot",
                    bucket_granularity="day",
                    bucket_start=start_day + timedelta(days=offset),
                    value=value,
                    raw_json=None,
                )
            )
        self.db.commit()

        refreshed = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="all",
        )

        newsnow_series = next(
            series for series in refreshed.trend.series if series.source == "newsnow" and series.metric == "hot_hit_count"
        )
        self.assertEqual([point.value for point in newsnow_series.points], [2.0, 5.0, 9.0])

    def test_keyword_search_derives_history_from_newsnow_content_timeline(self) -> None:
        query = f"timeline-{uuid4().hex[:8]}"
        initial = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="all",
        )
        job = BackfillJob(keyword_id=initial.keyword.id, status="pending")
        self.db.add(job)
        self.db.flush()
        self.db.add(
            BackfillJobTask(
                job_id=job.id,
                source="newsnow",
                task_type="snapshot",
                status="pending",
            )
        )
        self.db.commit()

        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        class TimelineProvider:
            name = "timeline"

            def fetch_github_history(self, target_ref: str):
                raise AssertionError(f"unexpected github history request for {target_ref}")

            def fetch_github_content(self, target_ref: str):
                raise AssertionError(f"unexpected github content request for {target_ref}")

            def fetch_newsnow_snapshot(self, keyword_query: str):
                self_query = keyword_query
                return (
                    [
                        TrendPointInput(
                            source="newsnow",
                            metric="hot_hit_count",
                            source_type="snapshot",
                            bucket_granularity="day",
                            bucket_start=today,
                            value=4.0,
                            raw_json=f'{{"query":"{self_query}"}}',
                        ),
                        TrendPointInput(
                            source="newsnow",
                            metric="platform_count",
                            source_type="snapshot",
                            bucket_granularity="day",
                            bucket_start=today,
                            value=2.0,
                            raw_json=f'{{"query":"{self_query}"}}',
                        ),
                    ],
                    [
                        ContentItemInput(
                            source="newsnow",
                            source_type="snapshot",
                            external_key=f"{self_query}:1",
                            title=f"{self_query} item 1",
                            url="https://example.com/1",
                            summary="first",
                            author="provider",
                            published_at=today - timedelta(days=2, hours=-2),
                            meta_json="{}",
                        ),
                        ContentItemInput(
                            source="newsnow",
                            source_type="snapshot",
                            external_key=f"{self_query}:2",
                            title=f"{self_query} item 2",
                            url="https://example.com/2",
                            summary="second",
                            author="provider",
                            published_at=today - timedelta(days=1, hours=-3),
                            meta_json="{}",
                        ),
                        ContentItemInput(
                            source="newsnow",
                            source_type="snapshot",
                            external_key=f"{self_query}:3",
                            title=f"{self_query} item 3",
                            url="https://example.com/3",
                            summary="third",
                            author="provider",
                            published_at=today - timedelta(days=1, hours=-6),
                            meta_json="{}",
                        ),
                        ContentItemInput(
                            source="newsnow",
                            source_type="snapshot",
                            external_key=f"{self_query}:4",
                            title=f"{self_query} item 4",
                            url="https://example.com/4",
                            summary="fourth",
                            author="provider",
                            published_at=today,
                            meta_json="{}",
                        ),
                    ],
                )

            def fetch_google_news_archive(self, keyword_query: str):
                self_query = keyword_query
                return [
                    ContentItemInput(
                        source="google_news",
                        source_type="archive",
                        external_key=f"{self_query}:archive:1",
                        title=f"{self_query} archive item",
                        url="https://example.com/archive/1",
                        summary="archive",
                        author="provider",
                        published_at=today - timedelta(days=3, hours=-1),
                        meta_json="{}",
                    )
                ]

        with patch("app.services.backfill.get_data_provider", return_value=TimelineProvider()):
            run_backfill_job(job.id)

        self.db.close()
        self.db = SessionLocal()

        refreshed = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="all",
        )

        history_series = next(
            series
            for series in refreshed.trend.series
            if series.source == "keyword_history"
            and series.metric == "matched_item_count"
            and series.source_type == "timeline"
        )
        self.assertEqual([point.value for point in history_series.points], [1.0, 1.0, 2.0, 1.0])
        self.assertFalse(any(series.source == "newsnow" and series.metric == "hot_hit_count" for series in refreshed.trend.series))

    def test_track_toggle_round_trip(self) -> None:
        query = f"keyword-{uuid4().hex[:8]}"
        payload = search_keyword(
            db=self.db,
            background_tasks=BackgroundTasks(),
            query=query,
            period="30d",
        )

        tracked = set_track_state(self.db, payload.keyword.id, tracked=True)
        self.assertTrue(tracked.is_tracked)

        untracked = set_track_state(self.db, payload.keyword.id, tracked=False)
        self.assertFalse(untracked.is_tracked)

    def test_collector_refreshes_tracked_keywords(self) -> None:
        query = f"tracked-{uuid4().hex[:8]}"
        tracked = ensure_tracked(query)
        self.assertTrue(tracked.is_tracked)

        tracked_keywords = list_tracked_keywords()
        self.assertTrue(any(item.id == tracked.id for item in tracked_keywords))

        refreshed = refresh_keyword(query, run_backfill_now=True)
        self.assertEqual(refreshed.keyword.id, tracked.id)

        collected = collect_tracked_keywords()
        self.assertTrue(any(item.keyword.id == tracked.id for item in collected))

    def test_management_lists_keywords_and_collect_runs(self) -> None:
        query = f"owner-{uuid4().hex[:8]}/repo-{uuid4().hex[:8]}"
        payload = refresh_keyword(query, run_backfill_now=True)

        keywords = list_keywords()
        self.assertTrue(any(item.id == payload.keyword.id for item in keywords))

        tracked_only_keywords = list_keywords(tracked_only=True)
        self.assertFalse(any(item.id == payload.keyword.id for item in tracked_only_keywords))

        runs = list_collect_runs(limit=20)
        self.assertTrue(any(run.keyword_id == payload.keyword.id for run in runs))

    def test_scheduler_run_once_updates_state(self) -> None:
        query = f"scheduler-{uuid4().hex[:8]}"
        ensure_tracked(query)

        def fake_job_runner(**_: object):
            return type(
                "FakeCollectResponse",
                (),
                {
                    "triggered_count": 1,
                    "results": [],
                },
            )()

        scheduler = CollectionScheduler(
            job_runner=fake_job_runner,
            enabled=True,
            interval_seconds=60,
            initial_delay_seconds=0,
            period="30d",
            run_backfill_now=True,
        )

        response = scheduler.run_once()
        snapshot = scheduler.snapshot()

        self.assertEqual(response.triggered_count, 1)
        self.assertEqual(snapshot.last_status, "success")
        self.assertEqual(snapshot.last_triggered_count, 1)
        self.assertEqual(snapshot.iteration_count, 1)


if __name__ == "__main__":
    unittest.main()
