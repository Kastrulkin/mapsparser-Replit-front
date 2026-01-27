CREATE TABLE Users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, phone TEXT, password_hash TEXT, is_superadmin BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_active BOOLEAN DEFAULT 1, is_verified BOOLEAN DEFAULT 1, telegram_id TEXT, reset_token TEXT, reset_token_expires TIMESTAMP);
CREATE TABLE Businesses (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, industry TEXT, business_type TEXT, address TEXT, working_hours TEXT, phone TEXT, email TEXT, website TEXT, owner_id TEXT NOT NULL, is_active BOOLEAN DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, network_id TEXT, yandex_org_id TEXT, yandex_url TEXT, yandex_rating FLOAT, yandex_reviews_total INTEGER, yandex_reviews_30d INTEGER, yandex_last_sync TIMESTAMP, latitude REAL, longitude REAL, subscription_tier TEXT DEFAULT 'trial', subscription_status TEXT DEFAULT 'active', city TEXT, country TEXT, timezone TEXT DEFAULT 'UTC', working_hours_json TEXT, waba_phone_id TEXT, waba_access_token TEXT, whatsapp_phone TEXT, whatsapp_verified INTEGER DEFAULT 0, telegram_bot_token TEXT, ai_agent_enabled INTEGER DEFAULT 0, ai_agent_type TEXT, ai_agent_id TEXT, ai_agent_tone TEXT, ai_agent_restrictions TEXT, ai_agent_language TEXT DEFAULT 'en', FOREIGN KEY (owner_id) REFERENCES Users (id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS "UserServices" (id TEXT PRIMARY KEY, business_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT, category TEXT, keywords TEXT, price TEXT, is_active BOOLEAN DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, user_id TEXT, FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE);
CREATE TABLE UserSessions (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, token TEXT UNIQUE NOT NULL, expires_at TIMESTAMP NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, ip_address TEXT, user_agent TEXT, FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE);
CREATE TABLE FinancialTransactions (id TEXT PRIMARY KEY, business_id TEXT, amount REAL, description TEXT, transaction_type TEXT, date DATE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, client_type TEXT DEFAULT 'returning', master_id TEXT, user_id TEXT, transaction_date DATE, services TEXT DEFAULT '[]', notes TEXT DEFAULT '', FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE);
CREATE TABLE FinancialMetrics (id TEXT PRIMARY KEY, business_id TEXT, metric_name TEXT, metric_value REAL, period TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE);
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
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, step INTEGER DEFAULT 1,
                    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
                );
CREATE INDEX idx_wizard_business_id 
                ON BusinessOptimizationWizard(business_id)
            ;
CREATE TABLE UserNews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                service_id TEXT,
                source_text TEXT,
                generated_text TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            , updated_at TIMESTAMP);
CREATE TABLE ROIData (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            investment_amount DECIMAL(10,2) NOT NULL,
            returns_amount DECIMAL(10,2) NOT NULL,
            roi_percentage DECIMAL(5,2) NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE Networks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES Users (id) ON DELETE CASCADE
        );
CREATE TABLE Masters (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            specialization TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
        );
CREATE UNIQUE INDEX idx_users_telegram_id_unique ON Users(telegram_id) WHERE telegram_id IS NOT NULL;
CREATE INDEX idx_businesses_network_id ON Businesses(network_id);
CREATE INDEX idx_masters_business_id ON Masters(business_id);
CREATE INDEX idx_users_telegram_id ON Users(telegram_id);
CREATE TABLE TelegramBindTokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, business_id TEXT,
            FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
        );
CREATE INDEX idx_telegram_bind_tokens_token ON TelegramBindTokens(token);
CREATE INDEX idx_telegram_bind_tokens_user_id ON TelegramBindTokens(user_id);
CREATE TABLE YandexBusinessStats (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                date DATE NOT NULL,
                rating FLOAT,
                reviews_total INTEGER,
                reviews_30d INTEGER,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            );
CREATE INDEX idx_yandex_stats_business_id ON YandexBusinessStats(business_id);
CREATE INDEX idx_yandex_stats_business_date ON YandexBusinessStats(business_id, date);
CREATE TABLE PricelistOptimizations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                original_file_path TEXT,
                optimized_data TEXT,
                services_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            );
