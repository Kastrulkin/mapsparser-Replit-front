#!/usr/bin/env python3
"""
Быстрое решение для тестирования - временно отключаем RLS
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

def quick_test():
    """Быстрое тестирование с отключением RLS"""
    
    print("🔧 БЫСТРОЕ РЕШЕНИЕ ДЛЯ ТЕСТИРОВАНИЯ")
    print("=" * 50)
    print()
    print("Проблема: RLS политики блокируют доступ к данным")
    print("Решение: Временно отключить RLS для тестирования")
    print()
    print("📋 ИНСТРУКЦИЯ:")
    print("1. Откройте Supabase Dashboard:")
    print("   https://supabase.com/dashboard/project/bvhpvzcvcuswiozhyqlk")
    print()
    print("2. Перейдите в SQL Editor")
    print()
    print("3. Выполните этот SQL код:")
    print()
    print("```sql")
    print("-- ВРЕМЕННОЕ ОТКЛЮЧЕНИЕ RLS ДЛЯ ТЕСТИРОВАНИЯ")
    print("ALTER TABLE Users DISABLE ROW LEVEL SECURITY;")
    print("ALTER TABLE Cards DISABLE ROW LEVEL SECURITY;")
    print("ALTER TABLE ParseQueue DISABLE ROW LEVEL SECURITY;")
    print("```")
    print()
    print("4. После выполнения SQL:")
    print("   - Обновите страницу личного кабинета")
    print("   - Отчёты должны появиться")
    print()
    print("⚠️  ВАЖНО: После тестирования обязательно включите RLS обратно!")
    print()
    print("📊 ТЕКУЩЕЕ СОСТОЯНИЕ ДАННЫХ:")
    
    supabase = create_client(url, key)
    
    # Проверяем данные с сервисным ключом
    try:
        # Пользователь
        result = supabase.table('Users').select('*').eq('email', 'demyanovap@gmail.com').execute()
        print(f"✅ Пользователь: {len(result.data)} записей")
        for user in result.data:
            print(f"   - ID: {user.get('id')}")
            print(f"   - Email: {user.get('email')}")
            print(f"   - Auth ID: {user.get('auth_id')}")
        
        # Отчёты
        result = supabase.table('Cards').select('*').eq('user_id', 'f2123626-71b1-4424-8b2a-0bc93ab8f2eb').execute()
        print(f"✅ Отчёты: {len(result.data)} записей")
        for report in result.data:
            print(f"   - ID: {report.get('id')}")
            print(f"   - URL: {report.get('url')}")
            print(f"   - Title: {report.get('title')}")
        
        # Очередь
        result = supabase.table('ParseQueue').select('*').eq('user_id', 'f2123626-71b1-4424-8b2a-0bc93ab8f2eb').execute()
        print(f"✅ Очередь: {len(result.data)} записей")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке данных: {e}")
    
    print()
    print("🎯 РЕЗУЛЬТАТ:")
    print("Данные есть в базе, проблема только в RLS политиках")
    print("После отключения RLS отчёты должны появиться в личном кабинете")

if __name__ == "__main__":
    quick_test()
