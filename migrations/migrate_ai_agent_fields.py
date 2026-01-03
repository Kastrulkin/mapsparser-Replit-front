#!/usr/bin/env python3
"""
Миграция для добавления полей WABA, Telegram credentials и промптов ИИ агента
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from safe_db_utils import safe_migrate, get_db_connection
import sqlite3

def migrate_ai_agent_fields(cursor):
    """Миграция для добавления полей ИИ агента"""
    
    print("🔄 Расширение таблицы Businesses для WABA и Telegram credentials...")
    
    # Добавляем новые поля в Businesses (если их ещё нет)
    new_fields = [
        ('waba_phone_id', 'TEXT'),  # Phone ID для WABA
        ('waba_access_token', 'TEXT'),  # Access Token для WABA
        ('telegram_bot_token', 'TEXT'),  # Токен пользовательского Telegram бота
        ('ai_agent_enabled', 'INTEGER DEFAULT 0'),  # Включен ли ИИ агент
        ('ai_agent_tone', 'TEXT DEFAULT "professional"'),  # Тон общения (professional, friendly, casual)
        ('ai_agent_restrictions', 'TEXT'),  # Ограничения для ИИ агента (JSON)
    ]
    
    for field_name, field_type in new_fields:
        try:
            cursor.execute(f'ALTER TABLE Businesses ADD COLUMN {field_name} {field_type}')
            print(f"  ✅ Добавлено поле: {field_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  ℹ️  Поле {field_name} уже существует")
            else:
                print(f"  ⚠️  Ошибка при добавлении {field_name}: {e}")
    
    print("\n🔄 Создание таблицы AIAgentConversations...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS AIAgentConversations (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            client_phone TEXT NOT NULL,
            client_name TEXT,
            current_state TEXT DEFAULT 'greeting',
            conversation_history TEXT,
            last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
        )
    """)
    print("  ✅ Таблица AIAgentConversations создана/проверена")
    
    # Создаём индексы
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_conversations_business_id ON AIAgentConversations(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_conversations_client_phone ON AIAgentConversations(client_phone)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_conversations_state ON AIAgentConversations(current_state)")
        print("  ✅ Индексы для AIAgentConversations созданы")
    except Exception as e:
        print(f"  ⚠️  Ошибка создания индексов: {e}")
    
    print("\n🔄 Создание таблицы AIAgentMessages...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS AIAgentMessages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            message_type TEXT NOT NULL,
            content TEXT NOT NULL,
            sender TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES AIAgentConversations(id) ON DELETE CASCADE
        )
    """)
    print("  ✅ Таблица AIAgentMessages создана/проверена")
    
    # Создаём индексы для сообщений
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_messages_conversation_id ON AIAgentMessages(conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_messages_created_at ON AIAgentMessages(created_at)")
        print("  ✅ Индексы для AIAgentMessages созданы")
    except Exception as e:
        print(f"  ⚠️  Ошибка создания индексов: {e}")

def main():
    """Главная функция миграции"""
    print("=" * 60)
    print("🚀 Миграция: Добавление полей для ИИ агента")
    print("=" * 60)
    
    success = safe_migrate(
        migrate_ai_agent_fields,
        "Добавление полей WABA, Telegram credentials и промптов ИИ агента"
    )
    
    if success:
        print("\n✅ Миграция завершена успешно!")
    else:
        print("\n❌ Миграция завершена с ошибками!")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())

