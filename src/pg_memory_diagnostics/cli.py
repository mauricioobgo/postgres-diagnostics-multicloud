from __future__ import annotations

import argparse
import os
from pathlib import Path

from pg_memory_diagnostics.analysis import analyze_snapshot
from pg_memory_diagnostics.collector import collect_snapshot, load_snapshot, save_snapshot
from pg_memory_diagnostics.connection import (
    DEFAULT_PROXY_HOST,
    DEFAULT_PROXY_PORT,
    DEFAULT_SOCKET_DIR,
    build_cloudsql_proxy_dsn,
)
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

    proxy = parser.add_argument_group("Cloud SQL Auth Proxy")
    proxy.add_argument(
        "--cloudsql-proxy",
        action="store_true",
        default=_env_bool("PGMD_CLOUDSQL_PROXY"),
        help="Build the DSN for a locally running Cloud SQL Auth Proxy instead of passing --dsn.",
    )
    proxy.add_argument(
        "--cloudsql-proxy-mode",
        choices=["tcp", "unix"],
        default=os.getenv("PGMD_CLOUDSQL_PROXY_MODE", "tcp"),
        help="How the Auth Proxy is listening: a local TCP port (default) or a Unix socket.",
    )
    proxy.add_argument(
        "--cloudsql-instance",
        default=os.getenv("PGMD_CLOUDSQL_INSTANCE"),
        help="INSTANCE_CONNECTION_NAME (project:region:instance), required for Unix-socket mode.",
    )
    proxy.add_argument(
        "--cloudsql-proxy-host",
        default=os.getenv("PGMD_CLOUDSQL_PROXY_HOST", DEFAULT_PROXY_HOST),
        help=f"Host the TCP proxy listens on (default {DEFAULT_PROXY_HOST}).",
    )
    proxy.add_argument(
        "--cloudsql-proxy-port",
        type=int,
        default=int(os.getenv("PGMD_CLOUDSQL_PROXY_PORT", str(DEFAULT_PROXY_PORT))),
        help=f"Port the proxy listens on (default {DEFAULT_PROXY_PORT}).",
    )
    proxy.add_argument(
        "--cloudsql-socket-dir",
        default=os.getenv("PGMD_CLOUDSQL_SOCKET_DIR", DEFAULT_SOCKET_DIR),
        help=f"Directory the Unix-socket proxy uses (default {DEFAULT_SOCKET_DIR}).",
    )
    proxy.add_argument("--db-user", default=os.getenv("PGMD_DB_USER"), help="Database user (Cloud SQL proxy mode).")
    proxy.add_argument("--db-password", default=os.getenv("PGMD_DB_PASSWORD"), help="Database password (Cloud SQL proxy mode).")
    proxy.add_argument("--db-name", default=os.getenv("PGMD_DB_NAME"), help="Database name (Cloud SQL proxy mode).")
    return parser


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.output:
        parser.error("Provide --output or set PGMD_OUTPUT.")

    sources = [bool(args.dsn), bool(args.snapshot_in), bool(args.cloudsql_proxy)]
    if sum(sources) != 1:
        parser.error("Provide exactly one connection source: --dsn, --snapshot-in, or --cloudsql-proxy.")

    dsn = args.dsn
    if args.cloudsql_proxy:
        try:
            dsn = build_cloudsql_proxy_dsn(
                user=args.db_user,
                password=args.db_password,
                dbname=args.db_name,
                mode=args.cloudsql_proxy_mode,
                host=args.cloudsql_proxy_host,
                port=args.cloudsql_proxy_port,
                socket_dir=args.cloudsql_socket_dir,
                instance_connection_name=args.cloudsql_instance,
            )
        except ValueError as exc:
            parser.error(str(exc))

    if args.snapshot_in:
        snapshot = load_snapshot(args.snapshot_in)
    else:
        snapshot = collect_snapshot(
            dsn=dsn,
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
