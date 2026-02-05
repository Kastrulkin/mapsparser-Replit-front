#!/usr/bin/env python3
"""
Инициализация схемы PostgreSQL из schema_postgres.sql
"""
import os
import sys

# Устанавливаем переменные окружения для PostgreSQL
os.environ['DB_TYPE'] = 'postgres'
os.environ['DATABASE_URL'] = 'postgresql://beautybot_user:local_dev_password@localhost:5432/beautybot_local'

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from safe_db_utils import get_db_connection
    
    print("🔄 Инициализация схемы PostgreSQL...")
    print(f"📊 DATABASE_URL: {os.getenv('DATABASE_URL')}")
    print()
    
    # Читаем schema_postgres.sql
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'schema_postgres.sql')
    
    if not os.path.exists(schema_path):
        print(f"❌ Файл схемы не найден: {schema_path}")
        sys.exit(1)
    
    print(f"📄 Читаю схему из: {schema_path}")
    
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    # Подключаемся к PostgreSQL
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print("🔨 Применяю схему...")
        cursor.execute(schema_sql)
        conn.commit()
        print("✅ Схема применена успешно!")
        
        # Проверяем созданные таблицы
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        print(f"\n📊 Создано таблиц: {len(tables)}")
        for table in tables[:10]:  # Показываем первые 10
            table_name = table['table_name'] if isinstance(table, dict) else table[0]
            print(f"   - {table_name}")
        if len(tables) > 10:
            print(f"   ... и еще {len(tables) - 10} таблиц")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка применения схемы: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
    
    print()
    print("✅ Инициализация завершена!")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
