-- Usage:
--   psql "$DATABASE_URL" -v days=30 -f scripts/sql/parsing96/d0_ai_learning_baseline.sql
--
-- Purpose:
--   Baseline of Ralph loop / AI learning signals by capability and prompt version.

\if :{?days}
\else
\set days 30
\endif

\pset footer off

SELECT
    CASE
        WHEN to_regclass('public.ailearningevents') IS NOT NULL THEN 1
        ELSE 0
    END AS ailearningevents_exists
\gset

\if :ailearningevents_exists

WITH filtered AS (
    SELECT
        e.capability,
        COALESCE(NULLIF(BTRIM(e.intent), ''), 'operations') AS intent,
        COALESCE(NULLIF(BTRIM(e.event_type), ''), 'unknown') AS event_type,
        COALESCE(e.accepted, FALSE) AS accepted,
        COALESCE(e.rejected, FALSE) AS rejected,
        COALESCE(e.edited_before_accept, FALSE) AS edited_before_accept,
        COALESCE(NULLIF(BTRIM(e.prompt_key), ''), 'unknown') AS prompt_key,
        COALESCE(NULLIF(BTRIM(e.prompt_version), ''), 'unknown') AS prompt_version,
        e.user_id,
        e.business_id,
        e.created_at
    FROM ailearningevents e
    WHERE e.created_at >= NOW() - make_interval(days => :days)
),
capability_rollup AS (
    SELECT
        f.capability,
        COUNT(*)::int AS total_events,
        COUNT(*) FILTER (WHERE f.event_type = 'generated')::int AS generated_total,
        COUNT(*) FILTER (WHERE f.accepted)::int AS accepted_total,
        COUNT(*) FILTER (WHERE f.rejected)::int AS rejected_total,
        COUNT(*) FILTER (WHERE f.accepted AND f.edited_before_accept)::int AS accepted_edited_total,
        COUNT(DISTINCT f.business_id)::int AS businesses_touched,
        COUNT(DISTINCT f.user_id)::int AS users_touched,
        MAX(f.created_at) AS latest_event_at
    FROM filtered f
    GROUP BY f.capability
)
SELECT
    cr.capability,
    cr.total_events,
    cr.generated_total,
    cr.accepted_total,
    cr.rejected_total,
    cr.accepted_edited_total,
    CASE
        WHEN cr.accepted_total + cr.rejected_total > 0
            THEN ROUND((cr.accepted_total::numeric / (cr.accepted_total + cr.rejected_total)::numeric) * 100.0, 2)
        ELSE 0
    END AS acceptance_rate_pct,
    CASE
        WHEN cr.accepted_total > 0
            THEN ROUND((cr.accepted_edited_total::numeric / cr.accepted_total::numeric) * 100.0, 2)
        ELSE 0
    END AS edit_rate_within_accept_pct,
    cr.businesses_touched,
    cr.users_touched,
    cr.latest_event_at
FROM capability_rollup cr
ORDER BY cr.capability;

WITH filtered AS (
    SELECT
        e.capability,
        COALESCE(NULLIF(BTRIM(e.intent), ''), 'operations') AS intent,
        COALESCE(NULLIF(BTRIM(e.event_type), ''), 'unknown') AS event_type,
        COALESCE(e.accepted, FALSE) AS accepted,
        COALESCE(e.rejected, FALSE) AS rejected,
        COALESCE(e.edited_before_accept, FALSE) AS edited_before_accept,
        COALESCE(NULLIF(BTRIM(e.prompt_key), ''), 'unknown') AS prompt_key,
        COALESCE(NULLIF(BTRIM(e.prompt_version), ''), 'unknown') AS prompt_version,
        e.user_id,
        e.business_id,
        e.created_at
    FROM ailearningevents e
    WHERE e.created_at >= NOW() - make_interval(days => :days)
)
SELECT
    f.capability,
    f.prompt_key,
    f.prompt_version,
    COUNT(*)::int AS total_events,
    COUNT(*) FILTER (WHERE f.event_type = 'generated')::int AS generated_total,
    COUNT(*) FILTER (WHERE f.accepted)::int AS accepted_total,
    COUNT(*) FILTER (WHERE f.rejected)::int AS rejected_total,
    COUNT(*) FILTER (WHERE f.accepted AND f.edited_before_accept)::int AS accepted_edited_total,
    CASE
        WHEN COUNT(*) FILTER (WHERE f.accepted OR f.rejected) > 0
            THEN ROUND((
                COUNT(*) FILTER (WHERE f.accepted)::numeric
                / COUNT(*) FILTER (WHERE f.accepted OR f.rejected)::numeric
            ) * 100.0, 2)
        ELSE 0
    END AS acceptance_rate_pct,
    MAX(f.created_at) AS latest_event_at
FROM filtered f
GROUP BY f.capability, f.prompt_key, f.prompt_version
ORDER BY accepted_total DESC, generated_total DESC, f.capability, f.prompt_key, f.prompt_version;

\else

SELECT
    'ailearningevents_missing'::text AS status,
    :days::text AS lookback_days,
    'Table ailearningevents is not present in this environment yet.'::text AS notes;

\endif
