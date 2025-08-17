#!/usr/bin/env python3
"""
Скрипт для исправления несоответствия ID пользователя между Auth и таблицей Users
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

email = "demyanovap@yandex.ru"
print(f"Исправляем несоответствие ID для пользователя: {email}")

try:
    # Получаем пользователя из Auth
    auth_result = supabase.auth.admin.list_users()
    auth_user = None
    
    for user in auth_result.users:
        if user.email == email:
            auth_user = user
            print(f"Пользователь в Auth: ID={user.id}, Email={user.email}")
            break
    
    if not auth_user:
        print("Пользователь не найден в Auth!")
        exit(1)
    
    # Получаем пользователя из таблицы Users
    users_result = supabase.table('Users').select('*').eq('email', email).execute()
    
    if users_result.data:
        current_user = users_result.data[0]
        print(f"Пользователь в таблице Users: ID={current_user['id']}, Email={current_user['email']}")
        
        # Если ID не совпадают, обновляем запись в Users
        if current_user['id'] != auth_user.id:
            print(f"ID не совпадают! Auth: {auth_user.id}, Users: {current_user['id']}")
            
            # Удаляем старую запись
            supabase.table('Users').delete().eq('id', current_user['id']).execute()
            print("Старая запись удалена")
            
            # Создаем новую запись с правильным ID
            new_user_data = {
                'id': auth_user.id,
                'email': auth_user.email,
                'created_at': auth_user.created_at,
                'updated_at': auth_user.updated_at,
                'phone': current_user.get('phone'),
                'name': current_user.get('name'),
                'yandex_url': current_user.get('yandex_url')
            }
            
            insert_result = supabase.table('Users').insert(new_user_data).execute()
            print(f"Создана новая запись с правильным ID: {insert_result.data}")
        else:
            print("ID совпадают, ничего не нужно исправлять")
    else:
        print("Пользователь не найден в таблице Users, создаем запись")
        
        # Создаем запись в Users с правильным ID из Auth
        new_user_data = {
            'id': auth_user.id,
            'email': auth_user.email,
            'created_at': auth_user.created_at,
            'updated_at': auth_user.updated_at
        }
        
        insert_result = supabase.table('Users').insert(new_user_data).execute()
        print(f"Создана запись в Users: {insert_result.data}")
        
except Exception as e:
    print(f"Ошибка: {e}")
