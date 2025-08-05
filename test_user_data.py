#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

def test_users_table():
    print("=== Тестирование таблицы Users ===")
    
    try:
        # Получаем всех пользователей
        result = supabase.table('Users').select('*').execute()
        print(f'Всего пользователей в базе: {len(result.data)}')
        
        if result.data:
            print('\nПользователи:')
            for user in result.data:
                print(f"ID: {user.get('id')}")
                print(f"Email: {user.get('email')}")
                print(f"Имя: {user.get('name', 'Не указано')}")
                print(f"Телефон: {user.get('phone', 'Не указан')}")
                print(f"Yandex URL: {user.get('yandex_url', 'Не указан')}")
                print(f"Создан: {user.get('created_at')}")
                print("-" * 50)
        else:
            print("В таблице Users нет данных")
            
    except Exception as e:
        print(f"Ошибка при работе с таблицей Users: {e}")

def test_specific_user(user_id):
    print(f"\n=== Тестирование конкретного пользователя {user_id} ===")
    
    try:
        result = supabase.table('Users').select('*').eq('id', user_id).execute()
        
        if result.data:
            user = result.data[0]
            print(f"Найден пользователь:")
            print(f"ID: {user.get('id')}")
            print(f"Email: {user.get('email')}")
            print(f"Имя: {user.get('name', 'Не указано')}")
            print(f"Телефон: {user.get('phone', 'Не указан')}")
            print(f"Yandex URL: {user.get('yandex_url', 'Не указан')}")
            print(f"Создан: {user.get('created_at')}")
        else:
            print(f"Пользователь с ID {user_id} не найден")
            
    except Exception as e:
        print(f"Ошибка при поиске пользователя: {e}")

if __name__ == "__main__":
    test_users_table()
    
    # Тестируем конкретного пользователя (замените на реальный ID)
    # test_specific_user("some-user-id") 