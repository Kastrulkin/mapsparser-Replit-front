#!/usr/bin/env python3
"""
Безопасная миграция: добавление поля master_id в FinancialTransactions
"""
from safe_db_utils import safe_migrate, get_db_connection

def add_master_id_to_transactions(cursor):
    """Добавить поле master_id в таблицу FinancialTransactions"""
    # Проверяем, существует ли уже поле
    cursor.execute("PRAGMA table_info(FinancialTransactions)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'master_id' not in columns:
        print("➕ Добавляю поле master_id в FinancialTransactions...")
        cursor.execute("""
            ALTER TABLE FinancialTransactions 
            ADD COLUMN master_id TEXT
        """)
        print("✅ Поле master_id добавлено")
    else:
        print("ℹ️  Поле master_id уже существует")

if __name__ == "__main__":
    print("🔄 Начинаю миграцию: добавление master_id в FinancialTransactions")
    success = safe_migrate(add_master_id_to_transactions, "Добавление master_id в FinancialTransactions")
    
    if success:
        print("✅ Миграция завершена успешно!")
    else:
        print("❌ Миграция не удалась. Проверьте логи выше.")

