#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Загружаем .env файл
load_dotenv()

# Читаем переменные окружения
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

if not url or not key:
    print("Ошибка: SUPABASE_URL или SUPABASE_KEY не найдены в .env файле")
    exit(1)

# Создаем клиент Supabase
supabase: Client = create_client(url, key)

print("Проверяем RLS политики на таблице Users...")

try:
    # Получаем информацию о RLS политиках
    # Это можно сделать через SQL запрос
    result = supabase.rpc('get_rls_policies', {'table_name': 'Users'}).execute()
    print(f"RLS политики: {result.data}")
    
except Exception as e:
    print(f"Ошибка при получении RLS политик: {e}")
    print("Попробуем другой способ...")
    
    try:
        # Попробуем получить информацию о таблице
        result = supabase.table('Users').select('*').limit(1).execute()
        print(f"Доступ к таблице: {result.data}")
    except Exception as e2:
        print(f"Ошибка доступа к таблице: {e2}")
