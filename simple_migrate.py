#!/usr/bin/env python3
"""
Простой скрипт для переноса данных
"""
import sqlite3

def migrate_data():
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
    
    print("=== ПОЛЬЗОВАТЕЛИ ===")
    for user in users:
        print(f"ID: {user[0]}")
        print(f"Email: {user[1]}")
        print(f"Name: {user[3]}")
        print(f"Phone: {user[4]}")
        print(f"Password Hash: {user[2][:20]}...")
        print("---")
    
    print("\n=== БИЗНЕСЫ ===")
    for business in businesses:
        print(f"ID: {business[0]}")
        print(f"Name: {business[1]}")
        print(f"Owner: {business[10]}")
        print(f"Address: {business[5]}")
        print("---")
    
    print("\n=== УСЛУГИ ===")
    for service in services:
        print(f"ID: {service[0]}")
        print(f"User: {service[1]}")
        print(f"Name: {service[3]}")
        print(f"Category: {service[2]}")
        print("---")
    
    # Создаем SQL для переноса
    sql_commands = []
    
    # Пользователи
    for user in users:
        sql_commands.append(f"""
INSERT OR REPLACE INTO Users (id, email, password_hash, name, phone, created_at, is_active, is_verified, is_superadmin)
VALUES ('{user[0]}', '{user[1]}', '{user[2]}', '{user[3]}', '{user[4]}', '{user[5]}', {user[6]}, {user[7]}, {user[8] if len(user) > 8 else 0});""")
    
    # Бизнесы
    for business in businesses:
        sql_commands.append(f"""
INSERT OR REPLACE INTO Businesses (id, name, description, industry, business_type, address, working_hours, phone, email, website, owner_id, is_active, created_at, updated_at)
VALUES ('{business[0]}', '{business[1]}', '{business[2]}', '{business[3]}', '{business[4]}', '{business[5]}', '{business[6]}', '{business[7]}', '{business[8]}', '{business[9]}', '{business[10]}', {business[11]}, '{business[12]}', '{business[13]}');""")
    
    # Услуги
    for service in services:
        sql_commands.append(f"""
INSERT OR REPLACE INTO UserServices (id, user_id, category, name, description, keywords, price, created_at, updated_at)
VALUES ('{service[0]}', '{service[1]}', '{service[2]}', '{service[3]}', '{service[4]}', '{service[5]}', '{service[6]}', '{service[7]}', '{service[8]}');""")
    
    # Сохраняем SQL
    with open('migrate_data.sql', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sql_commands))
    
    print(f"\n✅ Создан файл migrate_data.sql с {len(sql_commands)} командами")
    print("📋 Выполните на сервере: sqlite3 reports.db < migrate_data.sql")
    
    conn.close()

if __name__ == "__main__":
    migrate_data()
