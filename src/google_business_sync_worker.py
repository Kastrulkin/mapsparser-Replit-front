#!/usr/bin/env python3
"""
Каркас воркера для синхронизации данных из Google Business Profile
(Google My Business).

Важно:
- Здесь нет реальных вызовов Google API — только структура.
- Реальная интеграция через OAuth 2.0 и Business Profile API
  будет добавлена отдельным этапом.
"""

from __future__ import annotations

import json
from datetime import datetime, date
from typing import List

from database_manager import DatabaseManager
from external_sources import ExternalSource, ExternalReview, ExternalStatsPoint, make_stats_id


class GoogleBusinessSyncWorker:
    def __init__(self) -> None:
        self.source = ExternalSource.GOOGLE_BUSINESS

    def _load_active_accounts(self, db: DatabaseManager) -> List[dict]:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM ExternalBusinessAccounts
            WHERE source = ? AND is_active = 1
            """,
            (self.source,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def _fake_fetch_reviews(self, account: dict) -> List[ExternalReview]:
        """Заглушка вместо реального вызова Google Business Profile API."""
        now = datetime.utcnow()
        rid = f"{account['id']}_google_demo_review"
        return [
            ExternalReview(
                id=rid,
                business_id=account["business_id"],
                source=self.source,
                external_review_id=rid,
                rating=5,
                author_name="Google Demo Author",
                text="Demo review from Google Business (placeholder).",
                published_at=now,
                raw_payload={"demo": True},
            )
        ]

    def _fake_fetch_stats(self, account: dict) -> List[ExternalStatsPoint]:
        today_str = date.today().isoformat()
        sid = make_stats_id(account["business_id"], self.source, today_str)
        return [
            ExternalStatsPoint(
                id=sid,
                business_id=account["business_id"],
                source=self.source,
                date=today_str,
                views_total=200,
                clicks_total=20,
                actions_total=8,
                rating=4.7,
                reviews_total=56,
                raw_payload={"demo": True},
            )
        ]

    def _upsert_reviews(self, db: DatabaseManager, reviews: List[ExternalReview]) -> None:
        cursor = db.conn.cursor()
        for r in reviews:
            cursor.execute(
                """
                INSERT INTO ExternalBusinessReviews (
                    id, business_id, account_id, source, external_review_id,
                    rating, author_name, text, response_text, response_at,
                    published_at, raw_payload, created_at, updated_at
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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

    def _upsert_stats(self, db: DatabaseManager, stats: List[ExternalStatsPoint]) -> None:
        cursor = db.conn.cursor()
        for s in stats:
            cursor.execute(
                """
                INSERT INTO ExternalBusinessStats (
                    id, business_id, account_id, source, date,
                    views_total, clicks_total, actions_total,
                    rating, reviews_total, raw_payload,
                    created_at, updated_at
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    views_total=excluded.views_total,
                    clicks_total=excluded.clicks_total,
                    actions_total=excluded.actions_total,
                    rating=excluded.rating,
                    reviews_total=excluded.reviews_total,
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
                    json.dumps(s.raw_payload or {}),
                ),
            )

    def run_once(self) -> None:
        db = DatabaseManager()
        try:
            accounts = self._load_active_accounts(db)
            print(f"[GoogleBusinessSyncWorker] Активных аккаунтов: {len(accounts)}")
            for acc in accounts:
                try:
                    reviews = self._fake_fetch_reviews(acc)
                    stats = self._fake_fetch_stats(acc)
                    self._upsert_reviews(db, reviews)
                    self._upsert_stats(db, stats)

                    cursor = db.conn.cursor()
                    cursor.execute(
                        """
                        UPDATE ExternalBusinessAccounts
                        SET last_sync_at = ?, last_error = NULL
                        WHERE id = ?
                        """,
                        (datetime.utcnow(), acc["id"]),
                    )
                    db.conn.commit()
                    print(f"[GoogleBusinessSyncWorker] Синк демо-данных для аккаунта {acc['id']} завершён")
                except Exception as e:  # noqa: BLE001
                    db.conn.rollback()
                    cursor = db.conn.cursor()
                    cursor.execute(
                        """
                        UPDATE ExternalBusinessAccounts
                        SET last_error = ?
                        WHERE id = ?
                        """,
                        (str(e), acc["id"]),
                    )
                    db.conn.commit()
                    print(f"[GoogleBusinessSyncWorker] Ошибка синхронизации аккаунта {acc['id']}: {e}")
        finally:
            db.close()


def main() -> None:
    worker = GoogleBusinessSyncWorker()
    worker.run_once()


if __name__ == "__main__":
    main()


