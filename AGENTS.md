# AGENTS

## Repository purpose

This repository is for **PostgreSQL diagnosis focused on memory, MVCC health, and table-level operational issues**.

Primary targets:

- PostgreSQL on AWS RDS / Aurora PostgreSQL
- PostgreSQL on Google Cloud SQL
- Generic PostgreSQL deployments when only SQL-level evidence is available

## Engineering expectations

- Use **uv** for Python workflows.
- Keep configuration in `pyproject.toml`.
- Prefer SQL-first evidence that works in managed PostgreSQL environments.
- When adding new diagnostics, include:
  - the SQL used to collect data
  - analysis logic
  - HTML report rendering
  - README updates
  - tests where practical

## Diagnostic scope

The tool should continue to cover:

- memory settings and connection-driven memory risk
- table-level dead tuple and stale statistics analysis
- MVCC blockers such as long-running transactions and idle-in-transaction sessions
- autovacuum visibility and vacuum progress
- temp spill behavior
- index usage and table access patterns
- optional deeper checks with `pg_stat_statements`, `pg_buffercache`, and `pgstattuple`

## Guardrails

- Avoid claiming host-level memory facts that SQL cannot prove in managed services.
- Mark extension-dependent diagnostics clearly.
- Prefer conservative heuristics and label them as estimates.
- Keep AWS- and GCP-specific advice tied to service limitations or parameter behavior.

