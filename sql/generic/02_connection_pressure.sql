SELECT
  count(*) AS total_connections,
  count(*) FILTER (WHERE state = 'active') AS active_connections,
  count(*) FILTER (WHERE state = 'idle') AS idle_connections,
  count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_txn_connections,
  count(*) FILTER (WHERE wait_event IS NOT NULL) AS waiting_connections,
  count(*) FILTER (WHERE backend_type = 'client backend') AS client_backends
FROM pg_stat_activity;

