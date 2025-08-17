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

print("Проверяем структуру таблицы Users...")

try:
    # Получаем информацию о таблице
    result = supabase.table('Users').select('*').limit(1).execute()
    
    if result.data:
        print("Структура таблицы Users:")
        for key, value in result.data[0].items():
            print(f"  {key}: {type(value).__name__}")
    else:
        print("Таблица Users пуста")
        
except Exception as e:
    print(f"Ошибка: {e}")
