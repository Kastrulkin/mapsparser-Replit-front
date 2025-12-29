#!/usr/bin/env python3
"""
Миграция: Создание таблицы ChatGPTUserSessions для персонализации и учета истории
"""
from safe_db_utils import get_db_connection, safe_migrate

def migrate():
    """Создать таблицу ChatGPTUserSessions"""
    
    def create_chatgpt_sessions_table(cursor):
        # Проверяем, существует ли таблица
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ChatGPTUserSessions'
        """)
        
        if cursor.fetchone():
            print("✅ Таблица ChatGPTUserSessions уже существует")
        else:
            print("📝 Создаем таблицу ChatGPTUserSessions...")
            cursor.execute("""
                CREATE TABLE ChatGPTUserSessions (
                    id TEXT PRIMARY KEY,
                    chatgpt_user_id TEXT NOT NULL,
                    business_id TEXT,
                    session_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_interaction_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_interactions INTEGER DEFAULT 0,
                    preferred_city TEXT,
                    preferred_service_types TEXT,
                    search_history TEXT,
                    booking_history TEXT,
                    preferences_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE SET NULL
                )
            """)
            
            # Создаем индексы для быстрого поиска
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chatgpt_sessions_user_id 
                ON ChatGPTUserSessions(chatgpt_user_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chatgpt_sessions_business_id 
                ON ChatGPTUserSessions(business_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chatgpt_sessions_last_interaction 
                ON ChatGPTUserSessions(last_interaction_at DESC)
            """)
            
            print("✅ Таблица ChatGPTUserSessions создана с индексами")
    
    safe_migrate(
        create_chatgpt_sessions_table,
        "Создание таблицы ChatGPTUserSessions"
    )

if __name__ == "__main__":
    migrate()

