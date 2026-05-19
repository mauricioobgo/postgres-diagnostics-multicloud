from __future__ import annotations

from pg_memory_diagnostics.models import QuerySpec


QUERY_CATALOG: dict[str, QuerySpec] = {
    "server_identity": QuerySpec(
        key="server_identity",
        title="Server identity",
        description="Basic database identity and uptime context.",
        sql="""
        SELECT
          now() AT TIME ZONE 'UTC' AS collected_at,
          current_database() AS database_name,
          current_user AS current_user,
          version() AS server_version,
          pg_is_in_recovery() AS recovery_state,
          pg_postmaster_start_time() AS postmaster_start_time;
        """.strip(),
    ),
    "settings": QuerySpec(
        key="settings",
        title="Memory-related settings",
        description="Core PostgreSQL configuration affecting memory behavior.",
        sql="""
        SELECT
          name,
          setting,
          unit,
          boot_val,
          source,
          short_desc
        FROM pg_settings
        WHERE name IN (
          'shared_buffers',
          'work_mem',
          'maintenance_work_mem',
          'autovacuum_work_mem',
          'autovacuum_vacuum_threshold',
          'autovacuum_vacuum_scale_factor',
          'autovacuum_analyze_threshold',
          'autovacuum_analyze_scale_factor',
          'temp_buffers',
          'effective_cache_size',
          'max_connections',
          'hash_mem_multiplier',
          'max_worker_processes',
          'max_parallel_workers',
          'max_parallel_workers_per_gather',
          'max_parallel_maintenance_workers',
          'idle_in_transaction_session_timeout',
          'temp_file_limit',
          'huge_pages'
        )
        ORDER BY name;
        """.strip(),
    ),
    "connection_summary": QuerySpec(
        key="connection_summary",
        title="Connection summary",
        description="Connection counts and session state distribution.",
        sql="""
        SELECT
          count(*) AS total_connections,
          count(*) FILTER (WHERE state = 'active') AS active_connections,
          count(*) FILTER (WHERE state = 'idle') AS idle_connections,
          count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_txn_connections,
          count(*) FILTER (WHERE wait_event IS NOT NULL) AS waiting_connections,
          count(*) FILTER (WHERE backend_type = 'client backend') AS client_backends
        FROM pg_stat_activity;
        """.strip(),
    ),
    "database_temp": QuerySpec(
        key="database_temp",
        title="Temporary file usage by database",
        description="Temp-file activity is a strong signal for sort/hash spill pressure.",
        sql="""
        SELECT
          datname AS database_name,
          temp_files,
          temp_bytes
        FROM pg_stat_database
        ORDER BY temp_bytes DESC NULLS LAST;
        """.strip(),
    ),
    "extensions": QuerySpec(
        key="extensions",
        title="Installed extensions",
        description="Discovers optional observability extensions.",
        sql="SELECT extname FROM pg_extension ORDER BY extname;",
    ),
    "table_health": QuerySpec(
        key="table_health",
        title="Table health overview",
        description="Dead tuples, stale statistics, HOT update ratio, and table size by relation.",
        sql="""
        SELECT
          st.schemaname AS schema_name,
          st.relname AS table_name,
          pg_total_relation_size(st.relid) AS table_bytes,
          st.n_live_tup AS live_rows_est,
          st.n_dead_tup AS dead_rows_est,
          round(100 * st.n_dead_tup::numeric / NULLIF(st.n_live_tup + st.n_dead_tup, 0), 2) AS dead_row_pct_est,
          st.n_mod_since_analyze AS mod_since_analyze,
          st.n_ins_since_vacuum AS ins_since_vacuum,
          round(100 * st.n_tup_hot_upd::numeric / NULLIF(st.n_tup_upd, 0), 2) AS hot_update_pct,
          st.last_vacuum,
          st.last_autovacuum,
          st.last_analyze,
          st.last_autoanalyze
        FROM pg_stat_user_tables st
        ORDER BY st.n_dead_tup DESC, pg_total_relation_size(st.relid) DESC
        LIMIT 50;
        """.strip(),
    ),
    "long_running_transactions": QuerySpec(
        key="long_running_transactions",
        title="Long-running transactions",
        description="MVCC blockers and long-lived transaction snapshots from pg_stat_activity.",
        sql="""
        SELECT
          pid,
          application_name,
          usename,
          state,
          age(clock_timestamp(), xact_start) AS xact_age,
          age(backend_xmin) AS backend_xmin_age,
          age(clock_timestamp(), query_start) AS query_age,
          wait_event_type,
          wait_event,
          left(regexp_replace(query, '\\s+', ' ', 'g'), 240) AS query
        FROM pg_stat_activity
        WHERE xact_start IS NOT NULL
        ORDER BY age(clock_timestamp(), xact_start) DESC
        LIMIT 25;
        """.strip(),
    ),
    "replication_slot_health": QuerySpec(
        key="replication_slot_health",
        title="Replication slot health",
        description="Replication slots with old xmin/catalog_xmin can block cleanup and retain MVCC history longer than expected.",
        sql="""
        SELECT
          slot_name,
          slot_type,
          active,
          restart_lsn,
          wal_status,
          CASE WHEN xmin IS NOT NULL THEN age(xmin) END AS xmin_age,
          CASE WHEN catalog_xmin IS NOT NULL THEN age(catalog_xmin) END AS catalog_xmin_age
        FROM pg_replication_slots
        ORDER BY GREATEST(COALESCE(age(xmin), 0), COALESCE(age(catalog_xmin), 0)) DESC, slot_name;
        """.strip(),
    ),
    "vacuum_progress": QuerySpec(
        key="vacuum_progress",
        title="Vacuum progress",
        description="Currently running VACUUM workers and progress counters.",
        sql="""
        SELECT
          p.pid,
          n.nspname AS schema_name,
          c.relname AS table_name,
          p.phase,
          p.heap_blks_total,
          p.heap_blks_scanned,
          p.heap_blks_vacuumed,
          p.index_vacuum_count,
          p.max_dead_tuples,
          p.num_dead_tuples
        FROM pg_stat_progress_vacuum p
        JOIN pg_class c ON c.oid = p.relid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        ORDER BY p.pid;
        """.strip(),
    ),
    "index_usage": QuerySpec(
        key="index_usage",
        title="Index usage overview",
        description="Large indexes with little or no usage are common sources of write amplification and wasted cache space.",
        sql="""
        SELECT
          s.schemaname AS schema_name,
          s.relname AS table_name,
          s.indexrelname AS index_name,
          pg_relation_size(s.indexrelid) AS index_bytes,
          s.idx_scan,
          s.idx_tup_read,
          s.idx_tup_fetch
        FROM pg_stat_user_indexes s
        ORDER BY s.idx_scan ASC, pg_relation_size(s.indexrelid) DESC
        LIMIT 50;
        """.strip(),
    ),
    "pg_stat_statements_memory": QuerySpec(
        key="pg_stat_statements_memory",
        title="Spill-heavy statements",
        description="Shows statements with temp block usage from pg_stat_statements.",
        optional_extension="pg_stat_statements",
        sql="""
        SELECT
          queryid,
          calls,
          temp_blks_read,
          temp_blks_written,
          round(((temp_blks_read + temp_blks_written) * current_setting('block_size')::numeric) / 1024 / 1024, 2) AS temp_mb,
          left(regexp_replace(query, '\\s+', ' ', 'g'), 240) AS query
        FROM pg_stat_statements
        WHERE temp_blks_read > 0 OR temp_blks_written > 0
        ORDER BY (temp_blks_read + temp_blks_written) DESC
        LIMIT 25;
        """.strip(),
    ),
    "pg_buffercache_top_relations": QuerySpec(
        key="pg_buffercache_top_relations",
        title="Top relations in buffer cache",
        description="Highlights relations occupying the shared buffer cache.",
        optional_extension="pg_buffercache",
        sql="""
        SELECT
          n.nspname AS schema_name,
          c.relname AS relation_name,
          count(*) AS buffers,
          round(count(*) * current_setting('block_size')::numeric / 1024 / 1024, 2) AS buffer_mb
        FROM pg_buffercache b
        JOIN pg_class c ON b.relfilenode = pg_relation_filenode(c.oid)
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE b.reldatabase IN (0, (SELECT oid FROM pg_database WHERE datname = current_database()))
        GROUP BY n.nspname, c.relname
        ORDER BY buffers DESC
        LIMIT 25;
        """.strip(),
    ),
    "pgstattuple_approx_top_tables": QuerySpec(
        key="pgstattuple_approx_top_tables",
        title="Approximate tuple-level bloat candidates",
        description="Uses pgstattuple_approx to identify tables with dead tuples and free space.",
        optional_extension="pgstattuple",
        sql="""
        SELECT
          n.nspname AS schema_name,
          c.relname AS table_name,
          stats.table_len,
          stats.dead_tuple_percent,
          stats.approx_free_percent
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN LATERAL pgstattuple_approx(c.oid) stats
        WHERE c.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY stats.dead_tuple_percent DESC, stats.table_len DESC
        LIMIT 20;
        """.strip(),
    ),
    "aws_session_breakdown": QuerySpec(
        key="aws_session_breakdown",
        title="AWS session breakdown",
        description="RDS/Aurora-oriented session grouping for app and user hotspots.",
        sql="""
        SELECT
          usename,
          application_name,
          state,
          backend_type,
          count(*) AS sessions
        FROM pg_stat_activity
        GROUP BY usename, application_name, state, backend_type
        ORDER BY sessions DESC, usename, application_name;
        """.strip(),
    ),
    "gcp_session_breakdown": QuerySpec(
        key="gcp_session_breakdown",
        title="Google Cloud SQL session breakdown",
        description="Cloud SQL-friendly breakdown of waiting and application patterns.",
        sql="""
        SELECT
          application_name,
          state,
          wait_event_type,
          wait_event,
          count(*) AS sessions
        FROM pg_stat_activity
        GROUP BY application_name, state, wait_event_type, wait_event
        ORDER BY sessions DESC, application_name;
        """.strip(),
    ),
}


BASE_QUERY_ORDER = [
    "server_identity",
    "settings",
    "connection_summary",
    "database_temp",
    "table_health",
    "long_running_transactions",
    "replication_slot_health",
    "vacuum_progress",
    "index_usage",
    "extensions",
]


CLOUD_QUERY_ORDER: dict[str, list[str]] = {
    "aws": ["aws_session_breakdown"],
    "gcp": ["gcp_session_breakdown"],
    "generic": [],
}


FOLLOW_UP_QUERY_GROUPS: dict[str, list[str]] = {
    "generic": [
        "connection_summary",
        "database_temp",
        "table_health",
        "long_running_transactions",
        "replication_slot_health",
        "vacuum_progress",
        "index_usage",
        "pg_stat_statements_memory",
        "pg_buffercache_top_relations",
        "pgstattuple_approx_top_tables",
    ],
    "aws": [
        "aws_session_breakdown",
        "pg_stat_statements_memory",
        "pg_buffercache_top_relations",
        "pgstattuple_approx_top_tables",
    ],
    "gcp": [
        "gcp_session_breakdown",
        "pg_stat_statements_memory",
        "pg_buffercache_top_relations",
        "pgstattuple_approx_top_tables",
    ],
}
