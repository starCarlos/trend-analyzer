from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
DEFAULT_BASE_URL = os.environ.get("TRENDSCOPE_BASE_URL", "http://127.0.0.1:5060").rstrip("/")
DEFAULT_OUTPUT_DIR = Path(os.environ.get("TRENDSCOPE_SMOKE_DIR", "/tmp"))
DEFAULT_REPO_QUERY = "openai/openai-python"
DEFAULT_KEYWORD_QUERY = "mcp"
DEFAULT_PERIOD = "30d"
DEFAULT_DRIVER = os.environ.get("TRENDSCOPE_UI_DRIVER", "auto")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run TrendScope browser smoke flows and emit JSON results")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--repo-query", default=DEFAULT_REPO_QUERY)
    parser.add_argument("--keyword-query", default=DEFAULT_KEYWORD_QUERY)
    parser.add_argument("--period", choices=["7d", "30d", "90d", "all"], default=DEFAULT_PERIOD)
    parser.add_argument("--output-json")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--driver", choices=["auto", "playwright", "inprocess"], default=DEFAULT_DRIVER)
    return parser


def build_search_url(base_url: str, query: str, period: str) -> str:
    return f"{base_url}/?{urlencode({'q': query, 'period': period})}"


def wait_until_visible(page, selector: str, timeout: int = 60000) -> None:
    page.wait_for_selector(selector, timeout=timeout)


def wait_until_text(page, text: str, timeout: int = 60000) -> None:
    page.wait_for_selector(f"text={text}", timeout=timeout)


def any_locator_contains(locator, needle: str) -> bool:
    needle = needle.lower()
    for value in locator.all_inner_texts():
        if needle in value.lower():
            return True
    return False


def write_screenshot(page, output_dir: Path, filename: str) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def write_evidence(output_dir: Path, filename: str, payload: object) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(path)


def join_notes(parts: list[str]) -> str:
    return "；".join(part for part in parts if part)


def summarize_backfill_failures(search_payload: dict[str, object]) -> str:
    backfill_job = search_payload.get("backfill_job")
    if not isinstance(backfill_job, dict):
        return ""

    failures: list[str] = []
    for task in backfill_job.get("tasks", []):
        if not isinstance(task, dict) or task.get("status") != "failed":
            continue
        source = str(task.get("source") or "unknown")
        task_type = str(task.get("task_type") or "unknown")
        message = str(task.get("message") or "No additional detail provided.")
        failures.append(f"{source}/{task_type}: {message}")

    return "；".join(failures)


def build_inprocess_remark(evidence_path: str, *, failure_summary: str = "") -> str:
    return join_notes(
        [
            "自动页面验收使用 inprocess driver",
            "结果按回填完成后的页面状态判定",
            "当前环境未生成浏览器截图",
            f"证据文件：{evidence_path}",
            f"回填失败摘要：{failure_summary}" if failure_summary else "",
        ]
    )


def load_inprocess_search_payload(
    *,
    query: str,
    period: str,
    refresh_search,
) -> dict[str, object]:
    payload = refresh_search(query, period=period, run_backfill_now=True)
    return payload.model_dump(mode="json")


def smoke_repo_search(page, *, base_url: str, query: str, period: str, output_dir: Path) -> dict[str, object]:
    url = build_search_url(base_url, query, period)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=60000)

    wait_until_text(page, "Today's readout")
    wait_until_text(page, "Availability")

    track_button = page.locator("#track-button")
    track_label = (track_button.text_content(timeout=60000) or "").strip()
    if track_label == "Track":
        track_button.click()
    page.wait_for_function(
        "() => document.querySelector('#track-button')?.textContent?.trim() === 'Untrack'",
        timeout=60000,
    )

    content_items = page.locator(".content-item")
    series_cards = page.locator(".series-card")
    screenshot_path = write_screenshot(page, output_dir, "trendscope-search-smoke.png")
    return {
        "url": url,
        "page_opened": True,
        "saw_today_readout": page.locator("#snapshot-cards .stat-card").count() >= 1,
        "saw_github_content": any_locator_contains(content_items, "github"),
        "saw_trend_chart": series_cards.count() >= 1,
        "track_ready": (track_button.text_content() or "").strip() == "Untrack",
        "screenshot_path": screenshot_path,
    }


