"""add evidence-based lead research for scoped agent prospecting

Revision ID: 20260715_001
Revises: 20260714_002
Create Date: 2026-07-15 10:00:00.000000
"""

from alembic import op


revision = "20260715_001"
down_revision = "20260714_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_workstream_research (
            id UUID PRIMARY KEY,
            workstream_id UUID NOT NULL REFERENCES lead_workstreams(id) ON DELETE CASCADE,
            score SMALLINT NOT NULL,
            qualification_stage TEXT NOT NULL,
            signal_label TEXT NOT NULL,
            score_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
            why_now TEXT,
            signals_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            sources_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            contact_evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            suggested_opener TEXT,
            opener_source_url TEXT,
            limitations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            report_hash TEXT NOT NULL,
            created_by_agent_client_id TEXT REFERENCES agent_clients(id) ON DELETE SET NULL,
            researched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_lead_workstream_research_score CHECK (score BETWEEN 0 AND 100),
            CONSTRAINT ck_lead_workstream_research_stage CHECK (
                qualification_stage IN ('high_intent', 'problem_aware', 'trigger_present', 'potential_fit')
            ),
            CONSTRAINT ck_lead_workstream_research_label CHECK (
                signal_label IN ('strong_signal', 'reason_to_check', 'fit_only')
            )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE lead_workstream_research
        ADD COLUMN IF NOT EXISTS contact_evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE lead_workstream_research
        ADD COLUMN IF NOT EXISTS opener_source_url TEXT
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_workstream_research_hash
        ON lead_workstream_research(workstream_id, report_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_workstream_research_latest
        ON lead_workstream_research(workstream_id, researched_at DESC, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_workstream_research_signal
        ON lead_workstream_research(signal_label, score DESC, researched_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_client_prospecting_grants (
            id UUID PRIMARY KEY,
            agent_client_id TEXT NOT NULL REFERENCES agent_clients(id) ON DELETE CASCADE,
            workstream_type TEXT NOT NULL,
            client_business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_agent_client_prospecting_grant_type CHECK (
                workstream_type IN ('localos_sales', 'client_partnership')
            ),
            CONSTRAINT ck_agent_client_prospecting_grant_client CHECK (
                (workstream_type = 'localos_sales' AND client_business_id IS NULL)
                OR (workstream_type = 'client_partnership' AND client_business_id IS NOT NULL)
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_client_prospecting_grant
        ON agent_client_prospecting_grants(
            agent_client_id,
            workstream_type,
            COALESCE(client_business_id, '')
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_prospecting_imports (
            id UUID PRIMARY KEY,
            agent_client_id TEXT NOT NULL REFERENCES agent_clients(id) ON DELETE CASCADE,
            idempotency_key TEXT NOT NULL,
            report_hash TEXT NOT NULL,
            result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_prospecting_import_idempotency
        ON agent_prospecting_imports(agent_client_id, idempotency_key)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_agent_prospecting_import_idempotency")
    op.execute("DROP TABLE IF EXISTS agent_prospecting_imports")
    op.execute("DROP INDEX IF EXISTS uq_agent_client_prospecting_grant")
    op.execute("DROP TABLE IF EXISTS agent_client_prospecting_grants")
    op.execute("DROP INDEX IF EXISTS idx_lead_workstream_research_signal")
    op.execute("DROP INDEX IF EXISTS idx_lead_workstream_research_latest")
    op.execute("DROP INDEX IF EXISTS uq_lead_workstream_research_hash")
    op.execute("DROP TABLE IF EXISTS lead_workstream_research")
