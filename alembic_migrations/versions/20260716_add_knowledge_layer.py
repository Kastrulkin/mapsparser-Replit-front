"""add evidence-based knowledge layer

Revision ID: 20260716_001
Revises: 20260715_002
Create Date: 2026-07-16 09:00:00.000000
"""

from alembic import op


revision = "20260716_001"
down_revision = "20260715_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id UUID PRIMARY KEY,
            source_type TEXT NOT NULL,
            external_key TEXT NOT NULL,
            title TEXT NOT NULL,
            canonical_url TEXT,
            source_role TEXT NOT NULL DEFAULT 'unknown',
            visibility TEXT NOT NULL DEFAULT 'public',
            sensitivity_class TEXT NOT NULL DEFAULT 'public',
            pii_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
            allowed_uses JSONB NOT NULL DEFAULT '[]'::jsonb,
            status TEXT NOT NULL DEFAULT 'candidate',
            cursor_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            last_collected_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_sources_role CHECK (
                source_role IN ('expert', 'salon', 'vendor', 'community', 'service', 'competitor', 'unknown')
            ),
            CONSTRAINT ck_knowledge_sources_visibility CHECK (
                visibility IN ('public', 'private', 'invite', 'internal')
            ),
            CONSTRAINT ck_knowledge_sources_sensitivity CHECK (
                sensitivity_class IN ('public', 'internal', 'tenant_confidential', 'personal_data', 'shared_deidentified')
            ),
            CONSTRAINT ck_knowledge_sources_status CHECK (status IN ('candidate', 'active', 'paused'))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_sources_external
        ON knowledge_sources(source_type, external_key)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_documents (
            id UUID PRIMARY KEY,
            source_id UUID NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            external_id TEXT NOT NULL,
            document_type TEXT NOT NULL,
            title TEXT,
            content_text TEXT NOT NULL,
            permalink TEXT,
            published_at TIMESTAMPTZ,
            content_hash TEXT NOT NULL,
            sensitivity_class TEXT NOT NULL DEFAULT 'public',
            pii_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
            allowed_uses JSONB NOT NULL DEFAULT '[]'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            invalidated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_documents_sensitivity CHECK (
                sensitivity_class IN ('public', 'internal', 'tenant_confidential', 'personal_data', 'shared_deidentified')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_documents_source_external
        ON knowledge_documents(source_id, external_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_documents_hash
        ON knowledge_documents(content_hash, invalidated_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_documents_business
        ON knowledge_documents(business_id, document_type, published_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_analysis_runs (
            id UUID PRIMARY KEY,
            run_type TEXT NOT NULL,
            analysis_version TEXT NOT NULL,
            model TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            source_id UUID REFERENCES knowledge_sources(id) ON DELETE SET NULL,
            document_count INTEGER NOT NULL DEFAULT 0,
            processed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            token_budget INTEGER,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            transmitted_classes JSONB NOT NULL DEFAULT '[]'::jsonb,
            error_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_analysis_runs_status CHECK (
                status IN ('queued', 'running', 'completed', 'partial', 'failed', 'blocked')
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_analysis_runs_created
        ON knowledge_analysis_runs(status, created_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_document_analyses (
            id UUID PRIMARY KEY,
            document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
            analysis_run_id UUID REFERENCES knowledge_analysis_runs(id) ON DELETE SET NULL,
            content_hash TEXT NOT NULL,
            analysis_version TEXT NOT NULL,
            analyzer_kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            facets_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            summary_text TEXT,
            confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
            limitations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            raw_result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_document_analysis_confidence CHECK (confidence BETWEEN 0 AND 1),
            CONSTRAINT ck_knowledge_document_analysis_status CHECK (
                status IN ('completed', 'partial', 'failed', 'blocked')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_document_analysis_version
        ON knowledge_document_analyses(document_id, content_hash, analysis_version, analyzer_kind)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_concepts (
            id UUID PRIMARY KEY,
            concept_type TEXT NOT NULL,
            canonical_key TEXT NOT NULL,
            label TEXT NOT NULL,
            industry TEXT,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            sensitivity_class TEXT NOT NULL DEFAULT 'public',
            allowed_uses JSONB NOT NULL DEFAULT '[]'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_concepts_type CHECK (
                concept_type IN (
                    'topic', 'pain', 'segment', 'service', 'format', 'sales_angle',
                    'cta', 'intervention', 'capability', 'metric', 'search_intent',
                    'objection', 'practice', 'offer', 'audience_language', 'market_signal'
                )
            ),
            CONSTRAINT ck_knowledge_concepts_sensitivity CHECK (
                sensitivity_class IN ('public', 'internal', 'tenant_confidential', 'personal_data', 'shared_deidentified')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_concepts_scope
        ON knowledge_concepts(concept_type, canonical_key, COALESCE(industry, ''), COALESCE(business_id, ''))
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_assertions (
            id UUID PRIMARY KEY,
            assertion_type TEXT NOT NULL,
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_id TEXT NOT NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            industry TEXT,
            confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
            allowed_uses JSONB NOT NULL DEFAULT '[]'::jsonb,
            sensitivity_class TEXT NOT NULL DEFAULT 'public',
            analysis_version TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            invalidated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_assertions_confidence CHECK (confidence BETWEEN 0 AND 1),
            CONSTRAINT ck_knowledge_assertions_sensitivity CHECK (
                sensitivity_class IN ('public', 'internal', 'tenant_confidential', 'personal_data', 'shared_deidentified')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_assertions_active
        ON knowledge_assertions(
            assertion_type, subject_type, subject_id, predicate, object_type, object_id,
            COALESCE(business_id, ''), COALESCE(analysis_version, '')
        ) WHERE invalidated_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_assertions_lookup
        ON knowledge_assertions(industry, predicate, confidence DESC, created_at DESC)
        WHERE invalidated_at IS NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_claims (
            id UUID PRIMARY KEY,
            claim_type TEXT NOT NULL,
            title TEXT NOT NULL,
            statement_text TEXT NOT NULL,
            industry TEXT,
            segment TEXT,
            evidence_level TEXT NOT NULL DEFAULT 'insufficient_evidence',
            sample_businesses INTEGER NOT NULL DEFAULT 0,
            evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            limitations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            sensitivity_class TEXT NOT NULL DEFAULT 'internal',
            privacy_status TEXT NOT NULL DEFAULT 'draft',
            status TEXT NOT NULL DEFAULT 'candidate',
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            invalidated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_learning_claims_evidence_level CHECK (
                evidence_level IN ('observed_after', 'associated_with', 'likely_contributed', 'causal_evidence', 'insufficient_evidence')
            ),
            CONSTRAINT ck_learning_claims_privacy_status CHECK (
                privacy_status IN ('draft', 'pending_review', 'approved', 'rejected')
            ),
            CONSTRAINT ck_learning_claims_status CHECK (status IN ('candidate', 'active', 'invalidated'))
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_evidence (
            id UUID PRIMARY KEY,
            assertion_id UUID REFERENCES knowledge_assertions(id) ON DELETE CASCADE,
            claim_id UUID REFERENCES learning_claims(id) ON DELETE CASCADE,
            document_id UUID REFERENCES knowledge_documents(id) ON DELETE SET NULL,
            source_id UUID REFERENCES knowledge_sources(id) ON DELETE SET NULL,
            excerpt TEXT,
            observed_at TIMESTAMPTZ,
            confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
            analysis_version TEXT,
            allowed_uses JSONB NOT NULL DEFAULT '[]'::jsonb,
            sensitivity_class TEXT NOT NULL DEFAULT 'public',
            pii_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
            invalidated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_evidence_owner CHECK (
                (assertion_id IS NOT NULL AND claim_id IS NULL)
                OR (assertion_id IS NULL AND claim_id IS NOT NULL)
            ),
            CONSTRAINT ck_knowledge_evidence_confidence CHECK (confidence BETWEEN 0 AND 1)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_evidence_assertion
        ON knowledge_evidence(assertion_id, invalidated_at)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_evidence_origin
        ON knowledge_evidence(assertion_id, document_id, source_id, COALESCE(analysis_version, ''))
        WHERE invalidated_at IS NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS business_action_events (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            action_type TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed',
            hypothesis_id UUID REFERENCES knowledge_assertions(id) ON DELETE SET NULL,
            approval_id TEXT,
            before_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            after_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            limitations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            evaluation_window_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_business_action_events_status CHECK (
                status IN ('confirmed', 'external_change_detected', 'reverted', 'superseded')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_business_action_events_source
        ON business_action_events(business_id, action_type, source_type, source_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_business_action_events_business
        ON business_action_events(business_id, occurred_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS privacy_release_reviews (
            id UUID PRIMARY KEY,
            claim_id UUID NOT NULL REFERENCES learning_claims(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'pending',
            reviewer_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            redacted_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            decision_reason TEXT,
            reviewed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_privacy_release_reviews_status CHECK (
                status IN ('pending', 'approved', 'rejected')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_privacy_release_reviews_pending
        ON privacy_release_reviews(claim_id) WHERE status = 'pending'
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW knowledge_nodes_v AS
        SELECT 'source'::text AS node_type, id::text AS node_id, title AS label,
               NULL::text AS business_id, sensitivity_class, metadata_json
        FROM knowledge_sources
        UNION ALL
        SELECT 'document', id::text, COALESCE(NULLIF(title, ''), document_type), business_id,
               sensitivity_class, metadata_json
        FROM knowledge_documents
        WHERE invalidated_at IS NULL
        UNION ALL
        SELECT 'concept', id::text, label, business_id, sensitivity_class, metadata_json
        FROM knowledge_concepts
        UNION ALL
        SELECT 'claim', id::text, title, NULL::text, sensitivity_class, metadata_json
        FROM learning_claims
        WHERE invalidated_at IS NULL
        UNION ALL
        SELECT 'action', id::text, action_type, business_id, 'tenant_confidential', metadata_json
        FROM business_action_events
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW knowledge_edges_v AS
        SELECT id::text AS edge_id, subject_type, subject_id, predicate,
               object_type, object_id, business_id, confidence, sensitivity_class,
               allowed_uses, created_at
        FROM knowledge_assertions
        WHERE invalidated_at IS NULL
        UNION ALL
        SELECT ('source-document:' || d.id::text), 'source', d.source_id::text, 'PROVIDES',
               'document', d.id::text, d.business_id, 1::numeric, d.sensitivity_class,
               d.allowed_uses, d.created_at
        FROM knowledge_documents d
        WHERE d.invalidated_at IS NULL
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW metric_observations_v AS
        SELECT ('card-seo:' || c.id)::text AS observation_id, c.business_id,
               'map_seo_score'::text AS metric_name, c.seo_score::numeric AS metric_value,
               COALESCE(c.updated_at, c.created_at)::timestamptz AS observed_at,
               'cards'::text AS source_type, c.id::text AS source_id
        FROM cards c
        WHERE COALESCE(c.is_latest, TRUE) AND c.seo_score IS NOT NULL
        UNION ALL
        SELECT ('external-views:' || s.id), s.business_id, 'map_views', s.views_total::numeric,
               CASE WHEN s.date ~ '^\\d{4}-\\d{2}-\\d{2}$' THEN s.date::date::timestamptz ELSE s.updated_at::timestamptz END,
               'externalbusinessstats', s.id
        FROM externalbusinessstats s WHERE s.views_total IS NOT NULL
        UNION ALL
        SELECT ('external-actions:' || s.id), s.business_id, 'map_actions', s.actions_total::numeric,
               CASE WHEN s.date ~ '^\\d{4}-\\d{2}-\\d{2}$' THEN s.date::date::timestamptz ELSE s.updated_at::timestamptz END,
               'externalbusinessstats', s.id
        FROM externalbusinessstats s WHERE s.actions_total IS NOT NULL
        UNION ALL
        SELECT ('social-reach:' || m.id), p.business_id, 'social_reach', m.reach::numeric,
               m.metric_date::timestamptz, 'social_post_metrics', m.id
        FROM social_post_metrics m
        JOIN social_posts p ON p.id = m.social_post_id
        """
    )


def downgrade():
    op.execute("DROP VIEW IF EXISTS metric_observations_v")
    op.execute("DROP VIEW IF EXISTS knowledge_edges_v")
    op.execute("DROP VIEW IF EXISTS knowledge_nodes_v")
    op.execute("DROP TABLE IF EXISTS privacy_release_reviews")
    op.execute("DROP TABLE IF EXISTS business_action_events")
    op.execute("DROP TABLE IF EXISTS knowledge_evidence")
    op.execute("DROP TABLE IF EXISTS learning_claims")
    op.execute("DROP TABLE IF EXISTS knowledge_assertions")
    op.execute("DROP TABLE IF EXISTS knowledge_concepts")
    op.execute("DROP TABLE IF EXISTS knowledge_document_analyses")
    op.execute("DROP TABLE IF EXISTS knowledge_analysis_runs")
    op.execute("DROP TABLE IF EXISTS knowledge_documents")
    op.execute("DROP TABLE IF EXISTS knowledge_sources")