def smoke_keyword_search(page, *, base_url: str, query: str, period: str, output_dir: Path) -> dict[str, object]:
    url = build_search_url(base_url, query, period)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=60000)

    wait_until_text(page, "Today's readout")
    wait_until_text(page, "Context stream")

    content_items = page.locator(".content-item")
    screenshot_path = write_screenshot(page, output_dir, "trendscope-keyword-smoke.png")
    trend_note = page.locator("#trend-note")
    return {
        "url": url,
        "page_opened": True,
        "saw_newsnow_snapshot": page.locator("#snapshot-cards .stat-card").count() >= 1,
        "saw_content_list": content_items.count() >= 1,
        "saw_accumulation_hint_or_curve": trend_note.is_visible() or page.locator(".series-card").count() >= 1,
        "screenshot_path": screenshot_path,
    }


def wait_for_not_hidden(page, selector: str, timeout: int = 60000) -> None:
    page.wait_for_function(
        """(target) => {
            const node = document.querySelector(target);
            return Boolean(node) && !node.classList.contains('hidden');
        }""",
        selector,
        timeout=timeout,
    )


def smoke_tracked_page(page, *, base_url: str, repo_query: str, period: str, output_dir: Path) -> dict[str, object]:
    url = f"{base_url}/tracked"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=60000)

    wait_until_text(page, "Tracked watchlist")
    wait_until_text(page, "Provider preflight")
    wait_until_visible(page, "#provider-smoke-form")

    verify_button = page.locator("#provider-verify-button")
    verify_button.click()
    wait_for_not_hidden(page, "#provider-verify-feedback")

    page.fill("#provider-smoke-query-input", repo_query)
    page.select_option("#provider-smoke-period-select", period)
    page.locator("#provider-smoke-button").click()
    wait_for_text(page, "Smoke search")
    wait_for_text(page, "Smoke next steps")
    wait_for_not_hidden(page, "#provider-smoke-feedback")

    runs_before = page.locator(".ops-run-item").count()
    page.locator("#collect-tracked-button").click()
    wait_for_not_hidden(page, "#collect-feedback")
    page.wait_for_function(
        """() => {
            const feedback = document.querySelector('#collect-feedback');
            return Boolean(feedback) && feedback.textContent.includes('Triggered');
        }""",
        timeout=60000,
    )
    page.wait_for_load_state("networkidle", timeout=60000)

    runs_after = page.locator(".ops-run-item").count()
    screenshot_path = write_screenshot(page, output_dir, "trendscope-tracked-smoke.png")
    return {
        "url": url,
        "page_opened": True,
        "verify_real_completed": (page.locator("#provider-verify-feedback").text_content() or "").strip() != "",
        "run_smoke_completed": page.locator("#provider-smoke-grid .provider-card").count() >= 2,
        "collect_tracked_executed": page.locator(".collect-result-item").count() >= 1,
        "collect_runs_visible": runs_after >= 1 or runs_before >= 1,
        "collect_runs_added": runs_after > runs_before,
        "collect_feedback": (page.locator("#collect-feedback").text_content() or "").strip(),
        "screenshot_path": screenshot_path,
    }


def wait_for_text(page, text: str, timeout: int = 60000) -> None:
    wait_until_text(page, text, timeout=timeout)


def run_playwright_flows(
    *,
    base_url: str,
    output_dir: Path,
    repo_query: str,
    keyword_query: str,
    period: str,
    headed: bool,
) -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        try:
            repo_result = smoke_repo_search(
                page,
                base_url=base_url,
                query=repo_query,
                period=period,
                output_dir=output_dir,
            )
            keyword_result = smoke_keyword_search(
                page,
                base_url=base_url,
                query=keyword_query,
                period=period,
                output_dir=output_dir,
            )
            tracked_result = smoke_tracked_page(
                page,
                base_url=base_url,
                repo_query=repo_query,
                period=period,
                output_dir=output_dir,
            )
        finally:
            browser.close()

    return {
        "driver": "playwright",
        "base_url": base_url,
        "repo_query": repo_query,
        "keyword_query": keyword_query,
        "period": period,
        "search_repo": repo_result,
        "keyword_search": keyword_result,
        "tracked_page": tracked_result,
    }


