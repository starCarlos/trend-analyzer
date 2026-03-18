from __future__ import annotations

from app.config import Settings, get_settings
from app.schemas import ProviderCheckPayload, ProviderStatusPayload
from app.services.provider_registry import iter_online_provider_specs


ALLOWED_PROVIDER_MODES = {"mock", "real", "auto"}


def get_provider_status(settings: Settings | None = None) -> ProviderStatusPayload:
    settings = settings or get_settings()
    requested_mode = settings.provider_mode.strip().lower()
    mode = requested_mode if requested_mode in ALLOWED_PROVIDER_MODES else "invalid"

    handlers = {
        "github": _diagnose_github,
        "newsnow": _diagnose_newsnow,
        "google_news": _diagnose_google_news,
        "gdelt": _diagnose_gdelt,
    }
    providers = [handlers[spec.source](settings, mode) for spec in iter_online_provider_specs()]

    return ProviderStatusPayload(
        requested_mode=requested_mode,
        resolved_provider=mode,
        summary=_build_summary(mode, providers),
        providers=providers,
    )


def _diagnose_github(settings: Settings, mode: str) -> ProviderCheckPayload:
    issues: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    if not settings.github_api_base_url.strip():
        issues.append("GITHUB_API_BASE_URL 为空。")
    if settings.github_history_max_pages <= 0:
        issues.append("GITHUB_HISTORY_MAX_PAGES 必须大于 0。")
    if settings.request_timeout_seconds <= 0:
        issues.append("REQUEST_TIMEOUT_SECONDS 必须大于 0。")
    if not settings.github_token.strip():
        warnings.append("GITHUB_TOKEN 为空，真实请求可用但更容易触发限流。")
    if settings.http_proxy.strip():
        notes.append("HTTP_PROXY 已配置，真实请求会经过代理。")

    return _build_check(
        source="github",
        mode=mode,
        can_use_real_provider=not issues,
        issues=issues,
        warnings=warnings,
        notes=notes,
        auto_ready_note="Auto 模式会优先请求真实 GitHub，失败后回退到 mock。",
        auto_fallback_note="Auto 模式下 GitHub 真实配置不完整，实际会回退到 mock。",
        mock_note="PROVIDER_MODE=mock，GitHub 不会发起真实网络请求。",
        ready_note="GitHub 真实配置在本地看起来可用，但当前还没有在线验证网络连通性。",
    )


def _diagnose_newsnow(settings: Settings, mode: str) -> ProviderCheckPayload:
    issues: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []
    source_ids = [item.strip() for item in settings.newsnow_source_ids.split(",") if item.strip()]

    if not settings.newsnow_base_url.strip():
        issues.append("NEWSNOW_BASE_URL 为空。")
    if not source_ids:
        issues.append("NEWSNOW_SOURCE_IDS 为空。")
    if settings.request_timeout_seconds <= 0:
        issues.append("REQUEST_TIMEOUT_SECONDS 必须大于 0。")
    if source_ids:
        notes.append(f"NEWSNOW_SOURCE_IDS 当前包含 {len(source_ids)} 个 source id。")
    if settings.http_proxy.strip():
        notes.append("HTTP_PROXY 已配置，真实请求会经过代理。")

    return _build_check(
        source="newsnow",
        mode=mode,
        can_use_real_provider=not issues,
        issues=issues,
        warnings=warnings,
        notes=notes,
        auto_ready_note="Auto 模式会优先请求真实 NewsNow，失败后回退到 mock。",
        auto_fallback_note="Auto 模式下 NewsNow 真实配置不完整，实际会回退到 mock。",
        mock_note="PROVIDER_MODE=mock，NewsNow 不会发起真实网络请求。",
        ready_note="NewsNow 真实配置在本地看起来可用，但当前还没有在线验证网络连通性。",
    )


def _diagnose_google_news(settings: Settings, mode: str) -> ProviderCheckPayload:
    issues: list[str] = []
    warnings: list[str] = []
    notes: list[str] = ["Google News RSS 无需额外 token。"]

    if not settings.google_news_enabled:
        issues.append("GOOGLE_NEWS_ENABLED=false。")
    if settings.google_news_max_items <= 0:
        issues.append("GOOGLE_NEWS_MAX_ITEMS 必须大于 0。")
    if settings.request_timeout_seconds <= 0:
        issues.append("REQUEST_TIMEOUT_SECONDS 必须大于 0。")
    if settings.http_proxy.strip():
        notes.append("HTTP_PROXY 已配置，真实请求会经过代理。")

    return _build_check(
        source="google_news",
        mode=mode,
        can_use_real_provider=not issues,
        issues=issues,
        warnings=warnings,
        notes=notes,
        auto_ready_note="Auto 模式会优先请求真实 Google News RSS，失败后回退到 mock。",
        auto_fallback_note="Auto 模式下 Google News 真实配置不完整，实际会回退到 mock。",
        mock_note="PROVIDER_MODE=mock，Google News 不会发起真实网络请求。",
        ready_note="Google News RSS 在本地看起来可用，但当前还没有在线验证网络连通性。",
    )


