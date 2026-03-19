from __future__ import annotations

import argparse
import json
from datetime import date
import os
import shlex
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlencode
from uuid import uuid4

from local_acceptance import (
    build_parser as build_local_acceptance_parser,
    parse_base_url,
    stop_backend,
    wait_for_health,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
ENV_PATH = BACKEND_DIR / ".env"
DEFAULT_RECORD_DIR = ROOT_DIR / "docs" / "acceptance-records"
UI_SMOKE_SCRIPT = ROOT_DIR / "scripts" / "ui_smoke_test.py"
DEFAULT_BASE_URL = build_local_acceptance_parser().get_default("base_url")
CORE_PROVIDER_SOURCES = ("github", "newsnow")
RAW_PROVIDER_SOURCES = CORE_PROVIDER_SOURCES + ("google_news", "direct_rss", "gdelt")


def default_backend_python() -> str:
    candidates = [
        BACKEND_DIR / ".venv" / "bin" / "python",
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def default_ui_python() -> str:
    return sys.executable


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def infer_mode_from_record_path(record_path: Path) -> str | None:
    stem = record_path.stem.lower()
    if "-auto-" in f"-{stem}-":
        return "auto"
    if "-real-" in f"-{stem}-":
        return "real"
    return None


def default_record_path(mode: str | None) -> Path:
    if not mode:
        env_values = parse_env_file(ENV_PATH)
        mode = env_values.get("PROVIDER_MODE", "auto").strip().lower() or "auto"
    return DEFAULT_RECORD_DIR / f"{date.today().isoformat()}-{mode}-provider-acceptance.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update a real-provider acceptance record with current CLI outputs")
    parser.add_argument("--record")
    parser.add_argument("--mode", choices=["auto", "real"], default=None)
    parser.add_argument("--backend-python", default=default_backend_python())
    parser.add_argument("--ui-python", default=default_ui_python())
    parser.add_argument("--query", default="openai/openai-python")
    parser.add_argument("--keyword-query", default="mcp")
    parser.add_argument("--period", choices=["7d", "30d", "90d", "all"], default="30d")
    parser.add_argument("--probe-mode", choices=["current", "real"], default="real")
    parser.add_argument("--force-search", action="store_true")
    parser.add_argument("--run-ui", action="store_true")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--screenshots-dir")
    parser.add_argument("--skip-status", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    return parser


def run_json_command(command: list[str]) -> tuple[str, dict[str, object]]:
    return run_json_command_with_env(command)


def run_json_command_with_env(
    command: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> tuple[str, dict[str, object]]:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    completed = subprocess.run(
        command,
        cwd=BACKEND_DIR,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError(f"Command returned empty stdout: {' '.join(command)}")
    return stdout, json.loads(stdout)


def section_range(content: str, heading: str, *, stop_tokens: tuple[str, ...] = ("\n## ",)) -> tuple[int, int]:
    start = content.find(heading)
    if start < 0:
        raise ValueError(f"Section heading not found: {heading}")
    candidates = [content.find(token, start + len(heading)) for token in stop_tokens]
    valid = [candidate for candidate in candidates if candidate >= 0]
    end = min(valid) if valid else len(content)
    return start, end


def update_line_in_section(
    content: str,
    heading: str,
    label: str,
    value: str,
    *,
    stop_tokens: tuple[str, ...] = ("\n## ",),
) -> str:
    start, end = section_range(content, heading, stop_tokens=stop_tokens)
    section = content[start:end]
    prefix = f"- {label}："
    lines = section.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"{prefix}{value}{newline}"
            break
    updated = "".join(lines)
    return content[:start] + updated + content[end:]


def replace_nth_fenced_block_in_section(
    content: str,
    heading: str,
    fence: str,
    new_block_text: str,
    *,
    occurrence: int = 1,
    stop_tokens: tuple[str, ...] = ("\n## ",),
) -> str:
    start, end = section_range(content, heading, stop_tokens=stop_tokens)
    section = content[start:end]
    token = f"```{fence}\n"
    search_from = 0
    block_start = -1
    for _ in range(occurrence):
        block_start = section.find(token, search_from)
        if block_start < 0:
            raise ValueError(f"Fence block not found in section {heading}: {fence}")
        search_from = block_start + len(token)
    block_body_start = block_start + len(token)
    block_end = section.find("\n```", block_body_start)
    if block_end < 0:
        raise ValueError(f"Fence block terminator not found in section {heading}: {fence}")
    replacement = f"{token}{new_block_text.rstrip()}\n```"
    updated = section[:block_start] + replacement + section[block_end + 4 :]
    return content[:start] + updated + content[end:]


def pretty_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def command_markdown(command: list[str]) -> str:
    rendered: list[str] = []
    for part in command:
        try:
            candidate = Path(part).expanduser()
            if candidate.is_absolute():
                part = str(candidate.relative_to(ROOT_DIR))
        except Exception:
            pass
        rendered.append(shlex.quote(part))
    return " ".join(rendered)


def pass_fail(value: bool) -> str:
    return "通过" if value else "失败"


def yes_no(value: bool) -> str:
    return "是" if value else "否"


def iter_raw_provider_entries(payload: dict[str, object]) -> list[dict[str, object]]:
    providers = payload.get("providers")
    if isinstance(providers, list):
        return [item for item in providers if isinstance(item, dict)]

    entries: list[dict[str, object]] = []
    for source in RAW_PROVIDER_SOURCES:
        item = payload.get(source)
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        entry.setdefault("source", source)
        entries.append(entry)
    return entries


def get_raw_provider_entry(payload: dict[str, object], source: str) -> dict[str, object]:
    for entry in iter_raw_provider_entries(payload):
        if str(entry.get("source") or "") == source:
            return entry
    return {}


def get_raw_provider_status(payload: dict[str, object], source: str) -> str:
    return str(get_raw_provider_entry(payload, source).get("status") or "")


def raw_verify_payload_core_success(payload: dict[str, object]) -> bool:
    return all(get_raw_provider_status(payload, source) == "success" for source in CORE_PROVIDER_SOURCES)


def raw_status_payload_core_ready(payload: dict[str, object], *, expected_mode: str | None) -> bool:
    mode_matches = expected_mode in {None, "", str(payload.get("requested_mode") or "")}
    return mode_matches and all(
        get_raw_provider_status(payload, source) != "misconfigured" for source in CORE_PROVIDER_SOURCES
    )


def render_path(path: str) -> str:
    try:
        candidate = Path(path).expanduser()
        if candidate.is_absolute():
            return str(candidate.relative_to(ROOT_DIR))
    except Exception:
        pass
    return path


def default_screenshots_dir(record_path: Path) -> Path:
    return record_path.parent / f"{record_path.stem}-assets"


def run_ui_capture(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError(f"UI smoke command returned empty stdout: {' '.join(command)}")
    return json.loads(stdout)


def start_backend_with_env(
    *,
    base_url: str,
    backend_python: str,
    env_overrides: dict[str, str],
) -> subprocess.Popen[str]:
    host, port = parse_base_url(base_url)
    env = os.environ.copy()
    env["HOST"] = host
    env["PORT"] = str(port)
    env["RELOAD"] = "0"
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.update(env_overrides)
    return subprocess.Popen(
        [backend_python, str(BACKEND_DIR / "run_server.py")],
        cwd=BACKEND_DIR,
        env=env,
        text=True,
    )


def validate_empty_startup(backend_python: str) -> tuple[str, str]:
    port = 18081
    base_url = f"http://127.0.0.1:{port}"
    db_path = Path("/tmp") / f"trendscope-empty-startup-{uuid4().hex}.db"
    env_overrides = {
        "DATABASE_URL": f"sqlite:///{db_path}",
        "APP_ENV": "empty_db_probe",
        "PROVIDER_MODE": "mock",
        "SCHEDULER_ENABLED": "0",
    }
    process: subprocess.Popen[str] | None = None
    try:
        process = start_backend_with_env(
            base_url=base_url,
            backend_python=backend_python,
            env_overrides=env_overrides,
        )
        health = wait_for_health(
            base_url=base_url,
            timeout_seconds=20.0,
            request_timeout=2.0,
            process=process,
        )
        note = (
            f"临时空库启动成功；db={render_path(str(db_path))}；"
            f"health.env={health.get('environment') or 'unknown'}；"
            f"provider_mode={health.get('provider_mode') or 'unknown'}"
        )
        return "通过", note
    except Exception as exc:
        return "失败", f"临时空库启动失败：{summarize_exception(exc)}"
    finally:
        stop_backend(process)


def validate_error_readability(backend_python: str) -> tuple[str, str]:
    env_overrides = {
        "PROVIDER_MODE": "real",
        "GITHUB_TOKEN": "",
        "GITHUB_API_BASE_URL": "",
        "NEWSNOW_BASE_URL": "",
        "NEWSNOW_SOURCE_IDS": "",
        "REQUEST_TIMEOUT_SECONDS": "8",
        "HTTP_PROXY": "",
    }
    try:
        _, status_payload = run_json_command_with_env(
            [backend_python, "-m", "app.cli", "provider-status"],
            env_overrides=env_overrides,
        )
        _, verify_payload = run_json_command_with_env(
            [backend_python, "-m", "app.cli", "provider-verify", "--probe-mode", "real"],
            env_overrides=env_overrides,
        )
    except Exception as exc:
        return "失败", f"可读性验证执行失败：{summarize_exception(exc)}"

    github_status = get_raw_provider_entry(status_payload, "github")
    newsnow_status = get_raw_provider_entry(status_payload, "newsnow")
    github_verify = get_raw_provider_entry(verify_payload, "github")
    newsnow_verify = get_raw_provider_entry(verify_payload, "newsnow")

    github_status_ok = github_status.get("status") == "misconfigured" and bool(github_status.get("issues"))
    newsnow_status_ok = newsnow_status.get("status") == "misconfigured" and bool(newsnow_status.get("issues"))
    github_verify_ok = github_verify.get("status") == "skipped" and "本地配置不完整" in str(
        github_verify.get("message") or ""
    )
    newsnow_verify_ok = newsnow_verify.get("status") == "skipped" and "本地配置不完整" in str(
        newsnow_verify.get("message") or ""
    )

    if github_status_ok and newsnow_status_ok and github_verify_ok and newsnow_verify_ok:
        return "部分通过", "已自动验证 provider 配置缺失和在线探测跳过文案可读；search/backfill/collect 失败仍需人工构造。"
    return "失败", "provider 配置缺失或在线探测跳过文案不符合预期。"


def summarize_exception(exc: Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        combined = "\n".join(
            part.strip()
            for part in [exc.stderr or "", exc.stdout or ""]
            if part and part.strip()
        )
        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        if lines:
            launch_line = next((line for line in lines if "BrowserType.launch:" in line), "")
            permission_line = next((line for line in lines if "Operation not permitted" in line), "")
            if launch_line and permission_line and permission_line not in launch_line:
                return f"{launch_line}；{permission_line}"
            if launch_line:
                return launch_line
            if permission_line:
                return permission_line
            return lines[-1]
    return str(exc)


def build_search_url(base_url: str, query: str, period: str) -> str:
    return f"{base_url.rstrip('/')}/?{urlencode({'q': query, 'period': period})}"


def normalize_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def update_table_row_in_section(content: str, heading: str, row_label: str, result: str, note: str) -> str:
    start, end = section_range(content, heading)
    section = content[start:end]
    lines = section.splitlines(keepends=True)
    prefix = f"| {row_label} |"
    replacement = (
        f"| {row_label} | {normalize_table_cell(result)} | {normalize_table_cell(note)} |\n"
    )
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            break
    updated = "".join(lines)
    return content[:start] + updated + content[end:]


def join_notes(parts: list[str]) -> str:
    cleaned = [part for part in parts if part]
    return "；".join(cleaned)


def evaluate_repo_ui(payload: dict[str, object] | None) -> tuple[str, str, bool | None]:
    if payload is None:
        return "待人工确认", "未自动执行页面验收。", None
    missing: list[str] = []
    if not payload.get("page_opened"):
        missing.append("页面未正常打开")
    if not payload.get("saw_today_readout"):
        missing.append("未看到今日快照")
    if not payload.get("saw_github_content"):
        missing.append("未看到 GitHub 内容流")
    if not payload.get("saw_trend_chart"):
        missing.append("未看到趋势图")
    if not payload.get("track_ready"):
        missing.append("Track/Untrack 未就绪")
    if missing:
        return "失败", "；".join(missing), False
    return "通过", "搜索页关键元素齐全，Track/Untrack 可切换。", True


def evaluate_keyword_ui(payload: dict[str, object] | None) -> tuple[str, str, bool | None]:
    if payload is None:
        return "待人工确认", "未自动执行页面验收。", None
    missing: list[str] = []
    if not payload.get("page_opened"):
        missing.append("页面未正常打开")
    if not payload.get("saw_newsnow_snapshot"):
        missing.append("未看到 NewsNow 快照")
    if not payload.get("saw_content_list"):
        missing.append("未看到内容列表")
    if not payload.get("saw_accumulation_hint_or_curve"):
        missing.append("未看到累计提示或累计曲线")
    if missing:
        return "失败", "；".join(missing), False
    return "通过", "普通关键词搜索页关键元素齐全。", True


def evaluate_tracked_flow(payload: dict[str, object] | None) -> tuple[str, str]:
    if payload is None:
        return "待人工确认", "未自动执行 `/tracked` 页面验收。"
    if not payload.get("page_opened"):
        return "失败", "`/tracked` 页面未正常打开。"
    if not payload.get("collect_tracked_executed"):
        return "失败", "未完成 `Collect tracked` 自动验证。"
    if payload.get("collect_runs_added"):
        return "部分通过", "已自动验证 `Collect tracked`，collect runs 有新增；scheduler 持续写入仍需人工观察。"
    return "部分通过", "已自动触发 `Collect tracked`，但本次未观察到新增 collect runs；scheduler 持续写入仍需人工观察。"


def evaluate_error_readability() -> tuple[str, str]:
    return "待人工确认", "当前脚本只覆盖成功路径，失败场景仍需人工构造并确认错误提示可读。"


def update_prd_mapping_section(
    content: str,
    *,
    repo_payload: dict[str, object] | None,
    keyword_payload: dict[str, object] | None,
    tracked_payload: dict[str, object] | None,
    smoke_ok: bool | None,
    startup_result: str = "待人工确认",
    startup_note: str = "当前脚本不会自动清空数据库，只能证明现有环境可启动。",
    error_readability_result: str = "待人工确认",
    error_readability_note: str = "当前脚本只覆盖成功路径，失败场景仍需人工构造并确认错误提示可读。",
    ui_error: str | None = None,
) -> str:
    heading = "## 9. PRD 验收项映射"
    if ui_error and repo_payload is None:
        repo_result, repo_note = "失败", f"页面验收执行失败：{ui_error}"
    else:
        repo_result, repo_note, _ = evaluate_repo_ui(repo_payload)
    if ui_error and keyword_payload is None:
        keyword_result, keyword_note = "失败", f"页面验收执行失败：{ui_error}"
    else:
        keyword_result, keyword_note, _ = evaluate_keyword_ui(keyword_payload)
    if ui_error and tracked_payload is None:
        tracked_result, tracked_note = "失败", f"页面验收执行失败：{ui_error}"
    else:
        tracked_result, tracked_note = evaluate_tracked_flow(tracked_payload)
    if smoke_ok is False:
        repo_note = join_notes([repo_note, "provider smoke 搜索未通过，需先修复 CLI 链路。"])
        keyword_note = join_notes([keyword_note, "provider smoke 搜索未通过，需先修复 CLI 链路。"])

    content = update_table_row_in_section(content, heading, "可以从空库启动", startup_result, startup_note)
    content = update_table_row_in_section(
        content,
        heading,
        "GitHub 项目首次搜索能完成冷启动并看到历史图",
        repo_result,
        repo_note,
    )
    content = update_table_row_in_section(
        content,
        heading,
        "普通关键词首次搜索能看到 NewsNow 快照和内容列表",
        keyword_result,
        keyword_note,
    )
    content = update_table_row_in_section(
        content,
        heading,
        "加入追踪后，定时任务能持续写入新点位",
        tracked_result,
        tracked_note,
    )
    return update_table_row_in_section(
        content,
        heading,
        "搜索、回填、采集失败都有可读错误状态",
        error_readability_result,
        error_readability_note,
    )


def update_final_conclusion_section(
    content: str,
    *,
    status_ok: bool | None,
    verify_ok: bool | None,
    smoke_ok: bool | None,
    repo_payload: dict[str, object] | None,
    keyword_payload: dict[str, object] | None,
    tracked_payload: dict[str, object] | None,
    run_ui: bool,
    startup_result: str = "待人工确认",
    error_readability_result: str = "待人工确认",
    ui_error: str | None = None,
) -> str:
    heading = "## 10. 最终结论"
    _, _, repo_ok = evaluate_repo_ui(repo_payload)
    _, _, keyword_ok = evaluate_keyword_ui(keyword_payload)
    tracked_result, _ = evaluate_tracked_flow(tracked_payload)

    blockers: list[str] = []
    followups: list[str] = []

    if status_ok is False:
        blockers.append("Provider 预检未通过。")
    if verify_ok is False:
        blockers.append("在线探测未通过。")
    if smoke_ok is False:
        blockers.append("Smoke 总览未通过。")
    if startup_result == "失败":
        blockers.append("空库启动验证未通过。")
    if error_readability_result == "失败":
        blockers.append("失败场景可读性验证未通过。")
    if ui_error:
        blockers.append(f"页面验收执行失败：{ui_error}")
    if run_ui and repo_ok is False:
        blockers.append("GitHub 项目搜索页未通过。")
    if run_ui and keyword_ok is False:
        blockers.append("普通关键词搜索页未通过。")
    if run_ui and tracked_result == "失败":
        blockers.append("`/tracked` 页面验收未通过。")

    if not run_ui:
        followups.append("页面验收尚未执行。")
    if startup_result != "通过":
        followups.append("空库启动仍需人工验证。")
    if tracked_result != "通过":
        followups.append("scheduler 持续采集仍需人工观察。")
    if error_readability_result != "通过":
        followups.append("失败场景可读性仍需人工构造验证。")

    unique_followups: list[str] = []
    for item in followups:
        if item not in unique_followups:
            unique_followups.append(item)

    if blockers:
        verdict = "失败"
        allow_next = "否"
    elif unique_followups:
        verdict = "部分通过"
        allow_next = "是" if run_ui else "否"
    else:
        verdict = "通过"
        allow_next = "是"

    content = update_line_in_section(content, heading, "本次真实 provider 联调结果", f"`{verdict}`")
    content = update_line_in_section(content, heading, "是否允许继续上线前步骤", f"`{allow_next}`")
    content = update_line_in_section(content, heading, "阻塞项", join_notes(blockers))
    return update_line_in_section(content, heading, "后续动作", join_notes(unique_followups))


def update_status_section(
    content: str,
    stdout: str,
    payload: dict[str, object],
    command: list[str],
    *,
    expected_mode: str | None,
) -> str:
    heading = "## 4. Provider 预检结果"
    github = get_raw_provider_entry(payload, "github")
    newsnow = get_raw_provider_entry(payload, "newsnow")
    is_ok = raw_status_payload_core_ready(payload, expected_mode=expected_mode)
    content = replace_nth_fenced_block_in_section(content, heading, "bash", command_markdown(command))
    content = update_line_in_section(content, heading, "`requested_mode`", str(payload["requested_mode"]))
    content = update_line_in_section(content, heading, "`resolved_provider`", str(payload["resolved_provider"]))
    content = update_line_in_section(content, heading, "GitHub 状态", str(github.get("status") or "missing"))
    content = update_line_in_section(content, heading, "NewsNow 状态", str(newsnow.get("status") or "missing"))
    content = update_line_in_section(content, heading, "是否通过", f"`{pass_fail(is_ok)}`")
    content = update_line_in_section(content, "## 2. 配置摘要", "`PROVIDER_MODE`", str(payload["requested_mode"]))
    return replace_nth_fenced_block_in_section(content, heading, "text", stdout)


def update_verify_section(content: str, stdout: str, payload: dict[str, object], command: list[str]) -> str:
    heading = "## 5. 在线探测结果"
    github = get_raw_provider_entry(payload, "github")
    newsnow = get_raw_provider_entry(payload, "newsnow")
    is_ok = raw_verify_payload_core_success(payload)
    content = replace_nth_fenced_block_in_section(content, heading, "bash", command_markdown(command))
    content = update_line_in_section(content, heading, "GitHub 状态", str(github.get("status") or "missing"))
    content = update_line_in_section(content, heading, "NewsNow 状态", str(newsnow.get("status") or "missing"))
    content = update_line_in_section(content, heading, "是否通过", f"`{pass_fail(is_ok)}`")
    return replace_nth_fenced_block_in_section(content, heading, "text", stdout)


def update_smoke_section(content: str, stdout: str, payload: dict[str, object], command: list[str]) -> str:
    heading = "## 6. Smoke 总览结果"
    verify = payload["provider_verify"]
    search = payload["search"]
    next_steps = payload.get("next_steps") or []
    is_ok = raw_verify_payload_core_success(verify) and str(search.get("status") or "") == "success"
    content = replace_nth_fenced_block_in_section(content, heading, "bash", command_markdown(command))
    content = update_line_in_section(content, heading, "summary", str(payload["summary"]))
    content = update_line_in_section(content, heading, "`search.status`", str(search["status"]))
    content = update_line_in_section(content, heading, "`search.message`", str(search["message"]))
    content = update_line_in_section(
        content,
        heading,
        "`next_steps`",
        "；".join(str(item) for item in next_steps) if next_steps else "",
    )
    content = update_line_in_section(content, heading, "是否通过", f"`{pass_fail(is_ok)}`")
    content = replace_nth_fenced_block_in_section(content, heading, "text", stdout)

    force_search_command = [part for part in command if part != "--force-search"]
    if "--force-search" not in force_search_command:
        force_search_command.append("--force-search")
    return replace_nth_fenced_block_in_section(
        content,
        heading,
        "bash",
        command_markdown(force_search_command),
        occurrence=2,
    )


def update_ui_sections(content: str, payload: dict[str, object]) -> str:
    repo = payload["search_repo"]
    keyword = payload["keyword_search"]
    tracked = payload["tracked_page"]
    subsection_tokens = ("\n### ", "\n## ")

    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "验证地址",
        str(repo["url"]),
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "是否可打开",
        f"`{yes_no(bool(repo['page_opened']))}`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "是否看到今日快照",
        f"`{yes_no(bool(repo['saw_today_readout']))}`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "是否看到 GitHub 内容流",
        f"`{yes_no(bool(repo['saw_github_content']))}`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "是否看到趋势图",
        f"`{yes_no(bool(repo['saw_trend_chart']))}`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "`Track/Untrack` 是否正常",
        f"`{yes_no(bool(repo['track_ready']))}`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "截图路径",
        render_path(str(repo["screenshot_path"])),
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "备注",
        str(repo.get("remark") or ""),
        stop_tokens=subsection_tokens,
    )

    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "验证地址",
        str(keyword["url"]),
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "是否看到 NewsNow 快照",
        f"`{yes_no(bool(keyword['saw_newsnow_snapshot']))}`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "是否看到内容列表",
        f"`{yes_no(bool(keyword['saw_content_list']))}`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "是否看到累计提示或累计曲线",
        f"`{yes_no(bool(keyword['saw_accumulation_hint_or_curve']))}`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "截图路径",
        render_path(str(keyword["screenshot_path"])),
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "备注",
        str(keyword.get("remark") or ""),
        stop_tokens=subsection_tokens,
    )

    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "是否可打开",
        f"`{yes_no(bool(tracked['page_opened']))}`",
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "`Verify real` 是否正常",
        f"`{yes_no(bool(tracked['verify_real_completed']))}`",
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "`Run smoke` 是否正常",
        f"`{yes_no(bool(tracked['run_smoke_completed']))}`",
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "是否看到 collect runs",
        f"`{yes_no(bool(tracked['collect_runs_visible']))}`",
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "截图路径",
        render_path(str(tracked["screenshot_path"])),
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "备注",
        join_notes([str(tracked.get("collect_feedback") or ""), str(tracked.get("remark") or "")]),
        stop_tokens=("\n## ",),
    )

    content = update_line_in_section(
        content,
        "## 8. 追踪与采集结果",
        "是否验证 `Collect tracked`",
        f"`{yes_no(bool(tracked['collect_tracked_executed']))}`",
    )
    content = update_line_in_section(
        content,
        "## 8. 追踪与采集结果",
        "是否验证 scheduler",
        "未自动验证",
    )
    content = update_line_in_section(
        content,
        "## 8. 追踪与采集结果",
        "collect runs 是否新增",
        f"`{yes_no(bool(tracked['collect_runs_added']))}`",
    )
    content = update_line_in_section(
        content,
        "## 8. 追踪与采集结果",
        "是否观察到新点位或更新时间变化",
        "未自动验证",
    )
    content = update_line_in_section(
        content,
        "## 8. 追踪与采集结果",
        "备注",
        str(tracked.get("collect_feedback") or ""),
    )
    return content


def update_ui_failure_sections(
    content: str,
    *,
    base_url: str,
    repo_query: str,
    keyword_query: str,
    period: str,
    error_message: str,
) -> str:
    subsection_tokens = ("\n### ", "\n## ")
    repo_url = build_search_url(base_url, repo_query, period)
    keyword_url = build_search_url(base_url, keyword_query, period)
    tracked_url = f"{base_url.rstrip('/')}/tracked"
    remark = f"自动页面验收失败：{error_message}"

    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "验证地址",
        repo_url,
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "是否可打开",
        "`否`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "是否看到今日快照",
        "`否`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "是否看到 GitHub 内容流",
        "`否`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "是否看到趋势图",
        "`否`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "`Track/Untrack` 是否正常",
        "`否`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.1 GitHub 项目搜索",
        "备注",
        remark,
        stop_tokens=subsection_tokens,
    )

    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "验证地址",
        keyword_url,
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "是否看到 NewsNow 快照",
        "`否`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "是否看到内容列表",
        "`否`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "是否看到累计提示或累计曲线",
        "`否`",
        stop_tokens=subsection_tokens,
    )
    content = update_line_in_section(
        content,
        "### 7.2 普通关键词搜索",
        "备注",
        remark,
        stop_tokens=subsection_tokens,
    )

    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "验证地址",
        tracked_url,
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "是否可打开",
        "`否`",
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "`Verify real` 是否正常",
        "`否`",
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "`Run smoke` 是否正常",
        "`否`",
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "是否看到 collect runs",
        "`否`",
        stop_tokens=("\n## ",),
    )
    content = update_line_in_section(
        content,
        "### 7.3 `/tracked` 页",
        "备注",
        remark,
        stop_tokens=("\n## ",),
    )

    content = update_line_in_section(
        content,
        "## 8. 追踪与采集结果",
        "是否验证 `Collect tracked`",
        "`否`",
    )
    content = update_line_in_section(
        content,
        "## 8. 追踪与采集结果",
        "是否验证 scheduler",
        "未自动验证",
    )
    content = update_line_in_section(
        content,
        "## 8. 追踪与采集结果",
        "collect runs 是否新增",
        "`否`",
    )
    content = update_line_in_section(
        content,
        "## 8. 追踪与采集结果",
        "是否观察到新点位或更新时间变化",
        "未自动验证",
    )
    return update_line_in_section(content, "## 8. 追踪与采集结果", "备注", remark)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    record_path = Path(args.record).expanduser() if args.record else default_record_path(args.mode)
    if not record_path.exists():
        parser.error(
            f"Record file not found: {record_path}. "
            "Run scripts/init_real_provider_acceptance_record.py first, or pass --record."
        )

    content = record_path.read_text(encoding="utf-8")
    backend_python = str(Path(args.backend_python).expanduser())
    ui_python = str(Path(args.ui_python).expanduser())
    expected_mode = args.mode or infer_mode_from_record_path(record_path)
    status_ok: bool | None = None
    verify_ok: bool | None = None
    smoke_ok: bool | None = None
    repo_payload: dict[str, object] | None = None
    keyword_payload: dict[str, object] | None = None
    tracked_payload: dict[str, object] | None = None
    startup_result, startup_note = validate_empty_startup(backend_python)
    error_readability_result, error_readability_note = validate_error_readability(backend_python)
    ui_error: str | None = None

    if not args.skip_status:
        status_command = [backend_python, "-m", "app.cli", "provider-status"]
        status_stdout, status_payload = run_json_command(status_command)
        status_ok = raw_status_payload_core_ready(status_payload, expected_mode=expected_mode)
        content = update_status_section(
            content,
            status_stdout,
            status_payload,
            status_command,
            expected_mode=expected_mode,
        )

    if not args.skip_verify:
        verify_command = [backend_python, "-m", "app.cli", "provider-verify", "--probe-mode", args.probe_mode]
        verify_stdout, verify_payload = run_json_command(verify_command)
        verify_ok = raw_verify_payload_core_success(verify_payload)
        content = update_verify_section(content, verify_stdout, verify_payload, verify_command)

    if not args.skip_smoke:
        smoke_command = [
            backend_python,
            "-m",
            "app.cli",
            "provider-smoke",
            args.query,
            "--period",
            args.period,
            "--probe-mode",
            args.probe_mode,
        ]
        if args.force_search:
            smoke_command.append("--force-search")
        smoke_stdout, smoke_payload = run_json_command(smoke_command)
        smoke_ok = raw_verify_payload_core_success(smoke_payload["provider_verify"]) and str(
            smoke_payload["search"].get("status") or ""
        ) == "success"
        content = update_smoke_section(content, smoke_stdout, smoke_payload, smoke_command)

    if args.run_ui:
        screenshots_dir = (
            Path(args.screenshots_dir).expanduser()
            if args.screenshots_dir
            else default_screenshots_dir(record_path)
        )
        ui_command = [
            ui_python,
            str(UI_SMOKE_SCRIPT),
            "--base-url",
            args.base_url,
            "--output-dir",
            str(screenshots_dir),
            "--repo-query",
            args.query,
            "--keyword-query",
            args.keyword_query,
            "--period",
            args.period,
        ]
        try:
            ui_payload = run_ui_capture(ui_command)
        except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            ui_error = summarize_exception(exc)
            content = update_ui_failure_sections(
                content,
                base_url=args.base_url,
                repo_query=args.query,
                keyword_query=args.keyword_query,
                period=args.period,
                error_message=ui_error,
            )
        else:
            repo_payload = ui_payload["search_repo"]
            keyword_payload = ui_payload["keyword_search"]
            tracked_payload = ui_payload["tracked_page"]
            content = update_ui_sections(content, ui_payload)

    content = update_prd_mapping_section(
        content,
        repo_payload=repo_payload,
        keyword_payload=keyword_payload,
        tracked_payload=tracked_payload,
        smoke_ok=smoke_ok,
        startup_result=startup_result,
        startup_note=startup_note,
        error_readability_result=error_readability_result,
        error_readability_note=error_readability_note,
        ui_error=ui_error,
    )
    content = update_final_conclusion_section(
        content,
        status_ok=status_ok,
        verify_ok=verify_ok,
        smoke_ok=smoke_ok,
        repo_payload=repo_payload,
        keyword_payload=keyword_payload,
        tracked_payload=tracked_payload,
        run_ui=args.run_ui,
        startup_result=startup_result,
        error_readability_result=error_readability_result,
        ui_error=ui_error,
    )

    record_path.write_text(content, encoding="utf-8")
    print(record_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
