-- Largest relations on disk, including indexes and TOAST. Large relations
-- concentrate vacuum cost, bloat risk, and slow scans.
SELECT
  n.nspname AS schema_name,
  c.relname AS relation_name,
  c.relkind AS relation_kind,
  pg_total_relation_size(c.oid) AS total_bytes,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS total_pretty,
  pg_table_size(c.oid) AS table_bytes,
  pg_indexes_size(c.oid) AS index_bytes,
  (pg_total_relation_size(c.oid) - pg_table_size(c.oid) - pg_indexes_size(c.oid)) AS toast_bytes
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'm', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 25;
