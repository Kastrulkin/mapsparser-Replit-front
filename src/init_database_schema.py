#!/usr/bin/env python3
"""
Единая функция инициализации схемы базы данных
Создаёт все необходимые таблицы при первом запуске
"""
from safe_db_utils import get_db_connection, get_db_path
import os
from core.default_ai_prompts import get_default_ai_prompts

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
                subscription_tier TEXT DEFAULT 'trial',
                subscription_status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES Users (id) ON DELETE CASCADE,
                FOREIGN KEY (network_id) REFERENCES Networks (id) ON DELETE SET NULL
            )
        """)
        print("✅ Таблица Businesses создана/проверена")
        
        # Добавляем колонки subscription_tier и subscription_status, если их нет (для существующих БД)
        try:
            cursor.execute("PRAGMA table_info(Businesses)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'subscription_tier' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN subscription_tier TEXT DEFAULT 'trial'")
                print("✅ Добавлена колонка subscription_tier")
            
            if 'subscription_status' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN subscription_status TEXT DEFAULT 'active'")
                print("✅ Добавлена колонка subscription_status")
            
            # Добавляем колонки для ChatGPT API и AI агентов
            if 'city' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN city TEXT")
                print("✅ Добавлена колонка city")
            
            if 'country' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN country TEXT")
                print("✅ Добавлена колонка country")
            
            if 'timezone' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN timezone TEXT DEFAULT 'UTC'")
                print("✅ Добавлена колонка timezone")
            
            if 'latitude' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN latitude REAL")
                print("✅ Добавлена колонка latitude")
            
            if 'longitude' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN longitude REAL")
                print("✅ Добавлена колонка longitude")
            
            if 'working_hours_json' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN working_hours_json TEXT")
                print("✅ Добавлена колонка working_hours_json")
            
            # WhatsApp Business API
            if 'waba_phone_id' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN waba_phone_id TEXT")
                print("✅ Добавлена колонка waba_phone_id")
            
            if 'waba_access_token' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN waba_access_token TEXT")
                print("✅ Добавлена колонка waba_access_token")
            
            if 'whatsapp_phone' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN whatsapp_phone TEXT")
                print("✅ Добавлена колонка whatsapp_phone")
            
            if 'whatsapp_verified' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN whatsapp_verified INTEGER DEFAULT 0")
                print("✅ Добавлена колонка whatsapp_verified")
            
            # Telegram
            if 'telegram_bot_token' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN telegram_bot_token TEXT")
                print("✅ Добавлена колонка telegram_bot_token")
            
            # AI Agent settings
            if 'ai_agent_enabled' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN ai_agent_enabled INTEGER DEFAULT 0")
                print("✅ Добавлена колонка ai_agent_enabled")
            
            if 'ai_agent_type' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN ai_agent_type TEXT")
                print("✅ Добавлена колонка ai_agent_type")
            
            if 'ai_agent_id' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN ai_agent_id TEXT")
                print("✅ Добавлена колонка ai_agent_id")
            
            if 'ai_agent_tone' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN ai_agent_tone TEXT")
                print("✅ Добавлена колонка ai_agent_tone")
            
            if 'ai_agent_restrictions' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN ai_agent_restrictions TEXT")
                print("✅ Добавлена колонка ai_agent_restrictions")
            
            if 'ai_agent_language' not in columns:
                cursor.execute("ALTER TABLE Businesses ADD COLUMN ai_agent_language TEXT DEFAULT 'en'")
                print("✅ Добавлена колонка ai_agent_language")
                
        except Exception as e:
            print(f"⚠️ Ошибка при добавлении колонок: {e}")
        
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
        
        # ParseQueue - очередь парсинга карт и синхронизации
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ParseQueue (
                id TEXT PRIMARY KEY,
                url TEXT,
                user_id TEXT NOT NULL,
                business_id TEXT,
                task_type TEXT DEFAULT 'parse_card',
                account_id TEXT,
                source TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                retry_after TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица ParseQueue создана/проверена")
        
        # Проверяем и добавляем недостающие поля для обратной совместимости
        try:
            cursor.execute("PRAGMA table_info(ParseQueue)")
            columns = [row[1] for row in cursor.fetchall()]
            
            fields_to_add = [
                ("task_type", "TEXT DEFAULT 'parse_card'"),
                ("account_id", "TEXT"),
                ("source", "TEXT"),
                ("error_message", "TEXT"),
                ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            ]
            
            for field_name, field_type in fields_to_add:
                if field_name not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE ParseQueue ADD COLUMN {field_name} {field_type}")
                        print(f"✅ Добавлено поле {field_name} в ParseQueue")
                    except Exception as e:
                        print(f"⚠️ Ошибка при добавлении поля {field_name}: {e}")
        except Exception as e:
            print(f"⚠️ Ошибка проверки структуры ParseQueue: {e}")
        
        # SyncQueue - очередь синхронизации внешних источников (Яндекс.Бизнес, Google Business, 2ГИС)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SyncQueue (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'yandex_business',
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица SyncQueue создана/проверена")
        
        # ProxyServers - список прокси-серверов для ротации IP
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ProxyServers (
                id TEXT PRIMARY KEY,
                proxy_type TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                username TEXT,
                password TEXT,
                is_active INTEGER DEFAULT 1,
                last_used_at TIMESTAMP,
                last_checked_at TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                is_working INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Таблица ProxyServers создана/проверена")
        
        # MapParseResults - результаты парсинга карт
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS MapParseResults (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                url TEXT NOT NULL,
                map_type TEXT,
                rating TEXT,
                reviews_count INTEGER DEFAULT 0,
                unanswered_reviews_count INTEGER DEFAULT 0,
                news_count INTEGER DEFAULT 0,
                photos_count INTEGER DEFAULT 0,
                services_count INTEGER DEFAULT 0,
                report_path TEXT,
                analysis_json TEXT,
                products TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                title TEXT,
                address TEXT,
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
        
        # UserNews - сгенерированные новости
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserNews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                service_id TEXT,
                source_text TEXT,
                generated_text TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (service_id) REFERENCES UserServices(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_news_user_id ON UserNews(user_id)")
        print("✅ Таблица UserNews создана/проверена")
        
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
        
        # ===== ОБМЕН ОТЗЫВАМИ =====
        
        # ReviewExchangeParticipants - участники обмена отзывами
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ReviewExchangeParticipants (
                id TEXT PRIMARY KEY,
                telegram_id TEXT UNIQUE NOT NULL,
                telegram_username TEXT,
                name TEXT,
                phone TEXT,
                business_name TEXT,
                business_address TEXT,
                business_url TEXT,
                review_request TEXT,
                consent_personal_data INTEGER DEFAULT 0,
                subscribed_to_channel INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Таблица ReviewExchangeParticipants создана/проверена")
        
        # ReviewExchangeDistribution - распределение ссылок (чтобы не отправлять одну ссылку дважды)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ReviewExchangeDistribution (
                id TEXT PRIMARY KEY,
                sender_participant_id TEXT NOT NULL,
                receiver_participant_id TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_participant_id) REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_participant_id) REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
                UNIQUE(sender_participant_id, receiver_participant_id)
            )
        """)
        print("✅ Таблица ReviewExchangeDistribution создана/проверена")
        
        # ExternalBusinessReviews - отзывы из внешних источников
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ExternalBusinessReviews (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                source TEXT NOT NULL,
                external_review_id TEXT,
                rating INTEGER,
                author_name TEXT,
                text TEXT,
                published_at TIMESTAMP,
                response_text TEXT,
                response_at TIMESTAMP,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица ExternalBusinessReviews создана/проверена")

        # ExternalBusinessPosts - посты из внешних источников
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ExternalBusinessPosts (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                account_id TEXT,
                source TEXT NOT NULL,
                external_post_id TEXT,
                title TEXT,
                text TEXT,
                published_at TIMESTAMP,
                image_url TEXT,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица ExternalBusinessPosts создана/проверена")

        # ExternalBusinessPhotos - фото из внешних источников
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ExternalBusinessPhotos (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                account_id TEXT,
                source TEXT NOT NULL,
                external_photo_id TEXT,
                url TEXT NOT NULL,
                thumbnail_url TEXT,
                uploaded_at TIMESTAMP,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
        print("✅ Таблица ExternalBusinessPhotos создана/проверена")

        # ExternalBusinessStats - статистика из внешних источников
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ExternalBusinessStats (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                source TEXT NOT NULL,
                date TEXT NOT NULL,
                views_total INTEGER,
                clicks_total INTEGER,
                actions_total INTEGER,
                rating REAL,
                reviews_total INTEGER,
                photos_count INTEGER DEFAULT 0,
                news_count INTEGER DEFAULT 0,
                unanswered_reviews_count INTEGER,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE,
                UNIQUE(business_id, source, date)
            )
        """)
        print("✅ Таблица ExternalBusinessStats создана/проверена")
        
        # Миграция для ExternalBusinessStats: проверка наличия счетчиков
        try:
            cursor.execute("PRAGMA table_info(ExternalBusinessStats)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'photos_count' not in columns:
                cursor.execute("ALTER TABLE ExternalBusinessStats ADD COLUMN photos_count INTEGER DEFAULT 0")
                print("✅ Добавлено поле photos_count в ExternalBusinessStats")
            if 'news_count' not in columns:
                cursor.execute("ALTER TABLE ExternalBusinessStats ADD COLUMN news_count INTEGER DEFAULT 0")
                print("✅ Добавлено поле news_count в ExternalBusinessStats")
            if 'unanswered_reviews_count' not in columns:
                cursor.execute("ALTER TABLE ExternalBusinessStats ADD COLUMN unanswered_reviews_count INTEGER")
                print("✅ Добавлено поле unanswered_reviews_count в ExternalBusinessStats")
        except Exception as e:
            print(f"⚠️ Ошибка проверки ExternalBusinessStats: {e}")
        
        # Индексы для внешних таблиц
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_reviews_business_id ON ExternalBusinessReviews(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_reviews_source ON ExternalBusinessReviews(source)")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_stats_business_id ON ExternalBusinessStats(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_stats_source ON ExternalBusinessStats(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_stats_date ON ExternalBusinessStats(date)")
        print("✅ Индексы для внешних таблиц созданы/проверены")
        
        # WordstatKeywords - популярные запросы (SEO)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS WordstatKeywords (
                id TEXT PRIMARY KEY,
                keyword TEXT UNIQUE NOT NULL,
                views INTEGER DEFAULT 0,
                category TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_views ON WordstatKeywords(views DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_category ON WordstatKeywords(category)")
        print("✅ Таблица WordstatKeywords создана/проверена")
        
        # ===== ОПТИМИЗАЦИЯ =====
        
        # BusinessOptimizationWizard - данные мастера оптимизации
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessMetricsHistory (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                metric_date DATE NOT NULL,
                rating FLOAT,
                reviews_count INTEGER,
                photos_count INTEGER,
                news_count INTEGER,
                unanswered_reviews_count INTEGER,
                source TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_history_business_date 
            ON BusinessMetricsHistory(business_id, metric_date DESC)
        """)
        print("✅ Таблица BusinessMetricsHistory создана/проверена")

        # Миграция для BusinessMetricsHistory: проверка наличия поля unanswered_reviews_count
        try:
            cursor.execute("PRAGMA table_info(BusinessMetricsHistory)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'unanswered_reviews_count' not in columns:
                cursor.execute("ALTER TABLE BusinessMetricsHistory ADD COLUMN unanswered_reviews_count INTEGER")
                print("✅ Добавлено поле unanswered_reviews_count в BusinessMetricsHistory")
        except Exception as e:
            print(f"⚠️ Ошибка проверки BusinessMetricsHistory: {e}")

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
        
        # Индексы для SyncQueue
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_syncqueue_status ON SyncQueue(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_syncqueue_business_id ON SyncQueue(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_syncqueue_created_at ON SyncQueue(created_at)")
        
        # Индексы для ProxyServers
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proxy_servers_active ON ProxyServers(is_active, is_working)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proxy_servers_last_used ON ProxyServers(last_used_at)")
        
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
        
        # Prompts - промпты для AI (редактируемые через админку)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AIPrompts (
                id TEXT PRIMARY KEY,
                prompt_type TEXT UNIQUE NOT NULL,
                prompt_text TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                FOREIGN KEY (updated_by) REFERENCES Users(id) ON DELETE SET NULL
            )
        """)
        print("✅ Таблица AIPrompts создана/проверена")
        
        # Инициализируем дефолтные промпты, если их нет
        default_prompts = get_default_ai_prompts()
        
        for prompt_type, prompt_text, description in default_prompts:
            cursor.execute("""
                INSERT INTO AIPrompts (id, prompt_type, prompt_text, description)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (prompt_type) DO NOTHING
            """, (f"prompt_{prompt_type}", prompt_type, prompt_text, description))
        
        print("✅ Дефолтные промпты инициализированы")
        
        # AIAgents - ИИ агенты
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AIAgents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                personality TEXT,
                states_json TEXT,
                workflow TEXT,
                task TEXT,
                identity TEXT,
                speech_style TEXT,
                restrictions_json TEXT,
                variables_json TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Таблица AIAgents создана/проверена")

        # Инициализация дефолтных агентов
        default_agents = [
            {
                'id': 'booking_agent_default',
                'name': 'Booking Agent',
                'type': 'booking',
                'description': 'Агент для записи клиентов',
                'personality': 'Вежливый, пунктуальный администратор. Твоя задача - записать клиента на услугу.',
                'is_active': 1
            }
        ]
        
        for agent in default_agents:
            cursor.execute("""
                INSERT OR IGNORE INTO AIAgents (id, name, type, description, personality, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (agent['id'], agent['name'], agent['type'], agent['description'], agent['personality'], agent['is_active']))
            
        print("✅ Дефолтные AI агенты инициализированы")

        # BusinessTypes - типы бизнеса (редактируемые)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessTypes (
                id TEXT PRIMARY KEY,
                type_key TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Таблица BusinessTypes создана/проверена")
        
        # GrowthStages - этапы роста для типов бизнеса
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS GrowthStages (
                id TEXT PRIMARY KEY,
                business_type_id TEXT NOT NULL,
                stage_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                goal TEXT,
                expected_result TEXT,
                duration TEXT,
                is_permanent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_type_id) REFERENCES BusinessTypes(id) ON DELETE CASCADE,
                UNIQUE(business_type_id, stage_number)
            )
        """)
        print("✅ Таблица GrowthStages создана/проверена")
        
        # GrowthTasks - задачи для этапов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS GrowthTasks (
                id TEXT PRIMARY KEY,
                stage_id TEXT NOT NULL,
                task_number INTEGER NOT NULL,
                task_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stage_id) REFERENCES GrowthStages(id) ON DELETE CASCADE,
                UNIQUE(stage_id, task_number)
            )
        """)
        print("✅ Таблица GrowthTasks создана/проверена")
        
        # Инициализируем дефолтные типы бизнеса, если их нет
        default_business_types = [
            ('beauty_salon', 'Салон красоты', 'Салон красоты с полным спектром услуг'),
            ('barbershop', 'Барбершоп', 'Мужской барбершоп'),
            ('spa', 'SPA/Wellness', 'SPA и wellness центр'),
            ('nail_studio', 'Ногтевая студия', 'Студия маникюра и педикюра'),
            ('cosmetology', 'Косметология', 'Косметологический кабинет'),
            ('massage', 'Массаж', 'Массажный салон'),
            ('brows_lashes', 'Брови и ресницы', 'Студия бровей и ресниц'),
            ('makeup', 'Макияж', 'Студия макияжа'),
            ('tanning', 'Солярий', 'Студия загара'),
            ('other', 'Другое', 'Другой тип бизнеса')
        ]
        
        for type_key, label, description in default_business_types:
            cursor.execute("""
                INSERT OR IGNORE INTO BusinessTypes (id, type_key, label, description)
                VALUES (%s, %s, %s, %s)
            """, (f"bt_{type_key}", type_key, label, description))
        
        print("✅ Дефолтные типы бизнеса инициализированы")
        
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