def _diagnose_gdelt(settings: Settings, mode: str) -> ProviderCheckPayload:
    issues: list[str] = []
    warnings: list[str] = []
    notes: list[str] = ["GDELT Doc API 有官方限流，建议请求间隔至少 5 秒。"]

    if not settings.gdelt_enabled:
        issues.append("GDELT_ENABLED=false。")
    if settings.gdelt_max_items <= 0:
        issues.append("GDELT_MAX_ITEMS 必须大于 0。")
    if settings.request_timeout_seconds <= 0:
        issues.append("REQUEST_TIMEOUT_SECONDS 必须大于 0。")
    if settings.http_proxy.strip():
        notes.append("HTTP_PROXY 已配置，真实请求会经过代理。")

    return _build_check(
        source="gdelt",
        mode=mode,
        can_use_real_provider=not issues,
        issues=issues,
        warnings=warnings,
        notes=notes,
        auto_ready_note="Auto 模式会优先请求真实 GDELT，失败后回退到 mock。",
        auto_fallback_note="Auto 模式下 GDELT 真实配置不完整，实际会回退到 mock。",
        mock_note="PROVIDER_MODE=mock，GDELT 不会发起真实网络请求。",
        ready_note="GDELT 在本地看起来可用，但当前还没有在线验证网络连通性。",
    )


def _build_check(
    *,
    source: str,
    mode: str,
    can_use_real_provider: bool,
    issues: list[str],
    warnings: list[str],
    notes: list[str],
    auto_ready_note: str,
    auto_fallback_note: str,
    mock_note: str,
    ready_note: str,
) -> ProviderCheckPayload:
    final_notes = list(warnings) + list(notes)

    if mode == "mock":
        final_notes.insert(0, mock_note)
        return ProviderCheckPayload(
            source=source,
            mode=mode,
            preferred_provider="mock",
            fallback_provider=None,
            status="mock_only",
            can_use_real_provider=can_use_real_provider,
            issues=issues,
            notes=final_notes,
        )

    if mode == "real":
        final_notes.insert(0, ready_note if can_use_real_provider else "真实模式已启用，但当前本地配置不完整。")
        return ProviderCheckPayload(
            source=source,
            mode=mode,
            preferred_provider="real",
            fallback_provider=None,
            status="warning" if can_use_real_provider and warnings else "ready" if can_use_real_provider else "misconfigured",
            can_use_real_provider=can_use_real_provider,
            issues=issues,
            notes=final_notes,
        )

    if mode == "auto":
        final_notes.insert(0, auto_ready_note if can_use_real_provider else auto_fallback_note)
        return ProviderCheckPayload(
            source=source,
            mode=mode,
            preferred_provider="real" if can_use_real_provider else "mock",
            fallback_provider="mock",
            status="warning" if can_use_real_provider and warnings else "ready" if can_use_real_provider else "fallback_only",
            can_use_real_provider=can_use_real_provider,
            issues=issues,
            notes=final_notes,
        )

    final_notes.insert(0, "PROVIDER_MODE 不是有效值，应为 mock、real 或 auto。")
    return ProviderCheckPayload(
        source=source,
        mode=mode,
        preferred_provider="mock",
        fallback_provider=None,
        status="invalid_mode",
        can_use_real_provider=False,
        issues=["PROVIDER_MODE 配置无效。"],
        notes=final_notes,
    )


def _build_summary(mode: str, checks: list[ProviderCheckPayload]) -> str:
    if mode == "mock":
        return "当前是 mock 模式，所有数据源都会使用本地假数据。"

    if mode == "real":
        if any(check.status == "misconfigured" for check in checks):
            return "当前是 real 模式，但至少有一个数据源的本地配置不完整。"
        return "当前是 real 模式，本地配置看起来可用，但网络连通性和真实返回结果尚未验证。"

    if mode == "auto":
        if any(check.status == "fallback_only" for check in checks):
            return "当前是 auto 模式，至少有一个数据源因配置不完整会直接回退到 mock。"
        return "当前是 auto 模式，会先尝试真实 provider，失败后回退到 mock。"

    return "当前 PROVIDER_MODE 不是有效值，后端 provider 选择结果不可信。"
