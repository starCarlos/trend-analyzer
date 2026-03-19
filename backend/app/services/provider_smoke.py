from __future__ import annotations

from typing import Callable

from app.schemas import ProviderSmokePayload, ProviderSmokeSearchPayload
from app.services.collector import refresh_keyword
from app.services.provider_diagnostics import get_provider_status
from app.services.provider_registry import SMOKE_BLOCKING_PROVIDER_SOURCES, get_online_provider_spec
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
        and any(
            probe.status != "success"
            for probe in _iter_provider_probes(provider_verify, SMOKE_BLOCKING_PROVIDER_SOURCES)
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
    blocking_issues = _iter_provider_issues(provider_verify, SMOKE_BLOCKING_PROVIDER_SOURCES)
    archive_issues = _iter_provider_issues(provider_verify)

    if search.status == "success":
        if blocking_issues:
            return "核心实时源探测仍有失败或跳过，但本轮已强制执行端到端搜索。"
        if archive_issues:
            return "核心实时源探测和端到端搜索已执行；补充历史源仍有失败或跳过，但默认搜索链路可用。"
        return "预检、在线探测和端到端搜索都已执行，当前 provider 冒烟通过。"
    if search.status == "failed":
        return "预检和在线探测已执行，但端到端搜索失败。"
    probes = _iter_provider_probes(provider_verify)
    if probes and all(probe.status == "success" for probe in probes):
        return "在线探测成功，但本轮按默认策略没有执行真实搜索。"
    if blocking_issues:
        return "核心实时源在线探测未全部成功，端到端搜索已按默认策略跳过。"
    return "补充历史源在线探测仍有失败或跳过，但这不会阻塞默认搜索。"


def _build_next_steps(provider_verify, search: ProviderSmokeSearchPayload, force_search: bool) -> list[str]:
    steps: list[str] = []
    blocking_issues = _iter_provider_issues(provider_verify, SMOKE_BLOCKING_PROVIDER_SOURCES)
    archive_issues = _iter_provider_issues(provider_verify)

    if blocking_issues:
        steps.append(f"先处理 {_format_probe_labels(blocking_issues)} 在线探测失败或跳过，再做真实联调。")
    if archive_issues:
        steps.append(
            f"{_format_probe_labels(archive_issues)} 在线探测失败或跳过；这不会阻塞默认搜索，但会影响补充历史源完整性。"
        )
    if search.status == "skipped" and not force_search:
        steps.append("如果你仍想强制验证真实搜索，重新运行 provider-smoke 并开启 force_search。")
    if search.status == "failed":
        steps.append("查看 search.message 和 collect_runs 日志，定位真实 provider 失败点。")
    if search.status == "success":
        steps.append("接下来可在浏览器打开 /tracked 和搜索页，做人工联调验收。")

    if not steps:
        steps.append("当前 smoke 输出没有额外动作项。")

    return steps


def _iter_provider_probes(provider_verify, sources: tuple[str, ...] | None = None) -> list[object]:
    providers = getattr(provider_verify, "providers", None) or []
    if sources is None:
        return list(providers)
    source_set = set(sources)
    return [probe for probe in providers if probe.source in source_set]


def _iter_provider_issues(provider_verify, sources: tuple[str, ...] | None = None) -> list[object]:
    if sources is None:
        source_set = set(SMOKE_BLOCKING_PROVIDER_SOURCES)
        return [probe for probe in _iter_provider_probes(provider_verify) if probe.status != "success" and probe.source not in source_set]
    return [probe for probe in _iter_provider_probes(provider_verify, sources) if probe.status != "success"]


def _format_probe_labels(probes: list[object]) -> str:
    labels: list[str] = []
    for probe in probes:
        spec = get_online_provider_spec(probe.source)
        label = spec.label if spec else probe.source
        if label not in labels:
            labels.append(label)
    return "、".join(labels)
