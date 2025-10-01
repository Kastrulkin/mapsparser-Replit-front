#!/usr/bin/env python3
"""
Временный скрипт для тестирования без RLS
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

def test_without_rls():
    """Тестируем доступ к данным без RLS"""
    
    print("Тестируем доступ к данным...")
    
    # Проверяем пользователя
    try:
        result = supabase.table('Users').select('*').eq('email', 'demyanovap@gmail.com').execute()
        print(f"Пользователь найден: {len(result.data)} записей")
        for user in result.data:
            print(f"  - ID: {user.get('id')}, Email: {user.get('email')}, Auth ID: {user.get('auth_id')}")
    except Exception as e:
        print(f"Ошибка при поиске пользователя: {e}")
    
    # Проверяем отчёты
    try:
        result = supabase.table('Cards').select('*').eq('user_id', 'f2123626-71b1-4424-8b2a-0bc93ab8f2eb').execute()
        print(f"Отчёты найдены: {len(result.data)} записей")
        for report in result.data:
            print(f"  - ID: {report.get('id')}, URL: {report.get('url')}, Title: {report.get('title')}")
    except Exception as e:
        print(f"Ошибка при поиске отчётов: {e}")
    
    # Проверяем ParseQueue
    try:
        result = supabase.table('ParseQueue').select('*').eq('user_id', 'f2123626-71b1-4424-8b2a-0bc93ab8f2eb').execute()
        print(f"Заявки в очереди: {len(result.data)} записей")
        for queue in result.data:
            print(f"  - ID: {queue.get('id')}, URL: {queue.get('url')}, Status: {queue.get('status')}")
    except Exception as e:
        print(f"Ошибка при поиске очереди: {e}")

if __name__ == "__main__":
    test_without_rls()
