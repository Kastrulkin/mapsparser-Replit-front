#!/usr/bin/env python3
"""
Безопасная миграция: добавление поддержки сетей (network_id) в Businesses
"""
from safe_db_utils import safe_migrate, get_db_connection

def add_network_support(cursor):
    """Добавить поддержку сетей в таблицу Businesses"""
    # Проверяем существующие колонки
    cursor.execute("PRAGMA table_info(Businesses)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Добавляем network_id для связи бизнесов в сеть
    if 'network_id' not in columns:
        print("➕ Добавляю поле network_id в Businesses...")
        cursor.execute("""
            ALTER TABLE Businesses 
            ADD COLUMN network_id TEXT
        """)
        print("✅ Поле network_id добавлено")
    else:
        print("ℹ️  Поле network_id уже существует")
    
    # Создаем таблицу Networks для хранения информации о сетях
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Networks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES Users (id) ON DELETE CASCADE
        )
    """)
    print("✅ Таблица Networks создана/проверена")
    
    # Создаем таблицу Masters для хранения информации о мастерах
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Masters (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            specialization TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
        )
    """)
    print("✅ Таблица Masters создана/проверена")
    
    # Добавляем business_id в FinancialTransactions для связи с бизнесами
    cursor.execute("PRAGMA table_info(FinancialTransactions)")
    ft_columns = [row[1] for row in cursor.fetchall()]
    
    if 'business_id' not in ft_columns:
        print("➕ Добавляю поле business_id в FinancialTransactions...")
        cursor.execute("""
            ALTER TABLE FinancialTransactions 
            ADD COLUMN business_id TEXT
        """)
        print("✅ Поле business_id добавлено")
    else:
        print("ℹ️  Поле business_id уже существует")
    
    # Добавляем telegram_id в Users для связи с Telegram-ботом
    cursor.execute("PRAGMA table_info(Users)")
    user_columns = [row[1] for row in cursor.fetchall()]
    
    if 'telegram_id' not in user_columns:
        print("➕ Добавляю поле telegram_id в Users...")
        # В SQLite нельзя добавить UNIQUE колонку напрямую, добавляем без UNIQUE
        cursor.execute("""
            ALTER TABLE Users 
            ADD COLUMN telegram_id TEXT
        """)
        # Создаём уникальный индекс для telegram_id
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_telegram_id_unique ON Users(telegram_id) WHERE telegram_id IS NOT NULL")
            print("✅ Поле telegram_id добавлено с уникальным индексом")
        except:
            print("✅ Поле telegram_id добавлено (индекс может уже существовать)")
    else:
        print("ℹ️  Поле telegram_id уже существует")
    
    # Создаем индексы для производительности
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_businesses_network_id ON Businesses(network_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_masters_business_id ON Masters(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON Users(telegram_id)")
        print("✅ Индексы созданы/проверены")
    except:
        print("ℹ️  Индексы уже существуют или не удалось создать")

if __name__ == "__main__":
    print("🔄 Начинаю миграцию: добавление поддержки сетей")
    success = safe_migrate(add_network_support, "Добавление поддержки сетей (network_id, Networks, Masters)")
    
    if success:
        print("✅ Миграция завершена успешно!")
    else:
        print("❌ Миграция не удалась. Проверьте логи выше.")

