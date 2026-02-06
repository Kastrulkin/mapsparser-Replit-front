#!/usr/bin/env python3
"""
Миграция: Добавление колонки business_id в таблицу ClientInfo
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import safe_migrate

def migrate_clientinfo_add_business_id(cursor):
    """Добавить колонку business_id в таблицу ClientInfo"""
    
    # Проверяем текущую структуру
    cursor.execute("PRAGMA table_info(ClientInfo)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'business_id' in columns:
        print("✅ Колонка business_id уже существует, миграция не требуется")
        return
    
    print("🔄 Начинаю миграцию ClientInfo: добавление business_id...")
    
    # Сохраняем данные
    cursor.execute("SELECT * FROM ClientInfo")
    existing_data = cursor.fetchall()
    column_names = [col[1] for col in cursor.execute("PRAGMA table_info(ClientInfo)").fetchall()]
    
    print(f"📊 Найдено записей для миграции: {len(existing_data)}")
    print(f"📋 Текущие колонки: {column_names}")
    
    # Удаляем старую таблицу
    cursor.execute("DROP TABLE ClientInfo")
    
    # Создаем новую с правильной структурой
    cursor.execute("""
        CREATE TABLE ClientInfo (
            user_id TEXT,
            business_id TEXT,
            business_name TEXT,
            business_type TEXT,
            address TEXT,
            working_hours TEXT,
            description TEXT,
            services TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, business_id)
        )
    """)
    
    # Восстанавливаем данные
    restored_count = 0
    for row in existing_data:
        # Преобразуем row в словарь для удобства
        row_dict = dict(zip(column_names, row))
        
        user_id = row_dict.get('user_id', '')
        # Если business_id нет в старых данных, пытаемся найти его в таблице Businesses
        business_id = row_dict.get('business_id')
        if not business_id:
            # Пытаемся найти business_id из таблицы Businesses
            cursor.execute("SELECT id FROM Businesses WHERE owner_id = ? LIMIT 1", (user_id,))
            business_row = cursor.fetchone()
            if business_row:
                business_id = business_row[0]
            else:
                # Fallback: используем user_id (временное решение)
                business_id = user_id
                print(f"⚠️ Не найден business_id для user_id={user_id}, используем user_id как fallback")
        
        cursor.execute("""
            INSERT INTO ClientInfo (user_id, business_id, business_name, business_type, address, working_hours, description, services, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            business_id,
            row_dict.get('business_name', ''),
            row_dict.get('business_type', ''),
            row_dict.get('address', ''),
            row_dict.get('working_hours', ''),
            row_dict.get('description', ''),
            row_dict.get('services', ''),
            row_dict.get('updated_at', None)
        ))
        restored_count += 1
    
    print(f"✅ Восстановлено записей: {restored_count}")

if __name__ == "__main__":
    print("🔄 Запуск миграции ClientInfo: добавление business_id...")
    
    success = safe_migrate(
        migrate_clientinfo_add_business_id,
        "Добавление колонки business_id в таблицу ClientInfo"
    )
    
    if success:
        print("✅ Миграция выполнена успешно!")
        sys.exit(0)
    else:
        print("❌ Миграция завершилась с ошибкой")
        sys.exit(1)

