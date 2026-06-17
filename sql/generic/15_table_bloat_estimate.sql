-- Statistics-based table bloat estimate that needs no extension.
-- Adapted from the well-known check_postgres / ioguix bloat query.
-- Treat the result as an approximation; confirm with pgstattuple before acting.
SELECT
  schemaname AS schema_name,
  tablename AS table_name,
  reltuples::bigint AS est_rows,
  relpages::bigint AS actual_pages,
  otta AS expected_pages,
  ROUND((CASE WHEN otta = 0 THEN 0.0 ELSE sml.relpages::float / otta END)::numeric, 1) AS bloat_ratio,
  CASE WHEN relpages < otta THEN 0 ELSE bs * (sml.relpages - otta)::bigint END AS wasted_bytes,
  pg_size_pretty((CASE WHEN relpages < otta THEN 0 ELSE bs * (sml.relpages - otta)::bigint END)) AS wasted_pretty
FROM (
  SELECT
    schemaname, tablename, cc.reltuples, cc.relpages, bs,
    CEIL((cc.reltuples * ((datahdr + ma -
      (CASE WHEN datahdr % ma = 0 THEN ma ELSE datahdr % ma END)) + nullhdr2 + 4)) / (bs - 20::float)) AS otta
  FROM (
    SELECT
      ma, bs, schemaname, tablename,
      (datawidth + (hdr + ma - (CASE WHEN hdr % ma = 0 THEN ma ELSE hdr % ma END)))::numeric AS datahdr,
      (maxfracsum * (nullhdr + ma - (CASE WHEN nullhdr % ma = 0 THEN ma ELSE nullhdr % ma END))) AS nullhdr2
    FROM (
      SELECT
        schemaname, tablename, hdr, ma, bs,
        SUM((1 - null_frac) * avg_width) AS datawidth,
        MAX(null_frac) AS maxfracsum,
        hdr + (
          SELECT 1 + count(*) / 8
          FROM pg_stats s2
          WHERE null_frac <> 0 AND s2.schemaname = s.schemaname AND s2.tablename = s.tablename
        ) AS nullhdr
      FROM pg_stats s, (
        SELECT
          current_setting('block_size')::numeric AS bs,
          23 AS hdr,
          CASE WHEN version() ~ 'mingw32' THEN 8 ELSE 4 END AS ma
      ) AS constants
      WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
      GROUP BY 1, 2, 3, 4, 5
    ) AS foo
  ) AS rs
  JOIN pg_class cc ON cc.relname = rs.tablename
  JOIN pg_namespace nn ON cc.relnamespace = nn.oid
    AND nn.nspname = rs.schemaname
    AND nn.nspname NOT IN ('pg_catalog', 'information_schema')
  WHERE cc.relkind = 'r'
) AS sml
WHERE relpages > 128
ORDER BY wasted_bytes DESC
LIMIT 20;
