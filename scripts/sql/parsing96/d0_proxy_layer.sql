-- Usage:
--   psql "$DATABASE_URL" -f scripts/sql/parsing96/d0_proxy_layer.sql
--
-- Purpose:
--   Snapshot of current proxy pool health for D0 baseline and rollout gating.

\pset footer off

SELECT
    ps.id,
    ps.host,
    ps.port,
    ps.proxy_type,
    COALESCE(ps.is_active, FALSE) AS is_active,
    COALESCE(ps.is_working, FALSE) AS is_working,
    COALESCE(ps.success_count, 0) AS success_count,
    COALESCE(ps.failure_count, 0) AS failure_count,
    CASE
        WHEN COALESCE(ps.success_count, 0) + COALESCE(ps.failure_count, 0) > 0
            THEN ROUND(
                (COALESCE(ps.failure_count, 0)::numeric / (COALESCE(ps.success_count, 0) + COALESCE(ps.failure_count, 0))::numeric) * 100.0,
                2
            )
        ELSE 0
    END AS fail_rate_pct,
    ps.last_used_at,
    ps.last_checked_at,
    ps.updated_at
FROM proxyservers ps
ORDER BY
    COALESCE(ps.is_active, FALSE) DESC,
    COALESCE(ps.is_working, FALSE) DESC,
    fail_rate_pct ASC,
    COALESCE(ps.last_checked_at, ps.updated_at, ps.created_at) DESC;
