#!/usr/bin/env python3
"""
Воркер для синхронизации данных из Google Business Profile API
"""

from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from database_manager import DatabaseManager
from external_sources import ExternalSource, ExternalReview, ExternalStatsPoint, make_stats_id
from google_business_api import GoogleBusinessAPI
from google_business_auth import GoogleBusinessAuth
from auth_encryption import decrypt_auth_data, encrypt_auth_data


class GoogleBusinessSyncWorker:
    def __init__(self) -> None:
        self.source = ExternalSource.GOOGLE_BUSINESS
        self.auth = GoogleBusinessAuth()

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

    def _get_api_client(self, account: dict) -> Optional[GoogleBusinessAPI]:
        """Получить API клиент для аккаунта"""
        try:
            auth_data_encrypted = account.get('auth_data')
            if not auth_data_encrypted:
                print(f"⚠️ Нет auth_data для аккаунта {account['id']}")
                return None
            
            # Расшифровываем credentials
            auth_data_json = decrypt_auth_data(auth_data_encrypted)
            auth_data = json.loads(auth_data_json)
            
            # Восстанавливаем credentials
            credentials = self.auth.dict_to_credentials(auth_data)
            
            # Обновляем токен, если нужно
            if credentials.expired:
                credentials = self.auth.refresh_credentials(credentials)
                # Сохраняем обновленные credentials
                self._save_credentials(account['id'], credentials)
            
            return GoogleBusinessAPI(credentials)
        except Exception as e:
            print(f"❌ Ошибка создания API клиента для аккаунта {account['id']}: {e}")
            return None
    
    def _save_credentials(self, account_id: str, credentials: Credentials) -> None:
        """Сохранить обновленные credentials в БД"""
        try:
            creds_dict = self.auth.credentials_to_dict(credentials)
            creds_json = json.dumps(creds_dict)
            encrypted_creds = encrypt_auth_data(creds_json)
            
            db = DatabaseManager()
            cursor = db.conn.cursor()
            cursor.execute("""
                UPDATE ExternalBusinessAccounts
                SET auth_data = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (encrypted_creds, account_id))
            db.conn.commit()
            db.close()
        except Exception as e:
            print(f"⚠️ Ошибка сохранения credentials: {e}")
    
    def _fetch_reviews(self, account: dict) -> List[ExternalReview]:
        """Получить отзывы через API"""
        api = self._get_api_client(account)
        if not api:
            return []
        
        location_name = account.get('external_id')
        if not location_name:
            print(f"⚠️ Нет external_id для аккаунта {account['id']}")
            return []
        
        reviews_data = api.list_reviews(location_name)
        reviews = []
        
        for review_data in reviews_data:
            review_id = review_data.get('reviewId')
            review = review_data.get('review', {})
            
            # Парсим дату
            published_at = None
            create_time = review.get('createTime')
            if create_time:
                try:
                    published_at = datetime.fromisoformat(create_time.replace('Z', '+00:00'))
                except Exception:
                    pass
            
            # Парсим ответ организации
            response_text = None
            response_at = None
            reply = review.get('reply')
            if reply:
                response_text = reply.get('comment', '')
                if 'updateTime' in reply:
                    try:
                        response_at = datetime.fromisoformat(reply['updateTime'].replace('Z', '+00:00'))
                    except Exception:
                        pass
            
            reviews.append(ExternalReview(
                id=f"{account['business_id']}_google_{review_id}",
                business_id=account['business_id'],
                source=self.source,
                external_review_id=review_id,
                rating=review.get('starRating', {}).get('value') if review.get('starRating') else None,
                author_name=review.get('reviewer', {}).get('displayName', 'Анонимный пользователь'),
                text=review.get('comment', ''),
                published_at=published_at,
                response_text=response_text,
                response_at=response_at,
                raw_payload=review_data
            ))
        
        return reviews
    
    def _fetch_stats(self, account: dict) -> List[ExternalStatsPoint]:
        """Получить статистику через API"""
        api = self._get_api_client(account)
        if not api:
            return []
        
        location_name = account.get('external_id')
        if not location_name:
            return []
        
        # Получаем статистику за последние 30 дней
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        insights = api.get_insights(
            location_name,
            start_date.isoformat() + 'Z',
            end_date.isoformat() + 'Z'
        )
        
        # Парсим insights и создаем ExternalStatsPoint
        stats = []
        if insights and 'locationMetrics' in insights:
            for metric_data in insights['locationMetrics']:
                metric_values = metric_data.get('metricValues', [])
                if not metric_values:
                    continue
                
                # Агрегируем данные по дням
                daily_data = {}
                for value in metric_values:
                    time_value = value.get('timeValue', {})
                    time_range = time_value.get('timeRange', {})
                    start_time = time_range.get('startTime', {})
                    date_str = start_time.get('date', {})
                    
                    if not date_str:
                        continue
                    
                    day_key = f"{date_str.get('year')}-{date_str.get('month'):02d}-{date_str.get('day'):02d}"
                    if day_key not in daily_data:
                        daily_data[day_key] = {
                            'views_total': 0,
                            'clicks_total': 0,
                            'actions_total': 0
                        }
                    
                    metric_name = metric_data.get('metric')
                    dimensional_values = value.get('dimensionalValues', [{}])
                    metric_value = dimensional_values[0].get('value', 0) if dimensional_values else 0
                    
                    if 'VIEWS' in metric_name:
                        daily_data[day_key]['views_total'] += int(metric_value or 0)
                    elif 'ACTIONS' in metric_name:
                        daily_data[day_key]['actions_total'] += int(metric_value or 0)
                
                # Создаем ExternalStatsPoint для каждого дня
                for day_key, day_data in daily_data.items():
                    sid = make_stats_id(account['business_id'], self.source, day_key)
                    stats.append(ExternalStatsPoint(
                        id=sid,
                        business_id=account['business_id'],
                        source=self.source,
                        date=day_key,
                        views_total=day_data['views_total'],
                        clicks_total=day_data['clicks_total'],
                        actions_total=day_data['actions_total'],
                        rating=None,  # Рейтинг получаем отдельно
                        reviews_total=None,  # Количество отзывов получаем отдельно
                        raw_payload=insights
                    ))
        
        return stats
    
    def _publish_review_reply(self, account: dict, review_id: str, reply_text: str) -> bool:
        """Опубликовать ответ на отзыв"""
        api = self._get_api_client(account)
        if not api:
            return False
        
        location_name = account.get('external_id')
        if not location_name:
            return False
        
        return api.update_review_reply(location_name, review_id, reply_text)
    
    def _publish_post(self, account: dict, post_data: Dict[str, Any]) -> Optional[str]:
        """Опубликовать пост/новость"""
        api = self._get_api_client(account)
        if not api:
            return None
        
        location_name = account.get('external_id')
        if not location_name:
            return None
        
        return api.create_local_post(location_name, post_data)

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
                    reviews = self._fetch_reviews(acc)
                    stats = self._fetch_stats(acc)
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


