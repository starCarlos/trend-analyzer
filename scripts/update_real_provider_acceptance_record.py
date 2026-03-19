from __future__ import annotations

import argparse
import json
from datetime import date, datetime
import os
import shlex
import socket
from pathlib import Path
import subprocess
import sys
import time
from urllib import request
from urllib.parse import urlencode
from uuid import uuid4

from local_acceptance import (
    build_local_probe_opener,
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


def render_optional_yes_no(value: bool | None) -> str:
    if value is None:
        return "未自动验证"
    return f"`{yes_no(value)}`"


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


def find_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def probe_json_request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    timeout_seconds: float = 2.0,
) -> object:
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method=method)
    opener = build_local_probe_opener(url)
    try:
        with opener.open(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {url} returned invalid JSON: {exc}") from exc


def ensure_probe_process_alive(process: subprocess.Popen[str] | None) -> None:
    if process is not None and process.poll() is not None:
        raise RuntimeError(f"Probe backend exited early with code {process.returncode}.")


def wait_for_backfill_completion(
    *,
    base_url: str,
    keyword_id: int,
    timeout_seconds: float,
    process: subprocess.Popen[str] | None,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict[str, object] = {}
    while time.monotonic() < deadline:
        ensure_probe_process_alive(process)
        payload = probe_json_request(
            base_url,
            f"/api/keywords/{keyword_id}/backfill-status",
            timeout_seconds=2.0,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Backfill status probe did not return a JSON object.")
        last_payload = payload
        status = str(payload.get("status") or "")
        if status in {"success", "failed", "partial"}:
            return payload
        time.sleep(0.5)
    raise RuntimeError(
        f"Backfill probe did not finish within {timeout_seconds:.0f}s: "
        f"last_status={last_payload.get('status') or 'unknown'}"
    )


def has_readable_message(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return text.casefold() not in {"none", "null", "unknown"}


def normalize_scheduler_probe_query(query: str) -> str:
    candidate = query.strip()
    if "/" in candidate or candidate.startswith(("http://", "https://")):
        return candidate
    return "openai/openai-python"


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


def validate_scheduler_probe(
    backend_python: str,
    *,
    query: str,
    period: str,
) -> dict[str, object]:
    probe_query = normalize_scheduler_probe_query(query)
    port = find_available_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = Path("/tmp") / f"trendscope-scheduler-probe-{uuid4().hex}.db"
    env_overrides = {
        "DATABASE_URL": f"sqlite:///{db_path}",
        "APP_ENV": "scheduler_probe",
        "PROVIDER_MODE": "real",
        "SCHEDULER_ENABLED": "1",
        "SCHEDULER_INTERVAL_SECONDS": "5",
        "SCHEDULER_INITIAL_DELAY_SECONDS": "1",
        "SCHEDULER_PERIOD": period,
        "SCHEDULER_RUN_BACKFILL_NOW": "1",
    }
    process: subprocess.Popen[str] | None = None
    try:
        process = start_backend_with_env(
            base_url=base_url,
            backend_python=backend_python,
            env_overrides=env_overrides,
        )
        wait_for_health(
            base_url=base_url,
            timeout_seconds=20.0,
            request_timeout=2.0,
            process=process,
        )

        create_payload = probe_json_request(
            base_url,
            "/api/keywords",
            method="POST",
            payload={
                "query": probe_query,
                "track": True,
                "period": period,
                "run_backfill_now": False,
            },
            timeout_seconds=30.0,
        )
        if not isinstance(create_payload, dict):
            raise RuntimeError("Scheduler seed request did not return a JSON object.")
        keyword_payload = create_payload.get("keyword")
        if not isinstance(keyword_payload, dict):
            raise RuntimeError("Scheduler seed payload does not include keyword details.")
        keyword_id = int(keyword_payload["id"])
        initial_updated_at = str(keyword_payload.get("updated_at") or "")
        baseline_logs = probe_json_request(base_url, "/api/collect/logs?limit=50")
        if not isinstance(baseline_logs, list):
            raise RuntimeError("Collect logs baseline did not return a JSON list.")
        baseline_log_ids = {
            int(item["id"])
            for item in baseline_logs
            if isinstance(item, dict) and item.get("id") is not None
        }

        deadline = time.monotonic() + 90.0
        last_status_payload: dict[str, object] = {}
        latest_logs: list[dict[str, object]] = []
        observed_update = False
        while time.monotonic() < deadline:
            ensure_probe_process_alive(process)
            status_payload = probe_json_request(base_url, "/api/collect/status")
            logs_payload = probe_json_request(base_url, "/api/collect/logs?limit=50")
            keywords_payload = probe_json_request(base_url, "/api/keywords?tracked_only=true")
            if not isinstance(status_payload, dict):
                raise RuntimeError("Scheduler status probe did not return a JSON object.")
            if not isinstance(logs_payload, list):
                raise RuntimeError("Scheduler logs probe did not return a JSON list.")
            if not isinstance(keywords_payload, list):
                raise RuntimeError("Tracked keywords probe did not return a JSON list.")

            last_status_payload = status_payload
            latest_logs = [item for item in logs_payload if isinstance(item, dict)]
            tracked_keyword = next(
                (
                    item
                    for item in keywords_payload
                    if isinstance(item, dict) and int(item.get("id") or 0) == keyword_id
                ),
                None,
            )
            current_updated_at = str((tracked_keyword or {}).get("updated_at") or "")
            observed_update = observed_update or (
                bool(initial_updated_at) and bool(current_updated_at) and current_updated_at != initial_updated_at
            )
            new_success_logs = [
                item
                for item in latest_logs
                if int(item.get("id") or 0) not in baseline_log_ids
                and int(item.get("keyword_id") or 0) == keyword_id
                and str(item.get("status") or "") == "success"
            ]
            if (
                int(status_payload.get("iteration_count") or 0) >= 1
                and int(status_payload.get("last_triggered_count") or 0) >= 1
                and str(status_payload.get("last_status") or "") == "success"
                and bool(new_success_logs)
                and observed_update
            ):
                section_note = (
                    "另外补充使用临时 `scheduler_probe` 实例自动验证跨周期调度："
                    f"`/api/collect/status` 返回 `iteration_count={status_payload.get('iteration_count')}`、"
                    f"`last_triggered_count={status_payload.get('last_triggered_count')}`，"
                    "`/api/collect/logs` 新增 success 记录，"
                    f"tracked 条目 `{probe_query}` 的 `updated_at` 已更新。"
                )
                return {
                    "result": "通过",
                    "note": "已通过临时 `scheduler_probe` 实例自动验证：scheduler 跨周期运行成功，"
                    f"`last_triggered_count={status_payload.get('last_triggered_count')}`，"
                    "并新增 success `collect_runs` 记录。",
                    "section_note": section_note,
                    "scheduler_verified": True,
                    "collect_runs_added": True,
                    "observed_update": True,
                }
            time.sleep(1.0)

        return {
            "result": "失败",
            "note": "临时 `scheduler_probe` 实例未在超时内满足跨周期调度成功条件。",
            "section_note": (
                "尝试使用临时 `scheduler_probe` 实例自动验证跨周期调度，但未在超时内观察到"
                f"`iteration_count>=1`、新增 success `collect_runs` 与 `updated_at` 变化；"
                f"last_status={last_status_payload.get('last_status') or 'unknown'}。"
            ),
            "scheduler_verified": False,
            "collect_runs_added": any(
                int(item.get("id") or 0) not in baseline_log_ids and str(item.get("status") or "") == "success"
                for item in latest_logs
            ),
            "observed_update": observed_update,
        }
    except Exception as exc:
        return {
            "result": "失败",
            "note": f"临时 `scheduler_probe` 实例执行失败：{summarize_exception(exc)}",
            "section_note": f"尝试使用临时 `scheduler_probe` 实例自动验证跨周期调度失败：{summarize_exception(exc)}",
            "scheduler_verified": False,
            "collect_runs_added": False,
            "observed_update": False,
        }
    finally:
        stop_backend(process)


def validate_error_readability(
    backend_python: str,
    *,
    query: str,
    period: str,
) -> tuple[str, str]:
    probe_query = normalize_scheduler_probe_query(query)
    port = find_available_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = Path("/tmp") / f"trendscope-failure-probe-{uuid4().hex}.db"
    env_overrides = {
        "DATABASE_URL": f"sqlite:///{db_path}",
        "APP_ENV": "failure_probe",
        "PROVIDER_MODE": "real",
        "GITHUB_API_BASE_URL": "http://127.0.0.1:9",
        "NEWSNOW_BASE_URL": "http://127.0.0.1:9",
        "REQUEST_TIMEOUT_SECONDS": "1",
        "HTTP_PROXY": "",
    }
    process: subprocess.Popen[str] | None = None
    try:
        process = start_backend_with_env(
            base_url=base_url,
            backend_python=backend_python,
            env_overrides=env_overrides,
        )
        wait_for_health(
            base_url=base_url,
            timeout_seconds=20.0,
            request_timeout=2.0,
            process=process,
        )

        query_string = urlencode({"q": probe_query, "period": period})
        initial_search = probe_json_request(base_url, f"/api/search?{query_string}", timeout_seconds=10.0)
        if not isinstance(initial_search, dict):
            raise RuntimeError("Failure probe search did not return a JSON object.")
        keyword_payload = initial_search.get("keyword")
        if not isinstance(keyword_payload, dict):
            raise RuntimeError("Failure probe search did not return keyword details.")
        keyword_id = int(keyword_payload["id"])
        wait_for_backfill_completion(
            base_url=base_url,
            keyword_id=keyword_id,
            timeout_seconds=30.0,
            process=process,
        )
        search_payload = probe_json_request(base_url, f"/api/search?{query_string}", timeout_seconds=10.0)
        if not isinstance(search_payload, dict):
            raise RuntimeError("Failure probe refreshed search did not return a JSON object.")
        backfill_job = search_payload.get("backfill_job")
        if not isinstance(backfill_job, dict):
            raise RuntimeError("Failure probe refreshed search did not include backfill_job.")
        search_status = str(backfill_job.get("status") or "")
        error_message = str(backfill_job.get("error_message") or "")
        tasks = [
            item
            for item in backfill_job.get("tasks") or []
            if isinstance(item, dict)
        ]
        readable_task_messages = all(has_readable_message(item.get("message")) for item in tasks if item.get("status") != "pending")

        logs_before = probe_json_request(base_url, "/api/collect/logs?limit=50")
        if not isinstance(logs_before, list):
            raise RuntimeError("Failure probe collect logs baseline did not return a JSON list.")
        baseline_log_ids = {
            int(item["id"])
            for item in logs_before
            if isinstance(item, dict) and item.get("id") is not None
        }
        collect_payload = probe_json_request(
            base_url,
            "/api/collect/trigger",
            method="POST",
            payload={
                "query": probe_query,
                "tracked_only": False,
                "period": period,
                "run_backfill_now": True,
            },
            timeout_seconds=30.0,
        )
        if not isinstance(collect_payload, dict):
            raise RuntimeError("Failure probe collect trigger did not return a JSON object.")
        collect_results = collect_payload.get("results")
        if not isinstance(collect_results, list) or not collect_results or not isinstance(collect_results[0], dict):
            raise RuntimeError("Failure probe collect trigger did not return result items.")
        collect_status = str(collect_results[0].get("status") or "")

        logs_after = probe_json_request(base_url, "/api/collect/logs?limit=50")
        if not isinstance(logs_after, list):
            raise RuntimeError("Failure probe collect logs did not return a JSON list.")
        new_logs = [
            item
            for item in logs_after
            if isinstance(item, dict)
            and int(item.get("id") or 0) not in baseline_log_ids
            and int(item.get("keyword_id") or 0) == keyword_id
        ]
        readable_log = next(
            (
                item
                for item in new_logs
                if str(item.get("status") or "") in {"failed", "partial"}
                and has_readable_message(item.get("message"))
            ),
            None,
        )

        search_ok = search_status in {"failed", "partial"} and has_readable_message(error_message) and readable_task_messages
        collect_ok = collect_status in {"failed", "partial"} and readable_log is not None
        if search_ok and collect_ok:
            result = "通过" if search_status == "failed" and collect_status == "failed" else "部分通过"
            note = (
                "已通过临时 `failure_probe` 实例自动验证："
                f"`search` 返回 `backfill_job.status={search_status}` 与 `error_message`，"
                "task.message 和 `collect_logs.message` 都可读，"
                f"`collect/trigger` 返回 `results[0].status={collect_status}`。"
            )
            return result, note

        return "失败", (
            "临时 `failure_probe` 实例未得到预期失败态；"
            f"`search.status`={search_status or 'missing'}；"
            f"`collect.status`={collect_status or 'missing'}。"
        )
    except Exception as exc:
        return "失败", f"临时 `failure_probe` 实例执行失败：{summarize_exception(exc)}"
    finally:
        stop_backend(process)


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


def evaluate_tracked_flow(
    payload: dict[str, object] | None,
    *,
    scheduler_probe: dict[str, object] | None = None,
) -> tuple[str, str]:
    if scheduler_probe is not None:
        probe_result = str(scheduler_probe.get("result") or "")
        probe_note = str(scheduler_probe.get("note") or "")
        if probe_result == "通过":
            return "通过", probe_note
        if probe_result == "失败":
            if payload is not None and payload.get("page_opened") and payload.get("collect_tracked_executed"):
                if payload.get("collect_runs_added"):
                    manual_note = "已自动验证 `Collect tracked`，collect runs 有新增。"
                else:
                    manual_note = "已自动触发 `Collect tracked`，但本次未观察到新增 collect runs。"
                return "部分通过", join_notes([manual_note, probe_note])
            return "失败", probe_note

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


def update_collection_section(
    content: str,
    *,
    tracked_payload: dict[str, object] | None,
    scheduler_probe: dict[str, object] | None,
    ui_error: str | None = None,
) -> str:
    heading = "## 8. 追踪与采集结果"
    collect_tracked_verified: bool | None = None
    scheduler_verified: bool | None = None
    collect_runs_added: bool | None = None
    observed_update: bool | None = None
    remark_parts: list[str] = []

    if tracked_payload is not None:
        collect_tracked_verified = bool(tracked_payload.get("collect_tracked_executed"))
        collect_runs_added = bool(tracked_payload.get("collect_runs_added"))
        remark_parts.append(str(tracked_payload.get("collect_feedback") or ""))

    if scheduler_probe is not None:
        scheduler_verified = bool(scheduler_probe.get("scheduler_verified"))
        observed_update = bool(scheduler_probe.get("observed_update"))
        collect_runs_added = (collect_runs_added or False) or bool(scheduler_probe.get("collect_runs_added"))
        remark_parts.append(str(scheduler_probe.get("section_note") or scheduler_probe.get("note") or ""))

    if ui_error and tracked_payload is None:
        remark_parts.append(f"自动页面验收失败：{ui_error}")

    content = update_line_in_section(
        content,
        heading,
        "是否验证 `Collect tracked`",
        render_optional_yes_no(collect_tracked_verified),
    )
    content = update_line_in_section(
        content,
        heading,
        "是否验证 scheduler",
        render_optional_yes_no(scheduler_verified),
    )
    content = update_line_in_section(
        content,
        heading,
        "collect runs 是否新增",
        render_optional_yes_no(collect_runs_added),
    )
    content = update_line_in_section(
        content,
        heading,
        "是否观察到新点位或更新时间变化",
        render_optional_yes_no(observed_update),
    )
    return update_line_in_section(content, heading, "备注", join_notes(remark_parts))


def update_prd_mapping_section(
    content: str,
    *,
    repo_payload: dict[str, object] | None,
    keyword_payload: dict[str, object] | None,
    tracked_payload: dict[str, object] | None,
    scheduler_probe: dict[str, object] | None = None,
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
        tracked_result, tracked_note = evaluate_tracked_flow(tracked_payload, scheduler_probe=scheduler_probe)
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
    scheduler_probe: dict[str, object] | None = None,
    run_ui: bool,
    startup_result: str = "待人工确认",
    error_readability_result: str = "待人工确认",
    ui_error: str | None = None,
) -> str:
    heading = "## 10. 最终结论"
    _, _, repo_ok = evaluate_repo_ui(repo_payload)
    _, _, keyword_ok = evaluate_keyword_ui(keyword_payload)
    tracked_result, _ = evaluate_tracked_flow(tracked_payload, scheduler_probe=scheduler_probe)

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

    return content


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
    scheduler_probe: dict[str, object] | None = None
    startup_result, startup_note = validate_empty_startup(backend_python)
    if expected_mode == "real":
        scheduler_probe = validate_scheduler_probe(backend_python, query=args.query, period=args.period)
        error_readability_result, error_readability_note = validate_error_readability(
            backend_python,
            query=args.query,
            period=args.period,
        )
    else:
        error_readability_result, error_readability_note = evaluate_error_readability()
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

    content = update_collection_section(
        content,
        tracked_payload=tracked_payload,
        scheduler_probe=scheduler_probe,
        ui_error=ui_error,
    )
    content = update_prd_mapping_section(
        content,
        repo_payload=repo_payload,
        keyword_payload=keyword_payload,
        tracked_payload=tracked_payload,
        scheduler_probe=scheduler_probe,
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
        scheduler_probe=scheduler_probe,
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
