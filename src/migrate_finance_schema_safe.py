import os
import shutil
import sqlite3
from datetime import datetime


def get_db_path() -> str:
    preferred = os.path.abspath(os.path.join(os.path.dirname(__file__), 'reports.db'))
    fallback = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports.db'))
    if os.path.exists(preferred):
        return preferred
    if os.path.exists(fallback):
        return fallback
    # Если нет файла — всё равно вернём preferred (будет создан по пути)
    return preferred


def backup_db(db_path: str) -> str:
    backups_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'db_backups'))
    os.makedirs(backups_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(backups_dir, f"{os.path.basename(db_path).replace('.db', '')}_{ts}.db.backup")
    shutil.copy2(db_path, dst)
    return dst


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def migrate_financial_transactions(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    if not table_exists(cur, 'FinancialTransactions'):
        # Ничего не создаём здесь насильно — таблица должна существовать по init-скрипту
        return
    if not column_exists(cur, 'FinancialTransactions', 'client_type'):
        # Добавляем без CHECK, т.к. SQLite не поддерживает добавление CHECK через ALTER ADD COLUMN
        cur.execute("ALTER TABLE FinancialTransactions ADD COLUMN client_type TEXT DEFAULT 'returning'")
        # При желании можно нормализовать NULL -> 'returning'
        cur.execute("UPDATE FinancialTransactions SET client_type = 'returning' WHERE client_type IS NULL")
        conn.commit()


def migrate_roi_table(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ROIData (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            investment_amount DECIMAL(10,2) NOT NULL,
            returns_amount DECIMAL(10,2) NOT NULL,
            roi_percentage DECIMAL(5,2) NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def main():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"База данных не найдена по пути: {db_path}. Создавать новую миграцией не будем.")
        return

    backup_path = backup_db(db_path)
    print(f"✅ Бэкап создан: {backup_path}")

    conn = sqlite3.connect(db_path)
    try:
        migrate_financial_transactions(conn)
        migrate_roi_table(conn)
        print("✅ Миграция финансовых таблиц завершена без потери данных.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()


