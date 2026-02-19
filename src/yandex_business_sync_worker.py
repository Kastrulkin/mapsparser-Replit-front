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
from dotenv import load_dotenv

load_dotenv()

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
            WHERE id = %s AND source = %s
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
    
    def _sync_services_to_db(self, conn, business_id: str, products: list, owner_id: str):
        """
        Синхронизирует распаршенные услуги в таблицу UserServices.
        (Дубликат логики из worker.py для избежания циклических импортов)
        """
        if not products:
            return
            
        if not owner_id:
             print(f"⚠️ [SyncWorker] Service sync skipped: owner_id missing for {business_id}")
             # Fail fast
             raise ValueError(f"owner_id is required for service sync for {business_id}")

        cursor = conn.cursor()
        
        # 1. Проверяем наличие таблицы UserServices (PostgreSQL: to_regclass)
        cursor.execute("SELECT to_regclass('public.userservices') AS reg")
        reg = cursor.fetchone()
        # RealDictCursor возвращает dict; tuple — для sqlite
        reg_val = (reg.get('reg') if isinstance(reg, dict) else (reg[0] if reg else None)) if reg else None
        if not reg_val:
            return  # Таблицы нет — синхронизировать некуда
        
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
                        raw_str = str(raw_price).strip().lower()
                        # Заменяем запятую на точку для float
                        clean_str = raw_str.replace(',', '.')
                        
                        # Коэффициенты
                        multiplier = 1.0
                        if 'тыс' in raw_str:
                            multiplier = 1000.0
                        elif 'млн' in raw_str:
                            multiplier = 1000000.0
                            
                        # Извлекаем число (например "1.2")
                        # Регулярка ищет число с плавающей точкой
                        match = re.search(r'(\d+(?:\.\d+)?)', clean_str)
                        if match:
                            val = float(match.group(1))
                            price_cents = int(val * multiplier)
                    except:
                        pass
                
                # Ищем существующую услугу
                cursor.execute("""
                    SELECT id FROM UserServices 
                    WHERE business_id = %s AND name = %s
                """, (business_id, name))
                
                row = cursor.fetchone()
                
                if row:
                    service_id = row[0]
                    cursor.execute("""
                        UPDATE UserServices 
                        SET price = %s, description = %s, category = %s, updated_at = CURRENT_TIMESTAMP, is_active = 1
                        WHERE id = %s
                    """, (price_cents, description, category_name, service_id))
                    count_updated += 1
                else:
                    service_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO UserServices (id, business_id, user_id, name, description, category, price, is_active, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP)
                    """, (service_id, business_id, owner_id, name, description, category_name, price_cents))
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
        # В некоторых окружениях legacy-таблица может отсутствовать.
        cursor.execute("SELECT to_regclass('public.mapparseresults') AS reg")
        reg_row = cursor.fetchone()
        reg_val = None
        if isinstance(reg_row, dict):
            reg_val = reg_row.get("reg")
            if reg_val is None and reg_row:
                reg_val = next(iter(reg_row.values()))
        elif isinstance(reg_row, (list, tuple)):
            reg_val = reg_row[0] if reg_row else None
        else:
            reg_val = reg_row
        if not reg_val:
            return
        
        # Неотвеченные и общее количество — из БД (после upsert_reviews)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM ExternalBusinessReviews 
            WHERE business_id = %s AND source = %s 
              AND (response_text IS NULL OR TRIM(COALESCE(response_text, '')) = '' OR TRIM(response_text) = '—')
        """, (business_id, self.source))
        unr_row = cursor.fetchone()
        unanswered_reviews_count = list(unr_row.values())[0] if unr_row and isinstance(unr_row, dict) else (unr_row[0] if unr_row else 0)

        cursor.execute("""
            SELECT COUNT(*) FROM ExternalBusinessReviews
            WHERE business_id = %s AND source = %s
        """, (business_id, self.source))
        row = cursor.fetchone()
        db_reviews_count = list(row.values())[0] if row and isinstance(row, dict) else (row[0] if row else 0)
        if db_reviews_count and int(db_reviews_count) > reviews_count:
            reviews_count = int(db_reviews_count)

        # Получаем последние успешные данные из MapParseResults для сравнения/слияния
        cursor.execute("""
            SELECT rating, reviews_count, news_count, photos_count, unanswered_reviews_count
            FROM MapParseResults
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        existing_row = cursor.fetchone()

        def _v(r, k):
            if r is None:
                return None
            return r.get(k) if isinstance(r, dict) else (r[k] if isinstance(k, int) and isinstance(r, (list, tuple)) else None)

        # Рейтинг: берем из org_info, иначе из статистики, иначе из истории
        rating = org_info.get('rating') if org_info else None
        if not rating:
            cursor.execute("""
                SELECT rating 
                FROM ExternalBusinessStats 
                WHERE business_id = %s AND source = %s 
                ORDER BY date DESC LIMIT 1
            """, (business_id, self.source))
            stat_row = cursor.fetchone()
            rating = _v(stat_row, 'rating') or (stat_row[0] if stat_row and isinstance(stat_row, (list, tuple)) else None)

        # Smart Merge: если текущие данные пустые, берем из истории
        if existing_row:
            if not rating:
                rating = _v(existing_row, 'rating') or (existing_row[0] if isinstance(existing_row, (list, tuple)) else None)
            if reviews_count == 0:
                rc = _v(existing_row, 'reviews_count') or (existing_row[1] if isinstance(existing_row, (list, tuple)) else None)
                if rc and int(rc) > 0:
                    reviews_count = int(rc)
            if news_count == 0:
                nc = _v(existing_row, 'news_count') or (existing_row[2] if isinstance(existing_row, (list, tuple)) else None)
                if nc and int(nc) > 0:
                    news_count = int(nc)
            if photos_count == 0:
                pc = _v(existing_row, 'photos_count') or (existing_row[3] if isinstance(existing_row, (list, tuple)) else None)
                if pc and int(pc) > 0:
                    photos_count = int(pc)

        parse_id = str(uuid.uuid4())
        url = f"https://yandex.ru/sprav/{external_id or 'unknown'}"
        
        # Проверяем наличие колонок (PostgreSQL: information_schema)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'mapparseresults'
        """)
        columns = [row[0] for row in cursor.fetchall()]

        # Динамическое построение запроса
        fields = ["id", "business_id", "url", "map_type", "rating", "reviews_count", "news_count", "photos_count", "created_at"]
        values_qm = ["%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "CURRENT_TIMESTAMP"]
        values = [parse_id, business_id, url, 'yandex', str(rating) if rating else None, reviews_count, news_count, photos_count]

        if 'unanswered_reviews_count' in columns:
            fields.append("unanswered_reviews_count")
            values_qm.append("%s")
            values.append(unanswered_reviews_count)
            
        if 'services_count' in columns:
            fields.append("services_count")
            values_qm.append("%s")
            # Calculate services count from products list
            s_count = len(products) if products else 0
            values.append(s_count)
            
        if 'products' in columns and products:
            fields.append("products")
            values_qm.append("%s")
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
            
            # Ensure external_id is in account dict for fetch_reviews
            if 'external_id' not in account and 'external_id' in locals():
                account['external_id'] = external_id

            # FETCH OWNER ID (Strict)
            cursor = db.conn.cursor()
            cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (account['business_id'],))
            row = cursor.fetchone()
            owner_id = row[0] if row else None
            
            if not owner_id:
                print(f"⚠️ [SyncAccount] Owner ID missing for business {account['business_id']}. Service sync may fail.")
            
            # Fetch & Upsert
            reviews = parser.fetch_reviews(account)
            repository.upsert_reviews(reviews)

            # Неотвеченные — из БД (точнее, чем len парсера при пагинации)
            cursor.execute("""
                SELECT COUNT(*) FROM ExternalBusinessReviews
                WHERE business_id = %s AND source = %s
                  AND (response_text IS NULL OR TRIM(COALESCE(response_text, '')) IN ('', '—'))
            """, (account['business_id'], self.source))
            unr_row = cursor.fetchone()
            unanswered_count = list(unr_row.values())[0] if unr_row and isinstance(unr_row, dict) else (unr_row[0] if unr_row else 0)
            unanswered_count = int(unanswered_count) if unanswered_count else 0

            stats = parser.fetch_stats(account)
            # Доп. логика для org_info в последней точке статистики
            org_info = parser.fetch_organization_info(account)

            if org_info and stats:
                last_stat = stats[-1]
                if last_stat.raw_payload:
                    last_stat.raw_payload.update(org_info)
                else:
                    last_stat.raw_payload = org_info

            # reviews_total из БД (точнее при пагинации)
            cursor.execute("""
                SELECT COUNT(*) FROM ExternalBusinessReviews
                WHERE business_id = %s AND source = %s
            """, (account['business_id'], self.source))
            rt_row = cursor.fetchone()
            reviews_total_db = list(rt_row.values())[0] if rt_row and isinstance(rt_row, dict) else (rt_row[0] if rt_row else len(reviews))

            # Обновляем стат-поинты (или добавляем в последний)
            if stats:
                stats[-1].unanswered_reviews_count = unanswered_count
                stats[-1].reviews_total = int(reviews_total_db) if reviews_total_db else len(reviews)
                repository.upsert_stats(stats)
            else:
                today_str = datetime.now().strftime('%Y-%m-%d')
                stat_id = f"{account['business_id']}_{self.source}_{today_str}"
                new_stat = ExternalStatsPoint(
                    id=stat_id,
                    business_id=account['business_id'],
                    source=self.source,
                    date=today_str,
                    unanswered_reviews_count=unanswered_count,
                    rating=org_info.get('rating') if org_info else None,
                    reviews_total=int(reviews_total_db) if reviews_total_db else len(reviews)
                )
                stats = [new_stat]
                repository.upsert_stats(stats)
            
            posts = parser.fetch_posts(account)
            repository.upsert_posts(posts)
            
            photos_count = parser.fetch_photos_count(account)
            
            # --- EXTRACT AND SYNC SERVICES (NEW) ---
            try:
                products = parser.fetch_products(account)
                if products:
                    print(f"📦 Получено {len(products)} категорий услуг")
                    self._sync_services_to_db(db.conn, account['business_id'], products, owner_id=owner_id)
                else:
                    print("⚠️ Услуги не найдены или пустой список")
            except Exception as e:
                print(f"⚠️ Ошибка при синхронизации услуг: {e}")
                products = []
            
            # Обновляем MapParseResults для совместимости с UI
            self._update_map_parse_results(
                db, account, org_info,
                reviews_count=int(reviews_total_db) if reviews_total_db else len(reviews),
                news_count=len(posts),
                photos_count=photos_count,
                products=products,
            )

            # Принудительно обновляем статус синхронизации аккаунта.
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'externalbusinessaccounts'
                  AND column_name = 'last_sync_status'
                """
            )
            has_status_row = cursor.fetchone()
            has_last_sync_status = (
                (has_status_row.get("count", 0) if isinstance(has_status_row, dict) else has_status_row[0])
                > 0
            ) if has_status_row else False
            if has_last_sync_status:
                cursor.execute(
                    """
                    UPDATE ExternalBusinessAccounts
                    SET last_sync_at = CURRENT_TIMESTAMP,
                        last_sync_status = 'success',
                        last_error = NULL
                    WHERE id = %s
                    """,
                    (account['id'],),
                )
            else:
                cursor.execute(
                    """
                    UPDATE ExternalBusinessAccounts
                    SET last_sync_at = CURRENT_TIMESTAMP,
                        last_error = NULL
                    WHERE id = %s
                    """,
                    (account['id'],),
                )
            db.conn.commit()
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
