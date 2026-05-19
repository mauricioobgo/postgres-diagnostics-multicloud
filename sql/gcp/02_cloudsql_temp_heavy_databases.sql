SELECT
  datname AS database_name,
  temp_files,
  round(temp_bytes::numeric / 1024 / 1024 / 1024, 2) AS temp_gib,
  blk_read_time,
  blk_write_time
FROM pg_stat_database
ORDER BY temp_bytes DESC NULLS LAST;

