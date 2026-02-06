from abc import ABC, abstractmethod
from typing import List, Optional
from database_manager import DatabaseManager

class BaseSyncWorker(ABC):
    def __init__(self, source: str):
        self.source = source

    def _load_active_accounts(self, db: DatabaseManager) -> List[dict]:
        """Загрузить активные аккаунты для данного источника"""
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

    def _update_account_sync_status(self, db: DatabaseManager, account_id: str, error: Optional[str] = None) -> None:
        """Обновить статус синхронизации аккаунта"""
        cursor = db.conn.cursor()
        if error:
            cursor.execute(
                """
                UPDATE ExternalBusinessAccounts
                SET last_error = ?
                WHERE id = ?
                """,
                (str(error), account_id),
            )
        else:
            cursor.execute(
                """
                UPDATE ExternalBusinessAccounts
                SET last_sync_at = CURRENT_TIMESTAMP, last_error = NULL
                WHERE id = ?
                """,
                (account_id,),
            )
        db.conn.commit()

    @abstractmethod
    def sync_account(self, account_id: str) -> None:
        """Синхронизировать один аккаунт по ID"""
        pass

    @abstractmethod
    def run_once(self) -> None:
        """Запустить один цикл синхронизации (должен быть переопределен)"""
        pass
