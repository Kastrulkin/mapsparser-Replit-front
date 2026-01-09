#!/usr/bin/env python3
"""
Воркер для синхронизации данных из личных кабинетов Яндекс.Бизнес.
"""

from __future__ import annotations

import json
import uuid
import traceback
from typing import List, Optional
from datetime import datetime

from database_manager import DatabaseManager
from external_sources import ExternalSource, ExternalReview, ExternalStatsPoint
from auth_encryption import decrypt_auth_data
from yandex_business_parser import YandexBusinessParser
from base_sync_worker import BaseSyncWorker
from repositories.external_data_repository import ExternalDataRepository


class YandexBusinessSyncWorker(BaseSyncWorker):
    """Воркер синхронизации Яндекс.Бизнес аккаунтов."""

    def __init__(self) -> None:
        super().__init__(ExternalSource.YANDEX_BUSINESS)

    def _get_account_by_id(self, db: DatabaseManager, account_id: str) -> Optional[dict]:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM ExternalBusinessAccounts
            WHERE id = ? AND source = ?
            """,
            (account_id, self.source),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _upsert_reviews(self, db: DatabaseManager, reviews: List[ExternalReview]) -> None:
        """Вставка/обновление отзывов (для совместимости с worker.py)"""
        repository = ExternalDataRepository(db)
        repository.upsert_reviews(reviews)

    def _update_map_parse_results(self, db: DatabaseManager, account: dict, 
                                  org_info: dict, reviews_count: int, news_count: int, photos_count: int) -> None:
        """Обновление таблицы MapParseResults для отображения статуса в дашборде"""
        business_id = account.get('business_id')
        external_id = account.get('external_id')
        if not business_id:
            return

        cursor = db.conn.cursor()
        
        # Получаем данные о неотвеченных отзывах из БД
        # Так как мы только что сохранили отзывы в ExternalBusinessReviews, можем считать оттуда
        cursor.execute("""
            SELECT COUNT(*) 
            FROM ExternalBusinessReviews 
            WHERE business_id = ? AND source = ? 
              AND (response_text IS NULL OR response_text = '' OR response_text = '—')
        """, (business_id, self.source))
        unanswered_reviews_count = cursor.fetchone()[0]
        
        # Рейтинг берем из org_info или БД
        rating = org_info.get('rating')
        if not rating:
            cursor.execute("""
                SELECT rating 
                FROM ExternalBusinessStats 
                WHERE business_id = ? AND source = ? 
                ORDER BY date DESC LIMIT 1
            """, (business_id, self.source))
            row = cursor.fetchone()
            rating = row[0] if row else None

        parse_id = str(uuid.uuid4())
        url = f"https://yandex.ru/sprav/{external_id or 'unknown'}"
        
        # Проверяем наличие колонки unanswered_reviews_count (на всякий случай, хотя индекс создавался)
        cursor.execute("PRAGMA table_info(MapParseResults)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'unanswered_reviews_count' in columns:
            cursor.execute("""
                INSERT INTO MapParseResults (
                    id, business_id, url, map_type, rating, reviews_count, 
                    unanswered_reviews_count, news_count, photos_count, 
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                parse_id,
                business_id,
                url,
                'yandex',
                str(rating) if rating else None,
                reviews_count,
                unanswered_reviews_count,
                news_count,
                photos_count,
            ))
        else:
             cursor.execute("""
                INSERT INTO MapParseResults (
                    id, business_id, url, map_type, rating, reviews_count, 
                    news_count, photos_count, 
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                parse_id,
                business_id,
                url,
                'yandex',
                str(rating) if rating else None,
                reviews_count,
                news_count,
                photos_count,
            ))
        # Не делаем commit здесь, он будет в sync_account

    def sync_account(self, account_id: str) -> None:
        """Синхронизировать один аккаунт по ID"""
        db = DatabaseManager()
        try:
            repository = ExternalDataRepository(db)
            account = self._get_account_by_id(db, account_id)
            if not account:
                print(f"❌ Аккаунт {account_id} не найден")
                return

            print(f"🔄 Синхронизация аккаунта {account_id} ({account.get('business_id')})")
            
            # Расшифровываем auth_data
            auth_data_encrypted = account.get("auth_data_encrypted")
            if not auth_data_encrypted:
                raise ValueError("Нет auth_data")
            
            auth_data_plain = decrypt_auth_data(auth_data_encrypted)
            if not auth_data_plain:
                raise ValueError("Не удалось расшифровать auth_data")
            
            try:
                auth_data_dict = json.loads(auth_data_plain)
            except json.JSONDecodeError:
                auth_data_dict = {"cookies": auth_data_plain}
            
            parser = YandexBusinessParser(auth_data_dict)
            
            # Fetch & Upsert
            reviews = parser.fetch_reviews(account)
            repository.upsert_reviews(reviews)
            
            stats = parser.fetch_stats(account)
            # Доп. логика для org_info в последней точке статистики
            org_info = parser.fetch_organization_info(account)
            
            if stats:
                if org_info:
                    last_stat = stats[-1]
                    if last_stat.raw_payload:
                        last_stat.raw_payload.update(org_info)
                    else:
                        last_stat.raw_payload = org_info
                repository.upsert_stats(stats)
            
            posts = parser.fetch_posts(account)
            repository.upsert_posts(posts)
            
            photos_count = parser.fetch_photos_count(account)
            
            # Обновляем MapParseResults для совместимости с UI
            self._update_map_parse_results(
                db, account, org_info, 
                reviews_count=len(reviews), 
                news_count=len(posts), 
                photos_count=photos_count
            )

            self._update_account_sync_status(db, account['id'])
            print(f"✅ Синхронизация аккаунта {account_id} завершена")

        except Exception as e:
            print(f"❌ Ошибка синхронизации аккаунта {account_id}: {e}")
            traceback.print_exc()
            self._update_account_sync_status(db, account_id, error=str(e))
        finally:
            db.close()

    def run_once(self) -> None:
        """Один проход синхронизации по всем активным аккаунтам"""
        db = DatabaseManager()
        try:
            accounts = self._load_active_accounts(db)
            print(f"[YandexBusinessSyncWorker] Активных аккаунтов: {len(accounts)}")
            # Здесь мы закрываем соединение, так как sync_account открывает своё
            # Но _load_active_accounts принимает db...
            # Просто соберем ID
            account_ids = [acc['id'] for acc in accounts]
        finally:
            db.close()
            
        for acc_id in account_ids:
            self.sync_account(acc_id)


def main() -> None:
    worker = YandexBusinessSyncWorker()
    worker.run_once()


if __name__ == "__main__":
    main()
