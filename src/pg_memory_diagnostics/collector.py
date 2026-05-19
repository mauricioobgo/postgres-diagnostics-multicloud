from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pg_memory_diagnostics.catalog import BASE_QUERY_ORDER, CLOUD_QUERY_ORDER, QUERY_CATALOG


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    return value


def _rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [column.name for column in cursor.description]
    result: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        result.append({columns[index]: _normalize_value(value) for index, value in enumerate(row)})
    return result


def collect_snapshot(
    dsn: str,
    cloud: str,
    app_name: str,
    instance_memory_gib: float | None = None,
) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - depends on runtime install
        raise RuntimeError("psycopg is required for live collection. Install dependencies first.") from exc

    snapshot: dict[str, Any] = {
        "metadata": {
            "collected_at": datetime.now(tz=UTC).isoformat(),
            "cloud": cloud,
            "instance_memory_gib": instance_memory_gib,
            "source": "live",
        },
        "queries": {},
        "errors": {},
    }

    query_order = [*BASE_QUERY_ORDER, *CLOUD_QUERY_ORDER.get(cloud, [])]

    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET application_name = %s", (app_name,))

        for key in query_order:
            with connection.cursor() as cursor:
                try:
                    cursor.execute(QUERY_CATALOG[key].sql)
                    snapshot["queries"][key] = _rows_to_dicts(cursor)
                except Exception as exc:  # pragma: no cover - depends on DB privileges/features
                    snapshot["queries"][key] = []
                    snapshot["errors"][key] = str(exc)

        installed_extensions = {
            row["extname"]
            for row in snapshot["queries"].get("extensions", [])
            if row.get("extname")
        }
        for key, spec in QUERY_CATALOG.items():
            if not spec.optional_extension:
                continue
            if spec.optional_extension not in installed_extensions:
                continue
            with connection.cursor() as cursor:
                try:
                    cursor.execute(spec.sql)
                    snapshot["queries"][key] = _rows_to_dicts(cursor)
                except Exception as exc:  # pragma: no cover - depends on DB privileges/features
                    snapshot["queries"][key] = []
                    snapshot["errors"][key] = str(exc)

    return snapshot


def save_snapshot(snapshot: dict[str, Any], path: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


def load_snapshot(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
