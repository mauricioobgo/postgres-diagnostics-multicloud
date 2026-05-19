SELECT
  name,
  setting,
  unit,
  boot_val,
  source,
  short_desc
FROM pg_settings
WHERE name IN (
  'shared_buffers',
  'work_mem',
  'maintenance_work_mem',
  'autovacuum_work_mem',
  'autovacuum_vacuum_threshold',
  'autovacuum_vacuum_scale_factor',
  'autovacuum_analyze_threshold',
  'autovacuum_analyze_scale_factor',
  'temp_buffers',
  'effective_cache_size',
  'max_connections',
  'hash_mem_multiplier',
  'max_worker_processes',
  'max_parallel_workers',
  'max_parallel_workers_per_gather',
  'max_parallel_maintenance_workers',
  'idle_in_transaction_session_timeout',
  'temp_file_limit',
  'huge_pages'
)
ORDER BY name;
