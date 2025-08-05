#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

def fix_user_email():
    print("=== Исправление email пользователя ===")
    
    # Старый email (в таблице)
    old_email = "demyanovp@yandex.ru"
    # Новый email (в Auth)
    new_email = "demyanovap@yandex.ru"
    
    try:
        # Находим пользователя со старым email
        result = supabase.table('Users').select('*').eq('email', old_email).execute()
        
        if result.data:
            user = result.data[0]
            user_id = user.get('id')
            print(f"✅ Найден пользователь с ID: {user_id}")
            print(f"Старый email: {old_email}")
            print(f"Новый email: {new_email}")
            
            # Обновляем email
            update_result = supabase.table('Users').update({
                'email': new_email
            }).eq('id', user_id).execute()
            
            if update_result.data:
                print("✅ Email успешно обновлен!")
                updated_user = update_result.data[0]
                print(f"ID: {updated_user.get('id')}")
                print(f"Email: {updated_user.get('email')}")
                print(f"Имя: {updated_user.get('name', 'Не указано')}")
                print(f"Телефон: {updated_user.get('phone', 'Не указан')}")
                print(f"Yandex URL: {updated_user.get('yandex_url', 'Не указан')}")
            else:
                print("❌ Ошибка при обновлении email")
        else:
            print(f"❌ Пользователь с email {old_email} не найден")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def verify_fix():
    print("\n=== Проверка исправления ===")
    try:
        result = supabase.table('Users').select('*').eq('email', 'demyanovap@yandex.ru').execute()
        if result.data:
            user = result.data[0]
            print("✅ Пользователь найден с правильным email:")
            print(f"ID: {user.get('id')}")
            print(f"Email: {user.get('email')}")
            print(f"Имя: {user.get('name', 'Не указано')}")
            print(f"Телефон: {user.get('phone', 'Не указан')}")
            print(f"Yandex URL: {user.get('yandex_url', 'Не указан')}")
        else:
            print("❌ Пользователь с email demyanovap@yandex.ru не найден")
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")

if __name__ == "__main__":
    fix_user_email()
    verify_fix() 