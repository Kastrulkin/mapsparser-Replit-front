#!/usr/bin/env python3
"""
Скрипт для переноса данных из локальной базы на сервер
"""
import sqlite3
import json
import requests
import os

def get_local_data():
    """Получить данные из локальной базы"""
    conn = sqlite3.connect('reports.db')
    cursor = conn.cursor()
    
    # Получаем пользователей
    cursor.execute('SELECT * FROM Users')
    users = cursor.fetchall()
    
    # Получаем бизнесы
    cursor.execute('SELECT * FROM Businesses')
    businesses = cursor.fetchall()
    
    # Получаем услуги
    cursor.execute('SELECT * FROM UserServices')
    services = cursor.fetchall()
    
    # Получаем примеры услуг
    cursor.execute('SELECT * FROM UserServiceExamples')
    service_examples = cursor.fetchall()
    
    # Получаем примеры отзывов
    cursor.execute('SELECT * FROM UserReviewExamples')
    review_examples = cursor.fetchall()
    
    # Получаем примеры новостей
    cursor.execute('SELECT * FROM UserNewsExamples')
    news_examples = cursor.fetchall()
    
    conn.close()
    
    return {
        'users': users,
        'businesses': businesses,
        'services': services,
        'service_examples': service_examples,
        'review_examples': review_examples,
        'news_examples': news_examples
    }

def create_sql_script(data):
    """Создать SQL скрипт для переноса данных"""
    sql_script = []
    
    # Пользователи
    for user in data['users']:
        sql_script.append(f"""
INSERT OR REPLACE INTO Users (id, email, password_hash, name, phone, created_at, is_active, is_verified, is_superadmin)
VALUES ('{user[0]}', '{user[1]}', '{user[2]}', '{user[3]}', '{user[4]}', '{user[5]}', {user[6]}, {user[7]}, {user[8] if len(user) > 8 else 0});
        """)
    
    # Бизнесы
    for business in data['businesses']:
        sql_script.append(f"""
INSERT OR REPLACE INTO Businesses (id, name, description, industry, business_type, address, working_hours, phone, email, website, owner_id, is_active, created_at, updated_at)
VALUES ('{business[0]}', '{business[1]}', '{business[2]}', '{business[3]}', '{business[4]}', '{business[5]}', '{business[6]}', '{business[7]}', '{business[8]}', '{business[9]}', '{business[10]}', {business[11]}, '{business[12]}', '{business[13]}');
        """)
    
    # Услуги
    for service in data['services']:
        sql_script.append(f"""
INSERT OR REPLACE INTO UserServices (id, user_id, category, name, description, keywords, price, created_at, updated_at, business_id)
VALUES ('{service[0]}', '{service[1]}', '{service[2]}', '{service[3]}', '{service[4]}', '{service[5]}', '{service[6]}', '{service[7]}', '{service[8]}', '{service[9] if len(service) > 9 else "NULL"}');
        """)
    
    return '\n'.join(sql_script)

if __name__ == "__main__":
    print("📊 Получаем данные из локальной базы...")
    data = get_local_data()
    
    print(f"✅ Найдено:")
    print(f"  - Пользователей: {len(data['users'])}")
    print(f"  - Бизнесов: {len(data['businesses'])}")
    print(f"  - Услуг: {len(data['services'])}")
    print(f"  - Примеров услуг: {len(data['service_examples'])}")
    print(f"  - Примеров отзывов: {len(data['review_examples'])}")
    print(f"  - Примеров новостей: {len(data['news_examples'])}")
    
    # Создаем SQL скрипт
    sql_script = create_sql_script(data)
    
    # Сохраняем в файл
    with open('migrate_data.sql', 'w', encoding='utf-8') as f:
        f.write(sql_script)
    
    print("✅ SQL скрипт сохранен в migrate_data.sql")
    print("📋 Теперь выполните на сервере:")
    print("   sqlite3 reports.db < migrate_data.sql")
