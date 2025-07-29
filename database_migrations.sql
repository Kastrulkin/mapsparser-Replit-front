-- Добавление полей для ИИ-анализа в таблицу Cards
ALTER TABLE "Cards" 
ADD COLUMN IF NOT EXISTS "ai_analysis" jsonb,
ADD COLUMN IF NOT EXISTS "seo_score" integer,
ADD COLUMN IF NOT EXISTS "recommendations" text[],
ADD COLUMN IF NOT EXISTS "report_path" text;

-- Добавление индекса для быстрого поиска по seo_score
CREATE INDEX IF NOT EXISTS "idx_cards_seo_score" ON "Cards" ("seo_score");

-- Добавление индекса для поиска записей без анализа
CREATE INDEX IF NOT EXISTS "idx_cards_ai_analysis_null" ON "Cards" ("id") WHERE "ai_analysis" IS NULL; 