# PostgreSQL Memory & Storage Diagnostics

Python tooling and query packs for diagnosing PostgreSQL **memory and storage**
problems on self-managed Postgres plus managed PostgreSQL on **AWS RDS/Aurora
PostgreSQL** and **Google Cloud SQL for PostgreSQL** — including connections
through the **Cloud SQL Auth Proxy**.

The project produces a **plain-language HTML report** designed so *any* database
user (not just a PostgreSQL expert) can read it. Every finding includes:

- an **executive summary** with an overall health verdict and severity counts
- a "**What this means**" plain-language explanation
- a "**What to do**" recommendation
- the evidence behind the finding and suggested follow-up SQL
- links to authoritative PostgreSQL / AWS / Google Cloud references
- a **storage & memory at-a-glance** section with size bars and cache-hit ratios
- a **glossary** of PostgreSQL terms used in the report

## What this repository covers

The tool focuses on practical diagnosis areas that are safe to inspect from SQL.

**Memory**

- shared memory configuration (`shared_buffers`, `huge_pages`, `effective_cache_size`)
- per-session and per-operation memory risk (`work_mem`, `hash_mem_multiplier`, `temp_buffers`)
- maintenance memory (`maintenance_work_mem`, `autovacuum_work_mem`)
- connection pressure and idle connection waste
- temp file spill indicators from `pg_stat_database`
- cache hit ratio across databases

**Storage**

- database sizes and where storage is concentrated
- largest relations on disk (table + indexes + TOAST)
- estimated table bloat with a no-extension, statistics-based estimate
- `temp_file_limit` safety check (uncapped temp spill can fill the disk)
- WAL and checkpoint configuration visibility

**MVCC & maintenance**

- table-level dead-tuple, stale-statistics, and access-pattern analysis
- MVCC blocker analysis for long-running transactions and replication-slot retention risk
- vacuum progress and autovacuum visibility
- index usage checks for common inefficiency patterns

**Optional, extension-powered**

- buffer/cache visibility when `pg_buffercache` is available
- query spill indicators when `pg_stat_statements` is available
- accurate tuple-level bloat checks when `pgstattuple` is available

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
│   ├── analysis.py        # turns a snapshot into prioritized findings
│   ├── catalog.py         # the SQL diagnostic queries
│   ├── cli.py             # command-line entry point
│   ├── collector.py       # live snapshot collection
│   ├── connection.py      # DSN builder incl. Cloud SQL Auth Proxy
│   ├── html_report.py     # plain-language HTML report renderer
│   ├── knowledge.py       # explanations, recommendations, glossary
│   └── models.py
└── tests/
    ├── test_analysis.py
    ├── test_connection.py
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

### 3. Connect through the Cloud SQL Auth Proxy

The [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/connect-auth-proxy)
opens a secure, IAM-authenticated tunnel to a Cloud SQL instance. Start it first,
then point the tool at it with `--cloudsql-proxy` instead of building a DSN by hand.

**TCP mode** (the proxy listens on `127.0.0.1:5432`; it encrypts the hop itself,
so `sslmode=disable` is used for the local link):

```bash
# Terminal 1: start the proxy
./cloud-sql-proxy MY_PROJECT:us-central1:pg-main

# Terminal 2: run diagnostics against the local proxy port
uv run pg-memory-diagnostics \
  --cloudsql-proxy \
  --cloudsql-proxy-mode tcp \
  --db-user reporter \
  --db-password "$PGPASSWORD" \
  --db-name appdb \
  --cloud gcp \
  --instance-memory-gib 32 \
  --output reports/gcp-prod.html
```

**Unix socket mode** (common in Cloud Run / GKE, where the proxy creates
`/cloudsql/INSTANCE_CONNECTION_NAME`):

```bash
# Terminal 1: start the proxy with a Unix socket
./cloud-sql-proxy --unix-socket /cloudsql MY_PROJECT:us-central1:pg-main

# Terminal 2: run diagnostics over the socket
uv run pg-memory-diagnostics \
  --cloudsql-proxy \
  --cloudsql-proxy-mode unix \
  --cloudsql-instance MY_PROJECT:us-central1:pg-main \
  --db-user reporter \
  --db-name appdb \
  --cloud gcp \
  --instance-memory-gib 32 \
  --output reports/gcp-prod.html
```

The `INSTANCE_CONNECTION_NAME` uses the `project:region:instance` format. You can
also drive any of these from environment variables (see below).

### 4. Optional: save a raw snapshot for offline review

```bash
uv run pg-memory-diagnostics \
  --dsn "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require" \
  --cloud aws \
  --instance-memory-gib 16 \
  --snapshot-out reports/aws-prod-memory.json \
  --output reports/aws-prod-memory.html
```

### 5. Generate HTML from a saved snapshot

```bash
uv run pg-memory-diagnostics \
  --snapshot-in examples/sample_snapshot.json \
  --cloud gcp \
  --instance-memory-gib 32 \
  --output reports/sample.html
```

## CLI options

```text
--dsn                    PostgreSQL DSN for live collection
--snapshot-in            Load a previously saved JSON snapshot
--snapshot-out           Save collected live data to JSON
--cloud                  generic | aws | gcp
--instance-memory-gib    Total instance memory in GiB for ratio-based heuristics
--output                 HTML report path
--app-name               PostgreSQL application_name used for collection

Cloud SQL Auth Proxy:
--cloudsql-proxy         Build the DSN for a locally running Cloud SQL Auth Proxy
--cloudsql-proxy-mode    tcp (default) | unix
--cloudsql-instance      INSTANCE_CONNECTION_NAME (project:region:instance), required for unix mode
--cloudsql-proxy-host    Host the TCP proxy listens on (default 127.0.0.1)
--cloudsql-proxy-port    Port the proxy listens on (default 5432)
--cloudsql-socket-dir    Directory the Unix-socket proxy uses (default /cloudsql)
--db-user                Database user (proxy mode)
--db-password            Database password (proxy mode)
--db-name                Database name (proxy mode)
```

Provide exactly one connection source: `--dsn`, `--snapshot-in`, or `--cloudsql-proxy`.

Equivalent environment variables are also supported:

```text
PGMD_DSN
PGMD_CLOUD
PGMD_INSTANCE_MEMORY_GIB
PGMD_OUTPUT
PGMD_SNAPSHOT_IN
PGMD_SNAPSHOT_OUT
PGMD_APP_NAME

PGMD_CLOUDSQL_PROXY          (1/true/yes/on)
PGMD_CLOUDSQL_PROXY_MODE     (tcp | unix)
PGMD_CLOUDSQL_INSTANCE
PGMD_CLOUDSQL_PROXY_HOST
PGMD_CLOUDSQL_PROXY_PORT
PGMD_CLOUDSQL_SOCKET_DIR
PGMD_DB_USER
PGMD_DB_PASSWORD
PGMD_DB_NAME
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
- Connect through the **Cloud SQL Auth Proxy** with `--cloudsql-proxy` (TCP or Unix-socket mode). The proxy encrypts the connection itself, so the tool uses `sslmode=disable` for the local hop, as Google recommends.

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
