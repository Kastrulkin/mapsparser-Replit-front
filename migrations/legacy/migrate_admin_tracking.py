#!/usr/bin/env python3
"""
Миграция для добавления отслеживания токенов и заходов в систему
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from safe_db_utils import safe_migrate, get_db_connection

def migrate_admin_tracking(cursor):
    """Добавить таблицы для отслеживания токенов и заходов"""
    
    # Таблица для отслеживания использования токенов GigaChat
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS GigaChatTokenUsage (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            business_id TEXT,
            tokens_used INTEGER NOT NULL DEFAULT 0,
            request_type TEXT, -- 'screenshot', 'text', 'news', etc.
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE SET NULL
        )
    """)
    
    # Таблица для отслеживания заходов в систему
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS UserLoginHistory (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    """)
    
    # Таблица для управления доступом к токенам
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS UserTokenAccess (
            user_id TEXT PRIMARY KEY,
            tokens_paused BOOLEAN DEFAULT 0,
            paused_at TIMESTAMP,
            paused_reason TEXT,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    """)
    
    # Индексы для быстрого поиска
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_token_usage_user_id 
        ON GigaChatTokenUsage(user_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_token_usage_created_at 
        ON GigaChatTokenUsage(created_at)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_login_history_user_id 
        ON UserLoginHistory(user_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_login_history_created_at 
        ON UserLoginHistory(created_at)
    """)

if __name__ == "__main__":
    safe_migrate(migrate_admin_tracking, "Добавление отслеживания токенов и заходов в систему")



