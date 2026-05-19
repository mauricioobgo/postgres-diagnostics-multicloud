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

