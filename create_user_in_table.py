#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import uuid

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

print(f"Создаем пользователя в таблице Users: {email}")

try:
    # Проверяем, есть ли уже пользователь
    result = supabase.table('Users').select('*').eq('email', email).execute()
    
    if result.data:
        print(f"Пользователь уже существует: {result.data}")
    else:
        # Создаем нового пользователя
        new_user_data = {
            'id': str(uuid.uuid4()),
            'auth_id': auth_id,
            'email': email,
            'created_at': '2024-01-01T00:00:00Z',  # Примерная дата
            'updated_at': '2024-01-01T00:00:00Z'
        }
        
        insert_result = supabase.table('Users').insert(new_user_data).execute()
        print(f"Пользователь создан: {insert_result.data}")
        
except Exception as e:
    print(f"Ошибка: {e}")
