from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from init_real_provider_acceptance_record import (
    ENV_PATH,
    TEMPLATE_PATH,
    build_content,
    default_output_path,
    normalize_mode,
    parse_env_file,
)
from local_acceptance import (
    build_parser as build_local_acceptance_parser,
    load_health,
    start_backend,
    stop_backend,
    wait_for_health,
)
from update_real_provider_acceptance_record import (
    ROOT_DIR,
    command_markdown,
    update_line_in_section,
)


LOCAL_ACCEPTANCE_SCRIPT = ROOT_DIR / "scripts" / "local_acceptance.py"
UPDATE_RECORD_SCRIPT = ROOT_DIR / "scripts" / "update_real_provider_acceptance_record.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize and execute a real-provider acceptance workflow"
    )
    parser.add_argument("--mode", choices=["auto", "real"], default=None)
    parser.add_argument("--record")
    parser.add_argument("--force-init", action="store_true")
    parser.add_argument("--operator", default="")
    parser.add_argument("--machine", default="")
    parser.add_argument("--network", default="")
    parser.add_argument("--proxy", default="")
    parser.add_argument("--backend-python", default=build_local_acceptance_parser().get_default("backend_python"))
    parser.add_argument("--ui-python", default=sys.executable)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    parser.add_argument("--request-timeout", type=float, default=2.0)
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument("--local-with-ui", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--require-running", action="store_true")
    parser.add_argument("--query", default="openai/openai-python")
    parser.add_argument("--keyword-query", default="mcp")
    parser.add_argument("--period", choices=["7d", "30d", "90d", "all"], default="30d")
    parser.add_argument("--probe-mode", choices=["current", "real"], default="real")
    parser.add_argument("--force-search", action="store_true")
    parser.add_argument("--run-ui", action="store_true")
    parser.add_argument("--screenshots-dir")
    parser.add_argument("--skip-status", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    return parser


def ensure_record(args: argparse.Namespace) -> tuple[Path, str]:
    env_values = parse_env_file(ENV_PATH)
    mode = normalize_mode(args.mode, env_values)
    record_path = Path(args.record).expanduser() if args.record else default_output_path(mode)

    if record_path.exists() and not args.force_init:
        return record_path, mode

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    content = build_content(
        template,
        mode=mode,
        operator=args.operator,
        machine=args.machine,
        network=args.network,
        proxy=args.proxy,
    )
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(content, encoding="utf-8")
    return record_path, mode


def summarize_completed_run(completed: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if not lines:
        return ""
    for line in reversed(lines):
        if "Local acceptance" in line:
            tail = line
            break
    else:
        for line in reversed(lines):
            if line.startswith("[acceptance]"):
                tail = line
                break
        else:
            tail = lines[-1]
    if len(tail) <= 240:
        return tail
    return f"{tail[:237]}..."


def parse_completed_json(completed: subprocess.CompletedProcess[str]) -> dict[str, object] | None:
    stdout = completed.stdout.strip()
    if not stdout:
        return None
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def yes_no(value: bool) -> str:
    return "是" if value else "否"


def describe_local_acceptance_result(payload: dict[str, object] | None, fallback: str) -> str:
    if not payload:
        return fallback

    health = payload.get("health") if isinstance(payload.get("health"), dict) else {}
    parts = [
        f"health.env={health.get('environment') or 'unknown'}",
        f"provider_mode={health.get('provider_mode') or 'unknown'}",
        f"tests={yes_no(bool(payload.get('tests_ran')))}",
        f"ui={yes_no(bool(payload.get('ui_ran')))}",
        f"backend_already_running={yes_no(bool(payload.get('backend_already_running')))}",
        f"backend_auto_started={yes_no(bool(payload.get('backend_auto_started')))}",
    ]
    failure_message = str(payload.get("failure_message") or "")
    if failure_message:
        parts.append(f"failure={failure_message}")
    return "；".join(parts)


def should_run_local_ui(args: argparse.Namespace) -> bool:
    return args.local_with_ui and not args.run_ui


def build_local_acceptance_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(LOCAL_ACCEPTANCE_SCRIPT),
        "--base-url",
        args.base_url,
        "--backend-python",
        args.backend_python,
        "--ui-python",
        args.ui_python,
        "--startup-timeout",
        str(args.startup_timeout),
        "--request-timeout",
        str(args.request_timeout),
        "--json",
    ]
    if args.skip_tests:
        command.append("--skip-tests")
    if not should_run_local_ui(args):
        command.append("--skip-ui")
    if args.require_running:
        command.append("--require-running")
    return command


def update_local_section(record_path: Path, command: list[str], result: str, note: str) -> None:
    content = record_path.read_text(encoding="utf-8")
    content = update_line_in_section(
        content,
        "## 3. 本地验收前置结果",
        "是否先运行 `scripts/local_acceptance.py`",
        f"`{'是' if result != '未执行' else '否'}`",
    )
    content = update_line_in_section(
        content,
        "## 3. 本地验收前置结果",
        "命令",
        f"`{command_markdown(command)}`" if command else "",
    )
    content = update_line_in_section(content, "## 3. 本地验收前置结果", "结果", f"`{result}`")
    content = update_line_in_section(content, "## 3. 本地验收前置结果", "备注", note)
    record_path.write_text(content, encoding="utf-8")


def run_local_acceptance(args: argparse.Namespace, record_path: Path) -> None:
    if args.skip_local:
        update_local_section(record_path, [], "未执行", "本次通过编排脚本跳过本地验收。")
        return

    command = build_local_acceptance_command(args)

    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
    )
    result = "通过" if completed.returncode == 0 else "失败"
    payload = parse_completed_json(completed)
    note = describe_local_acceptance_result(payload, summarize_completed_run(completed))
    update_local_section(record_path, command, result, note)
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )


