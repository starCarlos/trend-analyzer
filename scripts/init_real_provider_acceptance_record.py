from __future__ import annotations

import argparse
from datetime import date
import os
from pathlib import Path
import platform
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT_DIR / "docs"
TEMPLATE_PATH = DOCS_DIR / "real-provider-acceptance-record-template.md"
DEFAULT_OUTPUT_DIR = DOCS_DIR / "acceptance-records"
ENV_PATH = ROOT_DIR / "backend" / ".env"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize a real-provider acceptance record from the template")
    parser.add_argument("--mode", choices=["auto", "real"], default=None)
    parser.add_argument("--operator", default=os.environ.get("USER", ""))
    parser.add_argument("--machine", default=platform.node())
    parser.add_argument("--network", default="")
    parser.add_argument("--proxy", default="")
    parser.add_argument("--output")
    parser.add_argument("--force", action="store_true")
    return parser


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


def default_output_path(mode: str) -> Path:
    filename = f"{date.today().isoformat()}-{mode}-provider-acceptance.md"
    return DEFAULT_OUTPUT_DIR / filename


def fill_field(content: str, label: str, value: str) -> str:
    prefix = f"- {label}："
    lines = content.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"{prefix}{value}{newline}"
            break
    return "".join(lines)


def normalize_mode(cli_mode: str | None, env_values: dict[str, str]) -> str:
    env_mode = env_values.get("PROVIDER_MODE", "").strip().lower()
    if cli_mode:
        return cli_mode
    if env_mode in {"auto", "real"}:
        return env_mode
    return "auto"


def build_content(template: str, *, mode: str, operator: str, machine: str, network: str, proxy: str) -> str:
    env_values = parse_env_file(ENV_PATH)
    python_executable = sys.executable
    os_name = platform.platform()

    filled = template
    filled = fill_field(filled, "验收日期", date.today().isoformat())
    filled = fill_field(filled, "验收人", operator)
    filled = fill_field(filled, "机器环境", machine)
    filled = fill_field(filled, "操作系统", os_name)
    filled = fill_field(filled, "Python 解释器", python_executable)
    filled = fill_field(filled, "网络环境", network)
    filled = fill_field(filled, "是否使用代理", proxy)
    filled = fill_field(filled, "验收模式", mode)
    filled = fill_field(filled, "`PROVIDER_MODE`", env_values.get("PROVIDER_MODE", mode))
    filled = fill_field(filled, "`GITHUB_API_BASE_URL`", env_values.get("GITHUB_API_BASE_URL", ""))
    filled = fill_field(filled, "`NEWSNOW_BASE_URL`", env_values.get("NEWSNOW_BASE_URL", ""))
    filled = fill_field(filled, "`NEWSNOW_SOURCE_IDS`", env_values.get("NEWSNOW_SOURCE_IDS", ""))
    filled = fill_field(filled, "`REQUEST_TIMEOUT_SECONDS`", env_values.get("REQUEST_TIMEOUT_SECONDS", ""))
    filled = fill_field(filled, "`SCHEDULER_ENABLED`", env_values.get("SCHEDULER_ENABLED", ""))
    return filled


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not TEMPLATE_PATH.exists():
        parser.error(f"Template not found: {TEMPLATE_PATH}")

    env_values = parse_env_file(ENV_PATH)
    mode = normalize_mode(args.mode, env_values)
    output_path = Path(args.output).expanduser() if args.output else default_output_path(mode)
    if output_path.exists() and not args.force:
        parser.error(f"Output already exists: {output_path}. Use --force to overwrite.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    content = build_content(
        template,
        mode=mode,
        operator=args.operator,
        machine=args.machine,
        network=args.network,
        proxy=args.proxy,
    )
    output_path.write_text(content, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
