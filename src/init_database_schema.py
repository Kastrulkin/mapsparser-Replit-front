#!/usr/bin/env python3
"""
Единая функция инициализации схемы базы данных
Создаёт все необходимые таблицы при первом запуске
"""
from safe_db_utils import get_db_connection, get_db_path
import os

def init_database_schema():
    """Инициализировать все таблицы базы данных"""
    db_path = get_db_path()
    
    # Проверяем, существует ли база данных
    db_exists = os.path.exists(db_path)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print("🔄 Инициализация схемы базы данных...")
        print(f"📁 База данных: {db_path}")
        print(f"📊 База {'существует' if db_exists else 'создаётся'}")
        print()
        
        # ===== ОСНОВНЫЕ ТАБЛИЦЫ =====
        
        # Users - пользователи
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT,
                phone TEXT,
                telegram_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                is_verified INTEGER DEFAULT 0,
                is_superadmin INTEGER DEFAULT 0
            )
        """)
        print("✅ Таблица Users создана/проверена")
        
        # Businesses - бизнесы
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
                network_id TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES Users (id) ON DELETE CASCADE,
                FOREIGN KEY (network_id) REFERENCES Networks (id) ON DELETE SET NULL
            )
        """)
        print("✅ Таблица Businesses создана/проверена")
        
        # UserSessions - сессии пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserSessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица UserSessions создана/проверена")
        
        # ===== ПАРСИНГ И ОЧЕРЕДЬ =====
        
        # ParseQueue - очередь парсинга карт
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ParseQueue (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                user_id TEXT NOT NULL,
                business_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                retry_after TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица ParseQueue создана/проверена")
        
        # MapParseResults - результаты парсинга карт
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS MapParseResults (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                url TEXT NOT NULL,
                map_type TEXT,
                rating TEXT,
                reviews_count INTEGER DEFAULT 0,
                news_count INTEGER DEFAULT 0,
                photos_count INTEGER DEFAULT 0,
                report_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица MapParseResults создана/проверена")
        
        # BusinessMapLinks - ссылки на карты для бизнесов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessMapLinks (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                business_id TEXT NOT NULL,
                url TEXT NOT NULL,
                map_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица BusinessMapLinks создана/проверена")
        
        # ===== ФИНАНСЫ =====
        
        # FinancialTransactions - финансовые транзакции
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS FinancialTransactions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                business_id TEXT NOT NULL,
                transaction_date DATE,
                amount REAL NOT NULL,
                client_type TEXT,
                services TEXT,
                notes TEXT,
                master_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE,
                FOREIGN KEY (master_id) REFERENCES Masters (id) ON DELETE SET NULL
            )
        """)
        print("✅ Таблица FinancialTransactions создана/проверена")
        
        # FinancialMetrics - финансовые метрики (кеш)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS FinancialMetrics (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                total_revenue REAL DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                average_check REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица FinancialMetrics создана/проверена")
        
        # ROIData - данные ROI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ROIData (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                investment REAL NOT NULL,
                revenue REAL NOT NULL,
                roi_percentage REAL NOT NULL,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица ROIData создана/проверена")
        
        # ===== УСЛУГИ И КОНТЕНТ =====
        
        # UserServices - услуги пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserServices (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                business_id TEXT NOT NULL,
                category TEXT,
                name TEXT NOT NULL,
                description TEXT,
                keywords TEXT,
                price TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица UserServices создана/проверена")
        
        # ===== СЕТИ И МАСТЕРА =====
        
        # Networks - сети бизнесов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Networks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES Users (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица Networks создана/проверена")
        
        # Masters - мастера
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Masters (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                name TEXT NOT NULL,
                specialization TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица Masters создана/проверена")
        
        # ===== TELEGRAM =====
        
        # TelegramBindTokens - токены привязки Telegram
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TelegramBindTokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                business_id TEXT,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица TelegramBindTokens создана/проверена")
        
        # ===== ОПТИМИЗАЦИЯ =====
        
        # BusinessOptimizationWizard - данные мастера оптимизации
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessOptimizationWizard (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                step INTEGER DEFAULT 1,
                data TEXT,
                completed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица BusinessOptimizationWizard создана/проверена")
        
        # PricelistOptimizations - оптимизации прайс-листов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PricelistOptimizations (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                original_text TEXT,
                optimized_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица PricelistOptimizations создана/проверена")
        
        # ===== ИНДЕКСЫ =====
        
        print()
        print("📊 Создание индексов...")
        
        # Индексы для ParseQueue
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_status ON ParseQueue(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_business_id ON ParseQueue(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_user_id ON ParseQueue(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_created_at ON ParseQueue(created_at)")
        
        # Индексы для Businesses
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_businesses_owner_id ON Businesses(owner_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_businesses_network_id ON Businesses(network_id)")
        
        # Индексы для FinancialTransactions (проверяем наличие колонок)
        try:
            cursor.execute("PRAGMA table_info(FinancialTransactions)")
            ft_columns = [row[1] for row in cursor.fetchall()]
            if 'business_id' in ft_columns:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_financial_transactions_business_id ON FinancialTransactions(business_id)")
            if 'transaction_date' in ft_columns:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_financial_transactions_date ON FinancialTransactions(transaction_date)")
        except Exception as e:
            print(f"⚠️ Пропущены индексы для FinancialTransactions: {e}")
        
        # Индексы для UserServices (проверяем наличие колонок)
        try:
            cursor.execute("PRAGMA table_info(UserServices)")
            us_columns = [row[1] for row in cursor.fetchall()]
            if 'business_id' in us_columns:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_services_business_id ON UserServices(business_id)")
        except Exception as e:
            print(f"⚠️ Пропущены индексы для UserServices: {e}")
        
        # Индексы для BusinessMapLinks
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_map_links_business_id ON BusinessMapLinks(business_id)")
        
        # Индексы для MapParseResults
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_map_parse_results_business_id ON MapParseResults(business_id)")
        
        print("✅ Индексы созданы/проверены")
        
        conn.commit()
        
        print()
        print("=" * 60)
        print("✅ Инициализация схемы базы данных завершена!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка инициализации схемы: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    init_database_schema()

