-- Cache hit ratio by database: the share of block reads served from memory
-- instead of disk. Low values mean the working set does not fit in cache.
SELECT
  datname AS database_name,
  blks_read,
  blks_hit,
  round(100 * blks_hit::numeric / NULLIF(blks_hit + blks_read, 0), 2) AS cache_hit_pct,
  temp_files,
  temp_bytes,
  deadlocks
FROM pg_stat_database
WHERE datname IS NOT NULL
ORDER BY (blks_hit + blks_read) DESC NULLS LAST;