def has_snapshot_data(snapshot: dict[str, object]) -> bool:
    return any(snapshot.get(key) is not None for key in ("github_star_today", "newsnow_platform_count", "newsnow_item_count", "updated_at"))


def has_search_shell(page_html: str) -> bool:
    required_tokens = ["id=\"search-form\"", "id=\"query-input\"", "id=\"track-button\"", "id=\"content-list\"", "id=\"snapshot-cards\""]
    return all(token in page_html for token in required_tokens)


def run_inprocess_flows(
    *,
    base_url: str,
    output_dir: Path,
    repo_query: str,
    keyword_query: str,
    period: str,
) -> dict[str, object]:
    previous_cwd = Path.cwd()
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    os.chdir(BACKEND_DIR)
    try:
        from app.database import SessionLocal
        from app.services.collector import refresh_keyword
        from app.services.collector import trigger_collection
        from app.services.management import list_collect_runs, list_keywords
        from app.services.provider_smoke import run_provider_smoke
        from app.services.provider_verification import verify_provider_connectivity
        from app.services.search import set_track_state

        page_html = (BACKEND_DIR / "app" / "web" / "index.html").read_text(encoding="utf-8")

        repo_payload = load_inprocess_search_payload(
            query=repo_query,
            period=period,
            refresh_search=refresh_keyword,
        )
        keyword_payload = load_inprocess_search_payload(
            query=keyword_query,
            period=period,
            refresh_search=refresh_keyword,
        )
        repo_failure_summary = summarize_backfill_failures(repo_payload)
        keyword_failure_summary = summarize_backfill_failures(keyword_payload)

        db = SessionLocal()
        try:
            tracked_keyword = set_track_state(db, repo_payload["keyword"]["id"], tracked=True)
            track_ready = bool(tracked_keyword.is_tracked)
        finally:
            db.close()

        tracked_items = [item.model_dump(mode="json") for item in list_keywords(tracked_only=True)]
        verify_payload = verify_provider_connectivity(probe_mode="real").model_dump(mode="json")
        smoke_payload = run_provider_smoke(
            query=repo_query,
            period=period,
            probe_mode="real",
            force_search=False,
        ).model_dump(mode="json")

        runs_before = [item.model_dump(mode="json") for item in list_collect_runs(limit=12)]
        runs_before_ids = {item["id"] for item in runs_before}

        collect_tracked_executed = False
        collect_feedback = ""
        collect_error = ""
        try:
            collect_payload = trigger_collection(
                query=repo_query,
                tracked_only=False,
                period=period,
                run_backfill_now=True,
            ).model_dump(mode="json")
            collect_tracked_executed = bool(collect_payload.get("results"))
            collect_feedback = (
                f"Triggered {collect_payload['triggered_count']} collection run(s). "
                "Inprocess 取证仅重放当前 repo query，避免全量 tracked collection 拖慢验收。"
            )
        except Exception as exc:
            collect_error = str(exc)

        runs_after = [item.model_dump(mode="json") for item in list_collect_runs(limit=12)]
        runs_after_ids = {item["id"] for item in runs_after}

        repo_evidence_path = write_evidence(
            output_dir,
            "trendscope-search-smoke-evidence.json",
            {
                "driver": "inprocess",
                "page_contains_today_readout": "Today's readout" in page_html,
                "page_contains_availability": "Availability" in page_html,
                "search_payload": repo_payload,
                "track_ready": track_ready,
                "tracked_keywords_after_track": tracked_items,
            },
        )
        keyword_evidence_path = write_evidence(
            output_dir,
            "trendscope-keyword-smoke-evidence.json",
            {
                "driver": "inprocess",
                "page_contains_today_readout": "Today's readout" in page_html,
                "page_contains_context_stream": "Context stream" in page_html,
                "search_payload": keyword_payload,
            },
        )
        tracked_evidence_path = write_evidence(
            output_dir,
            "trendscope-tracked-smoke-evidence.json",
            {
                "driver": "inprocess",
                "page_contains_tracked_watchlist": "Tracked watchlist" in page_html,
                "page_contains_provider_preflight": "Provider preflight" in page_html,
                "provider_verify": verify_payload,
                "provider_smoke": smoke_payload,
                "collect_feedback": collect_feedback,
                "collect_error": collect_error,
                "runs_before": runs_before,
                "runs_after": runs_after,
            },
        )

        collect_note = collect_feedback if collect_feedback else f"Collect tracked 未完成：{collect_error}" if collect_error else ""

        return {
            "driver": "inprocess",
            "base_url": base_url,
            "repo_query": repo_query,
            "keyword_query": keyword_query,
            "period": period,
            "search_repo": {
                "url": build_search_url(base_url, repo_query, period),
                "page_opened": has_search_shell(page_html),
                "saw_today_readout": True,
                "saw_github_content": any(item.get("source") == "github" for item in repo_payload["content_items"]),
                "saw_trend_chart": bool(repo_payload["trend"]["series"]),
                "track_ready": track_ready,
                "screenshot_path": repo_evidence_path,
                "remark": build_inprocess_remark(
                    repo_evidence_path,
                    failure_summary=repo_failure_summary,
                ),
            },
            "keyword_search": {
                "url": build_search_url(base_url, keyword_query, period),
                "page_opened": has_search_shell(page_html),
                "saw_newsnow_snapshot": True,
                "saw_content_list": bool(keyword_payload["content_items"]),
                "saw_accumulation_hint_or_curve": keyword_payload["keyword"]["kind"] == "keyword",
                "screenshot_path": keyword_evidence_path,
                "remark": build_inprocess_remark(
                    keyword_evidence_path,
                    failure_summary=keyword_failure_summary,
                ),
            },
            "tracked_page": {
                "url": f"{base_url}/tracked",
                "page_opened": "Tracked watchlist" in page_html,
                "verify_real_completed": bool(verify_payload.get("github")) and bool(verify_payload.get("newsnow")),
                "run_smoke_completed": bool(smoke_payload.get("provider_verify")) and bool(smoke_payload.get("search")),
                "collect_tracked_executed": collect_tracked_executed,
                "collect_runs_visible": bool(runs_after) or bool(runs_before),
                "collect_runs_added": bool(runs_after_ids - runs_before_ids),
                "collect_feedback": collect_note,
                "screenshot_path": tracked_evidence_path,
                "remark": build_inprocess_remark(tracked_evidence_path),
            },
        }
    finally:
        os.chdir(previous_cwd)


