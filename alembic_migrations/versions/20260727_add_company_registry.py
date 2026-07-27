"""add canonical company registry

Revision ID: 20260727_001
Revises: 20260724_001
Create Date: 2026-07-27
"""

from alembic import op


revision = "20260727_001"
down_revision = "20260724_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            canonical_name TEXT NOT NULL,
            legal_name TEXT,
            primary_category TEXT,
            status TEXT NOT NULL DEFAULT 'observed',
            first_seen_source TEXT NOT NULL DEFAULT 'unknown',
            merged_into_company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_companies_status CHECK (status IN ('observed', 'active', 'merged', 'archived')),
            CONSTRAINT ck_companies_merge_target CHECK (merged_into_company_id IS NULL OR merged_into_company_id <> id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_companies_name ON companies (LOWER(canonical_name))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_companies_status_updated ON companies (status, updated_at DESC)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_locations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            display_name TEXT,
            address TEXT,
            city TEXT,
            region TEXT,
            country TEXT,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            timezone TEXT,
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            status TEXT NOT NULL DEFAULT 'active',
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_company_locations_status CHECK (status IN ('active', 'merged', 'archived'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_company_locations_company ON company_locations (company_id, is_primary DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_company_locations_city ON company_locations (LOWER(city))")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_company_primary_location
        ON company_locations (company_id) WHERE is_primary IS TRUE AND status = 'active'
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_external_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_location_id UUID NOT NULL REFERENCES company_locations(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            external_id TEXT,
            canonical_url TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            sync_status TEXT NOT NULL DEFAULT 'idle',
            last_collected_at TIMESTAMPTZ,
            next_sync_at TIMESTAMPTZ,
            last_sync_error TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_company_external_profiles_status CHECK (status IN ('active', 'paused', 'archived')),
            CONSTRAINT ck_company_external_profiles_identity CHECK (
                NULLIF(TRIM(COALESCE(external_id, '')), '') IS NOT NULL
                OR NULLIF(TRIM(COALESCE(canonical_url, '')), '') IS NOT NULL
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_company_external_profile_id
        ON company_external_profiles (provider, external_id)
        WHERE external_id IS NOT NULL AND status <> 'archived'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_company_external_profile_url
        ON company_external_profiles (provider, canonical_url)
        WHERE canonical_url IS NOT NULL AND status <> 'archived'
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_identity_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            company_location_id UUID REFERENCES company_locations(id) ON DELETE CASCADE,
            key_type TEXT NOT NULL,
            normalized_value TEXT NOT NULL,
            source_url TEXT,
            confidence NUMERIC(5,4) NOT NULL DEFAULT 1,
            verification_status TEXT NOT NULL DEFAULT 'observed',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_company_identity_confidence CHECK (confidence BETWEEN 0 AND 1),
            CONSTRAINT ck_company_identity_status CHECK (verification_status IN ('observed', 'verified', 'rejected'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_company_identity_lookup ON company_identity_keys (key_type, normalized_value)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_company_identity_verified
        ON company_identity_keys (key_type, normalized_value)
        WHERE verification_status = 'verified'
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS business_company_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            company_location_id UUID REFERENCES company_locations(id) ON DELETE SET NULL,
            relation_role TEXT NOT NULL DEFAULT 'owner',
            is_primary BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_business_company_role CHECK (relation_role IN ('owner', 'operator', 'agency'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_business_company_links_company ON business_company_links (company_id, business_id)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_business_company_location_link
        ON business_company_links (business_id, company_id, company_location_id)
        WHERE company_location_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_business_company_without_location_link
        ON business_company_links (business_id, company_id)
        WHERE company_location_id IS NULL
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_contact_points (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            company_location_id UUID REFERENCES company_locations(id) ON DELETE CASCADE,
            contact_type TEXT NOT NULL,
            value TEXT NOT NULL,
            normalized_value TEXT NOT NULL,
            source_url TEXT,
            confidence NUMERIC(5,4) NOT NULL DEFAULT 0.5,
            verification_status TEXT NOT NULL DEFAULT 'observed',
            observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            verified_at TIMESTAMPTZ,
            invalidated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_company_contact_confidence CHECK (confidence BETWEEN 0 AND 1),
            CONSTRAINT ck_company_contact_status CHECK (verification_status IN ('observed', 'verified', 'rejected'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_company_contacts_lookup ON company_contact_points (contact_type, normalized_value)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_observations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            company_location_id UUID REFERENCES company_locations(id) ON DELETE CASCADE,
            predicate TEXT NOT NULL,
            value_json JSONB NOT NULL,
            source_type TEXT NOT NULL,
            source_url TEXT,
            evidence_id UUID REFERENCES knowledge_evidence(id) ON DELETE SET NULL,
            confidence NUMERIC(5,4) NOT NULL DEFAULT 0.5,
            status TEXT NOT NULL DEFAULT 'observed',
            observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            confirmed_at TIMESTAMPTZ,
            invalidated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_company_observation_confidence CHECK (confidence BETWEEN 0 AND 1),
            CONSTRAINT ck_company_observation_status CHECK (status IN ('observed', 'confirmed', 'stale', 'rejected'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_company_observations_company ON company_observations (company_id, predicate, observed_at DESC)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_social_source_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            company_location_id UUID REFERENCES company_locations(id) ON DELETE SET NULL,
            source_id UUID NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
            relation_type TEXT NOT NULL DEFAULT 'unconfirmed',
            confidence NUMERIC(5,4) NOT NULL DEFAULT 0.5,
            verification_status TEXT NOT NULL DEFAULT 'observed',
            evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_company_social_relation CHECK (relation_type IN ('official', 'brand_channel', 'expert_of_company', 'mentioned_in', 'unconfirmed')),
            CONSTRAINT ck_company_social_confidence CHECK (confidence BETWEEN 0 AND 1),
            UNIQUE (company_id, source_id, relation_type)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_relationships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            subject_company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            object_company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            context_business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            relationship_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'observed',
            source_url TEXT,
            confidence NUMERIC(5,4) NOT NULL DEFAULT 0.5,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_company_relationship_type CHECK (relationship_type IN ('competitor', 'supplier', 'partner')),
            CONSTRAINT ck_company_relationship_context CHECK (relationship_type <> 'partner' OR context_business_id IS NOT NULL),
            CONSTRAINT ck_company_relationship_distinct CHECK (subject_company_id <> object_company_id)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_company_relationship_context
        ON company_relationships (subject_company_id, object_company_id, context_business_id, relationship_type)
        WHERE context_business_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_company_relationship_global
        ON company_relationships (subject_company_id, object_company_id, relationship_type)
        WHERE context_business_id IS NULL
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_merge_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_company_id UUID NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
            target_company_id UUID NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
            status TEXT NOT NULL DEFAULT 'preview',
            reason TEXT NOT NULL,
            evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            idempotency_key TEXT NOT NULL UNIQUE,
            created_by TEXT,
            expires_at TIMESTAMPTZ NOT NULL,
            confirmed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_company_merge_status CHECK (status IN ('preview', 'confirmed', 'expired', 'reverted')),
            CONSTRAINT ck_company_merge_distinct CHECK (source_company_id <> target_company_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_source_subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            source_id UUID NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
            purposes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            topics_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            schedule_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (business_id, source_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_public_services (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_location_id UUID NOT NULL REFERENCES company_locations(id) ON DELETE CASCADE,
            external_profile_id UUID REFERENCES company_external_profiles(id) ON DELETE SET NULL,
            external_id TEXT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            price_text TEXT,
            source_url TEXT,
            observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            invalidated_at TIMESTAMPTZ,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_company_public_services_location ON company_public_services (company_location_id, observed_at DESC)")

    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS company_location_id UUID REFERENCES company_locations(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE parsequeue ADD COLUMN IF NOT EXISTS company_location_id UUID REFERENCES company_locations(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE parsequeue ADD COLUMN IF NOT EXISTS external_profile_id UUID REFERENCES company_external_profiles(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE parsequeue ADD COLUMN IF NOT EXISTS requested_by_business_id TEXT REFERENCES businesses(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE parsequeue ADD COLUMN IF NOT EXISTS force_refresh BOOLEAN NOT NULL DEFAULT FALSE")
    for table_name in ("cards", "externalbusinessreviews", "externalbusinessposts", "externalbusinessphotos", "externalbusinessstats", "businessmetricshistory"):
        op.execute(
            f"""
            DO $$ BEGIN
                IF to_regclass('public.{table_name}') IS NOT NULL THEN
                    ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS company_location_id UUID REFERENCES company_locations(id) ON DELETE SET NULL;
                    ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS external_profile_id UUID REFERENCES company_external_profiles(id) ON DELETE SET NULL;
                END IF;
            END $$
            """
        )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION localos_fill_company_location_context()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.company_location_id IS NULL AND NEW.business_id IS NOT NULL THEN
                SELECT link.company_location_id INTO NEW.company_location_id
                FROM business_company_links link
                WHERE link.business_id = NEW.business_id
                ORDER BY link.is_primary DESC, link.created_at ASC
                LIMIT 1;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table_name in ("parsequeue", "cards", "externalbusinessreviews", "externalbusinessposts", "externalbusinessphotos", "externalbusinessstats", "businessmetricshistory"):
        op.execute(
            f"""
            DO $$ BEGIN
                IF to_regclass('public.{table_name}') IS NOT NULL THEN
                    DROP TRIGGER IF EXISTS trg_{table_name}_company_context ON {table_name};
                    CREATE TRIGGER trg_{table_name}_company_context
                    BEFORE INSERT OR UPDATE ON {table_name}
                    FOR EACH ROW EXECUTE FUNCTION localos_fill_company_location_context();
                END IF;
            END $$
            """
        )
    op.execute(
        """
        DO $$ BEGIN
            IF to_regclass('public.partnership_partner_cards') IS NOT NULL THEN
                ALTER TABLE partnership_partner_cards ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE SET NULL;
                ALTER TABLE partnership_partner_cards ADD COLUMN IF NOT EXISTS company_location_id UUID REFERENCES company_locations(id) ON DELETE SET NULL;
            END IF;
        END $$
        """
    )
    for audit_table in ("adminprospectingleadpublicoffers", "sales_room_audit_offers"):
        op.execute(
            f"""
            DO $$ BEGIN
                IF to_regclass('public.{audit_table}') IS NOT NULL THEN
                    ALTER TABLE {audit_table} ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE SET NULL;
                    ALTER TABLE {audit_table} ADD COLUMN IF NOT EXISTS company_location_id UUID REFERENCES company_locations(id) ON DELETE SET NULL;
                    ALTER TABLE {audit_table} ADD COLUMN IF NOT EXISTS audit_context TEXT NOT NULL DEFAULT 'public';
                    ALTER TABLE {audit_table} ADD COLUMN IF NOT EXISTS context_business_id TEXT REFERENCES businesses(id) ON DELETE SET NULL;
                END IF;
            END $$
            """
        )


def downgrade():
    for table_name in ("businessmetricshistory", "externalbusinessstats", "externalbusinessphotos", "externalbusinessposts", "externalbusinessreviews", "cards", "parsequeue"):
        op.execute(
            f"""
            DO $$ BEGIN
                IF to_regclass('public.{table_name}') IS NOT NULL THEN
                    DROP TRIGGER IF EXISTS trg_{table_name}_company_context ON {table_name};
                END IF;
            END $$
            """
        )
    op.execute("DROP FUNCTION IF EXISTS localos_fill_company_location_context()")
    for audit_table in ("sales_room_audit_offers", "adminprospectingleadpublicoffers"):
        op.execute(
            f"""
            DO $$ BEGIN
                IF to_regclass('public.{audit_table}') IS NOT NULL THEN
                    ALTER TABLE {audit_table} DROP COLUMN IF EXISTS context_business_id;
                    ALTER TABLE {audit_table} DROP COLUMN IF EXISTS audit_context;
                    ALTER TABLE {audit_table} DROP COLUMN IF EXISTS company_location_id;
                    ALTER TABLE {audit_table} DROP COLUMN IF EXISTS company_id;
                END IF;
            END $$
            """
        )
    op.execute(
        """
        DO $$ BEGIN
            IF to_regclass('public.partnership_partner_cards') IS NOT NULL THEN
                ALTER TABLE partnership_partner_cards DROP COLUMN IF EXISTS company_location_id;
                ALTER TABLE partnership_partner_cards DROP COLUMN IF EXISTS company_id;
            END IF;
        END $$
        """
    )
    for table_name in ("businessmetricshistory", "externalbusinessstats", "externalbusinessphotos", "externalbusinessposts", "externalbusinessreviews", "cards"):
        op.execute(
            f"""
            DO $$ BEGIN
                IF to_regclass('public.{table_name}') IS NOT NULL THEN
                    ALTER TABLE {table_name} DROP COLUMN IF EXISTS external_profile_id;
                    ALTER TABLE {table_name} DROP COLUMN IF EXISTS company_location_id;
                END IF;
            END $$
            """
        )
    op.execute("ALTER TABLE parsequeue DROP COLUMN IF EXISTS external_profile_id")
    op.execute("ALTER TABLE parsequeue DROP COLUMN IF EXISTS company_location_id")
    op.execute("ALTER TABLE parsequeue DROP COLUMN IF EXISTS force_refresh")
    op.execute("ALTER TABLE parsequeue DROP COLUMN IF EXISTS requested_by_business_id")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS company_location_id")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS company_id")
    op.execute("DROP TABLE IF EXISTS company_public_services")
    op.execute("DROP TABLE IF EXISTS knowledge_source_subscriptions")
    op.execute("DROP TABLE IF EXISTS company_merge_events")
    op.execute("DROP TABLE IF EXISTS company_relationships")
    op.execute("DROP TABLE IF EXISTS company_social_source_links")
    op.execute("DROP TABLE IF EXISTS company_observations")
    op.execute("DROP TABLE IF EXISTS company_contact_points")
    op.execute("DROP TABLE IF EXISTS business_company_links")
    op.execute("DROP TABLE IF EXISTS company_identity_keys")
    op.execute("DROP TABLE IF EXISTS company_external_profiles")
    op.execute("DROP TABLE IF EXISTS company_locations")
    op.execute("DROP TABLE IF EXISTS companies")
