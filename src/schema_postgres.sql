-- PostgreSQL Schema for BeautyBot
-- Generated based on init_database_schema.py

-- Enable UUID extension just in case we want to use gen_random_uuid() later
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users
DROP TABLE IF EXISTS Users CASCADE;
CREATE TABLE Users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    phone TEXT,
    telegram_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    is_superadmin BOOLEAN DEFAULT FALSE,
    verification_token TEXT,
    reset_token TEXT,
    reset_token_expires TIMESTAMP
);

-- Networks
DROP TABLE IF EXISTS Networks CASCADE;
CREATE TABLE Networks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Businesses
DROP TABLE IF EXISTS Businesses CASCADE;
CREATE TABLE Businesses (
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
    owner_id TEXT NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    network_id TEXT REFERENCES Networks(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    subscription_tier TEXT DEFAULT 'trial',
    subscription_status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Extra columns
    city TEXT,
    country TEXT,
    timezone TEXT DEFAULT 'UTC',
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    working_hours_json TEXT, -- JSONB candidate in future
    waba_phone_id TEXT,
    waba_access_token TEXT,
    whatsapp_phone TEXT,
    whatsapp_verified BOOLEAN DEFAULT FALSE,
    telegram_bot_token TEXT,
    ai_agent_enabled BOOLEAN DEFAULT FALSE,
    ai_agent_type TEXT,
    ai_agent_id TEXT,
    ai_agent_tone TEXT,
    ai_agent_restrictions TEXT,
    -- Yandex Sync Fields
    -- Yandex Sync Fields
    yandex_org_id TEXT,
    yandex_url TEXT,
    yandex_rating DOUBLE PRECISION,
    yandex_reviews_total INTEGER,
    yandex_reviews_30d INTEGER,
    yandex_last_sync TIMESTAMP,
    
    -- Legacy/ChatGPT Sync Fields
    chatgpt_enabled BOOLEAN DEFAULT FALSE,
    chatgpt_context TEXT,
    chatgpt_api_key TEXT,
    chatgpt_model TEXT,
    ai_agents_config TEXT
    
);
CREATE INDEX IF NOT EXISTS idx_businesses_owner_id ON Businesses(owner_id);
CREATE INDEX IF NOT EXISTS idx_businesses_network_id ON Businesses(network_id);

-- UserSessions
DROP TABLE IF EXISTS UserSessions CASCADE;
CREATE TABLE UserSessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ParseQueue
DROP TABLE IF EXISTS ParseQueue CASCADE;
CREATE TABLE ParseQueue (
    id TEXT PRIMARY KEY,
    url TEXT,
    user_id TEXT NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    business_id TEXT REFERENCES Businesses(id) ON DELETE CASCADE,
    task_type TEXT DEFAULT 'parse_card',
    account_id TEXT,
    source TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_after TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_parsequeue_status ON ParseQueue(status);
CREATE INDEX IF NOT EXISTS idx_parsequeue_business_id ON ParseQueue(business_id);
CREATE INDEX IF NOT EXISTS idx_parsequeue_user_id ON ParseQueue(user_id);
CREATE INDEX IF NOT EXISTS idx_parsequeue_created_at ON ParseQueue(created_at);

-- SyncQueue
DROP TABLE IF EXISTS SyncQueue CASCADE;
CREATE TABLE SyncQueue (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'yandex_business',
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_syncqueue_status ON SyncQueue(status);
CREATE INDEX IF NOT EXISTS idx_syncqueue_business_id ON SyncQueue(business_id);
CREATE INDEX IF NOT EXISTS idx_syncqueue_created_at ON SyncQueue(created_at);

-- ProxyServers
DROP TABLE IF EXISTS ProxyServers CASCADE;
CREATE TABLE ProxyServers (
    id TEXT PRIMARY KEY,
    proxy_type TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    username TEXT,
    password TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    last_checked_at TIMESTAMP,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    is_working BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_proxy_servers_active ON ProxyServers(is_active, is_working);
CREATE INDEX IF NOT EXISTS idx_proxy_servers_last_used ON ProxyServers(last_used_at);

-- MapParseResults
DROP TABLE IF EXISTS MapParseResults CASCADE;
CREATE TABLE MapParseResults (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
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
    is_verified BOOLEAN DEFAULT FALSE -- Added during recent updates
);
CREATE INDEX IF NOT EXISTS idx_map_parse_results_business_id ON MapParseResults(business_id);

-- BusinessMapLinks
DROP TABLE IF EXISTS BusinessMapLinks CASCADE;
CREATE TABLE BusinessMapLinks (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    map_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_business_map_links_business_id ON BusinessMapLinks(business_id);

-- Masters
DROP TABLE IF EXISTS Masters CASCADE;
CREATE TABLE Masters (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    specialization TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FinancialTransactions
DROP TABLE IF EXISTS FinancialTransactions CASCADE;
CREATE TABLE FinancialTransactions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    transaction_date DATE,
    amount DOUBLE PRECISION NOT NULL,
    client_type TEXT,
    services TEXT,
    notes TEXT,
    master_id TEXT REFERENCES Masters(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_financial_transactions_business_id ON FinancialTransactions(business_id);
CREATE INDEX IF NOT EXISTS idx_financial_transactions_date ON FinancialTransactions(transaction_date);

-- FinancialMetrics
DROP TABLE IF EXISTS FinancialMetrics CASCADE;
CREATE TABLE FinancialMetrics (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_revenue DOUBLE PRECISION DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    average_check DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROIData
DROP TABLE IF EXISTS ROIData CASCADE;
CREATE TABLE ROIData (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    investment DOUBLE PRECISION NOT NULL,
    revenue DOUBLE PRECISION NOT NULL,
    roi_percentage DOUBLE PRECISION NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- UserServices
DROP TABLE IF EXISTS UserServices CASCADE;
CREATE TABLE UserServices (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    category TEXT,
    name TEXT NOT NULL,
    description TEXT,
    keywords TEXT,
    price TEXT,
    optimized_name TEXT,
    chatgpt_context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_services_business_id ON UserServices(business_id);

-- UserNews
DROP TABLE IF EXISTS UserNews CASCADE;
CREATE TABLE UserNews (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    service_id TEXT REFERENCES UserServices(id) ON DELETE SET NULL,
    source_text TEXT,
    generated_text TEXT NOT NULL,
    approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_news_user_id ON UserNews(user_id);

-- TelegramBindTokens
DROP TABLE IF EXISTS TelegramBindTokens CASCADE;
CREATE TABLE TelegramBindTokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    business_id TEXT REFERENCES Businesses(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ReviewExchangeParticipants
DROP TABLE IF EXISTS ReviewExchangeParticipants CASCADE;
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
    consent_personal_data BOOLEAN DEFAULT FALSE,
    subscribed_to_channel BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ReviewExchangeDistribution
DROP TABLE IF EXISTS ReviewExchangeDistribution CASCADE;
CREATE TABLE ReviewExchangeDistribution (
    id TEXT PRIMARY KEY,
    sender_participant_id TEXT NOT NULL REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
    receiver_participant_id TEXT NOT NULL REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sender_participant_id, receiver_participant_id)
);

-- ExternalBusinessReviews
DROP TABLE IF EXISTS ExternalBusinessReviews CASCADE;
CREATE TABLE ExternalBusinessReviews (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ext_reviews_business_id ON ExternalBusinessReviews(business_id);
CREATE INDEX IF NOT EXISTS idx_ext_reviews_source ON ExternalBusinessReviews(source);

-- ExternalBusinessPosts
DROP TABLE IF EXISTS ExternalBusinessPosts CASCADE;
CREATE TABLE ExternalBusinessPosts (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    account_id TEXT,
    source TEXT NOT NULL,
    external_post_id TEXT,
    title TEXT,
    text TEXT,
    published_at TIMESTAMP,
    image_url TEXT,
    raw_payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ExternalBusinessPhotos
DROP TABLE IF EXISTS ExternalBusinessPhotos CASCADE;
CREATE TABLE ExternalBusinessPhotos (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    account_id TEXT,
    source TEXT NOT NULL,
    external_photo_id TEXT,
    url TEXT NOT NULL,
    thumbnail_url TEXT,
    uploaded_at TIMESTAMP,
    raw_payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ExternalBusinessStats
DROP TABLE IF EXISTS ExternalBusinessStats CASCADE;
CREATE TABLE ExternalBusinessStats (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    date TEXT NOT NULL, -- Assuming YYYY-MM-DD
    views_total INTEGER,
    clicks_total INTEGER,
    actions_total INTEGER,
    rating DOUBLE PRECISION,
    reviews_total INTEGER,
    unanswered_reviews_count INTEGER,
    raw_payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(business_id, source, date)
);
CREATE INDEX IF NOT EXISTS idx_ext_stats_business_id ON ExternalBusinessStats(business_id);
CREATE INDEX IF NOT EXISTS idx_ext_stats_source ON ExternalBusinessStats(source);
CREATE INDEX IF NOT EXISTS idx_ext_stats_date ON ExternalBusinessStats(date);

-- WordstatKeywords
DROP TABLE IF EXISTS WordstatKeywords CASCADE;
CREATE TABLE WordstatKeywords (
    id TEXT PRIMARY KEY,
    keyword TEXT UNIQUE NOT NULL,
    views INTEGER DEFAULT 0,
    category TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wordstat_views ON WordstatKeywords(views DESC);
CREATE INDEX IF NOT EXISTS idx_wordstat_category ON WordstatKeywords(category);

-- BusinessMetricsHistory
DROP TABLE IF EXISTS BusinessMetricsHistory CASCADE;
CREATE TABLE BusinessMetricsHistory (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id),
    metric_date DATE NOT NULL,
    rating DOUBLE PRECISION,
    reviews_count INTEGER,
    photos_count INTEGER,
    news_count INTEGER,
    unanswered_reviews_count INTEGER,
    source TEXT DEFAULT 'manual',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_metrics_history_business_date ON BusinessMetricsHistory(business_id, metric_date DESC);

-- BusinessOptimizationWizard
DROP TABLE IF EXISTS BusinessOptimizationWizard CASCADE;
CREATE TABLE BusinessOptimizationWizard (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    step INTEGER DEFAULT 1,
    data TEXT,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PricelistOptimizations
DROP TABLE IF EXISTS PricelistOptimizations CASCADE;
CREATE TABLE PricelistOptimizations (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    original_text TEXT,
    optimized_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AIPrompts
DROP TABLE IF EXISTS AIPrompts CASCADE;
CREATE TABLE AIPrompts (
    id TEXT PRIMARY KEY,
    prompt_type TEXT UNIQUE NOT NULL,
    prompt_text TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT REFERENCES Users(id) ON DELETE SET NULL
);

-- AIAgents
DROP TABLE IF EXISTS AIAgents CASCADE;
CREATE TABLE AIAgents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    personality TEXT,
    states_json TEXT, -- JSONB candidate
    workflow TEXT,
    task TEXT,
    identity TEXT,
    speech_style TEXT,
    restrictions_json TEXT,
    variables_json TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
