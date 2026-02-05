#!/usr/bin/env python3
"""
Создание тестовых данных для PostgreSQL
"""
import os
import sys
import uuid

# Устанавливаем переменные окружения для PostgreSQL
os.environ['DB_TYPE'] = 'postgres'
os.environ['DATABASE_URL'] = 'postgresql://beautybot_user:local_dev_password@localhost:5432/beautybot_local'

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from safe_db_utils import get_db_connection
    from auth_system import hash_password
    try:
        from src.query_adapter import QueryAdapter
    except ImportError:
        from query_adapter import QueryAdapter
    
    print("🌱 Создание тестовых данных...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, есть ли уже тестовый пользователь
        query = "SELECT id FROM Users WHERE email = ?"
        params = ('test@local.dev',)
        
        # Адаптируем для PostgreSQL если нужно
        if os.getenv('DB_TYPE', 'sqlite').lower() in ('postgres', 'postgresql'):
            query = QueryAdapter.adapt_query(query, params)
            params = QueryAdapter.adapt_params(params)
        
        cursor.execute(query, params)
        existing_user = cursor.fetchone()
        
        if existing_user:
            user_id = existing_user['id'] if isinstance(existing_user, dict) else existing_user[0]
            print(f"✅ Тестовый пользователь уже существует: {user_id}")
        else:
            # Создаем тестового пользователя
            user_id = str(uuid.uuid4())
            password_hash = hash_password('test_password_123')
            
            # Адаптируем запрос для PostgreSQL
            query = """
                INSERT INTO Users (id, email, password_hash, name, is_active, is_verified)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            params = (user_id, 'test@local.dev', password_hash, 'Test User', True, True)
            
            # Адаптируем для PostgreSQL если нужно
            if os.getenv('DB_TYPE', 'sqlite').lower() in ('postgres', 'postgresql'):
                query = QueryAdapter.adapt_query(query, params)
                params = QueryAdapter.adapt_params(params)
            
            cursor.execute(query, params)
            
            print(f"✅ Создан тестовый пользователь: {user_id}")
        
        # Проверяем, есть ли уже тестовый бизнес
        query = "SELECT id FROM Businesses WHERE owner_id = ?"
        params = (user_id,)
        
        # Адаптируем для PostgreSQL если нужно
        if os.getenv('DB_TYPE', 'sqlite').lower() in ('postgres', 'postgresql'):
            query = QueryAdapter.adapt_query(query, params)
            params = QueryAdapter.adapt_params(params)
        
        cursor.execute(query, params)
        existing_business = cursor.fetchone()
        
        if existing_business:
            business_id = existing_business['id'] if isinstance(existing_business, dict) else existing_business[0]
            print(f"✅ Тестовый бизнес уже существует: {business_id}")
        else:
            # Создаем тестовый бизнес
            business_id = str(uuid.uuid4())
            
            # Адаптируем запрос для PostgreSQL
            query = """
                INSERT INTO Businesses (id, name, owner_id, is_active)
                VALUES (?, ?, ?, ?)
            """
            params = (business_id, 'Test Business', user_id, True)
            
            # Адаптируем для PostgreSQL если нужно
            if os.getenv('DB_TYPE', 'sqlite').lower() in ('postgres', 'postgresql'):
                query = QueryAdapter.adapt_query(query, params)
                params = QueryAdapter.adapt_params(params)
            
            cursor.execute(query, params)
            
            print(f"✅ Создан тестовый бизнес: {business_id}")
        
        conn.commit()
        
        print()
        print("✅ Тестовые данные созданы!")
        print(f"   User ID: {user_id}")
        print(f"   Business ID: {business_id}")
        print(f"   Email: test@local.dev")
        print(f"   Password: test_password_123")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка создания тестовых данных: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
