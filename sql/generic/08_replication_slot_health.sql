SELECT
  slot_name,
  slot_type,
  active,
  restart_lsn,
  wal_status,
  CASE WHEN xmin IS NOT NULL THEN age(xmin) END AS xmin_age,
  CASE WHEN catalog_xmin IS NOT NULL THEN age(catalog_xmin) END AS catalog_xmin_age
FROM pg_replication_slots
ORDER BY GREATEST(COALESCE(age(xmin), 0), COALESCE(age(catalog_xmin), 0)) DESC, slot_name;

