#!/usr/bin/env python3
"""
Временное отключение RLS для тестирования
"""

import os
from dotenv import load_dotenv
from supabase import create_client
import requests

# Загружаем переменные окружения
load_dotenv()

# Подключаемся к Supabase
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

if not url or not key:
    print("Ошибка: SUPABASE_URL или SUPABASE_KEY не найдены")
    exit(1)

def disable_rls_temporarily():
    """Временно отключаем RLS для тестирования"""
    
    print("ВНИМАНИЕ: Это временное решение для тестирования!")
    print("RLS будет отключен для таблиц Users, Cards и ParseQueue")
    print("После тестирования нужно будет настроить RLS политики правильно")
    
    # SQL команды для отключения RLS
    sql_commands = [
        "ALTER TABLE Users DISABLE ROW LEVEL SECURITY;",
        "ALTER TABLE Cards DISABLE ROW LEVEL SECURITY;",
        "ALTER TABLE ParseQueue DISABLE ROW LEVEL SECURITY;"
    ]
    
    # Выполняем через REST API
    headers = {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'apikey': key
    }
    
    for i, sql in enumerate(sql_commands, 1):
        try:
            print(f"{i}. Выполняем: {sql}")
            
            # Используем REST API для выполнения SQL
            response = requests.post(
                f"{url}/rest/v1/rpc/exec",
                headers=headers,
                json={"sql": sql}
            )
            
            if response.status_code == 200:
                print("   ✅ Успешно")
            else:
                print(f"   ❌ Ошибка: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    
    print("\nПроверяем результат...")
    
    # Проверяем доступ с анонимным ключом
    anon_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ2aHB2emN2Y3Vzd2lvemh5cWxrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI0OTk4NTksImV4cCI6MjA2ODA3NTg1OX0.WN6Yig4ruyDmSDwX12vlZlzRaCOsekXC_WNdtwpeXqE'
    anon_supabase = create_client(url, anon_key)
    
    try:
        # Проверяем доступ к Users
        result = anon_supabase.table('Users').select('*').eq('email', 'demyanovap@gmail.com').execute()
        print(f"Доступ к Users: {len(result.data)} записей")
        
        # Проверяем доступ к Cards
        result = anon_supabase.table('Cards').select('*').eq('user_id', 'f2123626-71b1-4424-8b2a-0bc93ab8f2eb').execute()
        print(f"Доступ к Cards: {len(result.data)} записей")
        
        if len(result.data) > 0:
            print("✅ Проблема решена! Отчёты теперь доступны")
        else:
            print("❌ Проблема не решена")
            
    except Exception as e:
        print(f"Ошибка проверки: {e}")

if __name__ == "__main__":
    disable_rls_temporarily()
