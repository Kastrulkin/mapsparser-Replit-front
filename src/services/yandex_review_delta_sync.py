"""Incremental Yandex review persistence and completeness checks."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser
from psycopg2.extras import Json

from core.review_response_utils import extract_review_response_text
from services.yandex_full_reviews_sync import YANDEX_REVIEW_SOURCES


def _text(value: Any) -> str:
    return str(value or "").strip()


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    raw = _text(value)
    if not raw:
        return None
    try:
        return date_parser.parse(raw)
    except (TypeError, ValueError, OverflowError):
        return None


def load_known_yandex_review_ids(cursor: Any, business_id: str, *, limit: int = 100) -> list[str]:
    cursor.execute(
        """
        SELECT external_review_id
        FROM externalbusinessreviews
        WHERE business_id = %s
          AND is_current = TRUE
          AND LOWER(COALESCE(source, '')) = ANY(%s)
          AND COALESCE(external_review_id, '') <> ''
        ORDER BY published_at DESC NULLS LAST, updated_at DESC
        LIMIT %s
        """,
        (business_id, list(YANDEX_REVIEW_SOURCES), max(1, int(limit))),
    )
    rows = cursor.fetchall() or []
    result: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            value = row.get("external_review_id")
        else:
            value = row[0] if row else None
        review_id = _text(value)
        if review_id and not review_id.startswith("html_"):
            result.append(review_id)
    return result


def load_expected_yandex_reviews_total(cursor: Any, business_id: str) -> int:
    cursor.execute(
        """
        SELECT COALESCE(reviews_count, 0)
        FROM cards
        WHERE business_id = %s
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    if isinstance(row, dict):
        value = row.get("reviews_count")
    else:
        value = row[0] if row else 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def normalize_native_review(item: dict[str, Any]) -> dict[str, Any] | None:
    external_id = _text(
        item.get("external_review_id") or item.get("id") or item.get("reviewId") or item.get("review_id")
    )
    review_text = _text(item.get("text") or item.get("comment") or item.get("reviewText"))
    if not external_id or not review_text:
        return None
    rating_value = item.get("score") or item.get("rating")
    try:
        rating = int(float(rating_value)) if rating_value not in (None, "") else None
    except (TypeError, ValueError):
        rating = None
    response_text = _text(extract_review_response_text(item)) or None
    return {
        "external_review_id": external_id,
        "rating": rating,
        "author_name": _text(item.get("author") or item.get("author_name")) or "Анонимный пользователь",
        "author_profile_url": _text(item.get("author_profile_url") or item.get("authorProfileUrl")) or None,
        "text": review_text,
        "response_text": response_text,
        "response_at": _datetime(item.get("response_date") or item.get("response_at")),
        "published_at": _datetime(
            item.get("date") or item.get("published_at") or item.get("publishedAt") or item.get("createdAt")
        ),
        "raw_payload": item,
    }


def native_delta_completeness(
    card_data: dict[str, Any],
    *,
    known_review_ids: list[str],
    expected_total: int = 0,
) -> tuple[bool, str]:
    if not isinstance(card_data, dict) or card_data.get("error"):
        return False, _text((card_data or {}).get("error")) or "native_error"
    reviews = card_data.get("reviews") if isinstance(card_data.get("reviews"), list) else []
    normalized_ids = {
        _text(item.get("id") or item.get("reviewId") or item.get("review_id"))
        for item in reviews
        if isinstance(item, dict)
    }
    normalized_ids.discard("")
    run_meta = card_data.get("_parser_run") if isinstance(card_data.get("_parser_run"), dict) else {}
    if known_review_ids:
        if set(known_review_ids).intersection(normalized_ids) or bool(run_meta.get("delta_boundary_reached")):
            return True, "known_review_id"
        return False, _text(run_meta.get("review_stop_reason")) or "known_review_id_not_reached"
    expected = max(0, int(expected_total or 0))
    allowed_gap = max(2, round(expected * 0.02)) if expected else 0
    if expected and len(normalized_ids) >= expected - allowed_gap:
        return True, "initial_snapshot_complete"
    return False, "no_delta_boundary"


def apply_yandex_review_delta(
    cursor: Any,
    *,
    business_id: str,
    reviews: list[dict[str, Any]],
    source: str = "yandex_maps",
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in reviews:
        if not isinstance(item, dict):
            continue
        review = normalize_native_review(item)
        if not review:
            continue
        external_id = review["external_review_id"]
        if external_id in seen:
            continue
        seen.add(external_id)
        normalized.append(review)

    inserted_or_updated = 0
    unanswered = 0
    for review in normalized:
        external_id = review["external_review_id"]
        response_text = _text(review.get("response_text")) or None
        if not response_text:
            unanswered += 1
        row_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:{business_id}:{source}:{external_id}"))
        cursor.execute(
            """
            INSERT INTO externalbusinessreviews (
                id, business_id, source, external_review_id, rating, author_name,
                author_profile_url, text, response_text, response_at, published_at,
                raw_payload, is_current, last_seen_at, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, TRUE, NOW(), NOW(), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                rating = EXCLUDED.rating,
                author_name = EXCLUDED.author_name,
                author_profile_url = EXCLUDED.author_profile_url,
                text = EXCLUDED.text,
                response_text = COALESCE(
                    NULLIF(BTRIM(EXCLUDED.response_text), ''),
                    externalbusinessreviews.response_text
                ),
                response_at = CASE
                    WHEN NULLIF(BTRIM(EXCLUDED.response_text), '') IS NULL
                        THEN externalbusinessreviews.response_at
                    ELSE COALESCE(EXCLUDED.response_at, externalbusinessreviews.response_at)
                END,
                published_at = EXCLUDED.published_at,
                raw_payload = EXCLUDED.raw_payload,
                is_current = TRUE,
                last_seen_at = NOW(),
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
            ),
        )
        inserted_or_updated += 1
    return {
        "received": len(reviews),
        "normalized": len(normalized),
        "upserted": inserted_or_updated,
        "without_response_in_delta": unanswered,
    }
