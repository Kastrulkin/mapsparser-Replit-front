#!/usr/bin/env python3
"""
Воркер для синхронизации данных из личных кабинетов Яндекс.Бизнес.

Важные замечания:
- Этот файл содержит только каркас без реального парсинга ЛК.
- Реальные HTTP / Playwright-запросы к cabinet.yandex.* будут
  добавлены отдельно, чтобы не ломать прод и не нарушать ToS.

Сценарий работы (цель):
- Берём активные записи из ExternalBusinessAccounts с source='yandex_business'
- Для каждой:
    - поднимаем Playwright / HTTP-клиент с расшифрованным auth_data_encrypted
    - тянем XHR-эндпоинты кабинета (рейтинг, отзывы, статистика)
    - сохраняем "сырые" данные в ExternalBusinessReviews / ExternalBusinessStats
- При ошибках:
    - пишем last_error в ExternalBusinessAccounts
    - не валим воркер целиком
"""

from __future__ import annotations

import json
from datetime import datetime, date
from typing import List

from database_manager import DatabaseManager
from external_sources import ExternalSource, ExternalReview, ExternalStatsPoint, make_stats_id
from auth_encryption import decrypt_auth_data
from yandex_business_parser import YandexBusinessParser


class YandexBusinessSyncWorker:
    """Каркас воркера синхронизации Яндекс.Бизнес аккаунтов."""

    def __init__(self) -> None:
        self.source = ExternalSource.YANDEX_BUSINESS

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

    # ==== Заглушки с примером сохранения ====

    def _fake_fetch_reviews(self, account: dict) -> List[ExternalReview]:
        """
        Временная заглушка, чтобы не вызывать реальные внешние сервисы.

        Позже сюда приедет логика Playwright / HTTP-запросов
        к ЛК Яндекс.Бизнес.
        """
        today = datetime.utcnow()
        rid = f"{account['id']}_demo_review"
        return [
            ExternalReview(
                id=rid,
                business_id=account["business_id"],
                source=self.source,
                external_review_id=rid,
                rating=5,
                author_name="Demo Author",
                text="Это демо-отзыв из Яндекс.Бизнес (заглушка).",
                published_at=today,
                response_text=None,
                response_at=None,
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
                views_total=100,
                clicks_total=10,
                actions_total=5,
                rating=4.8,
                reviews_total=123,
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
        """Один проход синхронизации по всем активным аккаунтам Яндекс.Бизнес."""
        db = DatabaseManager()
        try:
            accounts = self._load_active_accounts(db)
            print(f"[YandexBusinessSyncWorker] Активных аккаунтов: {len(accounts)}")
            for acc in accounts:
                try:
                    # Расшифровываем auth_data
                    auth_data_encrypted = acc.get("auth_data_encrypted")
                    if not auth_data_encrypted:
                        print(f"⚠️ Нет auth_data для аккаунта {acc['id']}, пропускаем")
                        continue
                    
                    auth_data_plain = decrypt_auth_data(auth_data_encrypted)
                    if not auth_data_plain:
                        print(f"⚠️ Не удалось расшифровать auth_data для аккаунта {acc['id']}, пропускаем")
                        continue
                    
                    # Парсим JSON auth_data
                    try:
                        auth_data_dict = json.loads(auth_data_plain)
                    except json.JSONDecodeError:
                        # Если не JSON, предполагаем что это просто cookies строка
                        auth_data_dict = {"cookies": auth_data_plain}
                    
                    # Создаём парсер и получаем данные
                    parser = YandexBusinessParser(auth_data_dict)
                    reviews = parser.fetch_reviews(acc)
                    stats = parser.fetch_stats(acc)
                    
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
                    print(f"[YandexBusinessSyncWorker] Синк данных для аккаунта {acc['id']} завершён")
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
                    print(f"[YandexBusinessSyncWorker] Ошибка синхронизации аккаунта {acc['id']}: {e}")
        finally:
            db.close()


def main() -> None:
    worker = YandexBusinessSyncWorker()
    worker.run_once()


if __name__ == "__main__":
    main()


