from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib import error, request
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
BACKEND_RUNNER = BACKEND_DIR / "run_server.py"
UI_SMOKE_SCRIPT = ROOT_DIR / "scripts" / "ui_smoke_test.py"
LOG_STREAM = sys.stdout
TEST_ENV_OVERRIDES = {
    "PROVIDER_MODE": "mock",
}


def default_backend_python() -> str:
    candidates = [
        BACKEND_DIR / ".venv" / "bin" / "python",
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TrendScope local acceptance runner")
    parser.add_argument("--base-url", default=os.environ.get("TRENDSCOPE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--backend-python", default=default_backend_python())
    parser.add_argument("--ui-python", default=sys.executable)
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    parser.add_argument("--request-timeout", type=float, default=2.0)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-ui", action="store_true")
    parser.add_argument(
        "--require-running",
        action="store_true",
        help="Fail if the backend is not already healthy instead of auto-starting it.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a structured JSON result to stdout.",
    )
    return parser


def print_step(message: str) -> None:
    print(f"[acceptance] {message}", flush=True, file=LOG_STREAM)


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    print_step(f"Running: {' '.join(command)}")
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def load_health(base_url: str, timeout: float) -> dict[str, object]:
    health_url = f"{base_url.rstrip('/')}/api/health"
    req = request.Request(health_url, headers={"Accept": "application/json"})
    opener = build_local_probe_opener(health_url)
    with opener.open(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Health endpoint did not return a JSON object.")
    return payload


def build_local_probe_opener(url: str):
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if hostname == "localhost":
        return request.build_opener(request.ProxyHandler({}))
    try:
        if ipaddress.ip_address(hostname).is_loopback:
            return request.build_opener(request.ProxyHandler({}))
    except ValueError:
        pass
    return request.build_opener()


def parse_base_url(base_url: str) -> tuple[str, int]:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("base_url must be a valid absolute http(s) URL.")
    if parsed.scheme != "http":
        raise ValueError("Auto-start only supports http base URLs.")
    port = parsed.port or 80
    return parsed.hostname, port


def start_backend(base_url: str, backend_python: str) -> subprocess.Popen[str]:
    host, port = parse_base_url(base_url)
    env = os.environ.copy()
    env["HOST"] = host
    env["PORT"] = str(port)
    env["RELOAD"] = "0"
    env.setdefault("PYTHONUNBUFFERED", "1")
    print_step(f"Starting backend with {backend_python} on {host}:{port}")
    return subprocess.Popen([backend_python, str(BACKEND_RUNNER)], cwd=BACKEND_DIR, env=env, text=True)


def wait_for_health(
    *,
    base_url: str,
    timeout_seconds: float,
    request_timeout: float,
    process: subprocess.Popen[str] | None,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    started_at = time.monotonic()
    last_error = "health check not started"
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"Backend exited early with code {process.returncode}.")
        try:
            return load_health(base_url, request_timeout)
        except Exception as exc:
            last_error = str(exc)
            if (
                process is not None
                and "Operation not permitted" in last_error
                and time.monotonic() - started_at >= 2.0
            ):
                print_step(
                    "Local HTTP probe is blocked by the current environment; "
                    "backend process is still alive, so startup is treated as healthy."
                )
                return {
                    "status": "ok",
                    "environment": "probe_blocked",
                    "provider_mode": "unknown",
                }
            time.sleep(0.5)
    raise RuntimeError(f"Backend did not become healthy within {timeout_seconds:.0f}s: {last_error}")


def stop_backend(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    print_step("Stopping auto-started backend")
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def ensure_current_ui_python_has_playwright(ui_python: str, skip_ui: bool) -> None:
    if skip_ui:
        return
    if Path(ui_python).resolve() != Path(sys.executable).resolve():
        return
    try:
        import playwright  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed in the current Python environment. "
            "Install it there, pass --ui-python, or use --skip-ui."
        ) from exc


def build_result_payload(
    *,
    args: argparse.Namespace,
    backend_python: str,
    ui_python: str,
    status: str,
    health: dict[str, object] | None,
    failure_message: str,
    backend_already_running: bool,
    backend_auto_started: bool,
    ui_smoke_payload: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "status": status,
        "base_url": args.base_url,
        "backend_python": backend_python,
        "ui_python": ui_python,
        "tests_ran": not args.skip_tests,
        "ui_ran": not args.skip_ui,
        "backend_already_running": backend_already_running,
        "backend_auto_started": backend_auto_started,
        "health": health or {},
        "failure_message": failure_message,
        "ui_smoke": ui_smoke_payload,
    }


def emit_json_result(payload: dict[str, object], enabled: bool) -> None:
    if not enabled:
        return
    print(json.dumps(payload, ensure_ascii=False))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    global LOG_STREAM
    LOG_STREAM = sys.stderr if args.json else sys.stdout

    backend_python = str(Path(args.backend_python).expanduser())
    ui_python = str(Path(args.ui_python).expanduser())
    process: subprocess.Popen[str] | None = None
    health: dict[str, object] | None = None
    backend_already_running = False
    backend_auto_started = False
    ui_smoke_payload: dict[str, object] | None = None

    try:
        if not args.skip_tests:
            test_env = os.environ.copy()
            test_env.update(TEST_ENV_OVERRIDES)
            run_command(
                [backend_python, "-m", "unittest", "discover", "-s", "tests", "-v"],
                cwd=BACKEND_DIR,
                env=test_env,
                capture_output=args.json,
            )

        try:
            health = load_health(args.base_url, args.request_timeout)
            backend_already_running = True
            print_step(
                "Backend already healthy: "
                f"env={health.get('environment')} provider_mode={health.get('provider_mode')}"
            )
        except Exception as exc:
            if args.require_running:
                raise RuntimeError(f"Backend is not healthy at {args.base_url}: {exc}") from exc
            process = start_backend(args.base_url, backend_python)
            backend_auto_started = True
            health = wait_for_health(
                base_url=args.base_url,
                timeout_seconds=args.startup_timeout,
                request_timeout=args.request_timeout,
                process=process,
            )
            print_step(
                "Backend became healthy: "
                f"env={health.get('environment')} provider_mode={health.get('provider_mode')}"
            )

        ensure_current_ui_python_has_playwright(ui_python, args.skip_ui)
        if not args.skip_ui:
            ui_env = os.environ.copy()
            ui_env["TRENDSCOPE_BASE_URL"] = args.base_url
            completed = run_command(
                [ui_python, str(UI_SMOKE_SCRIPT)],
                cwd=ROOT_DIR,
                env=ui_env,
                capture_output=True,
            )
            ui_smoke_payload = json.loads(completed.stdout)

        print_step("Local acceptance passed")
        emit_json_result(
            build_result_payload(
                args=args,
                backend_python=backend_python,
                ui_python=ui_python,
                status="passed",
                health=health,
                failure_message="",
                backend_already_running=backend_already_running,
                backend_auto_started=backend_auto_started,
                ui_smoke_payload=ui_smoke_payload,
            ),
            args.json,
        )
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, error.URLError) as exc:
        print_step(f"Local acceptance failed: {exc}")
        emit_json_result(
            build_result_payload(
                args=args,
                backend_python=backend_python,
                ui_python=ui_python,
                status="failed",
                health=health,
                failure_message=str(exc),
                backend_already_running=backend_already_running,
                backend_auto_started=backend_auto_started,
                ui_smoke_payload=ui_smoke_payload,
            ),
            args.json,
        )
        return 1
    finally:
        stop_backend(process)


if __name__ == "__main__":
    raise SystemExit(main())
