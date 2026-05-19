SELECT
  st.schemaname AS schema_name,
  st.relname AS table_name,
  pg_total_relation_size(st.relid) AS table_bytes,
  st.n_live_tup AS live_rows_est,
  st.n_dead_tup AS dead_rows_est,
  round(100 * st.n_dead_tup::numeric / NULLIF(st.n_live_tup + st.n_dead_tup, 0), 2) AS dead_row_pct_est,
  st.n_mod_since_analyze AS mod_since_analyze,
  st.n_ins_since_vacuum AS ins_since_vacuum,
  round(100 * st.n_tup_hot_upd::numeric / NULLIF(st.n_tup_upd, 0), 2) AS hot_update_pct,
  st.last_vacuum,
  st.last_autovacuum,
  st.last_analyze,
  st.last_autoanalyze
FROM pg_stat_user_tables st
ORDER BY st.n_dead_tup DESC, pg_total_relation_size(st.relid) DESC
LIMIT 50;

