#!/usr/bin/env python3
"""
Скрипт для проверки пользователя в таблице Users
"""

import os
from dotenv import load_dotenv
from supabase import create_client

# Загружаем переменные окружения
load_dotenv()

# Подключаемся к Supabase
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

if not url or not key:
    print("Ошибка: SUPABASE_URL или SUPABASE_KEY не найдены")
    exit(1)

supabase = create_client(url, key)

# Проверяем пользователя по email
email = "demyanovap@yandex.ru"
print(f"Проверяем пользователя: {email}")

try:
    # Ищем в таблице Users
    result = supabase.table('Users').select('*').eq('email', email).execute()
    print(f"Пользователь в таблице Users: {result.data}")
    
    if not result.data:
        print("Пользователь НЕ найден в таблице Users!")
        print("Нужно создать запись в таблице Users")
        
        # Получаем данные из Auth
        auth_result = supabase.auth.admin.list_users()
        user_found = False
        
        for user in auth_result.users:
            if user.email == email:
                print(f"Пользователь найден в Auth: {user.id}")
                user_found = True
                
                # Создаем запись в таблице Users
                insert_result = supabase.table('Users').insert({
                    'id': user.id,
                    'email': user.email,
                    'created_at': user.created_at,
                    'updated_at': user.updated_at
                }).execute()
                
                print(f"Создана запись в Users: {insert_result.data}")
                break
        
        if not user_found:
            print("Пользователь не найден даже в Auth!")
    else:
        print("Пользователь найден в таблице Users")
        
except Exception as e:
    print(f"Ошибка: {e}")
