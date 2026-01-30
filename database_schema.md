# Database Schema

This document serves as the source of truth for the BeautyBot database schema. It is based on the PostgreSQL migration schema definitions (`src/schema_postgres.sql`).

## Tables

### Users
Stores user authentication and profile information.
- `id` (TEXT, PK): Unique user identifier.
- `email` (TEXT, UNIQUE): User email address.
- `password_hash` (TEXT): Hashed password.
- `name` (TEXT): User's full name.
- `phone` (TEXT): Contact phone number.
- `telegram_id` (TEXT): Telegram user ID.
- `is_active` (BOOLEAN): Whether the account is active.
- `is_verified` (BOOLEAN): Email verification status.
- `is_superadmin` (BOOLEAN): Administrative privileges.
- `verification_token` (TEXT): Token for email verification.
- `reset_token` (TEXT): Token for password reset.
- `reset_token_expires` (TIMESTAMP): Expiry for reset token.
- `created_at`, `updated_at`: Timestamps.

### Networks
Groups multiple businesses under a single owner.
- `id` (TEXT, PK)
- `name` (TEXT)
- `owner_id` (TEXT, FK -> Users.id)
- `description` (TEXT)
- `created_at`, `updated_at`

### Businesses
Represents individual beauty salons or service providers.
*Primary entity for most operations.*
- `id` (TEXT, PK)
- `name` (TEXT)
- `owner_id` (TEXT, FK -> Users.id)
- `network_id` (TEXT, FK -> Networks.id, NULLABLE)
- `description`, `industry`, `business_type`, `address`, `working_hours`, `phone`, `email`, `website`
- `is_active` (BOOLEAN)
- `subscription_tier` (TEXT): 'trial', 'basic', 'pro', etc.
- `subscription_status` (TEXT): 'active', 'expired', etc.
- **Location**: `city`, `country`, `timezone`, `latitude`, `longitude`
- **Integrations**:
    - WhatsApp: `waba_phone_id`, `waba_access_token`, `whatsapp_phone`, `whatsapp_verified`
    - Telegram: `telegram_bot_token`
    - AI Agent: `ai_agent_enabled`, `ai_agent_type`, `ai_agent_id`, `ai_agent_tone`, `ai_agent_restrictions`, `ai_agent_language`
    - Yandex: `yandex_org_id`, `yandex_url`, `yandex_rating`, `yandex_reviews_total`, `yandex_reviews_30d`, `yandex_last_sync`
    - **Legacy/Deprecated**: `chatgpt_enabled`, `chatgpt_context`, `ai_agents_config`

### UserSessions
Active user sessions / JWT tokens.
- `id` (TEXT, PK)
- `user_id` (TEXT, FK -> Users.id)
- `token` (TEXT, UNIQUE)
- `expires_at` (TIMESTAMP)

### UserServices
Services offered by a business.
- `id` (TEXT, PK)
- `business_id` (TEXT, FK -> Businesses.id)
- `name` (TEXT)
- `category` (TEXT)
- `price` (TEXT)
- `description`, `keywords`
- `optimized_name` (TEXT): AI-optimized name for SEO.
- `chatgpt_context` (TEXT): Context for AI generation.

### Masters
Employees or specialists working at a business.
- `id` (TEXT, PK)
- `business_id` (TEXT, FK -> Businesses.id)
- `name` (TEXT)
- `specialization` (TEXT)

### ParseQueue
Queue for background parsing tasks (e.g., parsing a Yandex Maps card).
- `id` (TEXT, PK)
- `user_id` (TEXT, FK -> Users.id)
- `business_id` (TEXT, FK -> Businesses.id)
- `url` (TEXT)
- `status` (TEXT): 'pending', 'processing', 'completed', 'failed'
- `task_type` (TEXT)

### SyncQueue
Queue for synchronization tasks (Yandex Business, Google, 2GIS).
- `id` (TEXT, PK)
- `business_id` (TEXT, FK -> Businesses.id)
- `source` (TEXT): e.g., 'yandex_business'
- `status` (TEXT)

### MapParseResults
Cached results of map parsing.
- `id` (TEXT, PK)
- `business_id` (TEXT, FK -> Businesses.id)
- `rating`, `reviews_count`, `news_count`, `photos_count`
- `products` (TEXT): JSON string of parsed products/services.
- `is_verified` (BOOLEAN)

### External Data Tables
Captured data from external platforms (Yandex, Google, 2GIS).
- **ExternalBusinessReviews**: Reviews text, rating, author, response status.
- **ExternalBusinessStats**: Daily statistics (views, clicks, actions).
- **ExternalBusinessPosts**: News posts/updates.
- **ExternalBusinessPhotos**: Business photos.
- **ExternalBusinessAccounts**: Auth data (cookies/tokens) for syncing.

### Financial Tables
- **FinancialTransactions**: Records of sales/services rendered.
- **FinancialMetrics**: Aggregated financial metrics.
- **ROIData**: Return on Investment calculations.

### Other Tables
- **ProxyServers**: Rotation pool for parsers.
- **BusinessMapLinks**: Links to business on different maps.
- **WordstatKeywords**: cached SEO keywords.
- **BusinessMetricsHistory**: Snapshots of business metrics over time.
- **TelegramBindTokens**: Tokens for linking Telegram accounts.
- **ReviewExchange* **: Tables for cross-promotion review system.
- **AIPrompts**: System prompts for AI generation features.
- **AIAgents**: Configuration for AI agents.

## Relationships
- **Users** 1:N **Businesses** (via `owner_id`)
- **Networks** 1:N **Businesses** (via `network_id`)
- **Businesses** 1:N **UserServices**
- **Businesses** 1:N **Masters**
- **Businesses** 1:N **ExternalBusinessReviews**
