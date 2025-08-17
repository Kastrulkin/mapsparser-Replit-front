#!/usr/bin/env python3
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Инициализируем клиент Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def check_user_reports():
    """Проверяем записи в Cards и ParseQueue для пользователя"""
    
    # ID пользователя из Users таблицы
    user_id = "ce740a6a-eb92-40ee-99fa-b1b7d596ad1b"
    email = "demyanovap@yandex.ru"
    
    print(f"Проверяем записи для пользователя:")
    print(f"Users.id: {user_id}")
    print(f"Email: {email}")
    print("-" * 50)
    
    # Проверяем записи в Cards
    print("Записи в Cards:")
    try:
        result = supabase.table('Cards').select('*').eq('user_id', user_id).execute()
        print(f"Найдено записей: {len(result.data)}")
        for record in result.data:
            print(f"  - ID: {record.get('id')}, URL: {record.get('url')}, Created: {record.get('created_at')}")
    except Exception as e:
        print(f"Ошибка при запросе к Cards: {e}")
    
    print()
    
    # Проверяем записи в ParseQueue
    print("Записи в ParseQueue:")
    try:
        result = supabase.table('ParseQueue').select('*').eq('user_id', user_id).execute()
        print(f"Найдено записей: {len(result.data)}")
        for record in result.data:
            print(f"  - ID: {record.get('id')}, URL: {record.get('url')}, Status: {record.get('status')}, Created: {record.get('created_at')}")
    except Exception as e:
        print(f"Ошибка при запросе к ParseQueue: {e}")
    
    print()
    
    # Проверяем все записи в Cards (чтобы увидеть, какие user_id там есть)
    print("Все записи в Cards (первые 5):")
    try:
        result = supabase.table('Cards').select('user_id, url, created_at').limit(5).execute()
        print(f"Всего записей в Cards: {len(result.data)}")
        for record in result.data:
            print(f"  - user_id: {record.get('user_id')}, URL: {record.get('url')}")
    except Exception as e:
        print(f"Ошибка при запросе к Cards: {e}")
    
    print()
    
    # Проверяем все записи в ParseQueue (чтобы увидеть, какие user_id там есть)
    print("Все записи в ParseQueue (первые 5):")
    try:
        result = supabase.table('ParseQueue').select('user_id, url, status, created_at').limit(5).execute()
        print(f"Всего записей в ParseQueue: {len(result.data)}")
        for record in result.data:
            print(f"  - user_id: {record.get('user_id')}, URL: {record.get('url')}, Status: {record.get('status')}")
    except Exception as e:
        print(f"Ошибка при запросе к ParseQueue: {e}")

if __name__ == "__main__":
    check_user_reports()
