#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

def update_user_data():
    print("=== Обновление данных пользователя ===")
    
    email = "demyanovap@yandex.ru"
    user_data = {
        'name': 'Павел Демьянов',
        'phone': '+7 (999) 123-45-67'
    }
    
    try:
        # Обновляем данные пользователя
        result = supabase.table('Users').update(user_data).eq('email', email).execute()
        
        if result.data:
            print("✅ Данные пользователя успешно обновлены!")
            user = result.data[0]
            print(f"ID: {user.get('id')}")
            print(f"Email: {user.get('email')}")
            print(f"Имя: {user.get('name')}")
            print(f"Телефон: {user.get('phone')}")
            print(f"Yandex URL: {user.get('yandex_url')}")
        else:
            print("❌ Ошибка при обновлении данных")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def verify_user_data():
    print("\n=== Проверка данных пользователя ===")
    try:
        result = supabase.table('Users').select('*').eq('email', 'demyanovap@yandex.ru').execute()
        if result.data:
            user = result.data[0]
            print("✅ Данные пользователя:")
            print(f"ID: {user.get('id')}")
            print(f"Email: {user.get('email')}")
            print(f"Имя: {user.get('name')}")
            print(f"Телефон: {user.get('phone')}")
            print(f"Yandex URL: {user.get('yandex_url')}")
            
            # Проверяем отчёты пользователя
            print(f"\n=== Отчёты пользователя ===")
            reports_result = supabase.table('Cards').select('*').eq('user_id', user.get('id')).execute()
            if reports_result.data:
                print(f"✅ Найдено отчётов: {len(reports_result.data)}")
                for i, report in enumerate(reports_result.data, 1):
                    print(f"\nОтчёт {i}:")
                    print(f"  ID: {report.get('id')}")
                    print(f"  URL: {report.get('url')}")
                    print(f"  Title: {report.get('title')}")
                    print(f"  Report Path: {report.get('report_path')}")
                    print(f"  SEO Score: {report.get('seo_score')}")
            else:
                print("❌ Отчётов не найдено")
        else:
            print("❌ Пользователь не найден")
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")

if __name__ == "__main__":
    update_user_data()
    verify_user_data() 