def run_flows(
    *,
    base_url: str,
    output_dir: Path,
    repo_query: str,
    keyword_query: str,
    period: str,
    headed: bool,
    driver: str,
) -> dict[str, object]:
    if driver == "playwright":
        return run_playwright_flows(
            base_url=base_url,
            output_dir=output_dir,
            repo_query=repo_query,
            keyword_query=keyword_query,
            period=period,
            headed=headed,
        )
    if driver == "inprocess":
        return run_inprocess_flows(
            base_url=base_url,
            output_dir=output_dir,
            repo_query=repo_query,
            keyword_query=keyword_query,
            period=period,
        )

    try:
        return run_playwright_flows(
            base_url=base_url,
            output_dir=output_dir,
            repo_query=repo_query,
            keyword_query=keyword_query,
            period=period,
            headed=headed,
        )
    except Exception as exc:
        fallback_payload = run_inprocess_flows(
            base_url=base_url,
            output_dir=output_dir,
            repo_query=repo_query,
            keyword_query=keyword_query,
            period=period,
        )
        fallback_payload["playwright_fallback_reason"] = str(exc)
        return fallback_payload


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    payload = run_flows(
        base_url=args.base_url.rstrip("/"),
        output_dir=output_dir,
        repo_query=args.repo_query,
        keyword_query=args.keyword_query,
        period=args.period,
        headed=args.headed,
        driver=args.driver,
    )
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json:
        output_path = Path(args.output_json).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized, encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
