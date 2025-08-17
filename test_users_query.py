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

email = "demyanovap@yandex.ru"
auth_id = "3063fd66-2146-44a0-9ec6-1feac95a7c01"

print("Тестируем запросы к таблице Users...")

try:
    # Тест 1: Поиск по email
    print("\n1. Поиск по email:")
    result1 = supabase.table('Users').select('*').eq('email', email).execute()
    print(f"Результат: {result1.data}")
    
    # Тест 2: Поиск по auth_id
    print("\n2. Поиск по auth_id:")
    result2 = supabase.table('Users').select('*').eq('auth_id', auth_id).execute()
    print(f"Результат: {result2.data}")
    
    # Тест 3: Поиск по id
    print("\n3. Поиск по id:")
    result3 = supabase.table('Users').select('*').eq('id', auth_id).execute()
    print(f"Результат: {result3.data}")
    
    # Тест 4: Получить всех пользователей
    print("\n4. Все пользователи:")
    result4 = supabase.table('Users').select('*').execute()
    print(f"Количество: {len(result4.data) if result4.data else 0}")
    
except Exception as e:
    print(f"Ошибка: {e}")
