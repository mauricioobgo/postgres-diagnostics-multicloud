# PostgreSQL Memory Diagnostics

Python tooling and query packs for diagnosing PostgreSQL memory pressure on self-managed Postgres plus managed PostgreSQL on **AWS RDS/Aurora PostgreSQL** and **Google Cloud SQL for PostgreSQL**.

The project produces an **HTML report** with:

- collected runtime settings and memory-adjacent statistics
- prioritized findings
- estimated memory-risk calculations
- table-level health checks
- MVCC and autovacuum risk checks
- cloud-specific notes for AWS and GCP
- suggested follow-up SQL for deeper investigation

## What this repository covers

The tool focuses on practical memory diagnosis areas that are safe to inspect from SQL:

- shared memory configuration (`shared_buffers`, `huge_pages`)
- per-session and per-operation memory risk (`work_mem`, `hash_mem_multiplier`, `temp_buffers`)
- maintenance memory (`maintenance_work_mem`, `autovacuum_work_mem`)
- connection pressure and idle connection waste
- temp file spill indicators from `pg_stat_database`
- table-level dead-tuple, stale-statistics, and access-pattern analysis
- MVCC blocker analysis for long-running transactions and replication-slot retention risk
- vacuum progress and autovacuum visibility
- index usage checks for common inefficiency patterns
- buffer/cache visibility when `pg_buffercache` is available
- query spill indicators when `pg_stat_statements` is available
- approximate tuple-level bloat checks when `pgstattuple` is available

## Repository layout

```text
postgres-memory-diagnostics/
├── pyproject.toml
├── README.md
├── examples/
│   └── sample_snapshot.json
├── sql/
│   ├── aws/
│   ├── gcp/
│   └── generic/
├── src/pg_memory_diagnostics/
│   ├── analysis.py
│   ├── catalog.py
│   ├── cli.py
│   ├── collector.py
│   ├── html_report.py
│   └── models.py
└── tests/
    ├── test_analysis.py
    └── test_html_report.py
```

## Quick start

### 1. Create a virtual environment with uv

```bash
uv venv
source .venv/bin/activate
uv sync
```

You can also configure the tool with environment variables:

```bash
cp .env.example .env
```

### 2. Run against a live database

```bash
uv run pg-memory-diagnostics \
  --dsn "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require" \
  --cloud aws \
  --instance-memory-gib 16 \
  --output reports/aws-prod-memory.html
```

For Google Cloud SQL:

```bash
uv run pg-memory-diagnostics \
  --dsn "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require" \
  --cloud gcp \
  --instance-memory-gib 32 \
  --output reports/gcp-prod-memory.html
```

### 3. Optional: save a raw snapshot for offline review

```bash
uv run pg-memory-diagnostics \
  --dsn "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require" \
  --cloud aws \
  --instance-memory-gib 16 \
  --snapshot-out reports/aws-prod-memory.json \
  --output reports/aws-prod-memory.html
```

### 4. Generate HTML from a saved snapshot

```bash
uv run pg-memory-diagnostics \
  --snapshot-in examples/sample_snapshot.json \
  --cloud gcp \
  --instance-memory-gib 32 \
  --output reports/sample.html
```

## CLI options

```text
--dsn                  PostgreSQL DSN for live collection
--snapshot-in          Load a previously saved JSON snapshot
--snapshot-out         Save collected live data to JSON
--cloud                generic | aws | gcp
--instance-memory-gib  Total instance memory in GiB for ratio-based heuristics
--output               HTML report path
--app-name             PostgreSQL application_name used for collection
```

Equivalent environment variables are also supported:

```text
PGMD_DSN
PGMD_CLOUD
PGMD_INSTANCE_MEMORY_GIB
PGMD_OUTPUT
PGMD_SNAPSHOT_IN
PGMD_SNAPSHOT_OUT
PGMD_APP_NAME
```

## Diagnostics added for table-level and MVCC analysis

The report now includes SQL-driven checks for:

- dead tuples and dead-tuple ratio estimates from `pg_stat_user_tables`
- stale planner statistics via `n_mod_since_analyze`, `last_analyze`, and `last_autoanalyze`
- HOT-vs-non-HOT update behavior using `n_tup_hot_upd` and `n_tup_newpage_upd`
- long-running and idle-in-transaction sessions from `pg_stat_activity`
- replication slot cleanup blockers from `pg_replication_slots`
- currently running vacuum activity from `pg_stat_progress_vacuum`
- unused/underused indexes from `pg_stat_user_indexes`
- optional tuple-level bloat estimates with `pgstattuple_approx`

These areas matter because PostgreSQL uses MVCC, meaning updates and deletes create row-version churn that must later be reclaimed by vacuuming and tracked by statistics. Poor vacuum/analyze hygiene, long-lived transactions, and spill-heavy queries are among the most common operational problems in busy PostgreSQL systems.

## Notes for managed PostgreSQL

### AWS RDS / Aurora PostgreSQL

- The report highlights connection pressure and parameter interactions that commonly surface through RDS/Aurora parameter groups.
- Temporary-file investigation is a first-class part of the report because spill-heavy workloads are a common performance and memory symptom in RDS and Aurora PostgreSQL.
- Some host-level memory evidence is intentionally unavailable from SQL in managed services; the report labels those gaps instead of guessing.

### Google Cloud SQL for PostgreSQL

- The report highlights Cloud SQL-friendly SQL diagnostics and flags where the service hides operating-system memory details.
- The report emphasizes idle connection waste and connection ceilings because managed PostgreSQL memory budgets are often harmed more by connection behavior than by a single tuning flag.
- Supply `--instance-memory-gib` so the tool can make stronger ratio-based recommendations.

## Limits

- PostgreSQL does **not** expose full per-process resident memory from plain SQL.
- Worst-case `work_mem` calculations are intentionally conservative and can significantly overstate real usage.
- Optional extensions materially improve the report:
  - `pg_stat_statements`
  - `pg_buffercache`
  - `pgstattuple`

## Validation

Run the included tests:

```bash
uv run -- python -m unittest discover -s tests -v
uv run -- python -m compileall src
uv run pg-memory-diagnostics --snapshot-in examples/sample_snapshot.json --cloud aws --instance-memory-gib 16 --output reports/sample-report.html
```

## Research basis

The repository design follows current official guidance around PostgreSQL MVCC, routine vacuuming, cumulative statistics views, tuple-level dead-space inspection, and managed-service memory diagnostics for AWS RDS/Aurora PostgreSQL and Google Cloud SQL.
