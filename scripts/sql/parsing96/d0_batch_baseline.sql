-- Usage:
--   psql "$DATABASE_URL" -v batch_id='localos_mass_20260319_136' -f scripts/sql/parsing96/d0_batch_baseline.sql
--
-- Purpose:
--   D0 baseline for a parsing batch with strict validity and latency metrics.

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

WITH status_counts AS (
    SELECT
        LOWER(COALESCE(pq.status, 'unknown')) AS status,
        COUNT(*)::int AS cnt
    FROM parsequeue pq
    WHERE pq.batch_id = :'batch_id'
    GROUP BY 1
),
batch_total AS (
    SELECT COALESCE(SUM(cnt), 0)::int AS total_tasks
    FROM status_counts
),
completed_businesses AS (
    SELECT DISTINCT pq.business_id
    FROM parsequeue pq
    WHERE pq.batch_id = :'batch_id'
      AND pq.status = 'completed'
      AND pq.business_id IS NOT NULL
),
latest_cards AS (
    SELECT
        c.business_id,
        NULLIF(BTRIM(COALESCE(c.title, '')), '') AS title,
        NULLIF(BTRIM(COALESCE(c.address, '')), '') AS address,
        NULLIF(BTRIM(COALESCE(c.rating::text, '')), '') AS rating_text,
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
    JOIN completed_businesses cb ON cb.business_id = c.business_id
),
service_counts AS (
    SELECT
        us.business_id,
        COUNT(*)::int AS active_services
    FROM userservices us
    JOIN completed_businesses cb ON cb.business_id = us.business_id
    WHERE us.business_id IS NOT NULL
      AND (us.is_active IS TRUE OR us.is_active IS NULL)
    GROUP BY us.business_id
),
latest_completed AS (
    SELECT
        lc.business_id,
        lc.title,
        lc.address,
        lc.rating_text,
        lc.reviews_count,
        lc.products_blocks,
        COALESCE(sc.active_services, 0) AS active_services
    FROM latest_cards lc
    LEFT JOIN service_counts sc ON sc.business_id = lc.business_id
    WHERE lc.rn = 1
),
valid_metrics AS (
    SELECT
        COUNT(*)::int AS completed_cards,
        COUNT(*) FILTER (
            WHERE title IS NOT NULL
              AND address IS NOT NULL
        )::int AS with_title_address,
        COUNT(*) FILTER (
            WHERE rating_text IS NOT NULL
               OR reviews_count > 0
        )::int AS with_rating_or_reviews,
        COUNT(*) FILTER (WHERE products_blocks > 0)::int AS with_products_blocks,
        COUNT(*) FILTER (WHERE active_services > 0)::int AS with_active_services,
        COUNT(*) FILTER (
            WHERE title IS NOT NULL
              AND address IS NOT NULL
              AND (rating_text IS NOT NULL OR reviews_count > 0)
              AND active_services > 0
        )::int AS valid_strict_services,
        COUNT(*) FILTER (
            WHERE title IS NOT NULL
              AND address IS NOT NULL
              AND (rating_text IS NOT NULL OR reviews_count > 0)
              AND products_blocks > 0
        )::int AS valid_strict_products
    FROM latest_completed
),
latency AS (
    SELECT
        COUNT(*)::int AS completed_with_timing,
        ROUND((
            percentile_cont(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (pq.updated_at - pq.created_at))
            ) / 60.0
        )::numeric, 2) AS p50_minutes,
        ROUND((
            percentile_cont(0.95) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (pq.updated_at - pq.created_at))
            ) / 60.0
        )::numeric, 2) AS p95_minutes
    FROM parsequeue pq
    WHERE pq.batch_id = :'batch_id'
      AND pq.status = 'completed'
      AND pq.created_at IS NOT NULL
      AND pq.updated_at IS NOT NULL
)
SELECT *
FROM (
    SELECT
        'batch_status'::text AS section,
        'total_tasks'::text AS metric,
        bt.total_tasks::text AS value,
        NULL::text AS notes
    FROM batch_total bt

    UNION ALL

    SELECT
        'batch_status',
        sc.status,
        sc.cnt::text,
        CASE
            WHEN bt.total_tasks > 0
                THEN ROUND((sc.cnt::numeric / bt.total_tasks::numeric) * 100.0, 2)::text || '%'
            ELSE '0%'
        END
    FROM status_counts sc
    CROSS JOIN batch_total bt

    UNION ALL

    SELECT 'validity', 'completed_cards', vm.completed_cards::text, NULL
    FROM valid_metrics vm

    UNION ALL

    SELECT 'validity', 'with_title_address', vm.with_title_address::text, NULL
    FROM valid_metrics vm

    UNION ALL

    SELECT 'validity', 'with_rating_or_reviews', vm.with_rating_or_reviews::text, NULL
    FROM valid_metrics vm

    UNION ALL

    SELECT 'validity', 'with_products_blocks', vm.with_products_blocks::text, NULL
    FROM valid_metrics vm

    UNION ALL

    SELECT 'validity', 'with_active_services', vm.with_active_services::text, NULL
    FROM valid_metrics vm

    UNION ALL

    SELECT 'validity', 'valid_strict_services', vm.valid_strict_services::text, NULL
    FROM valid_metrics vm

    UNION ALL

    SELECT 'validity', 'valid_strict_products', vm.valid_strict_products::text, NULL
    FROM valid_metrics vm

    UNION ALL

    SELECT
        'validity',
        'valid_strict_services_rate_of_batch',
        CASE
            WHEN bt.total_tasks > 0
                THEN ROUND((vm.valid_strict_services::numeric / bt.total_tasks::numeric) * 100.0, 2)::text
            ELSE '0'
        END,
        '%'
    FROM valid_metrics vm
    CROSS JOIN batch_total bt

    UNION ALL

    SELECT 'latency', 'completed_with_timing', COALESCE(l.completed_with_timing, 0)::text, 'tasks'
    FROM latency l

    UNION ALL

    SELECT 'latency', 'p50_minutes', COALESCE(l.p50_minutes, 0)::text, 'minutes'
    FROM latency l

    UNION ALL

    SELECT 'latency', 'p95_minutes', COALESCE(l.p95_minutes, 0)::text, 'minutes'
    FROM latency l
) baseline
ORDER BY
    CASE baseline.section
        WHEN 'batch_status' THEN 1
        WHEN 'validity' THEN 2
        WHEN 'latency' THEN 3
        ELSE 9
    END,
    baseline.metric;

\else

SELECT
    'parsequeue_batch_id_missing'::text AS status,
    'batch baseline requires parsequeue.batch_id in this environment'::text AS notes;

\endif
