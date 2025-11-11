#!/usr/bin/env python3
"""
Безопасная миграция базы данных для добавления таблицы BusinessOptimizationWizard
Использует safe_db_utils для защиты данных
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import safe_migrate, get_db_path, backup_database

def migrate_wizard_data_safe():
    """Безопасная миграция с бэкапом"""
    print("🔄 Выполняем безопасную миграцию для Мастера оптимизации...")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📁 Используем базу данных: {db_path}")
    
    def migration_callback(cursor):
        """Колбэк миграции"""
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
                    news_enabled TEXT,
                    news_frequency TEXT,
                    current_services_text TEXT,
                    -- Шаг 2: Предпочтения
                    preferences_like TEXT,
                    preferences_dislike TEXT,
                    favorite_formulations TEXT,
                    -- Шаг 3: Формулировки услуг
                    selected_service_formulations TEXT,
                    -- Шаг 4: Метрики бизнеса
                    business_age TEXT,
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
    
    success = safe_migrate(
        migration_callback,
        "Добавление таблицы BusinessOptimizationWizard"
    )
    
    print("=" * 60)
    return success

if __name__ == "__main__":
    success = migrate_wizard_data_safe()
    
    if success:
        print("\n✅ Миграция завершена успешно!")
        print("📝 Все существующие данные сохранены!")
        print("💾 Бэкап создан автоматически в db_backups/")
    else:
        print("\n❌ Миграция не удалась.")
        print("💾 База данных восстановлена из бэкапа")
        sys.exit(1)

