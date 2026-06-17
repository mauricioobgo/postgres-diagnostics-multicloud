-- On-disk size of each database. Shows where storage is concentrated.
SELECT
  datname AS database_name,
  pg_database_size(datname) AS size_bytes,
  pg_size_pretty(pg_database_size(datname)) AS size_pretty
FROM pg_database
WHERE datistemplate = false
ORDER BY pg_database_size(datname) DESC;
