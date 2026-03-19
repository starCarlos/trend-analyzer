from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Callable
from urllib import error, parse, request

from app.config import Settings, get_settings
from app.schemas import ProviderProbePayload, ProviderVerifyPayload
from app.services.direct_rss_catalog import iter_direct_rss_feeds
from app.services.provider_diagnostics import get_provider_status
from app.services.provider_registry import iter_online_provider_specs
from app.services.providers import ATOM_NAMESPACE, GDELT_DOC_API_URL
from app.services.provider_urls import build_newsnow_source_endpoint, iter_newsnow_source_endpoints, newsnow_request_headers


RequestJson = Callable[[str, dict[str, str]], tuple[object, dict[str, str]]]
RequestText = Callable[[str, dict[str, str]], tuple[str, dict[str, str]]]
ALLOWED_PROBE_MODES = {"current", "real"}
NEWSNOW_RETRY_ATTEMPTS = 2
GOOGLE_NEWS_PROBE_QUERY = '"openclaw" when:7d'
GDELT_PROBE_QUERY = "openclaw"

def verify_provider_connectivity(
    *,
    settings: Settings | None = None,
    probe_mode: str = "real",
    request_json: RequestJson | None = None,
    request_text: RequestText | None = None,
) -> ProviderVerifyPayload:
    settings = settings or get_settings()
    normalized_probe_mode = probe_mode.strip().lower()
    if normalized_probe_mode not in ALLOWED_PROBE_MODES:
        raise ValueError("probe_mode must be one of: current, real")

    provider_status = get_provider_status(settings)
    effective_mode = provider_status.resolved_provider if normalized_probe_mode == "current" else "real"

    if effective_mode == "mock":
        mock_messages = {
            "github": "Mock 模式下不会探测 GitHub 真实网络连通性。",
            "newsnow": "Mock 模式下不会探测 NewsNow 真实网络连通性。",
            "google_news": "Mock 模式下不会探测 Google News 真实网络连通性。",
            "direct_rss": "Mock 模式下不会探测 Direct RSS 真实网络连通性。",
            "gdelt": "Mock 模式下不会探测 GDELT 真实网络连通性。",
        }
        return ProviderVerifyPayload(
            probe_mode=normalized_probe_mode,
            requested_mode=provider_status.requested_mode,
            effective_mode=effective_mode,
            summary="当前模式是 mock，未执行任何真实网络探测。",
            providers=[
                ProviderProbePayload(
                    source=spec.source,
                    attempted_provider="mock",
                    status="skipped",
                    endpoint=None,
                    message=mock_messages[spec.source],
                )
                for spec in iter_online_provider_specs()
            ],
        )

    client = request_json or _ProbeHttpClient(settings).request_json
    text_client = request_text or _ProbeHttpClient(settings).request_text
    checks_by_source = {provider.source: provider for provider in provider_status.providers}
    verify_handlers = {
        "github": lambda check: _verify_github(settings, check, client),
        "newsnow": lambda check: _verify_newsnow(settings, check, client),
        "google_news": lambda check: _verify_google_news(settings, check, text_client),
        "direct_rss": lambda check: _verify_direct_rss(settings, check, text_client),
        "gdelt": lambda check: _verify_gdelt(settings, check, text_client),
    }
    probes = [verify_handlers[spec.source](checks_by_source.get(spec.source)) for spec in iter_online_provider_specs()]

    return ProviderVerifyPayload(
        probe_mode=normalized_probe_mode,
        requested_mode=provider_status.requested_mode,
        effective_mode=effective_mode,
        summary=_build_summary(normalized_probe_mode, probes),
        providers=probes,
    )


class _ProbeHttpClient:
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
        except error.HTTPError as exc:  # pragma: no cover - depends on network
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {detail[:200]}") from exc
        except error.URLError as exc:  # pragma: no cover - depends on network
            raise RuntimeError(f"Network error: {exc.reason}") from exc

    def request_text(self, url: str, headers: dict[str, str]) -> tuple[str, dict[str, str]]:
        req = request.Request(url, headers=headers)
        try:
            with self.opener.open(req, timeout=self.settings.request_timeout_seconds) as response:
                payload = response.read().decode("utf-8", errors="ignore")
                response_headers = {key: value for key, value in response.info().items()}
                return payload, response_headers
        except error.HTTPError as exc:  # pragma: no cover - depends on network
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {detail[:200]}") from exc
        except error.URLError as exc:  # pragma: no cover - depends on network
            raise RuntimeError(f"Network error: {exc.reason}") from exc


