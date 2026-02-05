-- Миграция: Добавление таблиц для парсера и обновление mapparseresults
-- Дата: 2026-02-03

-- 1. Обновление mapparseresults
ALTER TABLE mapparseresults 
ADD COLUMN IF NOT EXISTS parse_status TEXT,
ADD COLUMN IF NOT EXISTS missing_sections JSONB,
ADD COLUMN IF NOT EXISTS parsed_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS oid TEXT,
ADD COLUMN IF NOT EXISTS stats JSONB;

-- 2. Таблица для услуг бизнеса
CREATE TABLE IF NOT EXISTS business_services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    oid TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price TEXT,
    currency TEXT DEFAULT '₽',
    photo TEXT,
    is_top BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(business_id, oid, category, title)
);

CREATE INDEX IF NOT EXISTS idx_business_services_business_id ON business_services(business_id);
CREATE INDEX IF NOT EXISTS idx_business_services_oid ON business_services(oid);

-- 3. Таблица для новостей бизнеса
CREATE TABLE IF NOT EXISTS business_news (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    oid TEXT NOT NULL,
    post_id TEXT NOT NULL,
    text TEXT,
    content_short TEXT,
    publication_time TIMESTAMPTZ,
    photos JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(post_id)
);

CREATE INDEX IF NOT EXISTS idx_business_news_business_id ON business_news(business_id);
CREATE INDEX IF NOT EXISTS idx_business_news_oid ON business_news(oid);
CREATE INDEX IF NOT EXISTS idx_business_news_post_id ON business_news(post_id);

-- 4. Таблица для отзывов бизнеса
CREATE TABLE IF NOT EXISTS business_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    oid TEXT NOT NULL,
    review_id TEXT NOT NULL,
    author_name TEXT,
    author_public_id TEXT,
    rating TEXT,
    text TEXT,
    updated_time TIMESTAMPTZ,
    likes INTEGER DEFAULT 0,
    dislikes INTEGER DEFAULT 0,
    business_comment_text TEXT,
    business_comment_time TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(review_id)
);

CREATE INDEX IF NOT EXISTS idx_business_reviews_business_id ON business_reviews(business_id);
CREATE INDEX IF NOT EXISTS idx_business_reviews_oid ON business_reviews(oid);
CREATE INDEX IF NOT EXISTS idx_business_reviews_review_id ON business_reviews(review_id);
