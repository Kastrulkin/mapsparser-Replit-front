#!/usr/bin/env python3
"""
Скрипт для синхронизации данных из ClientInfo в таблицу Businesses
Создаёт бизнесы для пользователей, у которых есть данные в ClientInfo, но нет бизнеса в Businesses
"""
import sqlite3
import uuid
from datetime import datetime
from safe_db_utils import get_db_connection

def sync_clientinfo_to_businesses():
    """Синхронизировать данные из ClientInfo в Businesses"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("🔄 Начинаю синхронизацию ClientInfo → Businesses...")
    
    # Получаем все записи из ClientInfo, у которых есть business_name
    cursor.execute("""
        SELECT ci.user_id, ci.business_name, ci.business_type, ci.address, ci.working_hours,
               u.email, u.name as user_name
        FROM ClientInfo ci
        JOIN Users u ON ci.user_id = u.id
        WHERE ci.business_name IS NOT NULL AND ci.business_name != ''
    """)
    client_info_rows = cursor.fetchall()
    
    print(f"📋 Найдено записей в ClientInfo: {len(client_info_rows)}")
    
    created_count = 0
    updated_count = 0
    
    for row in client_info_rows:
        user_id = row[0]
        business_name = row[1]
        business_type = row[2] or 'beauty_salon'
        address = row[3] or ''
        working_hours = row[4] or ''
        
        # Проверяем, есть ли уже бизнес для этого пользователя с таким именем
        cursor.execute("""
            SELECT id, name FROM Businesses 
            WHERE owner_id = ? AND name = ? AND is_active = 1
        """, (user_id, business_name))
        existing_business = cursor.fetchone()
        
        if existing_business:
            # Бизнес уже существует - обновляем данные
            business_id = existing_business[0]
            cursor.execute("""
                UPDATE Businesses 
                SET business_type = ?, address = ?, working_hours = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (business_type, address, working_hours, business_id))
            updated_count += 1
            print(f"  ✅ Обновлён бизнес: {business_name} (ID: {business_id})")
        else:
            # Бизнеса нет - создаём новый
            business_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO Businesses 
                (id, name, business_type, address, working_hours, owner_id, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (business_id, business_name, business_type, address, working_hours, user_id))
            created_count += 1
            print(f"  ✅ Создан бизнес: {business_name} (ID: {business_id}) для пользователя {row[5]}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Синхронизация завершена:")
    print(f"   - Создано бизнесов: {created_count}")
    print(f"   - Обновлено бизнесов: {updated_count}")

if __name__ == "__main__":
    sync_clientinfo_to_businesses()