def _verify_github(
    settings: Settings,
    provider_check,
    request_json: RequestJson,
) -> ProviderProbePayload:
    endpoint = f"{settings.github_api_base_url.rstrip('/')}/rate_limit"
    if not provider_check.can_use_real_provider:
        return ProviderProbePayload(
            source="github",
            attempted_provider="real",
            status="skipped",
            endpoint=endpoint,
            message="跳过 GitHub 在线探测，因为本地配置不完整。",
        )

    headers = {
        "User-Agent": "TrendScope/0.1",
        "Accept": "application/json",
    }
    if settings.github_token.strip():
        headers["Authorization"] = f"Bearer {settings.github_token}"

    try:
        payload, _ = request_json(endpoint, headers)
    except Exception as exc:
        return ProviderProbePayload(
            source="github",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message=f"GitHub 在线探测失败: {exc}",
        )

    if not isinstance(payload, dict):
        return ProviderProbePayload(
            source="github",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message="GitHub 返回内容不是预期的 JSON object。",
        )

    rate = payload.get("rate") if isinstance(payload.get("rate"), dict) else {}
    remaining = rate.get("remaining")
    limit = rate.get("limit")
    return ProviderProbePayload(
        source="github",
        attempted_provider="real",
        status="success",
        endpoint=endpoint,
        message=f"GitHub 在线探测成功。rate limit remaining={remaining}, limit={limit}.",
    )


def _verify_newsnow(
    settings: Settings,
    provider_check,
    request_json: RequestJson,
) -> ProviderProbePayload:
    source_ids = [item.strip() for item in settings.newsnow_source_ids.split(",") if item.strip()]
    source_id = source_ids[0] if source_ids else "unknown"
    endpoint = build_newsnow_source_endpoint(settings.newsnow_base_url, source_id)
    if not provider_check.can_use_real_provider:
        return ProviderProbePayload(
            source="newsnow",
            attempted_provider="real",
            status="skipped",
            endpoint=endpoint if settings.newsnow_base_url.strip() else None,
            message="跳过 NewsNow 在线探测，因为本地配置不完整。",
        )

    errors: list[str] = []
    for candidate in iter_newsnow_source_endpoints(settings.newsnow_base_url, source_id):
        try:
            payload, _ = _request_newsnow_with_retry(candidate, request_json)
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")
            continue

        if not isinstance(payload, dict):
            errors.append(f"{candidate}: NewsNow 返回内容不是预期的 JSON object。")
            continue

        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        return ProviderProbePayload(
            source="newsnow",
            attempted_provider="real",
            status="success",
            endpoint=candidate,
            message=f"NewsNow 在线探测成功。source_id={source_id}, items={len(items)}.",
        )

    error_message = "；".join(errors) if errors else "没有可用的 NewsNow 探测 endpoint。"
    return ProviderProbePayload(
        source="newsnow",
        attempted_provider="real",
        status="failed",
        endpoint=endpoint,
        message=f"NewsNow 在线探测失败: {error_message}",
    )


def _verify_google_news(
    settings: Settings,
    provider_check,
    request_text: RequestText,
) -> ProviderProbePayload:
    endpoint = _build_google_news_probe_url()
    if provider_check is None or not provider_check.can_use_real_provider:
        return ProviderProbePayload(
            source="google_news",
            attempted_provider="real",
            status="skipped",
            endpoint=endpoint if settings.google_news_enabled else None,
            message="跳过 Google News 在线探测，因为本地配置不完整。",
        )

    try:
        xml_text, _ = request_text(
            endpoint,
            {
                "User-Agent": "TrendScope/0.1",
                "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
            },
        )
    except Exception as exc:
        return ProviderProbePayload(
            source="google_news",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message=f"Google News 在线探测失败: {exc}",
        )

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return ProviderProbePayload(
            source="google_news",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message=f"Google News RSS 解析失败: {exc}",
        )

    items = root.findall("./channel/item")
    return ProviderProbePayload(
        source="google_news",
        attempted_provider="real",
        status="success",
        endpoint=endpoint,
        message=f"Google News 在线探测成功。items={len(items)}.",
    )


