#!/usr/bin/env python3
"""
Миграция для добавления полей в таблицу Businesses
"""
from safe_db_utils import get_db_connection
import sqlite3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def migrate_business_fields():
    """Добавить новые поля в таблицу Businesses"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, какие поля уже существуют
        cursor.execute("PRAGMA table_info(Businesses)")
        columns = [column[1] for column in cursor.fetchall()]
        
        new_fields = [
            ("business_type", "TEXT"),
            ("address", "TEXT"),
            ("working_hours", "TEXT"),
            ("phone", "TEXT"),
            ("email", "TEXT"),
            ("website", "TEXT")
        ]
        
        for field_name, field_type in new_fields:
            if field_name not in columns:
                print(f"📝 Добавляем поле {field_name} в таблицу Businesses...")
                cursor.execute(f"ALTER TABLE Businesses ADD COLUMN {field_name} {field_type}")
                print(f"✅ Поле {field_name} добавлено")
            else:
                print(f"✅ Поле {field_name} уже существует")
        
        # Обновляем существующие бизнесы с тестовыми данными
        print("📝 Обновляем тестовые данные бизнесов...")
        
        # Бизнес 1: Салон красоты 'Элегант'
        cursor.execute("""
            UPDATE Businesses 
            SET business_type = 'beauty_salon',
                address = 'Невский проспект, 100, Санкт-Петербург',
                working_hours = '09:00-21:00',
                phone = '+7 (812) 123-45-67',
                email = 'elegant@beauty.ru',
                website = 'https://elegant-beauty.ru'
            WHERE name LIKE '%Элегант%'
        """)
        
        # Бизнес 2: Барбершоп 'Мужской стиль'
        cursor.execute("""
            UPDATE Businesses 
            SET business_type = 'barbershop',
                address = 'Литейный проспект, 50, Санкт-Петербург',
                working_hours = '10:00-22:00',
                phone = '+7 (812) 234-56-78',
                email = 'style@barber.ru',
                website = 'https://mens-style.ru'
            WHERE name LIKE '%Мужской стиль%'
        """)
        
        # Бизнес 3: Ногтевая студия 'Маникюр Плюс'
        cursor.execute("""
            UPDATE Businesses 
            SET business_type = 'nail_studio',
                address = 'Малая Посадская улица, 28/2, Санкт-Петербург',
                working_hours = '09:00-20:00',
                phone = '+7 (812) 345-67-89',
                email = 'manicure@plus.ru',
                website = 'https://manicure-plus.ru'
            WHERE name LIKE '%Маникюр Плюс%'
        """)
        
        conn.commit()
        print("🎉 Миграция завершена успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔄 Выполняем миграцию полей бизнеса...")
    success = migrate_business_fields()
    
    if success:
        print("\n✅ Миграция завершена!")
    else:
        print("\n❌ Миграция не удалась.")
        sys.exit(1)
