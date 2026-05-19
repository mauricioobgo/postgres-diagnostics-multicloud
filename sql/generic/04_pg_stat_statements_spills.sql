SELECT
  queryid,
  calls,
  temp_blks_read,
  temp_blks_written,
  round(((temp_blks_read + temp_blks_written) * current_setting('block_size')::numeric) / 1024 / 1024, 2) AS temp_mb,
  left(regexp_replace(query, '\\s+', ' ', 'g'), 240) AS query
FROM pg_stat_statements
WHERE temp_blks_read > 0 OR temp_blks_written > 0
ORDER BY (temp_blks_read + temp_blks_written) DESC
LIMIT 25;

