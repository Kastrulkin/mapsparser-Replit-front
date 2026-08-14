"""Complete Yandex review snapshots for reputation counters.

The regular place actor intentionally returns at most 50 reviews. This module
uses the dedicated reviews actor and only replaces the current snapshot after
the run passes completeness checks.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

from psycopg2.extras import Json

from core.review_response_utils import extract_review_response_text


DEFAULT_ACTOR_ID = "zen-studio/yandex-maps-reviews-scraper"
YANDEX_REVIEW_SOURCES = ("yandex", "yandex_maps", "yandex_business", "apify_yandex")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_actor_review(item: dict[str, Any]) -> dict[str, Any] | None:
    external_id = _text(item.get("reviewId") or item.get("id") or item.get("review_id"))
    review_text = _text(
        item.get("reviewText") or item.get("text") or item.get("full_text") or item.get("snippet")
    )
    if not external_id or not review_text:
        return None
    rating_value = item.get("rating") or item.get("score")
    try:
        rating = int(rating_value) if rating_value is not None else None
    except (TypeError, ValueError):
        rating = None
    response_text = _text(
        item.get("ownerReplyText")
        or item.get("businessComment")
        or item.get("business_comment")
        or extract_review_response_text(item)
    ) or None
    return {
        "external_review_id": external_id,
        "rating": rating,
        "author_name": _text(
            item.get("reviewerName") or item.get("authorName") or item.get("author") or item.get("userName")
        ) or "Анонимный пользователь",
        "author_profile_url": _text(
            item.get("reviewerProfileUrl") or item.get("authorProfileUrl") or item.get("author_profile_url")
        ) or None,
        "text": review_text,
        "response_text": response_text,
        "response_at": _parse_datetime(
            item.get("ownerReplyDate")
            or item.get("businessCommentDate")
            or item.get("response_date")
        ),
        "published_at": _parse_datetime(
            item.get("reviewDate") or item.get("date") or item.get("publishedAt") or item.get("createdAt")
        ),
        "raw_payload": item,
    }


def fetch_complete_yandex_reviews(
    map_url: str,
    *,
    max_reviews: int = 0,
    actor_id: str | None = None,
) -> list[dict[str, Any]]:
    try:
        from apify_client import ApifyClient
    except ImportError as error:
        raise RuntimeError("apify_client is unavailable") from error
    token = _text(os.environ.get("APIFY_TOKEN"))
    if not token:
        raise RuntimeError("APIFY_TOKEN is not configured")
    reviews_url = _text(map_url).rstrip("/") + "/reviews/"
    client = ApifyClient(token)
    run = client.actor(actor_id or os.environ.get("APIFY_YANDEX_REVIEWS_ACTOR_ID") or DEFAULT_ACTOR_ID).call(
        run_input={
            "startUrls": [{"url": reviews_url}],
            "maxReviewsPerPlace": max(0, int(max_reviews)),
            "maxPlaces": 1,
            "reviewSort": "newest",
            "language": "ru",
        }
    )
    if isinstance(run, dict):
        dataset_id = _text(run.get("defaultDatasetId"))
    else:
        dataset_id = _text(getattr(run, "default_dataset_id", None))
        if not dataset_id:
            dumped_run = run.model_dump(by_alias=True) if hasattr(run, "model_dump") else {}
            dataset_id = _text(dumped_run.get("defaultDatasetId"))
    if not dataset_id:
        raise RuntimeError("Yandex reviews actor returned no dataset")
    raw_items = client.dataset(dataset_id).list_items().items
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        review = normalize_actor_review(raw_item)
        if not review:
            continue
        external_id = review["external_review_id"]
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)
        normalized.append(review)
    return normalized


def apply_complete_review_snapshot(
    cursor: Any,
    *,
    business_id: str,
    reviews: list[dict[str, Any]],
    expected_total: int | None = None,
    source: str = "yandex_maps",
) -> dict[str, Any]:
    if not reviews:
        raise ValueError("Complete review snapshot is empty")
    expected = max(0, int(expected_total or 0))
    allowed_gap = max(2, round(expected * 0.02)) if expected else 0
    if expected and len(reviews) < expected - allowed_gap:
        raise ValueError(
            f"Review snapshot is incomplete: received {len(reviews)} of about {expected}"
        )
    snapshot_id = str(uuid.uuid4())
    cursor.execute(
        """
        UPDATE externalbusinessreviews
        SET is_current = FALSE, updated_at = NOW()
        WHERE business_id = %s
          AND LOWER(COALESCE(source, '')) = ANY(%s)
        """,
        (business_id, list(YANDEX_REVIEW_SOURCES)),
    )
    unanswered = 0
    for review in reviews:
        external_id = _text(review.get("external_review_id"))
        if not external_id:
            continue
        response_text = _text(review.get("response_text")) or None
        if not response_text:
            unanswered += 1
        row_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:{business_id}:{source}:{external_id}"))
        cursor.execute(
            """
            INSERT INTO externalbusinessreviews (
                id, business_id, source, external_review_id, rating, author_name,
                author_profile_url, text, response_text, response_at, published_at,
                raw_payload, is_current, last_seen_at, last_complete_snapshot_id,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, TRUE, NOW(), %s,
                NOW(), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                rating = EXCLUDED.rating,
                author_name = EXCLUDED.author_name,
                author_profile_url = EXCLUDED.author_profile_url,
                text = EXCLUDED.text,
                response_text = EXCLUDED.response_text,
                response_at = EXCLUDED.response_at,
                published_at = EXCLUDED.published_at,
                raw_payload = EXCLUDED.raw_payload,
                is_current = TRUE,
                last_seen_at = NOW(),
                last_complete_snapshot_id = EXCLUDED.last_complete_snapshot_id,
                updated_at = NOW()
            """,
            (
                row_id,
                business_id,
                source,
                external_id,
                review.get("rating"),
                review.get("author_name"),
                review.get("author_profile_url"),
                review.get("text"),
                response_text,
                review.get("response_at"),
                review.get("published_at"),
                Json(review.get("raw_payload") or {}),
                snapshot_id,
            ),
        )
    return {
        "snapshot_id": snapshot_id,
        "total": len(reviews),
        "with_response": len(reviews) - unanswered,
        "without_response": unanswered,
        "expected_total": expected or None,
    }


def sync_complete_yandex_reviews(
    cursor: Any,
    *,
    business_id: str,
    map_url: str,
    expected_total: int | None = None,
) -> dict[str, Any]:
    reviews = fetch_complete_yandex_reviews(map_url)
    return apply_complete_review_snapshot(
        cursor,
        business_id=business_id,
        reviews=reviews,
        expected_total=expected_total,
    )
