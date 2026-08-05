"""add staged outreach experiments and knowledge patterns

Revision ID: 20260805_001
Revises: 20260803_001
Create Date: 2026-08-05
"""

from alembic import op


revision = "20260805_001"
down_revision = "20260803_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_knowledge_patterns (
            id UUID PRIMARY KEY,
            pattern_key TEXT NOT NULL,
            version INTEGER NOT NULL,
            title TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            segment TEXT NOT NULL DEFAULT '',
            trigger_contract_json JSONB NOT NULL DEFAULT '{}',
            message_rule_json JSONB NOT NULL DEFAULT '{}',
            contraindications_json JSONB NOT NULL DEFAULT '[]',
            source_refs_json JSONB NOT NULL DEFAULT '[]',
            support_document_count INTEGER NOT NULL DEFAULT 0,
            support_source_count INTEGER NOT NULL DEFAULT 0,
            compiled_by TEXT NOT NULL DEFAULT 'deterministic',
            compiler_result_json JSONB NOT NULL DEFAULT '{}',
            reviewed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            approved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_outreach_pattern_version UNIQUE (pattern_key, version),
            CONSTRAINT chk_outreach_pattern_type CHECK (pattern_type IN ('signal', 'bridge', 'offer', 'sequence')),
            CONSTRAINT chk_outreach_pattern_status CHECK (status IN ('draft', 'approved', 'deprecated'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_outreach_patterns_lookup ON outreach_knowledge_patterns(status, segment, pattern_key, version DESC)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_experiments (
            id UUID PRIMARY KEY,
            experiment_key TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            scope_type TEXT NOT NULL DEFAULT 'platform',
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            workstream_type TEXT NOT NULL DEFAULT 'localos_sales',
            segment TEXT NOT NULL DEFAULT '',
            hypothesis_json JSONB NOT NULL DEFAULT '{}',
            policy_json JSONB NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'draft',
            current_stage TEXT NOT NULL DEFAULT 'canary_1',
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_outreach_experiment_scope CHECK (scope_type IN ('platform', 'business')),
            CONSTRAINT chk_outreach_experiment_status CHECK (status IN ('draft', 'active', 'paused', 'completed', 'cancelled'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_outreach_experiments_scope ON outreach_experiments(scope_type, business_id, status, updated_at DESC)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_experiment_members (
            id UUID PRIMARY KEY,
            experiment_id UUID NOT NULL REFERENCES outreach_experiments(id) ON DELETE CASCADE,
            workstream_id UUID NOT NULL REFERENCES lead_workstreams(id) ON DELETE CASCADE,
            campaign_id UUID REFERENCES outreach_campaigns(id) ON DELETE SET NULL,
            cohort TEXT NOT NULL,
            variant TEXT NOT NULL,
            pattern_id UUID REFERENCES outreach_knowledge_patterns(id) ON DELETE SET NULL,
            pattern_version INTEGER,
            status TEXT NOT NULL DEFAULT 'selected',
            exclusion_reason TEXT,
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_outreach_experiment_workstream UNIQUE (experiment_id, workstream_id),
            CONSTRAINT chk_outreach_member_variant CHECK (variant IN ('treatment', 'control')),
            CONSTRAINT chk_outreach_member_status CHECK (status IN ('selected', 'draft', 'approved', 'active', 'completed', 'excluded'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_outreach_experiment_members_stage ON outreach_experiment_members(experiment_id, cohort, variant, status)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS outreach_experiment_members")
    op.execute("DROP TABLE IF EXISTS outreach_experiments")
    op.execute("DROP TABLE IF EXISTS outreach_knowledge_patterns")
