#!/usr/bin/env python3
"""
Скрипт для миграции пользователей из Supabase в SQLite
"""
import sqlite3
import uuid
from datetime import datetime
from auth_system import create_user, hash_password

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn

def migrate_users_from_supabase():
    """Мигрировать пользователей из Supabase (если есть доступ)"""
    # Здесь можно добавить логику для получения пользователей из Supabase
    # Пока создадим тестовых пользователей
    test_users = [
        {
            "email": "admin@beautybot.pro",
            "password": "admin123",
            "name": "Администратор",
            "phone": "+7 (999) 123-45-67"
        },
        {
            "email": "test@example.com", 
            "password": "test123",
            "name": "Тестовый пользователь",
            "phone": "+7 (999) 987-65-43"
        }
    ]
    
    migrated_count = 0
    
    for user_data in test_users:
        try:
            result = create_user(
                user_data["email"],
                user_data["password"], 
                user_data["name"],
                user_data["phone"]
            )
            
            if "error" not in result:
                print(f"✅ Пользователь {user_data['email']} создан успешно")
                migrated_count += 1
            else:
                print(f"❌ Ошибка при создании пользователя {user_data['email']}: {result['error']}")
                
        except Exception as e:
            print(f"❌ Исключение при создании пользователя {user_data['email']}: {e}")
    
    print(f"\n📊 Мигрировано пользователей: {migrated_count}")
    return migrated_count

def create_admin_user():
    """Создать администратора системы"""
    admin_email = "admin@beautybot.pro"
    admin_password = "admin123"
    admin_name = "Системный администратор"
    
    try:
        result = create_user(admin_email, admin_password, admin_name)
        
        if "error" not in result:
            print(f"✅ Администратор создан: {admin_email}")
            return result
        else:
            print(f"❌ Ошибка при создании администратора: {result['error']}")
            return None
            
    except Exception as e:
        print(f"❌ Исключение при создании администратора: {e}")
        return None

def list_users():
    """Показать всех пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, email, name, phone, created_at, is_active, is_verified
            FROM Users 
            ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        
        if not users:
            print("📭 Пользователи не найдены")
            return
        
        print("👥 Список пользователей:")
        print("-" * 80)
        for user in users:
            status = "✅ Активен" if user['is_active'] else "❌ Заблокирован"
            verified = "✅ Подтвержден" if user['is_verified'] else "⏳ Не подтвержден"
            print(f"ID: {user['id']}")
            print(f"Email: {user['email']}")
            print(f"Имя: {user['name'] or 'Не указано'}")
            print(f"Телефон: {user['phone'] or 'Не указан'}")
            print(f"Статус: {status}")
            print(f"Подтверждение: {verified}")
            print(f"Создан: {user['created_at']}")
            print("-" * 80)
            
    except Exception as e:
        print(f"❌ Ошибка при получении списка пользователей: {e}")
    finally:
        conn.close()

def create_test_invite():
    """Создать тестовое приглашение"""
    from auth_system import create_invite
    
    # Получаем первого пользователя как приглашающего
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM Users LIMIT 1")
        user = cursor.fetchone()
        
        if not user:
            print("❌ Нет пользователей для создания приглашения")
            return
        
        result = create_invite(user['id'], "invited@example.com")
        
        if "error" not in result:
            print(f"✅ Приглашение создано: {result['email']}")
            print(f"Токен: {result['token']}")
            print(f"Ссылка: https://beautybot.pro/invite/{result['token']}")
        else:
            print(f"❌ Ошибка при создании приглашения: {result['error']}")
            
    except Exception as e:
        print(f"❌ Исключение при создании приглашения: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 Начинаем миграцию пользователей...")
    
    # Создаем администратора
    print("\n1️⃣ Создание администратора...")
    create_admin_user()
    
    # Мигрируем тестовых пользователей
    print("\n2️⃣ Миграция тестовых пользователей...")
    migrate_users_from_supabase()
    
    # Показываем список пользователей
    print("\n3️⃣ Список пользователей:")
    list_users()
    
    # Создаем тестовое приглашение
    print("\n4️⃣ Создание тестового приглашения...")
    create_test_invite()
    
    print("\n✅ Миграция завершена!")
