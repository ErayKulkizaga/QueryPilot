CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

REVOKE ALL ON public.pg_stat_statements FROM PUBLIC;
REVOKE ALL ON public.pg_stat_statements FROM querypilot_app;

CREATE OR REPLACE FUNCTION public.querypilot_workload_snapshot()
RETURNS TABLE (
    query_id TEXT,
    normalized_sql TEXT,
    calls BIGINT,
    total_exec_time_ms DOUBLE PRECISION,
    mean_exec_time_ms DOUBLE PRECISION,
    result_rows BIGINT,
    shared_blocks_read BIGINT,
    temp_blocks_written BIGINT
)
LANGUAGE SQL
SECURITY DEFINER
STABLE
SET search_path = pg_catalog, public
AS $$
    SELECT
        statement.queryid::TEXT,
        statement.query,
        statement.calls,
        statement.total_exec_time,
        statement.mean_exec_time,
        statement.rows,
        statement.shared_blks_read,
        statement.temp_blks_written
    FROM public.pg_stat_statements AS statement
    WHERE statement.dbid = (
        SELECT database.oid
        FROM pg_catalog.pg_database AS database
        WHERE database.datname = pg_catalog.current_database()
    )
      AND statement.toplevel
      AND statement.query ~* '^\s*(SELECT|WITH)\M'
      AND statement.query !~* '^\s*SELECT\s+set_config\('
      AND statement.query !~* '^\s*SELECT\s+CASE\s+WHEN\s+to_regclass\('
      AND statement.query NOT ILIKE '%querypilot_workload_snapshot%'
      AND statement.query NOT ILIKE '%querypilot_workload_queries%'
$$;

REVOKE ALL ON FUNCTION public.querypilot_workload_snapshot() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.querypilot_workload_snapshot() TO querypilot_app;

CREATE OR REPLACE VIEW public.querypilot_workload_queries
WITH (security_barrier = true)
AS
SELECT
    snapshot.query_id,
    snapshot.normalized_sql,
    snapshot.calls,
    snapshot.total_exec_time_ms,
    snapshot.mean_exec_time_ms,
    snapshot.result_rows,
    snapshot.shared_blocks_read,
    snapshot.temp_blocks_written
FROM public.querypilot_workload_snapshot() AS snapshot;

REVOKE ALL ON public.querypilot_workload_queries FROM PUBLIC;
GRANT SELECT ON public.querypilot_workload_queries TO querypilot_app;

COMMENT ON VIEW public.querypilot_workload_queries IS
    'Least-privilege QueryPilot projection over pg_stat_statements.';
