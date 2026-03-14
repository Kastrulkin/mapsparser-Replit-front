"""
Сервис для синхронизации данных Яндекс.Карт по бизнесам и сетям.

Сейчас использует адаптер YandexAdapter и записывает данные в:
- Businesses (кеш последних значений по Яндексу)
- YandexBusinessStats (исторические ряды по дням)
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from database_manager import DatabaseManager
from yandex_adapter import YandexAdapter, YandexBusinessStatsPayload


class YandexSyncService:
    """Сервис синхронизации данных Яндекс.Карт."""

    def __init__(self) -> None:
        self.adapter = YandexAdapter()

    def _upsert_stats_for_business(
        self, db: DatabaseManager, business_id: str, payload: YandexBusinessStatsPayload
    ) -> None:
        """Обновить кеш в Businesses и добавить запись в YandexBusinessStats."""
        cursor = db.conn.cursor()

        # Обновляем кеш-поля в Businesses
        cursor.execute(
            """
            UPDATE Businesses
            SET
                yandex_rating = ?,
                yandex_reviews_total = ?,
                yandex_reviews_30d = ?,
                yandex_last_sync = ?
            WHERE id = ?
            """,
            (
                payload.rating,
                payload.reviews_total,
                payload.reviews_30d,
                datetime.utcnow(),
                business_id,
            ),
        )

        # Добавляем историческую запись (по дате, без дубликатов за день)
        today = date.today().isoformat()
        cursor.execute(
            """
            SELECT id FROM YandexBusinessStats
            WHERE business_id = ? AND date = ?
            """,
            (business_id, today),
        )
        row = cursor.fetchone()

        if row:
            # Обновляем существующую запись за сегодняшний день
            cursor.execute(
                """
                UPDATE YandexBusinessStats
                SET rating = ?, reviews_total = ?, reviews_30d = ?, fetched_at = ?
                WHERE id = ?
                """,
                (
                    payload.rating,
                    payload.reviews_total,
                    payload.reviews_30d,
                    datetime.utcnow(),
                    row[0],
                ),
            )
        else:
            # Вставляем новую запись
            stat_id = f"{business_id}_{today}"
            cursor.execute(
                """
                INSERT INTO YandexBusinessStats (id, business_id, date, rating, reviews_total, reviews_30d, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stat_id,
                    business_id,
                    today,
                    payload.rating,
                    payload.reviews_total,
                    payload.reviews_30d,
                    datetime.utcnow(),
                ),
            )

    def sync_business(self, business_id: str) -> bool:
        """Синхронизировать Яндекс-данные для одного бизнеса."""
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            cursor.execute(
                "SELECT yandex_org_id, yandex_url, name FROM Businesses WHERE id = ?",
                (business_id,),
            )
            row = cursor.fetchone()
            if not row:
                print(f"[YandexSync] Бизнес {business_id} не найден")
                return False

            yandex_org_id, yandex_url, name = row
            # Если org_id отсутствует, пробуем извлечь его из URL
            if not yandex_org_id and yandex_url:
                yandex_org_id = self.adapter.parse_org_id_from_url(yandex_url)
                if yandex_org_id:
                    cursor.execute(
                        "UPDATE Businesses SET yandex_org_id = ? WHERE id = ?",
                        (yandex_org_id, business_id),
                    )

            if not yandex_org_id:
                print(f"[YandexSync] Для бизнеса {name} ({business_id}) не задан yandex_org_id")
                db.conn.commit()
                return False

            payload = self.adapter.fetch_business_stats(yandex_org_id)
            if not payload:
                print(f"[YandexSync] Не удалось получить данные Яндекс для {name} ({yandex_org_id})")
                db.conn.commit()
                return False

            self._upsert_stats_for_business(db, business_id, payload)
            db.conn.commit()
            print(f"[YandexSync] Успешно синхронизирован бизнес {name} ({business_id})")
            return True
        except Exception as e:
            print(f"[YandexSync] Ошибка синхронизации бизнеса {business_id}: {e}")
            db.conn.rollback()
            return False
        finally:
            db.close()

    def sync_network(self, network_id: str) -> int:
        """Синхронизировать Яндекс-данные для всех бизнесов сети."""
        db = DatabaseManager()
        cursor = db.conn.cursor()
        synced = 0
        try:
            cursor.execute(
                """
                SELECT id, name
                FROM Businesses
                WHERE network_id = ? AND is_active = 1
                """,
                (network_id,),
            )
            businesses = cursor.fetchall()
            if not businesses:
                print(f"[YandexSync] Для сети {network_id} нет активных бизнесов")
                return 0

            for business_id, name in businesses:
                ok = self.sync_business(business_id)
                if ok:
                    synced += 1

            return synced
        finally:
            db.close()



