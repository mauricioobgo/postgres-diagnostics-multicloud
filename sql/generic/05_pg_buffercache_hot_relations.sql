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