CREATE TABLE UserLoginHistory (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        );
CREATE TABLE UserTokenAccess (
            user_id TEXT PRIMARY KEY,
            tokens_paused BOOLEAN DEFAULT 0,
            paused_at TIMESTAMP,
            paused_reason TEXT,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        );
CREATE INDEX idx_login_history_user_id 
        ON UserLoginHistory(user_id)
    ;
CREATE INDEX idx_login_history_created_at 
        ON UserLoginHistory(created_at)
    ;
CREATE TABLE BusinessMapLinks (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                business_id TEXT,
                url TEXT,
                map_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE TABLE MapParseResults (
                id TEXT PRIMARY KEY,
                business_id TEXT,
                url TEXT,
                map_type TEXT,
                rating TEXT,
                reviews_count INTEGER,
                news_count INTEGER,
                photos_count INTEGER,
                report_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            , products TEXT DEFAULT NULL, unanswered_reviews_count INTEGER, is_verified INTEGER DEFAULT 0, phone TEXT, website TEXT, messengers TEXT, working_hours TEXT, services_count INTEGER DEFAULT 0, profile_completeness INTEGER DEFAULT 0, analysis_json TEXT, title TEXT, address TEXT);
CREATE TABLE BusinessTypes (
            id TEXT PRIMARY KEY,
            type_key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        , alert_threshold_news_days INTEGER DEFAULT 30, alert_threshold_photos_days INTEGER DEFAULT 90, alert_threshold_reviews_days INTEGER DEFAULT 7);
CREATE TABLE GrowthStages (
            id TEXT PRIMARY KEY,
            business_type_id TEXT NOT NULL,
            stage_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            goal TEXT,
            expected_result TEXT,
            duration TEXT,
            is_permanent INTEGER DEFAULT 0,
            tasks TEXT, -- JSON array of strings
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_type_id) REFERENCES BusinessTypes(id) ON DELETE CASCADE
        );
CREATE INDEX idx_businesses_coordinates 
            ON Businesses(latitude, longitude)
        ;
CREATE TABLE ParseQueue (
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
            );
CREATE TABLE SyncQueue (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'yandex_business',
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            );
CREATE TABLE ProxyServers (
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
            );
CREATE TABLE ReviewExchangeParticipants (
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
            );
CREATE TABLE ReviewExchangeDistribution (
                id TEXT PRIMARY KEY,
                sender_participant_id TEXT NOT NULL,
                receiver_participant_id TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_participant_id) REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_participant_id) REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
                UNIQUE(sender_participant_id, receiver_participant_id)
            );
CREATE INDEX idx_parsequeue_status ON ParseQueue(status);
CREATE INDEX idx_parsequeue_business_id ON ParseQueue(business_id);
CREATE INDEX idx_parsequeue_user_id ON ParseQueue(user_id);
CREATE INDEX idx_parsequeue_created_at ON ParseQueue(created_at);
CREATE INDEX idx_syncqueue_status ON SyncQueue(status);
CREATE INDEX idx_syncqueue_business_id ON SyncQueue(business_id);
CREATE INDEX idx_syncqueue_created_at ON SyncQueue(created_at);
CREATE INDEX idx_proxy_servers_active ON ProxyServers(is_active, is_working);
CREATE INDEX idx_proxy_servers_last_used ON ProxyServers(last_used_at);
CREATE INDEX idx_businesses_owner_id ON Businesses(owner_id);
CREATE INDEX idx_financial_transactions_business_id ON FinancialTransactions(business_id);
CREATE INDEX idx_financial_transactions_date ON FinancialTransactions(transaction_date);
CREATE INDEX idx_user_services_business_id ON UserServices(business_id);
CREATE INDEX idx_business_map_links_business_id ON BusinessMapLinks(business_id);
CREATE INDEX idx_map_parse_results_business_id ON MapParseResults(business_id);
CREATE TABLE AIPrompts (
                id TEXT PRIMARY KEY,
                prompt_type TEXT UNIQUE NOT NULL,
                prompt_text TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                FOREIGN KEY (updated_by) REFERENCES Users(id) ON DELETE SET NULL
            );
CREATE TABLE AIAgents (
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
            );
CREATE TABLE GrowthTasks (
                id TEXT PRIMARY KEY,
                stage_id TEXT NOT NULL,
                task_number INTEGER NOT NULL,
                task_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, check_logic TEXT, reward_value INTEGER DEFAULT 0, reward_type TEXT DEFAULT 'time_saved', tooltip TEXT, link_url TEXT, link_text TEXT, is_auto_verifiable INTEGER DEFAULT 0,
                FOREIGN KEY (stage_id) REFERENCES GrowthStages(id) ON DELETE CASCADE,
                UNIQUE(stage_id, task_number)
            );
