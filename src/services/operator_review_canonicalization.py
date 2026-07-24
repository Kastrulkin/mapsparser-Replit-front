CANONICAL_REVIEWS_CTE = """
WITH review_candidates AS (
    SELECT source_reviews.*,
           FIRST_VALUE(NULLIF(BTRIM(source_reviews.response_text), '')) OVER (
               PARTITION BY source_reviews.business_id,
                            LOWER(BTRIM(COALESCE(source_reviews.source, ''))),
                            source_reviews.rating,
                            LOWER(BTRIM(COALESCE(source_reviews.text, ''))),
                            COALESCE(source_reviews.published_at::date, source_reviews.created_at::date)
               ORDER BY CASE WHEN COALESCE(BTRIM(source_reviews.response_text), '') <> '' THEN 0 ELSE 1 END,
                        source_reviews.updated_at DESC NULLS LAST,
                        source_reviews.id
           ) AS matching_response_text,
           FIRST_VALUE(source_reviews.response_at) OVER (
               PARTITION BY source_reviews.business_id,
                            LOWER(BTRIM(COALESCE(source_reviews.source, ''))),
                            source_reviews.rating,
                            LOWER(BTRIM(COALESCE(source_reviews.text, ''))),
                            COALESCE(source_reviews.published_at::date, source_reviews.created_at::date)
               ORDER BY CASE WHEN COALESCE(BTRIM(source_reviews.response_text), '') <> '' THEN 0 ELSE 1 END,
                        source_reviews.updated_at DESC NULLS LAST,
                        source_reviews.id
           ) AS matching_response_at,
           ROW_NUMBER() OVER (
               PARTITION BY source_reviews.business_id,
                            LOWER(BTRIM(COALESCE(source_reviews.source, ''))),
                            source_reviews.rating,
                            LOWER(BTRIM(COALESCE(source_reviews.text, ''))),
                            COALESCE(source_reviews.published_at::date, source_reviews.created_at::date)
               ORDER BY CASE WHEN COALESCE(source_reviews.external_review_id, '') NOT LIKE 'html_%' THEN 0 ELSE 1 END,
                        CASE WHEN LOWER(COALESCE(source_reviews.author_name, '')) NOT IN ('', 'анонимный пользователь', 'anon') THEN 0 ELSE 1 END,
                        source_reviews.updated_at DESC NULLS LAST,
                        source_reviews.id
           ) AS canonical_rank
    FROM externalbusinessreviews source_reviews
), canonical_reviews AS (
    SELECT id, business_id, source, external_review_id, rating, author_name, text,
           COALESCE(NULLIF(BTRIM(response_text), ''), matching_response_text) AS response_text,
           COALESCE(response_at, matching_response_at) AS response_at,
           published_at, created_at, updated_at
    FROM review_candidates
    WHERE canonical_rank = 1
)
"""
