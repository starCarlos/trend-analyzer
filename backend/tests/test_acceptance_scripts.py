import subprocess
import sys
import unittest
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from local_acceptance import (  # noqa: E402
    build_local_probe_opener,
    build_result_payload,
    ensure_current_ui_python_has_playwright,
)
from run_real_provider_acceptance import (  # noqa: E402
    build_local_acceptance_command,
    describe_local_acceptance_result,
    parse_completed_json,
    should_run_local_ui,
    summarize_completed_run,
)
from ui_smoke_test import (  # noqa: E402
    build_inprocess_database_url,
    build_inprocess_remark,
    configure_inprocess_database,
    has_provider_probe_results,
    has_smoke_run_results,
    load_inprocess_search_payload,
    summarize_backfill_failures,
)
from update_real_provider_acceptance_record import (  # noqa: E402
    ROOT_DIR as RECORD_ROOT_DIR,
    command_markdown,
    summarize_exception,
    update_final_conclusion_section,
    update_prd_mapping_section,
    update_smoke_section,
    update_status_section,
    update_ui_sections,
    update_ui_failure_sections,
    update_verify_section,
)


TEMPLATE_PATH = ROOT_DIR / "docs" / "real-provider-acceptance-record-template.md"


class AcceptanceScriptTestCase(unittest.TestCase):
    def read_template(self) -> str:
        return TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_build_inprocess_database_url_uses_explicit_value_when_provided(self) -> None:
        self.assertEqual(
            build_inprocess_database_url("sqlite:////tmp/trendscope-explicit.db"),
            "sqlite:////tmp/trendscope-explicit.db",
        )

    def test_build_inprocess_database_url_defaults_to_temp_sqlite_file(self) -> None:
        database_url = build_inprocess_database_url()

        self.assertTrue(database_url.startswith("sqlite:///"))
        self.assertIn("trendscope-ui-smoke-", database_url)
        self.assertTrue(database_url.endswith(".db"))

    def test_configure_inprocess_database_sets_database_url(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            database_url = configure_inprocess_database("sqlite:////tmp/trendscope-isolated.db")
            self.assertEqual(database_url, "sqlite:////tmp/trendscope-isolated.db")
            self.assertEqual(os.environ["DATABASE_URL"], "sqlite:////tmp/trendscope-isolated.db")
            self.assertEqual(os.environ["APP_ENV"], "ui_smoke_inprocess")

    def test_command_markdown_uses_repo_relative_paths(self) -> None:
        command = [
            str(RECORD_ROOT_DIR / "backend" / ".venv" / "bin" / "python"),
            str(RECORD_ROOT_DIR / "scripts" / "local_acceptance.py"),
            "--base-url",
            "http://127.0.0.1:5081",
        ]

        rendered = command_markdown(command)

        self.assertIn("backend/.venv/bin/python", rendered)
        self.assertIn("scripts/local_acceptance.py", rendered)
        self.assertNotIn(str(RECORD_ROOT_DIR / "scripts" / "local_acceptance.py"), rendered)

    def test_update_prd_mapping_section_marks_pending_without_ui_payload(self) -> None:
        updated = update_prd_mapping_section(
            self.read_template(),
            repo_payload=None,
            keyword_payload=None,
            tracked_payload=None,
            smoke_ok=False,
            startup_result="待人工确认",
            startup_note="当前脚本不会自动清空数据库，只能证明现有环境可启动。",
            error_readability_result="待人工确认",
            error_readability_note="当前脚本只覆盖成功路径，失败场景仍需人工构造并确认错误提示可读。",
        )

        self.assertIn(
            "| GitHub 项目首次搜索能完成冷启动并看到历史图 | 待人工确认 | 未自动执行页面验收。；provider smoke 搜索未通过，需先修复 CLI 链路。 |",
            updated,
        )
        self.assertIn(
            "| 普通关键词首次搜索能看到 NewsNow 快照和内容列表 | 待人工确认 | 未自动执行页面验收。；provider smoke 搜索未通过，需先修复 CLI 链路。 |",
            updated,
        )

    def test_update_prd_mapping_section_marks_tracked_partial(self) -> None:
        tracked_payload = {
            "page_opened": True,
            "collect_tracked_executed": True,
            "collect_runs_added": False,
        }

        updated = update_prd_mapping_section(
            self.read_template(),
            repo_payload=None,
            keyword_payload=None,
            tracked_payload=tracked_payload,
            smoke_ok=True,
            startup_result="待人工确认",
            startup_note="当前脚本不会自动清空数据库，只能证明现有环境可启动。",
            error_readability_result="待人工确认",
            error_readability_note="当前脚本只覆盖成功路径，失败场景仍需人工构造并确认错误提示可读。",
        )

        self.assertIn(
            "| 加入追踪后，定时任务能持续写入新点位 | 部分通过 | 已自动触发 `Collect tracked`，但本次未观察到新增 collect runs；scheduler 持续写入仍需人工观察。 |",
            updated,
        )

    def test_update_prd_mapping_section_marks_ui_failure(self) -> None:
        updated = update_prd_mapping_section(
            self.read_template(),
            repo_payload=None,
            keyword_payload=None,
            tracked_payload=None,
            smoke_ok=True,
            startup_result="待人工确认",
            startup_note="当前脚本不会自动清空数据库，只能证明现有环境可启动。",
            error_readability_result="待人工确认",
            error_readability_note="当前脚本只覆盖成功路径，失败场景仍需人工构造并确认错误提示可读。",
            ui_error="BrowserType.launch failed",
        )

        self.assertIn(
            "| GitHub 项目首次搜索能完成冷启动并看到历史图 | 失败 | 页面验收执行失败：BrowserType.launch failed |",
            updated,
        )
        self.assertIn(
            "| 加入追踪后，定时任务能持续写入新点位 | 失败 | 页面验收执行失败：BrowserType.launch failed |",
            updated,
        )

    def test_update_prd_mapping_section_uses_automated_startup_and_error_results(self) -> None:
        updated = update_prd_mapping_section(
            self.read_template(),
            repo_payload=None,
            keyword_payload=None,
            tracked_payload=None,
            smoke_ok=True,
            startup_result="通过",
            startup_note="临时空库启动成功。",
            error_readability_result="部分通过",
            error_readability_note="已自动验证 provider 配置缺失和在线探测跳过文案可读。",
        )

        self.assertIn("| 可以从空库启动 | 通过 | 临时空库启动成功。 |", updated)
        self.assertIn(
            "| 搜索、回填、采集失败都有可读错误状态 | 部分通过 | 已自动验证 provider 配置缺失和在线探测跳过文案可读。 |",
            updated,
        )

    def test_update_final_conclusion_section_blocks_on_cli_failures(self) -> None:
        updated = update_final_conclusion_section(
            self.read_template(),
            status_ok=False,
            verify_ok=False,
            smoke_ok=False,
            repo_payload=None,
            keyword_payload=None,
            tracked_payload=None,
            run_ui=False,
            startup_result="待人工确认",
            error_readability_result="待人工确认",
        )

        self.assertIn("- 本次真实 provider 联调结果：`失败`", updated)
        self.assertIn("- 是否允许继续上线前步骤：`否`", updated)
        self.assertIn("- 阻塞项：Provider 预检未通过。；在线探测未通过。；Smoke 总览未通过。", updated)

    def test_update_final_conclusion_section_allows_progress_after_ui_success(self) -> None:
        repo_payload = {
            "page_opened": True,
            "saw_today_readout": True,
            "saw_github_content": True,
            "saw_trend_chart": True,
            "track_ready": True,
        }
        keyword_payload = {
            "page_opened": True,
            "saw_newsnow_snapshot": True,
            "saw_content_list": True,
            "saw_accumulation_hint_or_curve": True,
        }
        tracked_payload = {
            "page_opened": True,
            "collect_tracked_executed": True,
            "collect_runs_added": False,
        }

        updated = update_final_conclusion_section(
            self.read_template(),
            status_ok=True,
            verify_ok=True,
            smoke_ok=True,
            repo_payload=repo_payload,
            keyword_payload=keyword_payload,
            tracked_payload=tracked_payload,
            run_ui=True,
            startup_result="通过",
            error_readability_result="部分通过",
        )

        self.assertIn("- 本次真实 provider 联调结果：`部分通过`", updated)
        self.assertIn("- 是否允许继续上线前步骤：`是`", updated)
        self.assertIn("- 后续动作：scheduler 持续采集仍需人工观察。；失败场景可读性仍需人工构造验证。", updated)

    def test_update_final_conclusion_section_blocks_on_ui_execution_failure(self) -> None:
        updated = update_final_conclusion_section(
            self.read_template(),
            status_ok=True,
            verify_ok=True,
            smoke_ok=True,
            repo_payload=None,
            keyword_payload=None,
            tracked_payload=None,
            run_ui=True,
            startup_result="通过",
            error_readability_result="待人工确认",
            ui_error="BrowserType.launch failed",
        )

        self.assertIn("- 本次真实 provider 联调结果：`失败`", updated)
        self.assertIn("- 阻塞项：页面验收执行失败：BrowserType.launch failed", updated)

    def test_update_final_conclusion_section_blocks_on_startup_failure(self) -> None:
        updated = update_final_conclusion_section(
            self.read_template(),
            status_ok=True,
            verify_ok=True,
            smoke_ok=True,
            repo_payload=None,
            keyword_payload=None,
            tracked_payload=None,
            run_ui=False,
            startup_result="失败",
            error_readability_result="部分通过",
        )

        self.assertIn("- 本次真实 provider 联调结果：`失败`", updated)
        self.assertIn("- 阻塞项：空库启动验证未通过。", updated)

    def test_summarize_completed_run_prefers_acceptance_summary_line(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python", "scripts/local_acceptance.py"],
            returncode=0,
            stdout="\n".join(
                [
                    "[acceptance] Backend already healthy: env=local provider_mode=mock",
                    "[acceptance] Local acceptance passed",
                ]
            ),
            stderr="INFO: Finished server process [123]",
        )

        summary = summarize_completed_run(completed)

        self.assertEqual(summary, "[acceptance] Local acceptance passed")

    def test_parse_completed_json_returns_payload_dict(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python", "scripts/local_acceptance.py", "--json"],
            returncode=0,
            stdout='{"status":"passed","tests_ran":true}',
            stderr="",
        )

        payload = parse_completed_json(completed)

        self.assertEqual(payload, {"status": "passed", "tests_ran": True})

    def test_describe_local_acceptance_result_prefers_structured_fields(self) -> None:
        payload = {
            "tests_ran": True,
            "ui_ran": False,
            "backend_already_running": False,
            "backend_auto_started": True,
            "failure_message": "",
            "health": {
                "environment": "probe_blocked",
                "provider_mode": "unknown",
            },
        }

        description = describe_local_acceptance_result(payload, "fallback")

        self.assertEqual(
            description,
            "health.env=probe_blocked；provider_mode=unknown；tests=是；ui=否；backend_already_running=否；backend_auto_started=是",
        )

    def test_build_result_payload_reports_execution_flags(self) -> None:
        args = SimpleNamespace(
            base_url="http://127.0.0.1:5081",
            skip_tests=False,
            skip_ui=True,
        )

        payload = build_result_payload(
            args=args,
            backend_python="backend/.venv/bin/python",
            ui_python="backend/.venv/bin/python",
            status="passed",
            health={"environment": "local", "provider_mode": "mock"},
            failure_message="",
            backend_already_running=True,
            backend_auto_started=False,
            ui_smoke_payload=None,
        )

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["tests_ran"])
        self.assertFalse(payload["ui_ran"])
        self.assertTrue(payload["backend_already_running"])
        self.assertFalse(payload["backend_auto_started"])
        self.assertEqual(payload["health"]["provider_mode"], "mock")

    def test_build_local_probe_opener_bypasses_proxy_for_loopback(self) -> None:
        seen_args: list[tuple[object, ...]] = []

        def fake_build_opener(*handlers):
            seen_args.append(handlers)
            return object()

        with patch("local_acceptance.request.build_opener", side_effect=fake_build_opener):
            build_local_probe_opener("http://127.0.0.1:18081/api/health")
            build_local_probe_opener("http://localhost:18081/api/health")
            build_local_probe_opener("http://example.com/api/health")

        self.assertEqual(len(seen_args[0]), 1)
        self.assertEqual(type(seen_args[0][0]).__name__, "ProxyHandler")
        self.assertEqual(len(seen_args[1]), 1)
        self.assertEqual(type(seen_args[1][0]).__name__, "ProxyHandler")
        self.assertEqual(seen_args[2], ())

    @patch.dict("os.environ", {"TRENDSCOPE_UI_DRIVER": "inprocess"}, clear=False)
    def test_inprocess_ui_driver_skips_playwright_requirement(self) -> None:
        ensure_current_ui_python_has_playwright(sys.executable, skip_ui=False)

    def test_should_run_local_ui_skips_duplicate_ui_when_record_ui_enabled(self) -> None:
        args = SimpleNamespace(local_with_ui=True, run_ui=True)

        self.assertFalse(should_run_local_ui(args))

    def test_build_local_acceptance_command_omits_skip_ui_only_when_needed(self) -> None:
        args = SimpleNamespace(
            base_url="http://127.0.0.1:5081",
            backend_python="backend/.venv/bin/python",
            ui_python="backend/.venv/bin/python",
            startup_time_out=30.0,
            startup_timeout=30.0,
            request_timeout=2.0,
            skip_tests=False,
            local_with_ui=True,
            run_ui=False,
            require_running=False,
        )

        command = build_local_acceptance_command(args)

        self.assertIn("--json", command)
        self.assertNotIn("--skip-ui", command)

        args.run_ui = True
        command = build_local_acceptance_command(args)

        self.assertIn("--skip-ui", command)

    def test_update_ui_failure_sections_writes_failure_remarks(self) -> None:
        updated = update_ui_failure_sections(
            self.read_template(),
            base_url="http://127.0.0.1:5081",
            repo_query="anthropic/claude-code",
            keyword_query="mcp",
            period="30d",
            error_message="BrowserType.launch failed",
        )

        self.assertIn("- 验证地址：http://127.0.0.1:5081/?q=anthropic%2Fclaude-code&period=30d", updated)
        self.assertIn("- 是否可打开：`否`", updated)
        self.assertIn("- 备注：自动页面验收失败：BrowserType.launch failed", updated)
        self.assertIn("- 是否验证 scheduler：未自动验证", updated)

    def test_update_ui_sections_writes_optional_remarks(self) -> None:
        updated = update_ui_sections(
            self.read_template(),
            {
                "search_repo": {
                    "url": "http://127.0.0.1:5081/?q=anthropic%2Fclaude-code&period=30d",
                    "page_opened": True,
                    "saw_today_readout": True,
                    "saw_github_content": False,
                    "saw_trend_chart": False,
                    "track_ready": True,
                    "screenshot_path": "/tmp/repo-evidence.json",
                    "remark": "自动页面验收使用 inprocess driver",
                },
                "keyword_search": {
                    "url": "http://127.0.0.1:5081/?q=mcp&period=30d",
                    "saw_newsnow_snapshot": True,
                    "saw_content_list": False,
                    "saw_accumulation_hint_or_curve": True,
                    "screenshot_path": "/tmp/keyword-evidence.json",
                    "remark": "关键词页未生成浏览器截图",
                },
                "tracked_page": {
                    "page_opened": True,
                    "verify_real_completed": True,
                    "run_smoke_completed": True,
                    "collect_runs_visible": True,
                    "collect_tracked_executed": True,
                    "collect_runs_added": False,
                    "collect_feedback": "Triggered 1 collection run(s).",
                    "screenshot_path": "/tmp/tracked-evidence.json",
                    "remark": "tracked 页使用 inprocess driver",
                },
            },
        )

        self.assertIn("- 备注：自动页面验收使用 inprocess driver", updated)
        self.assertIn("- 备注：关键词页未生成浏览器截图", updated)
        self.assertIn("- 备注：Triggered 1 collection run(s).；tracked 页使用 inprocess driver", updated)

    def test_update_smoke_section_updates_force_search_example_query(self) -> None:
        updated = update_smoke_section(
            self.read_template(),
            '{"summary":"ok"}',
            {
                "summary": "smoke summary",
                "provider_verify": {
                    "github": {"status": "success"},
                    "newsnow": {"status": "success"},
                },
                "search": {
                    "status": "success",
                    "message": "端到端搜索执行成功。",
                },
                "next_steps": ["open tracked page"],
            },
            [
                "backend/.venv/bin/python",
                "-m",
                "app.cli",
                "provider-smoke",
                "openai/openai-python",
                "--period",
                "30d",
                "--probe-mode",
                "real",
            ],
        )

        self.assertIn("provider-smoke openai/openai-python --period 30d --probe-mode real", updated)
        self.assertIn("provider-smoke openai/openai-python --period 30d --probe-mode real --force-search", updated)

    def test_update_status_section_accepts_providers_array_shape(self) -> None:
        updated = update_status_section(
            self.read_template(),
            '{"summary":"ok"}',
            {
                "requested_mode": "real",
                "resolved_provider": "real",
                "providers": [
                    {"source": "github", "status": "ready"},
                    {"source": "newsnow", "status": "ready"},
                ],
            },
            ["backend/.venv/bin/python", "-m", "app.cli", "provider-status"],
            expected_mode="real",
        )

        self.assertIn("- GitHub 状态：ready", updated)
        self.assertIn("- NewsNow 状态：ready", updated)
        self.assertIn("- 是否通过：`通过`", updated)

    def test_update_verify_section_accepts_providers_array_shape(self) -> None:
        updated = update_verify_section(
            self.read_template(),
            '{"summary":"ok"}',
            {
                "summary": "verify summary",
                "providers": [
                    {"source": "github", "status": "success"},
                    {"source": "newsnow", "status": "success"},
                    {"source": "google_news", "status": "failed"},
                ],
            },
            ["backend/.venv/bin/python", "-m", "app.cli", "provider-verify", "--probe-mode", "real"],
        )

        self.assertIn("- GitHub 状态：success", updated)
        self.assertIn("- NewsNow 状态：success", updated)
        self.assertIn("- 是否通过：`通过`", updated)

    def test_update_smoke_section_accepts_nested_providers_array_shape(self) -> None:
        updated = update_smoke_section(
            self.read_template(),
            '{"summary":"ok"}',
            {
                "summary": "smoke summary",
                "provider_verify": {
                    "providers": [
                        {"source": "github", "status": "success"},
                        {"source": "newsnow", "status": "success"},
                        {"source": "google_news", "status": "failed"},
                    ]
                },
                "search": {
                    "status": "success",
                    "message": "端到端搜索执行成功。",
                },
                "next_steps": ["Google News 在线探测失败或跳过；这不会阻塞默认搜索。"],
            },
            [
                "backend/.venv/bin/python",
                "-m",
                "app.cli",
                "provider-smoke",
                "openai/openai-python",
                "--period",
                "30d",
                "--probe-mode",
                "real",
            ],
        )

        self.assertIn("- 是否通过：`通过`", updated)
        self.assertIn("Google News 在线探测失败或跳过", updated)

    def test_inprocess_completion_helpers_accept_providers_array_shape(self) -> None:
        self.assertTrue(
            has_provider_probe_results(
                {
                    "summary": "verify summary",
                    "providers": [
                        {"source": "github", "status": "success"},
                        {"source": "newsnow", "status": "success"},
                    ],
                }
            )
        )
        self.assertTrue(
            has_smoke_run_results(
                {
                    "summary": "smoke summary",
                    "provider_verify": {
                        "providers": [
                            {"source": "github", "status": "success"},
                        ]
                    },
                    "search": {
                        "status": "success",
                    },
                }
            )
        )

    def test_load_inprocess_search_payload_runs_backfill_now(self) -> None:
        class FakePayload:
            def model_dump(self, *, mode: str) -> dict[str, object]:
                self.mode = mode
                return {"status": "ok"}

        calls: list[tuple[str, str, bool]] = []
        payload = FakePayload()

        def fake_refresh(query: str, *, period: str, run_backfill_now: bool):
            calls.append((query, period, run_backfill_now))
            return payload

        result = load_inprocess_search_payload(
            query="mcp",
            period="30d",
            refresh_search=fake_refresh,
        )

        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(calls, [("mcp", "30d", True)])
        self.assertEqual(payload.mode, "json")

    def test_summarize_backfill_failures_joins_failed_tasks(self) -> None:
        summary = summarize_backfill_failures(
            {
                "backfill_job": {
                    "tasks": [
                        {
                            "source": "github",
                            "task_type": "content",
                            "status": "failed",
                            "message": "Network error",
                        },
                        {
                            "source": "newsnow",
                            "task_type": "snapshot",
                            "status": "success",
                            "message": "Stored 4 items",
                        },
                        {
                            "source": "newsnow",
                            "task_type": "snapshot",
                            "status": "failed",
                            "message": "Timed out",
                        },
                    ]
                }
            }
        )

        self.assertEqual(
            summary,
            "github/content: Network error；newsnow/snapshot: Timed out",
        )

    def test_build_inprocess_remark_includes_failure_summary(self) -> None:
        remark = build_inprocess_remark(
            "/tmp/evidence.json",
            failure_summary="newsnow/snapshot: Network error",
        )

        self.assertIn("自动页面验收使用 inprocess driver", remark)
        self.assertIn("结果按回填完成后的页面状态判定", remark)
        self.assertIn("回填失败摘要：newsnow/snapshot: Network error", remark)

    def test_summarize_exception_prefers_playwright_launch_reason(self) -> None:
        exc = subprocess.CalledProcessError(
            returncode=1,
            cmd=["python3", "scripts/ui_smoke_test.py"],
            stderr="\n".join(
                [
                    "Traceback",
                    "playwright._impl._errors.TargetClosedError: BrowserType.launch: Target page, context or browser has been closed",
                    "[pid=14][err] [0317/185407.172188:FATAL:content/browser/sandbox_host_linux.cc:41] Check failed: . shutdown: Operation not permitted (1)",
                ]
            ),
            output="",
        )

        summary = summarize_exception(exc)

        self.assertEqual(
            summary,
            "playwright._impl._errors.TargetClosedError: BrowserType.launch: Target page, context or browser has been closed；[pid=14][err] [0317/185407.172188:FATAL:content/browser/sandbox_host_linux.cc:41] Check failed: . shutdown: Operation not permitted (1)",
        )


if __name__ == "__main__":
    unittest.main()
