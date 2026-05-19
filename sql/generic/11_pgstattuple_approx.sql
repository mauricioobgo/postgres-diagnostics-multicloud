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

