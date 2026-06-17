"""Plain-language knowledge base for findings and PostgreSQL terminology.

The goal of this module is to make the report readable by *any* database user,
not only PostgreSQL experts. Each finding id maps to a short, jargon-light
explanation of what the signal means and a concrete recommendation for what to
do next. A glossary explains the terms that show up throughout the report.

Sources informing this guidance:
- PostgreSQL documentation: Routine Vacuuming, Cumulative Statistics, Resource
  Consumption (memory), WAL configuration.
- AWS RDS/Aurora PostgreSQL: diagnosing table and index bloat.
- Google Cloud SQL for PostgreSQL: connection management and the Cloud SQL Auth
  Proxy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FindingGuidance:
    category: str
    plain_explanation: str
    recommendation: str
    references: tuple[str, ...] = ()


_PG_MEM = "PostgreSQL docs: Resource Consumption (Memory) — https://www.postgresql.org/docs/current/runtime-config-resource.html"
_PG_VACUUM = "PostgreSQL docs: Routine Vacuuming — https://www.postgresql.org/docs/current/routine-vacuuming.html"
_PG_STATS = "PostgreSQL docs: Cumulative Statistics System — https://www.postgresql.org/docs/current/monitoring-stats.html"
_PG_WAL = "PostgreSQL docs: Write-Ahead Logging — https://www.postgresql.org/docs/current/wal-configuration.html"
_AWS_BLOAT = "AWS: Diagnosing table and index bloat — https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.diag-table-ind-bloat.html"
_GCP_CONN = "Google Cloud SQL: Manage connections — https://cloud.google.com/sql/docs/postgres/manage-connections"


# Keyed by Finding.id. Dynamic ids (e.g. "query-error-...") fall back to
# prefix matching in `guidance_for`.
FINDING_GUIDANCE: dict[str, FindingGuidance] = {
    "shared-buffers-low": FindingGuidance(
        category="memory",
        plain_explanation=(
            "shared_buffers is the pool of RAM PostgreSQL uses to cache table and "
            "index data. When it is small relative to the instance, PostgreSQL has "
            "to read from disk more often, which slows queries down."
        ),
        recommendation=(
            "A common starting point is roughly 25% of instance memory. Increase "
            "shared_buffers gradually and re-measure the cache hit ratio rather than "
            "jumping straight to a large value."
        ),
        references=(_PG_MEM,),
    ),
    "shared-buffers-high": FindingGuidance(
        category="memory",
        plain_explanation=(
            "shared_buffers is large compared to total memory. PostgreSQL also "
            "relies on the operating system's file cache and needs headroom for "
            "connections, sorts, and maintenance. Too-large shared_buffers can "
            "starve those other needs."
        ),
        recommendation=(
            "Keep shared_buffers in a balanced range (often ~25%, rarely above 40% "
            "of RAM) and leave memory for the OS cache and per-connection work."
        ),
        references=(_PG_MEM,),
    ),
    "max-connections-high": FindingGuidance(
        category="connections",
        plain_explanation=(
            "Every connection reserves backend memory even when idle. A very high "
            "max_connections usually means the application is not using a connection "
            "pooler, which multiplies memory risk under load."
        ),
        recommendation=(
            "Put a pooler (PgBouncer, RDS Proxy, or Cloud SQL connection pooling) in "
            "front of PostgreSQL and lower max_connections to a value the instance "
            "memory can actually support."
        ),
        references=(_GCP_CONN,),
    ),
    "idle-connections": FindingGuidance(
        category="connections",
        plain_explanation=(
            "Many sessions are connected but doing nothing. Idle sessions still hold "
            "backend memory and a connection slot, which is wasteful and can crowd "
            "out real work."
        ),
        recommendation=(
            "Use a connection pooler, lower the application pool size, and confirm "
            "the app returns connections promptly instead of holding them open."
        ),
        references=(_GCP_CONN,),
    ),
    "idle-in-transaction": FindingGuidance(
        category="connections",
        plain_explanation=(
            "Sessions are sitting inside an open transaction without doing work. "
            "Open transactions hold a snapshot that prevents VACUUM from cleaning up "
            "dead rows, so they directly cause bloat and table growth."
        ),
        recommendation=(
            "Find the responsible application code and commit/rollback promptly. Set "
            "idle_in_transaction_session_timeout so the server reaps these "
            "automatically."
        ),
        references=(_PG_VACUUM,),
    ),
    "idle-in-txn-timeout-disabled": FindingGuidance(
        category="config",
        plain_explanation=(
            "There is no server-side timeout to clean up sessions that are stuck "
            "inside a transaction, so a misbehaving client can block cleanup "
            "indefinitely."
        ),
        recommendation=(
            "Set idle_in_transaction_session_timeout (for example 5–15 minutes) so "
            "abandoned transactions cannot hold snapshots forever."
        ),
        references=(_PG_VACUUM,),
    ),
    "work-mem-risk": FindingGuidance(
        category="memory",
        plain_explanation=(
            "work_mem is the memory budget for each sort or hash *operation*. A "
            "single query can use it several times, and every connection can run "
            "queries at once, so a large work_mem multiplied by many connections is "
            "a big memory envelope."
        ),
        recommendation=(
            "Keep a modest global work_mem and raise it only for specific heavy "
            "queries/sessions with SET. Reduce max_connections via pooling so the "
            "worst-case total stays within instance memory."
        ),
        references=(_PG_MEM,),
    ),
    "potential-overcommit": FindingGuidance(
        category="memory",
        plain_explanation=(
            "Adding up shared_buffers, maintenance memory, and the worst-case "
            "per-connection working memory exceeds the instance's RAM. This is a "
            "deliberately pessimistic estimate, but it shows there is little safety "
            "margin under concurrent load."
        ),
        recommendation=(
            "Lower max_connections (pooling), reduce global work_mem, or move to a "
            "larger instance. Re-run after changes to confirm the envelope fits."
        ),
        references=(_PG_MEM,),
    ),
    "temp-spills": FindingGuidance(
        category="memory",
        plain_explanation=(
            "PostgreSQL wrote temporary files to disk because sorts, hashes, or "
            "maintenance work did not fit in memory. Spilling to disk is much slower "
            "than working in RAM and is a classic symptom of low work_mem or "
            "inefficient queries."
        ),
        recommendation=(
            "Identify the spilling statements (pg_stat_statements), add indexes or "
            "rewrite them, and raise work_mem for those specific operations. Set "
            "temp_file_limit to cap runaway temp usage."
        ),
        references=(_PG_MEM, _PG_STATS),
    ),
    "table-dead-tuples": FindingGuidance(
        category="maintenance",
        plain_explanation=(
            "PostgreSQL keeps old versions of rows ('dead tuples') until VACUUM "
            "removes them. A high dead-tuple ratio means VACUUM is falling behind, "
            "which wastes storage, bloats tables, and slows scans."
        ),
        recommendation=(
            "Make autovacuum more aggressive on hot tables (lower "
            "autovacuum_vacuum_scale_factor, raise autovacuum_work_mem/cost limits) "
            "and remove anything blocking cleanup such as long transactions or stale "
            "replication slots."
        ),
        references=(_PG_VACUUM, _AWS_BLOAT),
    ),
    "stale-analyze-stats": FindingGuidance(
        category="maintenance",
        plain_explanation=(
            "The planner relies on table statistics to choose good query plans. Many "
            "changes since the last ANALYZE means the planner may be working from "
            "outdated information and picking slow plans."
        ),
        recommendation=(
            "Run ANALYZE on the affected tables and tune autovacuum's analyze "
            "thresholds so statistics refresh more often on busy tables."
        ),
        references=(_PG_STATS,),
    ),
    "low-hot-update-ratio": FindingGuidance(
        category="maintenance",
        plain_explanation=(
            "A HOT update avoids touching indexes when a row changes. A low HOT ratio "
            "means updates are churning indexes and creating extra bloat and write "
            "I/O."
        ),
        recommendation=(
            "Lower the table's fillfactor to leave room for in-page updates, avoid "
            "updating indexed columns when possible, and drop unused indexes on "
            "write-heavy tables."
        ),
        references=(_PG_VACUUM,),
    ),
    "mvcc-blocker-long-xact": FindingGuidance(
        category="maintenance",
        plain_explanation=(
            "A long-running transaction is holding an old snapshot. Until it ends, "
            "VACUUM cannot remove dead rows newer than that snapshot anywhere in the "
            "database, so bloat accumulates across tables."
        ),
        recommendation=(
            "Track down and end the long transaction, batch large jobs into shorter "
            "transactions, and set statement/transaction timeouts to bound them."
        ),
        references=(_PG_VACUUM,),
    ),
    "replication-slot-retention": FindingGuidance(
        category="storage",
        plain_explanation=(
            "An inactive or lagging replication slot is pinning old row versions and "
            "WAL so they cannot be removed. This both bloats tables and can fill the "
            "disk with retained WAL."
        ),
        recommendation=(
            "Drop replication slots that are no longer used, or fix the consumer that "
            "is behind. Consider max_slot_wal_keep_size to cap WAL retention."
        ),
        references=(_PG_WAL, _PG_VACUUM),
    ),
    "unused-large-index": FindingGuidance(
        category="storage",
        plain_explanation=(
            "A large index is never (or almost never) used for reads, yet every "
            "INSERT/UPDATE/DELETE must still maintain it. It wastes storage and cache "
            "and slows down writes."
        ),
        recommendation=(
            "Confirm it is unused across the whole workload (including replicas), "
            "then DROP INDEX CONCURRENTLY. Re-check after a full business cycle so "
            "you do not drop something only used monthly."
        ),
        references=(_AWS_BLOAT, _PG_STATS),
    ),
    "pgstattuple-bloat-signal": FindingGuidance(
        category="storage",
        plain_explanation=(
            "A tuple-level scan found a table where a large share of space is dead "
            "tuples or free space — i.e. real, measured bloat rather than an "
            "estimate."
        ),
        recommendation=(
            "Schedule VACUUM (and for severe cases VACUUM FULL or pg_repack during a "
            "maintenance window) and tune autovacuum so the table does not re-bloat."
        ),
        references=(_AWS_BLOAT, _PG_VACUUM),
    ),
    "table-bloat-estimate": FindingGuidance(
        category="storage",
        plain_explanation=(
            "An estimate based on table statistics suggests a table is using "
            "significantly more space than its live data needs. Bloat wastes disk and "
            "makes scans read more pages than necessary."
        ),
        recommendation=(
            "Verify with pgstattuple, then reclaim space with VACUUM, pg_repack, or "
            "VACUUM FULL. Tune autovacuum to keep the table from bloating again."
        ),
        references=(_AWS_BLOAT, _PG_VACUUM),
    ),
    "low-cache-hit-ratio": FindingGuidance(
        category="memory",
        plain_explanation=(
            "The cache hit ratio is the share of block reads served from memory "
            "instead of disk. A low ratio means the working set does not fit in "
            "cache and queries are doing slow disk I/O."
        ),
        recommendation=(
            "Increase shared_buffers and/or instance memory, add indexes so queries "
            "read fewer pages, and confirm effective_cache_size reflects available "
            "OS cache."
        ),
        references=(_PG_MEM, _PG_STATS),
    ),
    "large-database-size": FindingGuidance(
        category="storage",
        plain_explanation=(
            "One database makes up most of the on-disk footprint. That is not a "
            "problem by itself, but it tells you where storage growth and bloat will "
            "have the biggest impact."
        ),
        recommendation=(
            "Watch its growth trend, keep autovacuum healthy on its largest tables, "
            "and make sure provisioned storage has headroom above current usage."
        ),
        references=(_AWS_BLOAT,),
    ),
    "high-disk-relation": FindingGuidance(
        category="storage",
        plain_explanation=(
            "A single relation (table plus its indexes and TOAST) dominates storage. "
            "Large relations are where bloat, vacuum cost, and slow scans concentrate."
        ),
        recommendation=(
            "Confirm its indexes are all used, keep autovacuum aggressive on it, and "
            "consider partitioning if it keeps growing without bound."
        ),
        references=(_AWS_BLOAT, _PG_VACUUM),
    ),
    "temp-file-limit-unset": FindingGuidance(
        category="config",
        plain_explanation=(
            "temp_file_limit is unlimited. A single runaway query that spills to disk "
            "can therefore consume all free storage and take the instance down."
        ),
        recommendation=(
            "Set temp_file_limit to a sane cap so one bad query cannot fill the disk, "
            "while still allowing normal spill-to-disk operations."
        ),
        references=(_PG_MEM,),
    ),
    "maintenance-work-mem-large": FindingGuidance(
        category="memory",
        plain_explanation=(
            "maintenance_work_mem is large. It speeds up VACUUM and index builds, but "
            "each autovacuum worker can use up to autovacuum_work_mem, so several "
            "workers at once can add up."
        ),
        recommendation=(
            "Keep maintenance_work_mem generous but bounded, and set "
            "autovacuum_work_mem explicitly so concurrent workers cannot collectively "
            "exhaust memory."
        ),
        references=(_PG_MEM, _PG_VACUUM),
    ),
    "effective-cache-size-low": FindingGuidance(
        category="config",
        plain_explanation=(
            "effective_cache_size is a hint that tells the planner how much memory is "
            "available for caching. If it is too low, the planner avoids index plans "
            "it should prefer."
        ),
        recommendation=(
            "Set effective_cache_size to roughly 50–75% of instance memory so the "
            "planner makes cache-aware choices. It does not allocate memory; it only "
            "informs planning."
        ),
        references=(_PG_MEM,),
    ),
    "missing-pg-stat-statements": FindingGuidance(
        category="config",
        plain_explanation=(
            "pg_stat_statements records per-query statistics. Without it, the report "
            "cannot point at the specific queries causing spills or heavy I/O."
        ),
        recommendation=(
            "Enable the pg_stat_statements extension (it is available on RDS/Aurora "
            "and Cloud SQL) to unlock query-level diagnostics."
        ),
        references=(_PG_STATS,),
    ),
    "missing-pg-buffercache": FindingGuidance(
        category="config",
        plain_explanation=(
            "pg_buffercache shows which relations occupy the shared buffer cache. "
            "Without it, the report cannot attribute cache usage to specific tables."
        ),
        recommendation=(
            "Install the pg_buffercache extension to see what is actually resident in "
            "the buffer cache."
        ),
        references=(_PG_MEM,),
    ),
    "missing-pgstattuple": FindingGuidance(
        category="config",
        plain_explanation=(
            "pgstattuple measures real dead-tuple and free-space ratios. Without it, "
            "bloat can only be estimated, not measured."
        ),
        recommendation=(
            "Install the pgstattuple extension for accurate, tuple-level bloat "
            "inspection on suspect tables."
        ),
        references=(_AWS_BLOAT,),
    ),
}


_QUERY_ERROR_GUIDANCE = FindingGuidance(
    category="config",
    plain_explanation=(
        "One diagnostic query could not run. On managed services (RDS/Aurora, Cloud "
        "SQL) this is usually a permission limit or a hidden system view rather than "
        "a real database problem."
    ),
    recommendation=(
        "Check that the reporting role has pg_monitor (or equivalent) privileges. "
        "The rest of the report is still valid."
    ),
)


def guidance_for(finding_id: str) -> FindingGuidance | None:
    if finding_id in FINDING_GUIDANCE:
        return FINDING_GUIDANCE[finding_id]
    if finding_id.startswith("query-error-"):
        return _QUERY_ERROR_GUIDANCE
    return None


# Glossary rendered at the bottom of the report so non-experts can follow along.
GLOSSARY: list[tuple[str, str]] = [
    ("MVCC", "Multi-Version Concurrency Control. PostgreSQL keeps multiple versions of a row so readers never block writers. Old versions become 'dead tuples' that VACUUM later removes."),
    ("Dead tuple", "An obsolete row version left behind by an UPDATE or DELETE. Dead tuples are reclaimed by VACUUM; if they pile up, the table bloats."),
    ("Bloat", "Disk space occupied by dead tuples and unused free space inside tables and indexes. Bloat wastes storage and forces scans to read more pages."),
    ("VACUUM / autovacuum", "The background process that removes dead tuples and refreshes free space. Autovacuum runs it automatically based on table activity."),
    ("shared_buffers", "The block of RAM PostgreSQL uses as its own data cache. Reads served from here avoid going to disk."),
    ("work_mem", "Memory budget for a single sort or hash operation. Exceeding it makes the operation spill to temporary files on disk."),
    ("Cache hit ratio", "The fraction of block reads served from memory instead of disk. Higher is better; low values mean the working set does not fit in cache."),
    ("Temp files / spill", "Temporary files PostgreSQL writes when an operation exceeds work_mem. Spilling to disk is far slower than staying in memory."),
    ("WAL", "Write-Ahead Log. PostgreSQL records every change here first for durability and replication. Retained WAL consumes disk."),
    ("Replication slot", "A marker that guarantees WAL and row versions are kept until a replica or consumer reads them. An abandoned slot can fill the disk and block cleanup."),
    ("TOAST", "The mechanism that stores oversized column values out-of-line in a side table. TOAST data counts toward a table's total size."),
    ("HOT update", "A 'Heap-Only Tuple' update that changes a row without updating its indexes, reducing index bloat and write I/O."),
    ("Cloud SQL Auth Proxy", "A Google-provided helper that opens a secure, IAM-authenticated tunnel to a Cloud SQL instance over a local TCP port or Unix socket."),
]
