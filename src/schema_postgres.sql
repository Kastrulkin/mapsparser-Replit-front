-- PostgreSQL Schema for BeautyBot
-- Generated based on init_database_schema.py

-- Enable UUID extension just in case we want to use gen_random_uuid() later
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users
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
    is_superadmin BOOLEAN DEFAULT FALSE
);

-- Networks
CREATE TABLE Networks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Businesses
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
    ai_agent_language TEXT DEFAULT 'en'
    
);
CREATE INDEX idx_businesses_owner_id ON Businesses(owner_id);
CREATE INDEX idx_businesses_network_id ON Businesses(network_id);

-- UserSessions
CREATE TABLE UserSessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ParseQueue
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
CREATE INDEX idx_parsequeue_status ON ParseQueue(status);
CREATE INDEX idx_parsequeue_business_id ON ParseQueue(business_id);
CREATE INDEX idx_parsequeue_user_id ON ParseQueue(user_id);
CREATE INDEX idx_parsequeue_created_at ON ParseQueue(created_at);

-- SyncQueue
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
CREATE INDEX idx_syncqueue_status ON SyncQueue(status);
CREATE INDEX idx_syncqueue_business_id ON SyncQueue(business_id);
CREATE INDEX idx_syncqueue_created_at ON SyncQueue(created_at);

-- ProxyServers
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
CREATE INDEX idx_proxy_servers_active ON ProxyServers(is_active, is_working);
CREATE INDEX idx_proxy_servers_last_used ON ProxyServers(last_used_at);

-- MapParseResults
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
CREATE INDEX idx_map_parse_results_business_id ON MapParseResults(business_id);

-- BusinessMapLinks
CREATE TABLE BusinessMapLinks (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    map_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_business_map_links_business_id ON BusinessMapLinks(business_id);

-- Masters
CREATE TABLE Masters (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    specialization TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FinancialTransactions
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
CREATE INDEX idx_financial_transactions_business_id ON FinancialTransactions(business_id);
CREATE INDEX idx_financial_transactions_date ON FinancialTransactions(transaction_date);

-- FinancialMetrics
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
CREATE TABLE UserServices (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    category TEXT,
    name TEXT NOT NULL,
    description TEXT,
    keywords TEXT,
    price TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_user_services_business_id ON UserServices(business_id);

-- UserNews
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
CREATE INDEX idx_user_news_user_id ON UserNews(user_id);

-- TelegramBindTokens
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
CREATE TABLE ReviewExchangeDistribution (
    id TEXT PRIMARY KEY,
    sender_participant_id TEXT NOT NULL REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
    receiver_participant_id TEXT NOT NULL REFERENCES ReviewExchangeParticipants(id) ON DELETE CASCADE,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sender_participant_id, receiver_participant_id)
);

-- ExternalBusinessReviews
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
CREATE INDEX idx_ext_reviews_business_id ON ExternalBusinessReviews(business_id);
CREATE INDEX idx_ext_reviews_source ON ExternalBusinessReviews(source);

-- ExternalBusinessPosts
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
CREATE INDEX idx_ext_stats_business_id ON ExternalBusinessStats(business_id);
CREATE INDEX idx_ext_stats_source ON ExternalBusinessStats(source);
CREATE INDEX idx_ext_stats_date ON ExternalBusinessStats(date);

-- WordstatKeywords
CREATE TABLE WordstatKeywords (
    id TEXT PRIMARY KEY,
    keyword TEXT UNIQUE NOT NULL,
    views INTEGER DEFAULT 0,
    category TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_wordstat_views ON WordstatKeywords(views DESC);
CREATE INDEX idx_wordstat_category ON WordstatKeywords(category);

-- BusinessMetricsHistory
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
CREATE INDEX idx_metrics_history_business_date ON BusinessMetricsHistory(business_id, metric_date DESC);

-- BusinessOptimizationWizard
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
CREATE TABLE PricelistOptimizations (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL REFERENCES Businesses(id) ON DELETE CASCADE,
    original_text TEXT,
    optimized_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AIPrompts
CREATE TABLE AIPrompts (
    id TEXT PRIMARY KEY,
    prompt_type TEXT UNIQUE NOT NULL,
    prompt_text TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT REFERENCES Users(id) ON DELETE SET NULL
);

-- AIAgents
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
