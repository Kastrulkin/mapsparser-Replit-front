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

def check_cards_rls():
    """Проверяем RLS политики на таблице Cards"""
    
    user_id = "ce740a6a-eb92-40ee-99fa-b1b7d596ad1b"
    
    print("Проверяем RLS политики на таблице Cards")
    print("-" * 50)
    
    # Проверяем запрос с анонимным ключом (как фронтенд)
    print("1. Запрос с анонимным ключом (как фронтенд):")
    try:
        # Используем анонимный ключ
        anon_key = os.environ.get("VITE_SUPABASE_KEY")
        anon_supabase = create_client(url, anon_key)
        
        result = anon_supabase.table('Cards').select('*').eq('user_id', user_id).execute()
        print(f"   Найдено записей: {len(result.data)}")
        for record in result.data:
            print(f"   - ID: {record.get('id')}, URL: {record.get('url')}")
    except Exception as e:
        print(f"   Ошибка: {e}")
    
    print()
    
    # Проверяем запрос с сервисным ключом (как Python скрипт)
    print("2. Запрос с сервисным ключом (как Python скрипт):")
    try:
        result = supabase.table('Cards').select('*').eq('user_id', user_id).execute()
        print(f"   Найдено записей: {len(result.data)}")
        for record in result.data:
            print(f"   - ID: {record.get('id')}, URL: {record.get('url')}")
    except Exception as e:
        print(f"   Ошибка: {e}")
    
    print()
    
    # Проверяем все записи в Cards
    print("3. Все записи в Cards (с сервисным ключом):")
    try:
        result = supabase.table('Cards').select('user_id, url, created_at').execute()
        print(f"   Всего записей: {len(result.data)}")
        for record in result.data:
            print(f"   - user_id: {record.get('user_id')}, URL: {record.get('url')}")
    except Exception as e:
        print(f"   Ошибка: {e}")

if __name__ == "__main__":
    check_cards_rls()
