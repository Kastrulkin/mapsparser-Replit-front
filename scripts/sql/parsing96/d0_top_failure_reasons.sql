-- Usage:
--   psql "$DATABASE_URL" -v batch_id='localos_mass_20260319_136' -f scripts/sql/parsing96/d0_top_failure_reasons.sql
--
-- Purpose:
--   Top failure reasons for one batch, aligned with src/parsing_failure_taxonomy.py.

\pset footer off

SELECT
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'parsequeue'
              AND column_name = 'batch_id'
        ) THEN 1
        ELSE 0
    END AS parsequeue_has_batch_id
\gset

\if :parsequeue_has_batch_id

WITH raw_failures AS (
    SELECT
        LOWER(COALESCE(pq.status, '')) AS status_lc,
        LOWER(COALESCE(pq.error_message, '')) AS msg_lc,
        COALESCE(pq.error_message, '') AS raw_error_message
    FROM parsequeue pq
    WHERE pq.batch_id = :'batch_id'
      AND (
            pq.error_message IS NOT NULL
         OR pq.status IN ('captcha', 'error', 'paused')
      )
),
classified AS (
    SELECT
        CASE
            WHEN status_lc = 'captcha' THEN 'captcha'
            WHEN msg_lc LIKE '%captcha_required%' OR msg_lc LIKE '%captcha_detected%' OR msg_lc LIKE '%вы не робот%' THEN 'captcha'
            WHEN msg_lc LIKE '%invalid_org_url%' OR msg_lc LIKE '%invalid org url%' THEN 'invalid_org_url'
            WHEN msg_lc LIKE '%dlq_reason=task_ttl_exceeded%' THEN 'task_ttl_exceeded'
            WHEN msg_lc LIKE '%dlq_reason=captcha_retry_exhausted%' THEN 'retry_exhausted'
            WHEN msg_lc LIKE '%blocked session%' OR msg_lc LIKE '%session lost%' OR msg_lc LIKE '%captcha_session_lost%' THEN 'blocked_session'
            WHEN msg_lc LIKE '%err_proxy_connection_failed%'
              OR msg_lc LIKE '%err_tunnel_connection_failed%'
              OR msg_lc LIKE '%proxy authentication%'
              OR msg_lc LIKE '%407%'
              OR msg_lc LIKE '%forbidden%' THEN 'proxy_transport'
            WHEN msg_lc LIKE '%timeout%'
              OR msg_lc LIKE '%timed out%'
              OR msg_lc LIKE '%navigation timeout%'
              OR msg_lc LIKE '%parser_subprocess_timeout%' THEN 'timeout'
            WHEN msg_lc LIKE '%low_quality_payload%' OR msg_lc LIKE '%services_upsert_zero%' THEN 'quality_gate_fail'
            WHEN msg_lc LIKE '%org_api_not_loaded%'
              OR msg_lc LIKE '%parser_returned_none%'
              OR msg_lc LIKE '%empty payload%' THEN 'empty_payload'
            WHEN msg_lc LIKE '%parser_subprocess_exception%'
              OR msg_lc LIKE '%playwright%'
              OR msg_lc LIKE '%cannot access ''l'' before initialization%'
              OR msg_lc LIKE '%module not found%' THEN 'parser_mismatch'
            ELSE 'unknown'
        END AS reason_code,
        status_lc,
        raw_error_message
    FROM raw_failures
),
totals AS (
    SELECT
        COUNT(*)::int AS failures_total
    FROM classified
),
batch_total AS (
    SELECT COUNT(*)::int AS batch_total
    FROM parsequeue pq
    WHERE pq.batch_id = :'batch_id'
),
reason_counts AS (
    SELECT
        c.reason_code,
        COUNT(*)::int AS failures_count,
        MIN(NULLIF(BTRIM(c.raw_error_message), '')) AS sample_error
    FROM classified c
    GROUP BY c.reason_code
)
SELECT
    rc.reason_code,
    rc.failures_count,
    CASE
        WHEN bt.batch_total > 0
            THEN ROUND((rc.failures_count::numeric / bt.batch_total::numeric) * 100.0, 2)
        ELSE 0
    END AS pct_of_batch,
    CASE
        WHEN t.failures_total > 0
            THEN ROUND((rc.failures_count::numeric / t.failures_total::numeric) * 100.0, 2)
        ELSE 0
    END AS pct_of_failures,
    LEFT(COALESCE(rc.sample_error, ''), 180) AS sample_error
FROM reason_counts rc
CROSS JOIN totals t
CROSS JOIN batch_total bt
ORDER BY rc.failures_count DESC, rc.reason_code
LIMIT 10;

\else

SELECT
    'parsequeue_batch_id_missing'::text AS status,
    'top failure reasons requires parsequeue.batch_id in this environment'::text AS notes;

\endif
