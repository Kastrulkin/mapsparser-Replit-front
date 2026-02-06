#!/usr/bin/env python3
"""
Воркер для синхронизации данных из личного кабинета 2ГИС.
Использует внутреннее API 2ГИС через cookies пользователя.
"""

from __future__ import annotations

import json
import traceback
from typing import Optional

from database_manager import DatabaseManager
from external_sources import ExternalSource
from auth_encryption import decrypt_auth_data
from two_gis_business_parser import TwoGisBusinessParser
from base_sync_worker import BaseSyncWorker
from repositories.external_data_repository import ExternalDataRepository


class TwoGisBusinessSyncWorker(BaseSyncWorker):
    """Воркер синхронизации 2ГИС аккаунтов."""

    def __init__(self) -> None:
        super().__init__(ExternalSource.TWO_GIS)

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

            print(f"🔄 Синхронизация аккаунта {account_id} ({account.get('business_id')}) [2GIS]")
            
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
            
            parser = TwoGisBusinessParser(auth_data_dict)
            
            # Fetch & Upsert
            reviews = parser.fetch_reviews(account)
            repository.upsert_reviews(reviews)
            
            stats = parser.fetch_stats(account)
            if stats:
                repository.upsert_stats(stats)
            
            posts = parser.fetch_posts(account)
            repository.upsert_posts(posts)
            
            self._update_account_sync_status(db, account['id'])
            print(f"✅ Синхронизация аккаунта {account_id} завершена [2GIS]")

        except Exception as e:
            print(f"❌ Ошибка синхронизации аккаунта {account_id}: {e}")
            traceback.print_exc()
            if db:
                self._update_account_sync_status(db, account_id, error=str(e))
        finally:
            if db:
                db.close()

    def run_once(self) -> None:
        """Один проход синхронизации по всем активным аккаунтам"""
        db = DatabaseManager()
        try:
            accounts = self._load_active_accounts(db)
            print(f"[TwoGisBusinessSyncWorker] Активных аккаунтов: {len(accounts)}")
            account_ids = [acc['id'] for acc in accounts]
        finally:
            db.close()
            
        for acc_id in account_ids:
            self.sync_account(acc_id)


def main() -> None:
    worker = TwoGisBusinessSyncWorker()
    worker.run_once()


if __name__ == "__main__":
    main()


