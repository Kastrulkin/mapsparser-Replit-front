#!/usr/bin/env python3
"""
Миграция: Создание таблицы ChatGPTRequests для мониторинга и логирования запросов
"""
from safe_db_utils import get_db_connection, safe_migrate

def migrate():
    """Создать таблицу ChatGPTRequests"""
    
    def create_chatgpt_requests_table(cursor):
        # Проверяем, существует ли таблица
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ChatGPTRequests'
        """)
        
        if cursor.fetchone():
            print("✅ Таблица ChatGPTRequests уже существует")
        else:
            print("📝 Создаем таблицу ChatGPTRequests...")
            cursor.execute("""
                CREATE TABLE ChatGPTRequests (
                    id TEXT PRIMARY KEY,
                    chatgpt_user_id TEXT,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    request_params TEXT,
                    response_status INTEGER,
                    response_time_ms INTEGER,
                    error_message TEXT,
                    business_id TEXT,
                    service_id TEXT,
                    booking_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE SET NULL
                )
            """)
            
            # Создаем индексы для быстрого поиска и аналитики
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chatgpt_requests_user_id 
                ON ChatGPTRequests(chatgpt_user_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chatgpt_requests_endpoint 
                ON ChatGPTRequests(endpoint)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chatgpt_requests_created_at 
                ON ChatGPTRequests(created_at DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chatgpt_requests_business_id 
                ON ChatGPTRequests(business_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chatgpt_requests_status 
                ON ChatGPTRequests(response_status)
            """)
            
            print("✅ Таблица ChatGPTRequests создана с индексами")
    
    safe_migrate(
        create_chatgpt_requests_table,
        "Создание таблицы ChatGPTRequests"
    )

if __name__ == "__main__":
    migrate()

