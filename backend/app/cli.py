from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from typing import Any

from app.main import health, scheduler
from app.services.provider_diagnostics import get_provider_status
from app.services.provider_smoke import run_provider_smoke
from app.services.provider_verification import verify_provider_connectivity
from app.services.collector import collect_tracked_keywords, ensure_tracked, list_tracked_keywords, refresh_keyword


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TrendScope local CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health", help="Print API health payload")

    search = subparsers.add_parser("search", help="Run one search against the local services layer")
    search.add_argument("query", help="Repository or keyword query")
    search.add_argument("--period", default="30d", choices=["7d", "30d", "90d", "all"])
    search.add_argument(
        "--no-backfill",
        action="store_true",
        help="Return the initial payload without forcing synchronous backfill execution",
    )

    track = subparsers.add_parser("track", help="Track a keyword or repository")
    track.add_argument("query", help="Repository or keyword query")

    subparsers.add_parser("list-tracked", help="List tracked keywords")
    subparsers.add_parser("scheduler-status", help="Show automatic collection scheduler state")
    subparsers.add_parser("provider-status", help="Show provider preflight and local configuration status")
    provider_verify = subparsers.add_parser("provider-verify", help="Run lightweight online provider connectivity checks")
    provider_verify.add_argument("--probe-mode", default="real", choices=["current", "real"])
    provider_smoke = subparsers.add_parser("provider-smoke", help="Run provider preflight, verify, and optional end-to-end search")
    provider_smoke.add_argument("query", help="Repository or keyword query used for smoke search")
    provider_smoke.add_argument("--period", default="30d", choices=["7d", "30d", "90d", "all"])
    provider_smoke.add_argument("--probe-mode", default="real", choices=["current", "real"])
    provider_smoke.add_argument("--force-search", action="store_true")

    collect = subparsers.add_parser("collect-tracked", help="Refresh all tracked keywords")
    collect.add_argument("--period", default="30d", choices=["7d", "30d", "90d", "all"])

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "health":
        _print(health())
        return

    if args.command == "search":
        payload = refresh_keyword(
            args.query,
            period=args.period,
            run_backfill_now=not args.no_backfill,
        )
        _print(payload.model_dump(mode="json"))
        return

    if args.command == "track":
        payload = ensure_tracked(args.query)
        _print(payload.model_dump(mode="json"))
        return

    if args.command == "list-tracked":
        payload = [item.model_dump(mode="json") for item in list_tracked_keywords()]
        _print(payload)
        return

    if args.command == "scheduler-status":
        _print(asdict(scheduler.snapshot()))
        return

    if args.command == "provider-status":
        _print(get_provider_status().model_dump(mode="json"))
        return

    if args.command == "provider-verify":
        _print(verify_provider_connectivity(probe_mode=args.probe_mode).model_dump(mode="json"))
        return

    if args.command == "provider-smoke":
        _print(
            run_provider_smoke(
                query=args.query,
                period=args.period,
                probe_mode=args.probe_mode,
                force_search=args.force_search,
            ).model_dump(mode="json")
        )
        return

    if args.command == "collect-tracked":
        payload = [item.model_dump(mode="json") for item in collect_tracked_keywords(period=args.period)]
        _print(payload)
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
