#!/usr/bin/env python3
"""
Скрипт для инициализации SQLite базы данных
"""
from safe_db_utils import get_db_connection
import sqlite3
import os
from datetime import datetime

def init_database():
    """Создать и инициализировать базу данных (безопасно, с проверкой существующих данных)"""
    from safe_db_utils import get_db_path, backup_database
    import os
    
    # Получаем путь к базе данных
    db_path = get_db_path()
    
    # Проверяем, существует ли база данных и есть ли в ней данные
    if os.path.exists(db_path):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем, есть ли таблица Users и данные в ней
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Users'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM Users")
            user_count = cursor.fetchone()[0]
            if user_count > 0:
                print(f"⚠️  База данных уже существует и содержит {user_count} пользователей!")
                print(f"📁 Путь: {db_path}")
                print("✅ Инициализация пропущена - данные сохранены")
                print("💡 Используйте миграции для обновления структуры БД")
                conn.close()
                return
        
        # Если база существует, но пустая - создаем бэкап
        print(f"💾 Создаю бэкап существующей базы данных...")
        backup_path = backup_database()
        if backup_path:
            print(f"✅ Бэкап создан: {backup_path}")
        conn.close()
    
    # Создаем базу данных
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Таблица Users - пользователи системы
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        name TEXT,
        phone TEXT,
        telegram_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        is_verified BOOLEAN DEFAULT 0,
        is_superadmin BOOLEAN DEFAULT 0,
        verification_token TEXT,
        reset_token TEXT,
        reset_token_expires TIMESTAMP
    )
    """)
    
    # 2. Таблица Invites - приглашённые пользователи
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Invites (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        invited_by TEXT NOT NULL,
        token TEXT UNIQUE NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (invited_by) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # 3. Таблица ParseQueue - очередь запрошенных отчётов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ParseQueue (
        id TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        user_id TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # 4. Таблица Cards - готовые отчёты
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Cards (
        id TEXT PRIMARY KEY,
        url TEXT,
        title TEXT,
        address TEXT,
        phone TEXT,
        site TEXT,
        rating REAL,
        reviews_count INTEGER,
        categories TEXT,
        overview TEXT,
        products TEXT,
        news TEXT,
        photos TEXT,
        features_full TEXT,
        competitors TEXT,
        hours TEXT,
        hours_full TEXT,
        report_path TEXT,
        user_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        seo_score INTEGER,
        ai_analysis TEXT,
        recommendations TEXT,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # Дополнительная таблица для управления сессиями
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS UserSessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        token TEXT UNIQUE NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        user_agent TEXT,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # Таблица для анализа скриншотов карточек
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ScreenshotAnalyses (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        image_path TEXT,
        analysis_result TEXT,
        completeness_score INTEGER,
        business_name TEXT,
        category TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # Таблица для SEO оптимизации прайс-листов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS PricelistOptimizations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        original_file_path TEXT,
        optimized_data TEXT,
        services_count INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # 7. Таблица FinancialTransactions - финансовые транзакции
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS FinancialTransactions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        transaction_date DATE NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        client_type TEXT NOT NULL CHECK (client_type IN ('new', 'returning')),
        services TEXT, -- JSON массив услуг
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # 8. Таблица FinancialMetrics - агрегированные метрики
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS FinancialMetrics (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        total_revenue DECIMAL(10,2) DEFAULT 0,
        total_orders INTEGER DEFAULT 0,
        new_clients INTEGER DEFAULT 0,
        returning_clients INTEGER DEFAULT 0,
        average_check DECIMAL(10,2) DEFAULT 0,
        retention_rate DECIMAL(5,2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # 9. Таблица ROIData - данные ROI
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ROIData (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        investment_amount DECIMAL(10,2) NOT NULL,
        returns_amount DECIMAL(10,2) NOT NULL,
        roi_percentage DECIMAL(5,2) NOT NULL,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # 10. Таблица ProgressStages - этапы прогресса
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ProgressStages (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        stage_number INTEGER NOT NULL,
        stage_name TEXT NOT NULL,
        stage_description TEXT,
        status TEXT NOT NULL CHECK (status IN ('completed', 'active', 'pending')),
        progress_percentage INTEGER DEFAULT 0,
        target_revenue DECIMAL(10,2),
        target_clients INTEGER,
        target_roi DECIMAL(5,2),
        current_revenue DECIMAL(10,2) DEFAULT 0,
        current_clients INTEGER DEFAULT 0,
        current_roi DECIMAL(5,2) DEFAULT 0,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # 11. Таблица StageTasks - задачи этапов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS StageTasks (
        id TEXT PRIMARY KEY,
        stage_id TEXT NOT NULL,
        task_title TEXT NOT NULL,
        task_description TEXT,
        is_completed BOOLEAN DEFAULT 0,
        priority INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (stage_id) REFERENCES ProgressStages (id) ON DELETE CASCADE
    )
    """)
    
    # 12. Таблица UserServices - услуги пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS UserServices (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        keywords TEXT, -- JSON массив ключевых слов
        price TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # 13. Таблица Businesses - компании/бизнесы
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Businesses (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        industry TEXT,
        business_type TEXT,
        address TEXT,
        working_hours TEXT,
        phone TEXT,
        email TEXT,
        website TEXT,
        owner_id TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (owner_id) REFERENCES Users (id) ON DELETE CASCADE
    )
    """)
    
    # 14. Таблица BusinessOptimizationWizard - данные Мастера оптимизации бизнеса
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS BusinessOptimizationWizard (
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
    
    # Добавляем тестовые данные
    cursor.execute("""
    INSERT OR REPLACE INTO Cards (id, url, title, report_path, user_id, seo_score, ai_analysis)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        "2a8b7279-ac0c-4218-9ec3-dfdbe410a0bd",
        "https://yandex.ru/maps/org/gagarin/180566191872/?ll=30.339235%2C59.859247&z=17.22",
        "Гагарин",
        "/root/mapsparser-Replit-front/data/report_Гагарин.html",
        "f2123626-71b1-4424-8b2a-0bc93ab8f2eb",
        100,
        "Отличный рейтинг показывает высокое качество услуг"
    ))
    
    conn.commit()
    conn.close()
    print("База данных инициализирована успешно!")

if __name__ == "__main__":
    init_database()
