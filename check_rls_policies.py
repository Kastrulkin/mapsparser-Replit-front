#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

def check_rls_policies():
    print("=== Проверка RLS политик ===")
    
    try:
        # Проверяем, включен ли RLS для таблицы Users
        result = supabase.rpc('exec_sql', {
            'sql': '''
            SELECT schemaname, tablename, rowsecurity 
            FROM pg_tables 
            WHERE tablename = 'Users' AND schemaname = 'public';
            '''
        }).execute()
        
        print("Статус RLS для таблицы Users:")
        if result.data:
            for row in result.data:
                print(f"  RLS включен: {row.get('rowsecurity')}")
        
        # Проверяем политики
        policies_result = supabase.rpc('exec_sql', {
            'sql': '''
            SELECT policyname, permissive, roles, cmd, qual 
            FROM pg_policies 
            WHERE tablename = 'Users' AND schemaname = 'public';
            '''
        }).execute()
        
        print("\nПолитики для таблицы Users:")
        if policies_result.data:
            for policy in policies_result.data:
                print(f"  - {policy.get('policyname')}")
                print(f"    Команда: {policy.get('cmd')}")
                print(f"    Условие: {policy.get('qual')}")
                print()
        else:
            print("  Политики не найдены")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке политик: {e}")

def test_user_access():
    print("\n=== Тест доступа пользователя ===")
    
    auth_id = "db12ed3e-4c96-4d66-91e6-b1dab012ce30"
    
    try:
        # Пробуем получить данные пользователя
        result = supabase.table('Users').select('*').eq('id', auth_id).execute()
        
        if result.data:
            user = result.data[0]
            print("✅ Доступ к данным пользователя есть:")
            print(f"ID: {user.get('id')}")
            print(f"Email: {user.get('email')}")
        else:
            print("❌ Доступ к данным пользователя отсутствует")
            
    except Exception as e:
        print(f"❌ Ошибка доступа: {e}")

def create_rls_policies():
    print("\n=== Создание RLS политик ===")
    
    try:
        # Включаем RLS
        enable_rls = supabase.rpc('exec_sql', {
            'sql': 'ALTER TABLE public."Users" ENABLE ROW LEVEL SECURITY;'
        }).execute()
        print("✅ RLS включен")
        
        # Создаём политики
        policies = [
            {
                'name': 'Users can view own data',
                'sql': 'CREATE POLICY "Users can view own data" ON public."Users" FOR SELECT USING (auth.uid() = id);'
            },
            {
                'name': 'Users can update own data', 
                'sql': 'CREATE POLICY "Users can update own data" ON public."Users" FOR UPDATE USING (auth.uid() = id);'
            },
            {
                'name': 'Users can insert own data',
                'sql': 'CREATE POLICY "Users can insert own data" ON public."Users" FOR INSERT WITH CHECK (auth.uid() = id);'
            }
        ]
        
        for policy in policies:
            try:
                result = supabase.rpc('exec_sql', {'sql': policy['sql']}).execute()
                print(f"✅ Политика '{policy['name']}' создана")
            except Exception as e:
                print(f"⚠️  Политика '{policy['name']}' уже существует или ошибка: {e}")
                
    except Exception as e:
        print(f"❌ Ошибка при создании политик: {e}")

if __name__ == "__main__":
    check_rls_policies()
    test_user_access()
    create_rls_policies() 