def _verify_gdelt(
    settings: Settings,
    provider_check,
    request_text: RequestText,
) -> ProviderProbePayload:
    endpoint = _build_gdelt_probe_url()
    if provider_check is None or not provider_check.can_use_real_provider:
        return ProviderProbePayload(
            source="gdelt",
            attempted_provider="real",
            status="skipped",
            endpoint=endpoint if settings.gdelt_enabled else None,
            message="跳过 GDELT 在线探测，因为本地配置不完整。",
        )

    try:
        raw_text, _ = request_text(
            endpoint,
            {
                "User-Agent": "TrendScope/0.1",
                "Accept": "application/json,text/plain,*/*",
            },
        )
    except Exception as exc:
        return ProviderProbePayload(
            source="gdelt",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message=f"GDELT 在线探测失败: {exc}",
        )

    stripped = raw_text.lstrip()
    if stripped.startswith("Please limit requests"):
        return ProviderProbePayload(
            source="gdelt",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message=f"GDELT 在线探测失败: {stripped[:200]}",
        )

    try:
        payload = json.loads(raw_text)
    except ValueError as exc:
        return ProviderProbePayload(
            source="gdelt",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message=f"GDELT 返回内容不是合法 JSON: {exc}",
        )

    if not isinstance(payload, dict):
        return ProviderProbePayload(
            source="gdelt",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message=f"GDELT 返回内容不是预期的 JSON object，而是 {type(payload).__name__}。",
        )

    articles = payload.get("articles") if isinstance(payload.get("articles"), list) else []
    return ProviderProbePayload(
        source="gdelt",
        attempted_provider="real",
        status="success",
        endpoint=endpoint,
        message=f"GDELT 在线探测成功。articles={len(articles)}.",
    )


def _verify_direct_rss(
    settings: Settings,
    provider_check,
    request_text: RequestText,
) -> ProviderProbePayload:
    endpoint = _build_direct_rss_probe_url(settings)
    if provider_check is None or not provider_check.can_use_real_provider:
        return ProviderProbePayload(
            source="direct_rss",
            attempted_provider="real",
            status="skipped",
            endpoint=endpoint if settings.direct_rss_enabled else None,
            message="跳过 Direct RSS 在线探测，因为本地配置不完整。",
        )

    try:
        xml_text, _ = request_text(
            endpoint,
            {
                "User-Agent": "TrendScope/0.1",
                "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
            },
        )
    except Exception as exc:
        return ProviderProbePayload(
            source="direct_rss",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message=f"Direct RSS 在线探测失败: {exc}",
        )

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return ProviderProbePayload(
            source="direct_rss",
            attempted_provider="real",
            status="failed",
            endpoint=endpoint,
            message=f"Direct RSS 解析失败: {exc}",
        )

    item_count = len(root.findall("./channel/item"))
    if item_count == 0 and root.tag.endswith("feed"):
        item_count = len(root.findall("atom:entry", ATOM_NAMESPACE))

    return ProviderProbePayload(
        source="direct_rss",
        attempted_provider="real",
        status="success",
        endpoint=endpoint,
        message=f"Direct RSS 在线探测成功。items={item_count}.",
    )


def _request_newsnow_with_retry(
    url: str,
    request_json: RequestJson,
) -> tuple[object, dict[str, str]]:
    last_exc: Exception | None = None
    for attempt in range(NEWSNOW_RETRY_ATTEMPTS):
        try:
            return request_json(url, newsnow_request_headers())
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < NEWSNOW_RETRY_ATTEMPTS and _is_retryable_newsnow_probe_error(exc):
                continue
            if attempt > 0 and _is_retryable_newsnow_probe_error(exc):
                raise RuntimeError(f"{exc} (after {attempt + 1} attempts)") from exc
            raise
    raise RuntimeError(f"NewsNow probe exhausted retries for {url}: {last_exc}")


def _is_retryable_newsnow_probe_error(exc: Exception) -> bool:
    message = str(exc).casefold()
    retryable_tokens = (
        "http 500",
        "http 502",
        "http 503",
        "http 504",
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


def _build_google_news_probe_url() -> str:
    encoded_query = parse.quote_plus(GOOGLE_NEWS_PROBE_QUERY)
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US%3Aen"


def _build_gdelt_probe_url() -> str:
    params = {
        "query": f'"{GDELT_PROBE_QUERY}"',
        "mode": "ArtList",
        "format": "json",
        "sort": "datedesc",
        "maxrecords": "1",
        "timespan": "7d",
    }
    return f"{GDELT_DOC_API_URL}?{parse.urlencode(params)}"


def _build_direct_rss_probe_url(settings: Settings) -> str:
    feeds = iter_direct_rss_feeds(settings.direct_rss_extra_feeds)
    return feeds[0].url if feeds else "https://example.com/direct-rss-unconfigured"


def _build_summary(
    probe_mode: str,
    probes: list[ProviderProbePayload],
) -> str:
    statuses = {probe.status for probe in probes}
    succeeded_sources = [probe.source for probe in probes if probe.status == "success"]
    if statuses == {"success"}:
        return f"{probe_mode} 模式在线探测成功，{len(succeeded_sources)} 个数据源都已返回响应。"
    if "failed" in statuses:
        return f"{probe_mode} 模式在线探测已执行，但至少有一个数据源失败。"
    if statuses == {"skipped"}:
        return f"{probe_mode} 模式在线探测被跳过，本地配置尚未满足真实请求条件。"
    return f"{probe_mode} 模式在线探测已完成，结果包含 success / skipped 混合状态。"
