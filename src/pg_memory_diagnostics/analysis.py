from __future__ import annotations

from typing import Any

from pg_memory_diagnostics.catalog import FOLLOW_UP_QUERY_GROUPS, QUERY_CATALOG
from pg_memory_diagnostics.models import Finding, ReportContext


BYTE_UNITS = {
    None: 1,
    "B": 1,
    "kB": 1024,
    "8kB": 8192,
    "MB": 1024 * 1024,
    "GB": 1024 * 1024 * 1024,
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def setting_to_bytes(row: dict[str, Any] | None) -> int:
    if not row:
        return 0
    multiplier = BYTE_UNITS.get(row.get("unit"), 1)
    return int(_safe_float(row.get("setting"), 0.0) * multiplier)


def bytes_to_mib(value: int | float) -> float:
    return float(value) / 1024 / 1024


def bytes_to_gib(value: int | float) -> float:
    return float(value) / 1024 / 1024 / 1024


def format_bytes(value: int | float) -> str:
    value = float(value)
    gib = 1024 * 1024 * 1024
    mib = 1024 * 1024
    kib = 1024
    if value >= gib:
        return f"{value / gib:.2f} GiB"
    if value >= mib:
        return f"{value / mib:.2f} MiB"
    if value >= kib:
        return f"{value / kib:.2f} KiB"
    return f"{value:.0f} B"


def _build_settings_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["name"]: row
        for row in snapshot.get("queries", {}).get("settings", [])
        if row.get("name")
    }


def _add_finding(
    findings: list[Finding],
    *,
    finding_id: str,
    severity: str,
    title: str,
    summary: str,
    evidence: list[str],
    suggested_query_keys: list[str],
) -> None:
    findings.append(
        Finding(
            id=finding_id,
            severity=severity,
            title=title,
            summary=summary,
            evidence=evidence,
            suggested_query_keys=suggested_query_keys,
        )
    )


