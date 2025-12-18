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
    
    updated_count = 0
    skipped_count = 0
    
    for row in client_info_rows:
        user_id = row[0]
        business_name = row[1]
        business_type = row[2] or 'beauty_salon'
        address = row[3] or ''
        working_hours = row[4] or ''
        
        # Ищем существующий бизнес для этого пользователя
        # Сначала по имени (если переименовали)
        cursor.execute("""
            SELECT id, name FROM Businesses 
            WHERE owner_id = ? AND name = ? AND is_active = 1
            LIMIT 1
        """, (user_id, business_name))
        existing_by_name = cursor.fetchone()
        
        if existing_by_name:
            # Нашли по имени - обновляем
            business_id = existing_by_name[0]
            cursor.execute("""
                UPDATE Businesses 
                SET business_type = ?, address = ?, working_hours = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (business_type, address, working_hours, business_id))
            updated_count += 1
            print(f"  ✅ Обновлён бизнес по имени: {business_name} (ID: {business_id})")
        else:
            # Не нашли по имени - ищем первый активный бизнес пользователя
            cursor.execute("""
                SELECT id, name FROM Businesses 
                WHERE owner_id = ? AND is_active = 1
                ORDER BY created_at ASC
                LIMIT 1
            """, (user_id,))
            first_business = cursor.fetchone()
            
            if first_business:
                # Нашли первый бизнес - обновляем его (включая название)
                business_id = first_business[0]
                cursor.execute("""
                    UPDATE Businesses 
                    SET name = ?, business_type = ?, address = ?, working_hours = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (business_name, business_type, address, working_hours, business_id))
                updated_count += 1
                print(f"  ✅ Обновлён первый бизнес пользователя: {first_business[1]} → {business_name} (ID: {business_id})")
            else:
                # У пользователя нет бизнесов - пропускаем (не создаём)
                skipped_count += 1
                print(f"  ⚠️ Пропущено: у пользователя {row[5]} нет бизнесов в таблице Businesses")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Синхронизация завершена:")
    print(f"   - Обновлено бизнесов: {updated_count}")
    print(f"   - Пропущено (нет бизнесов): {skipped_count}")

if __name__ == "__main__":
    sync_clientinfo_to_businesses()

