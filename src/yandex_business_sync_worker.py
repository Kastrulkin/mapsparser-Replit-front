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
    
    def _upsert_stats(self, db: DatabaseManager, stats: List[ExternalStatsPoint]) -> None:
        """Вставка/обновление статистики (для совместимости с main.py)"""
        repository = ExternalDataRepository(db)
        repository.upsert_stats(stats)
    
    def _sync_services_to_db(self, conn, business_id: str, products: list):
        """
        Синхронизирует распаршенные услуги в таблицу UserServices.
        (Дубликат логики из worker.py для избежания циклических импортов)
        """
        if not products:
            return

        cursor = conn.cursor()
        
        # 1. Проверяем наличие таблицы UserServices и нужных колонок
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UserServices'")
        if not cursor.fetchone():
            return # Если таблицы нет, то и синхронизировать некуда (она создается в worker.py или миграции)
        
        count_new = 0
        count_updated = 0
        
        for category_data in products:
            category_name = category_data.get('category', 'Разное')
            items = category_data.get('items', [])
            
            for item in items:
                name = item.get('name')
                if not name:
                    continue
                    
                raw_price = item.get('price', '')
                description = item.get('description', '')
                
                # Парсинг цены
                price_cents = None
                if raw_price:
                    try:
                        import re
                        digits = re.sub(r'[^0-9]', '', str(raw_price))
                        if digits:
                            price_cents = int(digits) * 100 
                    except:
                        pass
                
                # Ищем существующую услугу
                cursor.execute("""
                    SELECT id FROM UserServices 
                    WHERE business_id = ? AND name = ?
                """, (business_id, name))
                
                row = cursor.fetchone()
                
                if row:
                    service_id = row[0]
                    cursor.execute("""
                        UPDATE UserServices 
                        SET price = ?, description = ?, category = ?, updated_at = CURRENT_TIMESTAMP, is_active = 1
                        WHERE id = ?
                    """, (price_cents, description, category_name, service_id))
                    count_updated += 1
                else:
                    service_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO UserServices (id, business_id, name, description, category, price, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                    """, (service_id, business_id, name, description, category_name, price_cents))
                    count_new += 1
                    
        conn.commit()
        print(f"📊 [SyncWorker] Синхронизация услуг: {count_new} новых, {count_updated} обновлено.")

    def _upsert_posts(self, db: DatabaseManager, posts: list) -> None:
        """Вставка/обновление постов (для совместимости с main.py)"""
        repository = ExternalDataRepository(db)
        repository.upsert_posts(posts)

    def _update_map_parse_results(self, db: DatabaseManager, account: dict, 
                                  org_info: dict, reviews_count: int, news_count: int, photos_count: int,
                                  products: list = None) -> None:
        """Обновление таблицы MapParseResults для отображения статуса в дашборде"""
        business_id = account.get('business_id')
        external_id = account.get('external_id')
        if not business_id:
            return

        cursor = db.conn.cursor()
        
        # Получаем данные о неотвеченных отзывах из БД
        cursor.execute("""
            SELECT COUNT(*) 
            FROM ExternalBusinessReviews 
            WHERE business_id = ? AND source = ? 
              AND (response_text IS NULL OR response_text = '' OR response_text = '—')
        """, (business_id, self.source))
        unanswered_reviews_count = cursor.fetchone()[0]

        # Получаем последние успешные данные из MapParseResults для сравнения/слияния
        cursor.execute("""
            SELECT rating, reviews_count, news_count, photos_count, unanswered_reviews_count
            FROM MapParseResults
            WHERE business_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        existing_row = cursor.fetchone()
        
        # Рейтинг: берем из org_info, иначе из статистики, иначе из истории
        rating = org_info.get('rating')
        if not rating:
            cursor.execute("""
                SELECT rating 
                FROM ExternalBusinessStats 
                WHERE business_id = ? AND source = ? 
                ORDER BY date DESC LIMIT 1
            """, (business_id, self.source))
            stat_row = cursor.fetchone()
            rating = stat_row[0] if stat_row else None
            
        # Smart Merge: Если текущие данные пустые/хуже, берем из истории
        if existing_row:
             # Рейтинг
             if not rating and existing_row[0]:
                 rating = existing_row[0]
             
             # Отзывы: если сейчас 0, а было больше - берем старое
             if reviews_count == 0 and existing_row[1] and existing_row[1] > 0:
                 reviews_count = existing_row[1]
                 # И неотвеченные тоже берем старые, если вдруг сейчас 0 (хотя они считаются из БД)
                 # Но мы считали из ExternalBusinessReviews, куда только что записали. 
                 # Если записи не записались (ошибка парсера), count будет 0.
                 # В этом случае логично взять старое
                 if existing_row[4] is not None: # reviews_without_response check
                     # Проверим, есть ли колонка unanswered_reviews_count в MapParseResults
                     # (в fetchone она последняя, если запрос match'ит схему)
                     # В запросе выше: rating, reviews_count, news_count, photos_count, reviews_without_response
                     # В MapParseResults поля могут называться иначе. Проверим запрос:
                     # "SELECT rating, reviews_count, news_count, photos_count FROM..."
                     # А мы добавили reviews_without_response? Нет, надо быть осторожным с этим полем.
                     pass 
             
             # Новости
             if news_count == 0 and existing_row[2] and existing_row[2] > 0:
                 news_count = existing_row[2]
                 
             # Фото
             if photos_count == 0 and existing_row[3] and existing_row[3] > 0:
                 photos_count = existing_row[3]

        parse_id = str(uuid.uuid4())
        url = f"https://yandex.ru/sprav/{external_id or 'unknown'}"
        
        # Проверяем наличие колонки unanswered_reviews_count и products
        cursor.execute("PRAGMA table_info(MapParseResults)")
        columns = [row[1] for row in cursor.fetchall()]

        # Динамическое построение запроса
        fields = ["id", "business_id", "url", "map_type", "rating", "reviews_count", "news_count", "photos_count", "created_at"]
        values_qm = ["?", "?", "?", "?", "?", "?", "?", "?", "CURRENT_TIMESTAMP"]
        values = [parse_id, business_id, url, 'yandex', str(rating) if rating else None, reviews_count, news_count, photos_count]

        if 'unanswered_reviews_count' in columns:
            fields.append("unanswered_reviews_count")
            values_qm.append("?")
            values.append(unanswered_reviews_count)
            
        if 'products' in columns and products:
            fields.append("products")
            values_qm.append("?")
            values.append(json.dumps(products, ensure_ascii=False))

        query = f"INSERT INTO MapParseResults ({', '.join(fields)}) VALUES ({', '.join(values_qm)})"
        
        cursor.execute(query, tuple(values))
        # Не делаем commit здесь, он будет в sync_account

    def sync_account(self, account_id: str) -> None:
        """Синхронизировать один аккаунт по ID"""
        db = None
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
            
            # --- EXTRACT AND SYNC SERVICES (NEW) ---
            try:
                products = parser.fetch_products(account)
                if products:
                    print(f"📦 Получено {len(products)} категорий услуг")
                    self._sync_services_to_db(db.conn, account['business_id'], products)
                else:
                    print("⚠️ Услуги не найдены или пустой список")
            except Exception as e:
                print(f"⚠️ Ошибка при синхронизации услуг: {e}")
                products = []
            
            # Обновляем MapParseResults для совместимости с UI
            self._update_map_parse_results(
                db, account, org_info, 
                reviews_count=len(reviews), 
                news_count=len(posts), 
                photos_count=photos_count,
                products=products
            )
            db.conn.commit()

            self._update_account_sync_status(db, account['id'])
            print(f"✅ Синхронизация аккаунта {account_id} завершена")

        except Exception as e:
            print(f"❌ Ошибка синхронизации аккаунта {account_id}: {e}")
            traceback.print_exc()
            if db:
                self._update_account_sync_status(db, account_id, error=str(e))
            raise e
        finally:
            if db:
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
