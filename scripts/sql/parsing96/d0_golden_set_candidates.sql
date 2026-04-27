-- Usage:
--   psql "$DATABASE_URL" \
--     -v batch_id='localos_mass_20260319_136' \
--     -v valid_limit=80 \
--     -v partial_limit=60 \
--     -v failed_limit=60 \
--     -f scripts/sql/parsing96/d0_golden_set_candidates.sql
--
-- Purpose:
--   Build a manual-audit sample for golden set assembly from one batch.

\if :{?valid_limit}
\else
\set valid_limit 80
\endif

\if :{?partial_limit}
\else
\set partial_limit 60
\endif

\if :{?failed_limit}
\else
\set failed_limit 60
\endif

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

WITH latest_task AS (
    SELECT
        pq.id AS task_id,
        pq.batch_id,
        pq.business_id,
        pq.user_id,
        pq.url,
        pq.source,
        pq.status,
        pq.error_message,
        pq.created_at,
        pq.updated_at,
        ROW_NUMBER() OVER (
            PARTITION BY pq.business_id
            ORDER BY pq.updated_at DESC NULLS LAST, pq.created_at DESC NULLS LAST, pq.id DESC
        ) AS rn
    FROM parsequeue pq
    WHERE pq.batch_id = :'batch_id'
      AND pq.business_id IS NOT NULL
),
latest_card AS (
    SELECT
        c.business_id,
        NULLIF(BTRIM(COALESCE(c.title, '')), '') AS title,
        NULLIF(BTRIM(COALESCE(c.address, '')), '') AS address,
        c.rating,
        COALESCE(c.reviews_count, 0) AS reviews_count,
        CASE
            WHEN c.products IS NULL OR BTRIM(c.products) = '' THEN 0
            ELSE jsonb_array_length(c.products::jsonb)
        END AS products_blocks,
        ROW_NUMBER() OVER (
            PARTITION BY c.business_id
            ORDER BY c.updated_at DESC NULLS LAST, c.created_at DESC NULLS LAST, c.id DESC
        ) AS rn
    FROM cards c
),
service_counts AS (
    SELECT
        us.business_id,
        COUNT(*)::int AS active_services
    FROM userservices us
    WHERE us.business_id IS NOT NULL
      AND (us.is_active IS TRUE OR us.is_active IS NULL)
    GROUP BY us.business_id
),
base AS (
    SELECT
        lt.task_id,
        lt.batch_id,
        lt.business_id,
        b.name AS business_name,
        lt.url,
        lt.source,
        lt.status,
        lt.error_message,
        lt.created_at,
        lt.updated_at,
        lc.title,
        lc.address,
        lc.rating,
        lc.reviews_count,
        COALESCE(lc.products_blocks, 0) AS products_blocks,
        COALESCE(sc.active_services, 0) AS active_services
    FROM latest_task lt
    LEFT JOIN businesses b ON b.id = lt.business_id
    LEFT JOIN latest_card lc
        ON lc.business_id = lt.business_id
       AND lc.rn = 1
    LEFT JOIN service_counts sc ON sc.business_id = lt.business_id
    WHERE lt.rn = 1
),
classified AS (
    SELECT
        base.*,
        CASE
            WHEN base.status = 'completed'
             AND base.title IS NOT NULL
             AND base.address IS NOT NULL
             AND (base.rating IS NOT NULL OR base.reviews_count > 0)
             AND base.active_services > 0
                THEN 'valid_high_signal'
            WHEN base.status = 'completed'
                THEN 'completed_partial'
            ELSE 'failed_or_blocked'
        END AS audit_bucket
    FROM base
),
ranked AS (
    SELECT
        c.*,
        ROW_NUMBER() OVER (
            PARTITION BY c.audit_bucket
            ORDER BY RANDOM()
        ) AS bucket_rn
    FROM classified c
)
SELECT
    r.audit_bucket,
    r.bucket_rn,
    r.business_id,
    COALESCE(NULLIF(BTRIM(COALESCE(r.business_name, '')), ''), r.title, 'unknown_business') AS business_label,
    r.source,
    r.status,
    r.url,
    r.title,
    r.address,
    r.rating,
    r.reviews_count,
    r.active_services,
    r.products_blocks,
    LEFT(COALESCE(r.error_message, ''), 180) AS error_excerpt,
    r.updated_at
FROM ranked r
WHERE
    (r.audit_bucket = 'valid_high_signal' AND r.bucket_rn <= :valid_limit)
    OR (r.audit_bucket = 'completed_partial' AND r.bucket_rn <= :partial_limit)
    OR (r.audit_bucket = 'failed_or_blocked' AND r.bucket_rn <= :failed_limit)
ORDER BY
    CASE r.audit_bucket
        WHEN 'valid_high_signal' THEN 1
        WHEN 'completed_partial' THEN 2
        WHEN 'failed_or_blocked' THEN 3
        ELSE 9
    END,
    r.bucket_rn;

\else

SELECT
    'parsequeue_batch_id_missing'::text AS status,
    'golden set candidate query requires parsequeue.batch_id in this environment'::text AS notes;

\endif
