#!/usr/bin/env python3
"""
Безопасная миграция: создание таблицы для токенов привязки Telegram
"""
from safe_db_utils import safe_migrate, get_db_connection

def create_telegram_bind_tokens_table(cursor):
    """Создать таблицу для токенов привязки Telegram"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS TelegramBindTokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
        )
    """)
    print("✅ Таблица TelegramBindTokens создана/проверена")
    
    # Создаем индекс для быстрого поиска по токену
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_bind_tokens_token ON TelegramBindTokens(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_bind_tokens_user_id ON TelegramBindTokens(user_id)")
        print("✅ Индексы созданы/проверены")
    except:
        print("ℹ️  Индексы уже существуют или не удалось создать")

if __name__ == "__main__":
    print("🔄 Начинаю миграцию: создание таблицы для токенов привязки Telegram")
    success = safe_migrate(create_telegram_bind_tokens_table, "Создание таблицы TelegramBindTokens")
    
    if success:
        print("✅ Миграция завершена успешно!")
    else:
        print("❌ Миграция не удалась. Проверьте логи выше.")

