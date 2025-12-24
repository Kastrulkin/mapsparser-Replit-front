#!/usr/bin/env python3
"""
Быстрый тест парсера Яндекс.Бизнес для бизнеса "Оливер".
"""

import sys
import os

# Загружаем переменные окружения из .env
try:
    from dotenv import load_dotenv
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, '.env')
    load_dotenv(env_path)
    print(f"✅ Загружен .env из {env_path}")
except ImportError:
    print("⚠️ python-dotenv не установлен, переменные окружения не загружены из .env")
except Exception as e:
    print(f"⚠️ Ошибка загрузки .env: {e}")

# Добавляем src в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from database_manager import DatabaseManager

# Добавляем tests в путь
tests_path = os.path.join(project_root, 'tests')
sys.path.insert(0, tests_path)

# Импортируем функцию теста
try:
    from test_yandex_business_connection import test_business_connection
except ImportError:
    # Если не получилось, пробуем другой путь
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "test_yandex_business_connection",
        os.path.join(tests_path, "test_yandex_business_connection.py")
    )
    test_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module)
    test_business_connection = test_module.test_business_connection

def find_oliver_business_id():
    """Находит business_id для бизнеса 'Оливер'."""
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT id, name FROM Businesses WHERE name LIKE '%Оливер%' OR name LIKE '%Oliver%' LIMIT 1"
        )
        business = cursor.fetchone()
        if business:
            return business[0], business[1]
        return None, None
    finally:
        db.close()

if __name__ == "__main__":
    print("🔍 Поиск бизнеса 'Оливер'...")
    business_id, business_name = find_oliver_business_id()
    
    if not business_id:
        print("❌ Бизнес 'Оливер' не найден в БД")
        sys.exit(1)
    
    print(f"✅ Найден бизнес: {business_name} (ID: {business_id})")
    print()
    
    # Запускаем тест
    test_business_connection(business_id)

