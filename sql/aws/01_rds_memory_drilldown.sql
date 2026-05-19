SELECT
  usename,
  application_name,
  state,
  backend_type,
  count(*) AS sessions
FROM pg_stat_activity
GROUP BY usename, application_name, state, backend_type
ORDER BY sessions DESC, usename, application_name;

