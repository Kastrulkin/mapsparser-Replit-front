#!/usr/bin/env python3
"""
Воркер для синхронизации данных из Google Business Profile API
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from google.oauth2.credentials import Credentials

from database_manager import DatabaseManager
from external_sources import ExternalSource, ExternalReview, ExternalStatsPoint, make_stats_id
from google_business_api import GoogleBusinessAPI
from google_business_auth import GoogleBusinessAuth
from auth_encryption import decrypt_auth_data, encrypt_auth_data
from base_sync_worker import BaseSyncWorker
from repositories.external_data_repository import ExternalDataRepository


class GoogleBusinessSyncWorker(BaseSyncWorker):
    def __init__(self) -> None:
        super().__init__(ExternalSource.GOOGLE_BUSINESS)
        self.auth = GoogleBusinessAuth()

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

    def sync_account(self, account_id: str) -> None:
        """Синхронизировать один аккаунт по ID"""
        db = DatabaseManager()
        try:
            repository = ExternalDataRepository(db)
            account = self._get_account_by_id(db, account_id)
            if not account:
                print(f"❌ Аккаунт {account_id} не найден")
                return

            print(f"🔄 Синхронизация аккаунта {account_id}")
            try:
                reviews = self._fetch_reviews(account)
                stats = self._fetch_stats(account)
                
                repository.upsert_reviews(reviews)
                repository.upsert_stats(stats)

                self._update_account_sync_status(db, account['id'])
                print(f"✅ Синхронизация аккаунта {account_id} завершена")
            except Exception as e:
                self._update_account_sync_status(db, account['id'], error=str(e))
                print(f"❌ Ошибка синхронизации аккаунта {account_id}: {e}")
        finally:
            db.close()

    def run_once(self) -> None:
        db = DatabaseManager()
        try:
            accounts = self._load_active_accounts(db)
            print(f"[GoogleBusinessSyncWorker] Активных аккаунтов: {len(accounts)}")
            account_ids = [acc['id'] for acc in accounts]
        finally:
            db.close()
            
        for acc_id in account_ids:
            self.sync_account(acc_id)


def main() -> None:
    worker = GoogleBusinessSyncWorker()
    worker.run_once()


if __name__ == "__main__":
    main()
