#!/usr/bin/env python3
"""
Миграция базы данных для добавления таблицы BusinessOptimizationWizard
для хранения данных из Мастера оптимизации бизнеса
"""
import sqlite3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def migrate_wizard_data():
    """Добавить таблицу BusinessOptimizationWizard для данных мастера оптимизации"""
    # Используем тот же путь к БД, что и в основном приложении
    db_paths = [
        "src/reports.db",
        "reports.db"
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ База данных не найдена!")
        return False
    
    print(f"📁 Используем базу данных: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли уже таблица
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='BusinessOptimizationWizard'
        """)
        
        if not cursor.fetchone():
            print("📝 Создаем таблицу BusinessOptimizationWizard...")
            cursor.execute("""
                CREATE TABLE BusinessOptimizationWizard (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL,
                    -- Шаг 1: Диагностика карточки
                    card_url TEXT,
                    rating REAL,
                    reviews_count INTEGER,
                    photo_update_frequency TEXT,
                    news_enabled TEXT, -- 'Да' или 'Нет'
                    news_frequency TEXT,
                    current_services_text TEXT,
                    -- Шаг 2: Предпочтения
                    preferences_like TEXT,
                    preferences_dislike TEXT,
                    favorite_formulations TEXT, -- JSON массив до 5 формулировок
                    -- Шаг 3: Формулировки услуг (сохраняется как JSON)
                    selected_service_formulations TEXT, -- JSON объект с выбранными формулировками
                    -- Шаг 4: Метрики бизнеса
                    business_age TEXT, -- '0–6 мес', '6–12 мес', '1–3 года', '3+ лет'
                    regular_clients_count INTEGER,
                    crm_system TEXT,
                    location_type TEXT,
                    average_check DECIMAL(10,2),
                    monthly_revenue DECIMAL(10,2),
                    card_preferences_text TEXT,
                    -- Метаданные
                    wizard_completed BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
                )
            """)
            
            # Создаем индекс для быстрого поиска по business_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_wizard_business_id 
                ON BusinessOptimizationWizard(business_id)
            """)
            
            print("✅ Таблица BusinessOptimizationWizard создана")
        else:
            print("✅ Таблица BusinessOptimizationWizard уже существует")
        
        # Проверяем существующие данные - убеждаемся, что ничего не удалено
        cursor.execute("SELECT COUNT(*) FROM Businesses")
        businesses_count = cursor.fetchone()[0]
        print(f"✅ В таблице Businesses: {businesses_count} записей")
        
        cursor.execute("SELECT COUNT(*) FROM UserServices")
        services_count = cursor.fetchone()[0]
        print(f"✅ В таблице UserServices: {services_count} записей")
        
        cursor.execute("SELECT COUNT(*) FROM Users WHERE is_superadmin = 1")
        superadmin_count = cursor.fetchone()[0]
        print(f"✅ Суперпользователей: {superadmin_count}")
        
        conn.commit()
        print("🎉 Миграция завершена успешно!")
        print("\n📋 Структура таблицы BusinessOptimizationWizard:")
        cursor.execute("PRAGMA table_info(BusinessOptimizationWizard)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔄 Выполняем миграцию базы данных для Мастера оптимизации...")
    print("=" * 60)
    success = migrate_wizard_data()
    print("=" * 60)
    
    if success:
        print("\n✅ Миграция завершена успешно!")
        print("📝 Все существующие данные сохранены!")
    else:
        print("\n❌ Миграция не удалась.")
        sys.exit(1)

