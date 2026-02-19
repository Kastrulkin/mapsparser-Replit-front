from typing import List
import json
from database_manager import DatabaseManager
from external_sources import ExternalReview, ExternalStatsPoint, ExternalPost, ExternalPhoto

class ExternalDataRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def upsert_reviews(self, reviews: List[ExternalReview]) -> None:
        if not reviews:
            return
            
        cursor = self.db.conn.cursor()
        for r in reviews:
            cursor.execute(
                """
                INSERT INTO ExternalBusinessReviews (
                    id, business_id, source, external_review_id,
                    rating, author_name, text, response_text, response_at,
                    published_at, raw_payload, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    rating=excluded.rating,
                    author_name=excluded.author_name,
                    text=excluded.text,
                    response_text=excluded.response_text,
                    response_at=excluded.response_at,
                    published_at=excluded.published_at,
                    raw_payload=excluded.raw_payload,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    r.id,
                    r.business_id,
                    r.source,
                    r.external_review_id,
                    r.rating,
                    r.author_name,
                    r.text,
                    r.response_text,
                    r.response_at,
                    r.published_at,
                    json.dumps(r.raw_payload or {}),
                ),
            )

    def upsert_stats(self, stats: List[ExternalStatsPoint]) -> None:
        if not stats:
            return

        cursor = self.db.conn.cursor()
        for s in stats:
            cursor.execute(
                """
                INSERT INTO ExternalBusinessStats (
                    id, business_id, source, date,
                    views_total, clicks_total, actions_total,
                    rating, reviews_total, unanswered_reviews_count, raw_payload,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    views_total=excluded.views_total,
                    clicks_total=excluded.clicks_total,
                    actions_total=excluded.actions_total,
                    rating=excluded.rating,
                    reviews_total=excluded.reviews_total,
                    unanswered_reviews_count=excluded.unanswered_reviews_count,
                    raw_payload=excluded.raw_payload,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    s.id,
                    s.business_id,
                    s.source,
                    s.date,
                    s.views_total,
                    s.clicks_total,
                    s.actions_total,
                    s.rating,
                    s.reviews_total,
                    s.unanswered_reviews_count,
                    json.dumps(s.raw_payload or {}),
                ),
            )

    def upsert_posts(self, posts: List[ExternalPost]) -> None:
        if not posts:
            return

        cursor = self.db.conn.cursor()
        for p in posts:
            cursor.execute(
                """
                INSERT INTO ExternalBusinessPosts (
                    id, business_id, source, external_post_id,
                    title, text, published_at, image_url, raw_payload,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    text=excluded.text,
                    published_at=excluded.published_at,
                    image_url=excluded.image_url,
                    raw_payload=excluded.raw_payload,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    p.id,
                    p.business_id,
                    p.source,
                    p.external_post_id,
                    p.title,
                    p.text,
                    p.published_at,
                    p.image_url,
                    json.dumps(p.raw_payload or {}),
                ),
            )

    def upsert_photos(self, photos: List[ExternalPhoto]) -> None:
        if not photos:
            return

        cursor = self.db.conn.cursor()
        for p in photos:
            cursor.execute(
                """
                INSERT INTO ExternalBusinessPhotos (
                    id, business_id, source, external_photo_id,
                    url, thumbnail_url, uploaded_at, raw_payload,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    url=excluded.url,
                    thumbnail_url=excluded.thumbnail_url,
                    uploaded_at=excluded.uploaded_at,
                    raw_payload=excluded.raw_payload,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    p.id,
                    p.business_id,
                    p.source,
                    p.external_photo_id,
                    p.url,
                    p.thumbnail_url,
                    p.uploaded_at,
                    json.dumps(p.raw_payload or {}),
                ),
            )
