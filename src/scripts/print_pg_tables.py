#!/usr/bin/env python3
"""
Скрипт для проверки имен таблиц в PostgreSQL
Определяет, используются ли lowercase (users) или CamelCase (Users) таблицы
"""
import sys
import os

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.db_connection import get_db_connection

def main():
    conn = None
    try:
        print("🔍 Подключение к PostgreSQL...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем список всех таблиц в public schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        table_names = [t['table_name'] if isinstance(t, dict) else t[0] for t in tables]
        
        print(f"\n📋 Всего таблиц: {len(table_names)}")
        print("\n📊 Список таблиц:")
        for name in table_names:
            print(f"  - {name}")
        
        # Проверяем конкретно Users/users и Businesses/businesses
        print("\n🔍 Проверка критичных таблиц:")
        
        has_users = 'users' in table_names
        has_Users = 'Users' in table_names
        has_businesses = 'businesses' in table_names
        has_Businesses = 'Businesses' in table_names
        
        print(f"  users (lowercase): {'✅' if has_users else '❌'}")
        print(f"  Users (CamelCase): {'✅' if has_Users else '❌'}")
        print(f"  businesses (lowercase): {'✅' if has_businesses else '❌'}")
        print(f"  Businesses (CamelCase): {'✅' if has_Businesses else '❌'}")
        
        # Определяем стандарт
        print("\n📌 Анализ:")
        if has_users and not has_Users:
            print("  ✅ Стандарт: lowercase (users, businesses)")
            print("  📝 Рекомендация: использовать lowercase без кавычек в коде")
            standard = 'lowercase'
        elif has_Users and not has_users:
            print("  ✅ Стандарт: CamelCase (Users, Businesses)")
            print("  📝 Рекомендация: использовать CamelCase с кавычками \"Users\" в коде")
            standard = 'CamelCase'
        elif has_users and has_Users:
            print("  ⚠️  ОБНАРУЖЕНА ПРОБЛЕМА: есть и users, и Users!")
            print("  ❌ Это конфликт - нужно привести к одному стандарту")
            standard = 'conflict'
        else:
            print("  ⚠️  Не найдено ни users, ни Users")
            print("  📝 Предполагаем: CamelCase (как в schema_postgres.sql)")
            standard = 'CamelCase'
        
        # Проверяем другие таблицы на смешение
        camel_case_tables = [t for t in table_names if t[0].isupper()]
        lowercase_tables = [t for t in table_names if t[0].islower()]
        
        print("\n📊 Статистика:")
        print(f"  CamelCase таблиц: {len(camel_case_tables)}")
        print(f"  lowercase таблиц: {len(lowercase_tables)}")
        
        if camel_case_tables and lowercase_tables:
            print("\n  ⚠️  СМЕШЕНИЕ СТАНДАРТОВ!")
            print(f"  CamelCase: {', '.join(camel_case_tables[:5])}...")
            print(f"  lowercase: {', '.join(lowercase_tables[:5])}...")
        
        return standard
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    standard = main()
    if standard:
        print(f"\n✅ Определен стандарт: {standard}")
        sys.exit(0)
    else:
        print("\n❌ Не удалось определить стандарт")
        sys.exit(1)
