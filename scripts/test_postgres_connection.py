#!/usr/bin/env python3
"""
Тест подключения к PostgreSQL
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
    from config import DB_TYPE
    
    print(f"📊 DB_TYPE: {DB_TYPE}")
    print(f"📊 DATABASE_URL: {os.getenv('DATABASE_URL', 'not set')}")
    print()
    
    print("🔄 Подключаюсь к PostgreSQL...")
    conn = get_db_connection()
    
    print(f"✅ Подключение успешно!")
    print(f"   Тип соединения: {conn.__class__.__name__}")
    
    cursor = conn.cursor()
    
    # Проверка версии PostgreSQL
    cursor.execute("SELECT version()")
    version = cursor.fetchone()
    # RealDictCursor возвращает dict
    version_str = version['version'] if isinstance(version, dict) else version[0]
    print(f"   PostgreSQL версия: {version_str[:50]}...")
    
    # Проверка текущей БД
    cursor.execute("SELECT current_database(), current_user")
    db_info = cursor.fetchone()
    # RealDictCursor возвращает dict
    if isinstance(db_info, dict):
        db_name = db_info['current_database']
        db_user = db_info['current_user']
    else:
        db_name = db_info[0]
        db_user = db_info[1]
    print(f"   База данных: {db_name}")
    print(f"   Пользователь: {db_user}")
    
    cursor.close()
    conn.close()
    
    print()
    print("✅ Все проверки пройдены!")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
