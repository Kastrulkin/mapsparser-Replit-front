#!/usr/bin/env python3
"""
Скрипт для исправления RLS политик в Supabase
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

def fix_rls_policies():
    """Исправляем RLS политики для таблиц Users, Cards и ParseQueue"""
    
    print("Исправляем RLS политики...")
    
    # SQL команды для настройки RLS политик
    rls_commands = [
        # Включаем RLS для всех таблиц
        "ALTER TABLE Users ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE Cards ENABLE ROW LEVEL SECURITY;", 
        "ALTER TABLE ParseQueue ENABLE ROW LEVEL SECURITY;",
        
        # Удаляем старые политики (если есть)
        "DROP POLICY IF EXISTS \"Users can view own profile\" ON Users;",
        "DROP POLICY IF EXISTS \"Users can update own profile\" ON Users;",
        "DROP POLICY IF EXISTS \"Users can view own cards\" ON Cards;",
        "DROP POLICY IF EXISTS \"Users can view own queue\" ON ParseQueue;",
        
        # Создаем новые политики для Users
        """
        CREATE POLICY \"Users can view own profile\" ON Users
        FOR SELECT USING (
            auth.uid()::text = auth_id OR 
            auth.jwt() ->> 'email' = email
        );
        """,
        
        """
        CREATE POLICY \"Users can update own profile\" ON Users
        FOR UPDATE USING (
            auth.uid()::text = auth_id OR 
            auth.jwt() ->> 'email' = email
        );
        """,
        
        # Создаем политики для Cards
        """
        CREATE POLICY \"Users can view own cards\" ON Cards
        FOR SELECT USING (
            user_id IN (
                SELECT id FROM Users 
                WHERE auth_id = auth.uid()::text 
                OR email = auth.jwt() ->> 'email'
            )
        );
        """,
        
        # Создаем политики для ParseQueue
        """
        CREATE POLICY \"Users can view own queue\" ON ParseQueue
        FOR SELECT USING (
            user_id IN (
                SELECT id FROM Users 
                WHERE auth_id = auth.uid()::text 
                OR email = auth.jwt() ->> 'email'
            )
        );
        """,
        
        """
        CREATE POLICY \"Users can insert to queue\" ON ParseQueue
        FOR INSERT WITH CHECK (
            user_id IN (
                SELECT id FROM Users 
                WHERE auth_id = auth.uid()::text 
                OR email = auth.jwt() ->> 'email'
            )
        );
        """
    ]
    
    for i, command in enumerate(rls_commands, 1):
        try:
            print(f"{i}. Выполняем: {command[:50]}...")
            result = supabase.rpc('exec_sql', {'sql': command}).execute()
            print(f"   ✅ Успешно")
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
        
    except Exception as e:
        print(f"Ошибка проверки: {e}")

if __name__ == "__main__":
    fix_rls_policies()
