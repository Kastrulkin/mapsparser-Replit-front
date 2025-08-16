#!/usr/bin/env python3
"""
Скрипт для синхронизации ID из Auth в таблицу Users
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
print(f"Синхронизируем ID из Auth в таблицу Users для: {email}")

try:
    # Получаем пользователя из Auth
    auth_result = supabase.auth.admin.list_users()
    auth_user = None
    
    for user in auth_result:
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
        
        # Обновляем ID в таблице Users на ID из Auth
        if current_user['id'] != auth_user.id:
            print(f"Обновляем ID с {current_user['id']} на {auth_user.id}")
            
            # Обновляем запись в Users
            update_result = supabase.table('Users').update({
                'id': auth_user.id,
                'auth_id': auth_user.id  # Добавляем поле auth_id для связи
            }).eq('email', email).execute()
            
            print(f"Запись обновлена: {update_result.data}")
        else:
            print("ID уже совпадают")
            
        # Также обновляем отчёты в Cards и ParseQueue
        print("Обновляем отчёты в Cards...")
        cards_update = supabase.table('Cards').update({
            'user_id': auth_user.id
        }).eq('user_email', email).execute()
        print(f"Обновлено отчётов в Cards: {len(cards_update.data) if cards_update.data else 0}")
        
        print("Обновляем отчёты в ParseQueue...")
        queue_update = supabase.table('ParseQueue').update({
            'user_id': auth_user.id
        }).eq('user_email', email).execute()
        print(f"Обновлено отчётов в ParseQueue: {len(queue_update.data) if queue_update.data else 0}")
        
    else:
        print("Пользователь не найден в таблице Users, создаем запись")
        
        # Создаем запись в Users с правильным ID из Auth
        new_user_data = {
            'id': auth_user.id,
            'auth_id': auth_user.id,
            'email': auth_user.email,
            'created_at': auth_user.created_at,
            'updated_at': auth_user.updated_at
        }
        
        insert_result = supabase.table('Users').insert(new_user_data).execute()
        print(f"Создана запись в Users: {insert_result.data}")
        
except Exception as e:
    print(f"Ошибка: {e}")