def ensure_backend_for_ui(args: argparse.Namespace) -> subprocess.Popen[str] | None:
    try:
        load_health(args.base_url, args.request_timeout)
        return None
    except Exception as exc:
        if args.require_running:
            raise RuntimeError(f"Backend is not healthy at {args.base_url}: {exc}") from exc

    process = start_backend(args.base_url, args.backend_python)
    wait_for_health(
        base_url=args.base_url,
        timeout_seconds=args.startup_timeout,
        request_timeout=args.request_timeout,
        process=process,
    )
    return process


def build_update_command(args: argparse.Namespace, record_path: Path, mode: str) -> list[str]:
    command = [
        sys.executable,
        str(UPDATE_RECORD_SCRIPT),
        "--record",
        str(record_path),
        "--mode",
        mode,
        "--backend-python",
        args.backend_python,
        "--ui-python",
        args.ui_python,
        "--query",
        args.query,
        "--keyword-query",
        args.keyword_query,
        "--period",
        args.period,
        "--probe-mode",
        args.probe_mode,
        "--base-url",
        args.base_url,
    ]
    if args.force_search:
        command.append("--force-search")
    if args.run_ui:
        command.append("--run-ui")
    if args.screenshots_dir:
        command.extend(["--screenshots-dir", args.screenshots_dir])
    if args.skip_status:
        command.append("--skip-status")
    if args.skip_verify:
        command.append("--skip-verify")
    if args.skip_smoke:
        command.append("--skip-smoke")
    return command


def run_update_command(args: argparse.Namespace, record_path: Path, mode: str) -> None:
    process: subprocess.Popen[str] | None = None
    try:
        if args.run_ui:
            process = ensure_backend_for_ui(args)
        subprocess.run(
            build_update_command(args, record_path, mode),
            cwd=ROOT_DIR,
            check=True,
            text=True,
            capture_output=True,
        )
    finally:
        stop_backend(process)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    record_path, mode = ensure_record(args)
    run_local_acceptance(args, record_path)
    run_update_command(args, record_path, mode)
    print(record_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
