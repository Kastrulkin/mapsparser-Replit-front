#!/usr/bin/env python3
"""
Миграция к архитектуре с привязкой всех данных к бизнесам
"""
import sqlite3
import sys
import os
import uuid
from datetime import datetime

def migrate_to_business_architecture():
    """Миграция к новой архитектуре с business_id"""
    conn = sqlite3.connect("src/reports.db")
    cursor = conn.cursor()
    
    try:
        print("🔄 Начинаем миграцию к архитектуре с business_id...")
        
        # 1. Добавляем business_id в существующие таблицы
        print("📝 Добавляем business_id в таблицы...")
        
        tables_to_migrate = [
            "Cards",
            "FinancialTransactions", 
            "FinancialMetrics",
            "ScreenshotAnalyses"
        ]
        
        for table in tables_to_migrate:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN business_id TEXT;")
                print(f"✅ Добавлено поле business_id в {table}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"✅ Поле business_id уже существует в {table}")
                else:
                    print(f"⚠️ Ошибка в {table}: {e}")
        
        # 2. Создаем таблицу Services если её нет
        print("📝 Создаем таблицу Services...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Services (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                keywords TEXT,
                price TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица Services создана")
        
        # 3. Создаем индексы для производительности
        print("📝 Создаем индексы...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_businesses_owner_id ON Businesses(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_services_business_id ON Services(business_id)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_business_id ON FinancialTransactions(business_id)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_business_id ON FinancialMetrics(business_id)",
            "CREATE INDEX IF NOT EXISTS idx_cards_business_id ON Cards(business_id)",
            "CREATE INDEX IF NOT EXISTS idx_screenshots_business_id ON ScreenshotAnalyses(business_id)"
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                print(f"✅ Индекс создан")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Ошибка создания индекса: {e}")
        
        # 4. Привязываем существующие данные к бизнесам
        print("📝 Привязываем существующие данные к бизнесам...")
        
        # Получаем всех пользователей и их бизнесы
        cursor.execute("SELECT id, email FROM Users")
        users = cursor.fetchall()
        
        for user_id, user_email in users:
            # Находим бизнесы пользователя
            cursor.execute("SELECT id FROM Businesses WHERE owner_id = ?", (user_id,))
            user_businesses = cursor.fetchall()
            
            if user_businesses:
                # Берем первый бизнес пользователя
                business_id = user_businesses[0][0]
                
                # Привязываем Cards
                cursor.execute("""
                    UPDATE Cards 
                    SET business_id = ? 
                    WHERE user_id = ? AND business_id IS NULL
                """, (business_id, user_id))
                
                # Привязываем FinancialTransactions
                cursor.execute("""
                    UPDATE FinancialTransactions 
                    SET business_id = ? 
                    WHERE user_id = ? AND business_id IS NULL
                """, (business_id, user_id))
                
                # Привязываем FinancialMetrics
                cursor.execute("""
                    UPDATE FinancialMetrics 
                    SET business_id = ? 
                    WHERE user_id = ? AND business_id IS NULL
                """, (business_id, user_id))
                
                # Привязываем ScreenshotAnalyses
                cursor.execute("""
                    UPDATE ScreenshotAnalyses 
                    SET business_id = ? 
                    WHERE user_id = ? AND business_id IS NULL
                """, (business_id, user_id))
                
                print(f"✅ Данные пользователя {user_email} привязаны к бизнесу {business_id}")
            else:
                print(f"⚠️ У пользователя {user_email} нет бизнесов")
        
        # 5. Создаем тестовые услуги для каждого бизнеса
        print("📝 Создаем тестовые услуги...")
        cursor.execute("SELECT id, name, business_type FROM Businesses")
        businesses = cursor.fetchall()
        
        for business_id, business_name, business_type in businesses:
            # Создаем услуги в зависимости от типа бизнеса
            if business_type == 'beauty_salon':
                services = [
                    ("Женская стрижка", "Стрижка волос любой длины с укладкой", "haircut", "стрижка, волосы, укладка", "2500"),
                    ("Окрашивание", "Окрашивание волос в любой цвет", "coloring", "окрашивание, цвет, волосы", "3500"),
                    ("Маникюр", "Классический и аппаратный маникюр", "manicure", "маникюр, ногти, покрытие", "1500")
                ]
            elif business_type == 'barbershop':
                services = [
                    ("Мужская стрижка", "Классическая мужская стрижка", "haircut", "стрижка, мужская, классика", "1200"),
                    ("Бритье", "Бритье опасной бритвой", "shaving", "бритье, опасная бритва", "800"),
                    ("Укладка", "Укладка волос с укладкой", "styling", "укладка, волосы, стиль", "600")
                ]
            elif business_type == 'nail_studio':
                services = [
                    ("Маникюр", "Классический маникюр", "manicure", "маникюр, ногти", "1000"),
                    ("Педикюр", "Классический педикюр", "pedicure", "педикюр, ноги, ногти", "1500"),
                    ("Покрытие гель-лак", "Покрытие гель-лаком", "gel_polish", "гель-лак, покрытие, ногти", "800")
                ]
            else:
                services = [
                    ("Услуга 1", "Описание услуги 1", "general", "услуга, описание", "1000"),
                    ("Услуга 2", "Описание услуги 2", "general", "услуга, описание", "1500")
                ]
            
            for name, description, category, keywords, price in services:
                service_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT OR IGNORE INTO Services 
                    (id, business_id, name, description, category, keywords, price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (service_id, business_id, name, description, category, keywords, price))
            
            print(f"✅ Создано {len(services)} услуг для {business_name}")
        
        conn.commit()
        print("🎉 Миграция завершена успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔄 Выполняем миграцию к архитектуре с business_id...")
    success = migrate_to_business_architecture()
    
    if success:
        print("\n✅ Миграция завершена!")
        print("📊 Теперь все данные привязаны к бизнесам")
        print("🔐 Обычные пользователи видят только свои бизнесы")
        print("👑 Суперадмины могут переключаться между всеми бизнесами")
    else:
        print("\n❌ Миграция не удалась.")
        sys.exit(1)