CREATE TABLE BusinessMetricsHistory (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                metric_date DATE NOT NULL,
                rating FLOAT,
                reviews_count INTEGER,
                photos_count INTEGER,
                news_count INTEGER,
                source TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id)
            );
CREATE INDEX idx_metrics_history_business_date 
            ON BusinessMetricsHistory(business_id, metric_date DESC)
        ;
CREATE TABLE BusinessProfiles (
                                id TEXT PRIMARY KEY,
                                business_id TEXT NOT NULL,
                                contact_name TEXT,
                                contact_phone TEXT,
                                contact_email TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
                            );
CREATE TABLE ExternalBusinessAccounts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            source TEXT NOT NULL, -- 'yandex_business', '2gis', 'google_business'
            external_id TEXT, -- ID inside the external system (e.g. org_id)
            display_name TEXT,
            auth_data_encrypted TEXT, -- JSON with cookies, tokens, etc. (encrypted or plain)
            is_active INTEGER DEFAULT 1,
            last_sync_at TIMESTAMP,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE,
            UNIQUE(business_id, source)
        );
CREATE INDEX idx_ext_accounts_business_id ON ExternalBusinessAccounts(business_id);
CREATE INDEX idx_ext_accounts_source ON ExternalBusinessAccounts(source);
CREATE TABLE UserExamples (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            example_type TEXT NOT NULL,
            example_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        );
CREATE INDEX idx_user_examples_user_type ON UserExamples(user_id, example_type);
CREATE TABLE ExternalBusinessReviews (
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
            );
CREATE INDEX idx_ext_reviews_business_id ON ExternalBusinessReviews(business_id);
CREATE INDEX idx_ext_reviews_source ON ExternalBusinessReviews(source);
CREATE INDEX idx_ext_reviews_created_at ON ExternalBusinessReviews(created_at);
CREATE TABLE ExternalBusinessStats (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                source TEXT NOT NULL,
                date TEXT NOT NULL,
                views_total INTEGER,
                clicks_total INTEGER,
                actions_total INTEGER,
                rating REAL,
                reviews_total INTEGER,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE,
                UNIQUE(business_id, source, date)
            );
CREATE INDEX idx_ext_stats_business_id ON ExternalBusinessStats(business_id);
CREATE INDEX idx_ext_stats_source ON ExternalBusinessStats(source);
CREATE INDEX idx_ext_stats_date ON ExternalBusinessStats(date);
CREATE TABLE WordstatKeywords (
                id TEXT PRIMARY KEY,
                keyword TEXT UNIQUE NOT NULL,
                views INTEGER DEFAULT 0,
                category TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE INDEX idx_wordstat_views ON WordstatKeywords(views DESC);
CREATE INDEX idx_wordstat_category ON WordstatKeywords(category);
CREATE TABLE ProspectingLeads (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT,
                phone TEXT,
                website TEXT,
                rating REAL,
                reviews_count INTEGER,
                source_url TEXT,
                google_id TEXT,
                category TEXT,
                location TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE INDEX idx_user_sessions_token ON UserSessions(token);
CREATE INDEX idx_user_sessions_expires ON UserSessions(expires_at);
CREATE INDEX idx_businesses_active ON Businesses(is_active);
CREATE INDEX idx_businesses_subscription_status ON Businesses(subscription_status);
CREATE INDEX idx_ext_reviews_published_at ON ExternalBusinessReviews(published_at);
CREATE INDEX idx_ext_reviews_business_published ON ExternalBusinessReviews(business_id, published_at);
CREATE TABLE ClientInfo (
                    user_id TEXT,
                    business_id TEXT,
                    business_name TEXT,
                    business_type TEXT,
                    address TEXT,
                    working_hours TEXT,
                    description TEXT,
                    services TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, business_id)
                );
CREATE TABLE ExternalBusinessPosts (
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
            );
CREATE INDEX idx_ext_posts_business ON ExternalBusinessPosts(business_id);
CREATE TABLE ExternalBusinessPhotos (
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
            );
CREATE INDEX idx_ext_photos_business ON ExternalBusinessPhotos(business_id);
