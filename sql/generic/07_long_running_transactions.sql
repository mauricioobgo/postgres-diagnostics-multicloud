SELECT
  pid,
  application_name,
  usename,
  state,
  age(clock_timestamp(), xact_start) AS xact_age,
  age(backend_xmin) AS backend_xmin_age,
  age(clock_timestamp(), query_start) AS query_age,
  wait_event_type,
  wait_event,
  left(regexp_replace(query, '\\s+', ' ', 'g'), 240) AS query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
ORDER BY age(clock_timestamp(), xact_start) DESC
LIMIT 25;