def analyze_snapshot(
    snapshot: dict[str, Any],
    cloud: str,
    instance_memory_gib: float | None = None,
) -> ReportContext:
    metadata = dict(snapshot.get("metadata", {}))
    if instance_memory_gib is not None:
        metadata["instance_memory_gib"] = instance_memory_gib

    settings = _build_settings_map(snapshot)
    query_results = dict(snapshot.get("queries", {}))
    query_errors = dict(snapshot.get("errors", {}))
    findings: list[Finding] = []

    instance_memory_bytes = 0
    if metadata.get("instance_memory_gib") is not None:
        instance_memory_bytes = int(_safe_float(metadata.get("instance_memory_gib")) * 1024**3)

    shared_buffers = setting_to_bytes(settings.get("shared_buffers"))
    work_mem = setting_to_bytes(settings.get("work_mem"))
    maintenance_work_mem = setting_to_bytes(settings.get("maintenance_work_mem"))
    autovacuum_work_mem = setting_to_bytes(settings.get("autovacuum_work_mem"))
    temp_buffers = setting_to_bytes(settings.get("temp_buffers"))
    effective_cache_size = setting_to_bytes(settings.get("effective_cache_size"))
    max_connections = _safe_int(settings.get("max_connections", {}).get("setting"))
    hash_mem_multiplier = _safe_float(settings.get("hash_mem_multiplier", {}).get("setting"), 1.0)
    max_parallel_workers_per_gather = _safe_int(settings.get("max_parallel_workers_per_gather", {}).get("setting"), 0)
    idle_in_tx_timeout_ms = _safe_int(settings.get("idle_in_transaction_session_timeout", {}).get("setting"), 0)

    if autovacuum_work_mem <= 0:
        autovacuum_work_mem = maintenance_work_mem

    connection_summary = (query_results.get("connection_summary") or [{}])[0]
    total_connections = _safe_int(connection_summary.get("total_connections"))
    active_connections = _safe_int(connection_summary.get("active_connections"))
    idle_connections = _safe_int(connection_summary.get("idle_connections"))
    idle_in_txn_connections = _safe_int(connection_summary.get("idle_in_txn_connections"))

    temp_rows = query_results.get("database_temp") or []
    total_temp_bytes = sum(_safe_int(row.get("temp_bytes")) for row in temp_rows)
    top_temp_db = temp_rows[0] if temp_rows else None
    table_health_rows = query_results.get("table_health") or []
    long_xact_rows = query_results.get("long_running_transactions") or []
    slot_rows = query_results.get("replication_slot_health") or []
    index_usage_rows = query_results.get("index_usage") or []
    pgstattuple_rows = query_results.get("pgstattuple_approx_top_tables") or []

    estimated_single_query_mem = work_mem * max(1.0, hash_mem_multiplier)
    estimated_parallel_query_mem = estimated_single_query_mem * max(1, max_parallel_workers_per_gather)
    worst_case_connection_mem = estimated_single_query_mem * max_connections
    active_working_set_mem = estimated_single_query_mem * max(1, active_connections)
    potential_memory_commit = shared_buffers + worst_case_connection_mem + maintenance_work_mem

    if instance_memory_bytes:
        shared_ratio = shared_buffers / instance_memory_bytes if instance_memory_bytes else 0
        if shared_ratio < 0.15:
            _add_finding(
                findings,
                finding_id="shared-buffers-low",
                severity="medium",
                title="shared_buffers looks small for the instance size",
                summary="The configured shared buffer pool is below a typical starting range for PostgreSQL memory tuning.",
                evidence=[
                    f"shared_buffers = {format_bytes(shared_buffers)}",
                    f"instance memory = {format_bytes(instance_memory_bytes)}",
                    f"shared_buffers ratio = {shared_ratio:.1%}",
                ],
                suggested_query_keys=["pg_buffercache_top_relations"],
            )
        elif shared_ratio > 0.40:
            _add_finding(
                findings,
                finding_id="shared-buffers-high",
                severity="medium",
                title="shared_buffers is high relative to instance memory",
                summary="A very large shared buffer pool can squeeze memory available to connections, sorts, hashes, autovacuum, and the operating system cache.",
                evidence=[
                    f"shared_buffers = {format_bytes(shared_buffers)}",
                    f"instance memory = {format_bytes(instance_memory_bytes)}",
                    f"shared_buffers ratio = {shared_ratio:.1%}",
                ],
                suggested_query_keys=["pg_buffercache_top_relations"],
            )

    if max_connections >= 300:
        severity = "high" if max_connections >= 500 else "medium"
        _add_finding(
            findings,
            finding_id="max-connections-high",
            severity=severity,
            title="max_connections is high",
            summary="Large connection ceilings increase backend memory risk and often point to missing pooling.",
            evidence=[
                f"max_connections = {max_connections}",
                f"current total_connections = {total_connections}",
                f"idle_connections = {idle_connections}",
            ],
            suggested_query_keys=[
                "connection_summary",
                "aws_session_breakdown" if cloud == "aws" else "gcp_session_breakdown" if cloud == "gcp" else "connection_summary",
            ],
        )

    if total_connections and idle_connections / max(total_connections, 1) >= 0.60 and idle_connections >= 20:
        _add_finding(
            findings,
            finding_id="idle-connections",
            severity="medium",
            title="Many connections are idle",
            summary="Idle sessions still consume backend memory and often indicate connection pool inefficiency or application leakage.",
            evidence=[
                f"total_connections = {total_connections}",
                f"idle_connections = {idle_connections}",
                f"idle ratio = {idle_connections / total_connections:.1%}",
            ],
            suggested_query_keys=[
                "aws_session_breakdown" if cloud == "aws" else "gcp_session_breakdown" if cloud == "gcp" else "connection_summary"
            ],
        )

    if idle_in_txn_connections > 0:
        severity = "high" if idle_in_txn_connections >= 5 else "medium"
        _add_finding(
            findings,
            finding_id="idle-in-transaction",
            severity=severity,
            title="Idle-in-transaction sessions are present",
            summary="Idle transactions retain resources, can hold snapshots longer than needed, and often amplify memory and vacuum pressure.",
            evidence=[f"idle_in_txn_connections = {idle_in_txn_connections}"],
            suggested_query_keys=["connection_summary"],
        )

    if idle_in_txn_connections > 0 and idle_in_tx_timeout_ms == 0:
        _add_finding(
            findings,
            finding_id="idle-in-txn-timeout-disabled",
            severity="medium",
            title="idle_in_transaction_session_timeout is disabled",
            summary="Idle-in-transaction sessions are visible and there is no server-side timeout configured to clean them up automatically.",
            evidence=[
                f"idle_in_txn_connections = {idle_in_txn_connections}",
                f"idle_in_transaction_session_timeout = {idle_in_tx_timeout_ms} ms",
            ],
            suggested_query_keys=["long_running_transactions"],
        )

    if work_mem >= 64 * 1024 * 1024 and max_connections >= 200:
        _add_finding(
            findings,
            finding_id="work-mem-risk",
            severity="high",
            title="work_mem combined with connection count creates a large memory envelope",
            summary="The configured per-operation memory budget is large enough that concurrent sorts and hashes could pressure instance memory.",
            evidence=[
                f"work_mem = {format_bytes(work_mem)}",
                f"hash_mem_multiplier = {hash_mem_multiplier:.2f}",
                f"estimated single-query sort/hash envelope = {format_bytes(estimated_single_query_mem)}",
                f"worst-case work_mem across max_connections = {format_bytes(worst_case_connection_mem)}",
            ],
            suggested_query_keys=["pg_stat_statements_memory", "database_temp"],
        )

    if instance_memory_bytes and potential_memory_commit > instance_memory_bytes:
        _add_finding(
            findings,
            finding_id="potential-overcommit",
            severity="high",
            title="Conservative memory model exceeds instance memory",
            summary="A rough upper-bound estimate suggests PostgreSQL could overcommit memory under concurrent pressure. This model is intentionally conservative, but it is a strong tuning signal.",
            evidence=[
                f"shared_buffers = {format_bytes(shared_buffers)}",
                f"maintenance_work_mem = {format_bytes(maintenance_work_mem)}",
                f"worst-case work_mem across max_connections = {format_bytes(worst_case_connection_mem)}",
                f"conservative total = {format_bytes(potential_memory_commit)} vs instance memory {format_bytes(instance_memory_bytes)}",
            ],
            suggested_query_keys=["connection_summary", "pg_stat_statements_memory"],
        )

    if total_temp_bytes >= 1024**3:
        severity = "high" if total_temp_bytes >= 10 * 1024**3 else "medium"
        top_db_bits = []
        if top_temp_db:
            top_db_bits.append(
                f"top temp database = {top_temp_db.get('database_name')} ({format_bytes(_safe_int(top_temp_db.get('temp_bytes')))})"
            )
        _add_finding(
            findings,
            finding_id="temp-spills",
            severity=severity,
            title="Temporary file usage indicates memory spills",
            summary="Large temp-file volume usually means sorts, hashes, or maintenance work exceeded in-memory budgets.",
            evidence=[
                f"total temp bytes = {format_bytes(total_temp_bytes)}",
                *top_db_bits,
            ],
            suggested_query_keys=["database_temp", "pg_stat_statements_memory"],
        )

    if table_health_rows:
        worst_dead = max(table_health_rows, key=lambda row: _safe_float(row.get("dead_row_pct_est"), 0.0))
        if _safe_float(worst_dead.get("dead_row_pct_est"), 0.0) >= 10.0 and _safe_int(worst_dead.get("dead_rows_est")) >= 100000:
            _add_finding(
                findings,
                finding_id="table-dead-tuples",
                severity="high",
                title="One or more tables show heavy dead-tuple accumulation",
                summary="Dead rows suggest vacuum is not keeping up with update/delete churn or that cleanup is blocked by MVCC activity.",
                evidence=[
                    f"worst table = {worst_dead.get('schema_name')}.{worst_dead.get('table_name')}",
                    f"dead rows estimate = {_safe_int(worst_dead.get('dead_rows_est'))}",
                    f"dead row percent estimate = {_safe_float(worst_dead.get('dead_row_pct_est')):.2f}%",
                ],
                suggested_query_keys=["table_health", "long_running_transactions", "vacuum_progress", "pgstattuple_approx_top_tables"],
            )

        stale_table = max(table_health_rows, key=lambda row: _safe_int(row.get("mod_since_analyze"), 0))
        if _safe_int(stale_table.get("mod_since_analyze")) >= 100000:
            _add_finding(
                findings,
                finding_id="stale-analyze-stats",
                severity="medium",
                title="Some tables appear under-analyzed",
                summary="Large numbers of modifications since the last analyze can make the planner work from stale statistics.",
                evidence=[
                    f"stale table = {stale_table.get('schema_name')}.{stale_table.get('table_name')}",
                    f"n_mod_since_analyze = {_safe_int(stale_table.get('mod_since_analyze'))}",
                    f"last_autoanalyze = {stale_table.get('last_autoanalyze')}",
                ],
                suggested_query_keys=["table_health", "vacuum_progress"],
            )

        low_hot = [
            row for row in table_health_rows
            if _safe_float(row.get("hot_update_pct"), 0.0) < 10.0 and _safe_int(row.get("dead_rows_est")) >= 100000
        ]
        if low_hot:
            row = low_hot[0]
            _add_finding(
                findings,
                finding_id="low-hot-update-ratio",
                severity="medium",
                title="Some write-heavy tables have a low HOT update ratio",
                summary="A low HOT update ratio can mean more index churn, extra page pressure, and additional bloat during updates.",
                evidence=[
                    f"table = {row.get('schema_name')}.{row.get('table_name')}",
                    f"hot update percent = {_safe_float(row.get('hot_update_pct')):.2f}%",
                    f"dead rows estimate = {_safe_int(row.get('dead_rows_est'))}",
                ],
                suggested_query_keys=["table_health", "index_usage"],
            )

    if long_xact_rows:
        blocker = long_xact_rows[0]
        if _safe_int(blocker.get("backend_xmin_age")) >= 100000000:
            _add_finding(
                findings,
                finding_id="mvcc-blocker-long-xact",
                severity="high",
                title="Long-running transactions may be delaying MVCC cleanup",
                summary="A backend holding an old xmin can keep dead row versions visible longer and slow vacuum progress.",
                evidence=[
                    f"pid = {blocker.get('pid')}",
                    f"state = {blocker.get('state')}",
                    f"backend_xmin_age = {_safe_int(blocker.get('backend_xmin_age'))}",
                    f"xact_age = {blocker.get('xact_age')}",
                ],
                suggested_query_keys=["long_running_transactions", "vacuum_progress"],
            )

    if slot_rows:
        worst_slot = max(slot_rows, key=lambda row: max(_safe_int(row.get("xmin_age")), _safe_int(row.get("catalog_xmin_age"))))
        slot_age = max(_safe_int(worst_slot.get("xmin_age")), _safe_int(worst_slot.get("catalog_xmin_age")))
        if slot_age >= 100000000:
            _add_finding(
                findings,
                finding_id="replication-slot-retention",
                severity="high",
                title="A replication slot may be retaining old row versions or WAL longer than expected",
                summary="Old xmin or catalog_xmin on a slot can prevent cleanup and worsen MVCC-related storage pressure.",
                evidence=[
                    f"slot = {worst_slot.get('slot_name')}",
                    f"slot active = {worst_slot.get('active')}",
                    f"max xmin age = {slot_age}",
                ],
                suggested_query_keys=["replication_slot_health"],
            )

    if index_usage_rows:
        unused_large = [
            row for row in index_usage_rows
            if _safe_int(row.get("idx_scan")) == 0 and _safe_int(row.get("index_bytes")) >= 512 * 1024 * 1024
        ]
        if unused_large:
            row = unused_large[0]
            _add_finding(
                findings,
                finding_id="unused-large-index",
                severity="medium",
                title="A large index appears unused",
                summary="Large unused indexes consume storage and cache space and add write amplification to INSERT/UPDATE/DELETE workloads.",
                evidence=[
                    f"index = {row.get('schema_name')}.{row.get('index_name')}",
                    f"table = {row.get('table_name')}",
                    f"index size = {format_bytes(_safe_int(row.get('index_bytes')))}",
                    f"idx_scan = {_safe_int(row.get('idx_scan'))}",
                ],
                suggested_query_keys=["index_usage", "table_health"],
            )

    if pgstattuple_rows:
        row = pgstattuple_rows[0]
        if _safe_float(row.get("dead_tuple_percent"), 0.0) >= 10.0:
            _add_finding(
                findings,
                finding_id="pgstattuple-bloat-signal",
                severity="medium",
                title="pgstattuple flags a table as a likely bloat candidate",
                summary="Tuple-level inspection shows elevated dead tuples or free space on at least one large table.",
                evidence=[
                    f"table = {row.get('schema_name')}.{row.get('table_name')}",
                    f"dead tuple percent = {_safe_float(row.get('dead_tuple_percent')):.2f}%",
                    f"approx free percent = {_safe_float(row.get('approx_free_percent')):.2f}%",
                ],
                suggested_query_keys=["pgstattuple_approx_top_tables", "table_health"],
            )

    if maintenance_work_mem >= 1024**3:
        _add_finding(
            findings,
            finding_id="maintenance-work-mem-large",
            severity="medium",
            title="maintenance_work_mem is large",
            summary="Large maintenance memory can be useful for vacuum and index builds, but it should be weighed against concurrency and autovacuum worker behavior.",
            evidence=[
                f"maintenance_work_mem = {format_bytes(maintenance_work_mem)}",
                f"autovacuum_work_mem (effective) = {format_bytes(autovacuum_work_mem)}",
            ],
            suggested_query_keys=["database_temp"],
        )

    if effective_cache_size and shared_buffers and effective_cache_size < shared_buffers * 1.5:
        _add_finding(
            findings,
            finding_id="effective-cache-size-low",
            severity="low",
            title="effective_cache_size may be undersized",
            summary="A low planner cache estimate can bias execution plans away from index and cache-friendly choices.",
            evidence=[
                f"effective_cache_size = {format_bytes(effective_cache_size)}",
                f"shared_buffers = {format_bytes(shared_buffers)}",
            ],
            suggested_query_keys=["pg_buffercache_top_relations"],
        )

    installed_extensions = {row.get("extname") for row in query_results.get("extensions", [])}
    if "pg_stat_statements" not in installed_extensions:
        _add_finding(
            findings,
            finding_id="missing-pg-stat-statements",
            severity="low",
            title="pg_stat_statements is not installed",
            summary="Without pg_stat_statements the report cannot identify the statements most associated with temp spills and inefficient memory use.",
            evidence=["Extension pg_stat_statements not found in pg_extension."],
            suggested_query_keys=[],
        )

    if "pg_buffercache" not in installed_extensions:
        _add_finding(
            findings,
            finding_id="missing-pg-buffercache",
            severity="low",
            title="pg_buffercache is not installed",
            summary="Without pg_buffercache the report cannot attribute shared buffer residency to specific relations.",
            evidence=["Extension pg_buffercache not found in pg_extension."],
            suggested_query_keys=[],
        )

    if "pgstattuple" not in installed_extensions:
        _add_finding(
            findings,
            finding_id="missing-pgstattuple",
            severity="low",
            title="pgstattuple is not installed",
            summary="Without pgstattuple the report cannot run tuple-level dead-space inspection for likely bloat candidates.",
            evidence=["Extension pgstattuple not found in pg_extension."],
            suggested_query_keys=[],
        )

    for key, error in query_errors.items():
        _add_finding(
            findings,
            finding_id=f"query-error-{key}",
            severity="low",
            title=f"Query {key} could not be collected",
            summary="The report continued, but one diagnostic query failed. This usually means a permission limit, managed-service restriction, or version mismatch.",
            evidence=[error],
            suggested_query_keys=[],
        )

    findings.sort(key=lambda finding: {"high": 0, "medium": 1, "low": 2}.get(finding.severity, 3))

    derived = {
        "instance_memory_bytes": instance_memory_bytes,
        "shared_buffers_bytes": shared_buffers,
        "work_mem_bytes": work_mem,
        "maintenance_work_mem_bytes": maintenance_work_mem,
        "autovacuum_work_mem_bytes": autovacuum_work_mem,
        "temp_buffers_bytes": temp_buffers,
        "effective_cache_size_bytes": effective_cache_size,
        "max_connections": max_connections,
        "total_connections": total_connections,
        "active_connections": active_connections,
        "idle_connections": idle_connections,
        "idle_in_txn_connections": idle_in_txn_connections,
        "total_temp_bytes": total_temp_bytes,
        "estimated_single_query_mem_bytes": int(estimated_single_query_mem),
        "estimated_parallel_query_mem_bytes": int(estimated_parallel_query_mem),
        "active_working_set_mem_bytes": int(active_working_set_mem),
        "worst_case_connection_mem_bytes": int(worst_case_connection_mem),
        "potential_memory_commit_bytes": int(potential_memory_commit),
        "follow_up_query_keys": [*FOLLOW_UP_QUERY_GROUPS["generic"], *FOLLOW_UP_QUERY_GROUPS.get(cloud, [])],
    }

    return ReportContext(
        cloud=cloud,
        metadata=metadata,
        settings=settings,
        findings=findings,
        query_results=query_results,
        query_errors=query_errors,
        query_catalog=QUERY_CATALOG,
        derived=derived,
    )
