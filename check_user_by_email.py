#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

def check_user_by_email(email):
    print(f"=== Поиск пользователя по email: {email} ===")
    try:
        result = supabase.table('Users').select('*').eq('email', email).execute()
        if result.data:
            user = result.data[0]
            print("✅ Пользователь найден:")
            print(f"ID в таблице Users: {user.get('id')}")
            print(f"Email: {user.get('email')}")
            print(f"Имя: {user.get('name', 'Не указано')}")
            print(f"Телефон: {user.get('phone', 'Не указан')}")
            print(f"Yandex URL: {user.get('yandex_url', 'Не указан')}")
            print(f"Создан: {user.get('created_at')}")
            
            print(f"\n⚠️  Проблема: ID в Auth ({'db12ed3e-4c96-4d66-91e6-b1dab012ce30'}) не совпадает с ID в таблице ({user.get('id')})")
            
            return user.get('id')
        else:
            print(f"❌ Пользователь с email {email} не найден")
            return None
    except Exception as e:
        print(f"❌ Ошибка при поиске: {e}")
        return None

def check_all_users():
    print("\n=== Все пользователи в таблице Users ===")
    try:
        result = supabase.table('Users').select('*').execute()
        if result.data:
            print(f"Всего пользователей: {len(result.data)}")
            for user in result.data:
                print(f"\nID: {user.get('id')}")
                print(f"Email: {user.get('email')}")
                print(f"Имя: {user.get('name', 'Не указано')}")
                print("-" * 30)
        else:
            print("В таблице нет пользователей")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    email = "demyanovap@yandex.ru"
    correct_id = check_user_by_email(email)
    check_all_users()
    
    if correct_id:
        print(f"\n💡 Решение: Нужно обновить ID пользователя в Auth или создать запись с правильным ID") 