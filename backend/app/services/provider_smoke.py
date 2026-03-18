from __future__ import annotations

from typing import Callable

from app.schemas import ProviderSmokePayload, ProviderSmokeSearchPayload
from app.services.collector import refresh_keyword
from app.services.provider_diagnostics import get_provider_status
from app.services.provider_verification import verify_provider_connectivity


ProviderStatusLoader = Callable[[], object]
ProviderVerifyRunner = Callable[..., object]
SearchRunner = Callable[..., object]


def run_provider_smoke(
    *,
    query: str,
    period: str = "30d",
    probe_mode: str = "real",
    force_search: bool = False,
    provider_status_loader: ProviderStatusLoader = get_provider_status,
    provider_verify_runner: ProviderVerifyRunner = verify_provider_connectivity,
    search_runner: SearchRunner = refresh_keyword,
) -> ProviderSmokePayload:
    provider_status = provider_status_loader()
    provider_verify = provider_verify_runner(probe_mode=probe_mode)

    should_skip_search = (
        not force_search
        and (
            provider_verify.github.status != "success"
            or provider_verify.newsnow.status != "success"
        )
    )

    if should_skip_search:
        search = ProviderSmokeSearchPayload(
            query=query,
            period=period,
            status="skipped",
            message="在线探测没有全部成功，默认跳过真实搜索。需要强制执行时使用 force_search=true。",
        )
    else:
        try:
            payload = search_runner(query, period=period, run_backfill_now=True)
            search = ProviderSmokeSearchPayload(
                query=query,
                period=period,
                status="success",
                message="端到端搜索执行成功。",
                keyword_kind=payload.keyword.kind,
                normalized_query=payload.keyword.normalized_query,
                trend_series_count=len(payload.trend.series),
                content_item_count=len(payload.content_items),
                availability=payload.availability,
                backfill_status=payload.backfill_job.status if payload.backfill_job else "ready",
            )
        except Exception as exc:
            search = ProviderSmokeSearchPayload(
                query=query,
                period=period,
                status="failed",
                message=f"端到端搜索失败: {exc}",
            )

    return ProviderSmokePayload(
        query=query,
        period=period,
        probe_mode=probe_mode,
        force_search=force_search,
        summary=_build_summary(provider_verify, search),
        provider_status=provider_status,
        provider_verify=provider_verify,
        search=search,
        next_steps=_build_next_steps(provider_verify, search, force_search),
    )


def _build_summary(provider_verify, search: ProviderSmokeSearchPayload) -> str:
    if search.status == "success":
        return "预检、在线探测和端到端搜索都已执行，当前 provider 冒烟通过。"
    if search.status == "failed":
        return "预检和在线探测已执行，但端到端搜索失败。"
    if provider_verify.github.status == "success" and provider_verify.newsnow.status == "success":
        return "在线探测成功，但本轮按默认策略没有执行真实搜索。"
    return "在线探测未全部成功，端到端搜索已按默认策略跳过。"


def _build_next_steps(provider_verify, search: ProviderSmokeSearchPayload, force_search: bool) -> list[str]:
    steps: list[str] = []

    if provider_verify.github.status != "success":
        steps.append("先处理 GitHub 在线探测失败或跳过，再做真实联调。")
    if provider_verify.newsnow.status != "success":
        steps.append("先处理 NewsNow 在线探测失败或跳过，再做真实联调。")
    if search.status == "skipped" and not force_search:
        steps.append("如果你仍想强制验证真实搜索，重新运行 provider-smoke 并开启 force_search。")
    if search.status == "failed":
        steps.append("查看 search.message 和 collect_runs 日志，定位真实 provider 失败点。")
    if search.status == "success":
        steps.append("接下来可在浏览器打开 /tracked 和搜索页，做人工联调验收。")

    if not steps:
        steps.append("当前 smoke 输出没有额外动作项。")

    return steps
