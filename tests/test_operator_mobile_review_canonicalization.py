from services.operator_review_canonicalization import CANONICAL_REVIEWS_CTE


def test_mobile_reviews_merge_parser_duplicates_and_keep_existing_response():
    normalized = " ".join(CANONICAL_REVIEWS_CTE.lower().split())

    assert "partition by source_reviews.business_id" in normalized
    assert "lower(btrim(coalesce(source_reviews.text, '')))" in normalized
    assert "coalesce(source_reviews.published_at::date, source_reviews.created_at::date)" in normalized
    assert "first_value(nullif(btrim(source_reviews.response_text), ''))" in normalized
    assert "where canonical_rank = 1" in normalized
