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

