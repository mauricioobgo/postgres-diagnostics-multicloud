SELECT
  datname AS database_name,
  temp_files,
  temp_bytes
FROM pg_stat_database
ORDER BY temp_bytes DESC NULLS LAST;

