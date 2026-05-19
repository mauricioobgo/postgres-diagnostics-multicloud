SELECT
  application_name,
  state,
  wait_event_type,
  wait_event,
  count(*) AS sessions
FROM pg_stat_activity
GROUP BY application_name, state, wait_event_type, wait_event
ORDER BY sessions DESC, application_name;

