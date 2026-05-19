from __future__ import annotations

import argparse
import os
from pathlib import Path

from pg_memory_diagnostics.analysis import analyze_snapshot
from pg_memory_diagnostics.collector import collect_snapshot, load_snapshot, save_snapshot
from pg_memory_diagnostics.html_report import write_report


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def build_parser() -> argparse.ArgumentParser:
    load_env_file()
    parser = argparse.ArgumentParser(
        prog="pg-memory-diagnostics",
        description="Collect PostgreSQL memory diagnostics and render an HTML report.",
    )
    parser.add_argument("--dsn", default=os.getenv("PGMD_DSN"), help="PostgreSQL DSN for live collection.")
    parser.add_argument("--snapshot-in", default=os.getenv("PGMD_SNAPSHOT_IN"), help="Load a previously captured JSON snapshot.")
    parser.add_argument("--snapshot-out", default=os.getenv("PGMD_SNAPSHOT_OUT"), help="Save collected live data to a JSON snapshot.")
    parser.add_argument(
        "--cloud",
        default=os.getenv("PGMD_CLOUD", "generic"),
        choices=["generic", "aws", "gcp"],
        help="Cloud profile to use for cloud-specific guidance.",
    )
    parser.add_argument(
        "--instance-memory-gib",
        type=float,
        default=float(os.getenv("PGMD_INSTANCE_MEMORY_GIB")) if os.getenv("PGMD_INSTANCE_MEMORY_GIB") else None,
        help="Total database instance memory in GiB for ratio-based heuristics.",
    )
    parser.add_argument(
        "--output",
        default=os.getenv("PGMD_OUTPUT"),
        help="Path to the HTML report output file.",
    )
    parser.add_argument(
        "--app-name",
        default=os.getenv("PGMD_APP_NAME", "pg-memory-diagnostics"),
        help="application_name used during live collection.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.output:
        parser.error("Provide --output or set PGMD_OUTPUT.")

    if bool(args.dsn) == bool(args.snapshot_in):
        parser.error("Provide exactly one of --dsn or --snapshot-in.")

    if args.snapshot_in:
        snapshot = load_snapshot(args.snapshot_in)
    else:
        snapshot = collect_snapshot(
            dsn=args.dsn,
            cloud=args.cloud,
            app_name=args.app_name,
            instance_memory_gib=args.instance_memory_gib,
        )
        if args.snapshot_out:
            save_snapshot(snapshot, args.snapshot_out)

    context = analyze_snapshot(
        snapshot=snapshot,
        cloud=args.cloud,
        instance_memory_gib=args.instance_memory_gib,
    )
    write_report(context, args.output)

    print(f"HTML report written to {Path(args.output).resolve()}")
    if args.snapshot_out:
        print(f"Snapshot written to {Path(args.snapshot_out).resolve()}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
