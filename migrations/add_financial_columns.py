#!/usr/bin/env python3
"""
Добавляет отсутствующие колонки в таблицу FinancialTransactions.
Использует безопасное подключение из safe_db_utils.
"""
import os
import shutil
import sys
from datetime import datetime

# Добавляем src в путь для импорта safe_db_utils
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'src'))
sys.path.insert(0, SRC_DIR)

from safe_db_utils import get_db_connection


def main():
    # Бэкап
    db_path = os.path.join(SRC_DIR, 'reports.db')
    backup_dir = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'db_backups'))
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(
        backup_dir, f"reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db.backup"
    )
    shutil.copy2(db_path, backup_path)
    print(f"✅ Бэкап создан: {backup_path}")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(FinancialTransactions)")
    columns = {row[1] for row in cur.fetchall()}

    def add_column(sql):
        cur.execute(sql)
        print(f"Добавлена колонка: {sql}")

    if 'user_id' not in columns:
        add_column("ALTER TABLE FinancialTransactions ADD COLUMN user_id TEXT")
    if 'transaction_date' not in columns:
        add_column("ALTER TABLE FinancialTransactions ADD COLUMN transaction_date DATE")
    if 'services' not in columns:
        add_column("ALTER TABLE FinancialTransactions ADD COLUMN services TEXT DEFAULT '[]'")
    if 'notes' not in columns:
        add_column("ALTER TABLE FinancialTransactions ADD COLUMN notes TEXT DEFAULT ''")

    # Заполняем transaction_date из date, если она есть
    if 'transaction_date' in columns or 'transaction_date' not in columns:
        cur.execute("PRAGMA table_info(FinancialTransactions)")
        columns = {row[1] for row in cur.fetchall()}
        if 'transaction_date' in columns and 'date' in columns:
            cur.execute("""
                UPDATE FinancialTransactions
                SET transaction_date = COALESCE(transaction_date, date)
                WHERE date IS NOT NULL
            """)

    # Значения по умолчанию
    cur.execute("UPDATE FinancialTransactions SET services = COALESCE(services, '[]') WHERE services IS NULL")
    cur.execute("UPDATE FinancialTransactions SET notes = COALESCE(notes, '') WHERE notes IS NULL")

    conn.commit()
    conn.close()
    print("✅ Миграция FinancialTransactions завершена")


if __name__ == "__main__":
    main()

