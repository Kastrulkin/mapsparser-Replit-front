#!/usr/bin/env python3
"""
Миграция: Добавление полей для human-in-the-loop обработки капчи через noVNC
- captcha_required: требуется ли решение капчи оператором
- captcha_url: URL страницы с капчей
- captcha_session_id: UUID сессии браузера для noVNC
- captcha_token: одноразовый токен для доступа к сессии (TTL 15 минут)
- captcha_vnc_path: путь для открытия в кабинете (/tasks/{id}/captcha?token=...)
- captcha_started_at: время начала ожидания решения капчи
- captcha_status: статус капчи (waiting/resume/expired)
- resume_requested: флаг запроса на продолжение парсинга
"""
import sys
import os

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from safe_db_utils import safe_migrate

def migrate():
    """Добавить поля для обработки капчи"""
    
    def apply_migration(cursor):
        # Проверяем существование таблицы
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'parsequeue'
            )
        """)
        result = cursor.fetchone()
        if result:
            if isinstance(result, dict):
                table_exists = result.get('exists', False) or result.get(list(result.keys())[0], False)
            else:
                table_exists = result[0] if len(result) > 0 else False
        else:
            table_exists = False
        
        if not table_exists:
            print("   ⚠️  Таблица parsequeue не существует - пропускаем миграцию")
            return
        
        # Получаем список существующих колонок
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'parsequeue'
        """)
        rows = cursor.fetchall()
        existing_columns = [row['column_name'] if isinstance(row, dict) else row[0] for row in rows]
        
        print("📋 Добавление полей для обработки капчи в ParseQueue...")
        
        # Добавляем колонки, если их нет
        fields = [
            ('captcha_required', 'BOOLEAN DEFAULT FALSE'),
            ('captcha_url', 'TEXT'),
            ('captcha_session_id', 'TEXT'),
            ('captcha_token', 'TEXT'),
            ('captcha_token_expires_at', 'TIMESTAMP'),  # TTL 30 минут
            ('captcha_vnc_path', 'TEXT'),
            ('captcha_started_at', 'TIMESTAMP'),
            ('captcha_status', 'TEXT'),
            ('resume_requested', 'BOOLEAN DEFAULT FALSE'),
        ]
        
        for field_name, field_type in fields:
            if field_name not in existing_columns:
                cursor.execute(f"ALTER TABLE parsequeue ADD COLUMN {field_name} {field_type}")
                print(f"   ✅ Добавлена колонка {field_name}")
            else:
                print(f"   ✅ Колонка {field_name} уже существует")
        
        # Создаем индексы для быстрого поиска задач, ожидающих решения капчи
        print("\n📋 Создание индексов для captcha...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_parsequeue_captcha_status 
                ON parsequeue(captcha_status) 
                WHERE captcha_status IS NOT NULL
            """)
            print("   ✅ Индекс idx_parsequeue_captcha_status создан")
        except Exception as e:
            print(f"   ⚠️ Ошибка создания индекса: {e}")
        
        # Составной индекс для быстрого поиска задач "ждут оператора"
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_parsequeue_captcha_waiting 
                ON parsequeue(status, captcha_status) 
                WHERE captcha_required = TRUE AND captcha_status = 'waiting'
            """)
            print("   ✅ Индекс idx_parsequeue_captcha_waiting создан")
        except Exception as e:
            print(f"   ⚠️ Ошибка создания индекса: {e}")
        
        print("\n✅ Миграция полей капчи завершена успешно!")
    
    safe_migrate(apply_migration, "add_captcha_fields")

if __name__ == "__main__":
    migrate()
