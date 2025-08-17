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
expected_auth_id = "3063fd66-2146-44a0-9ec6-1feac95a7c01"

print(f"Проверяем auth_id для пользователя: {email}")

try:
    # Получаем пользователя из таблицы Users
    result = supabase.table('Users').select('*').eq('email', email).execute()
    
    if result.data:
        user = result.data[0]
        print(f"Пользователь найден:")
        print(f"  id: {user.get('id')}")
        print(f"  email: {user.get('email')}")
        print(f"  auth_id: {user.get('auth_id')}")
        print(f"  Ожидаемый auth_id: {expected_auth_id}")
        
        if user.get('auth_id') == expected_auth_id:
            print("✅ auth_id совпадает!")
        else:
            print("❌ auth_id НЕ совпадает!")
            print("Обновляем auth_id...")
            
            update_result = supabase.table('Users').update({
                'auth_id': expected_auth_id
            }).eq('email', email).execute()
            
            print(f"Результат обновления: {update_result.data}")
    else:
        print("Пользователь не найден в таблице Users")
        
except Exception as e:
    print(f"Ошибка: {e}")
