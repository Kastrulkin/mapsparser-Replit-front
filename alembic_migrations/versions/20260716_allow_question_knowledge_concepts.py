"""allow question concepts in the market knowledge graph

Revision ID: 20260716_004
Revises: 20260716_003
Create Date: 2026-07-16 19:30:00.000000
"""

from alembic import op


revision = "20260716_004"
down_revision = "20260716_003"
branch_labels = None
depends_on = None


CONCEPT_TYPES = (
    "'topic', 'pain', 'segment', 'service', 'format', 'sales_angle', "
    "'cta', 'intervention', 'capability', 'metric', 'search_intent', "
    "'objection', 'practice', 'offer', 'audience_language', 'market_signal'"
)


def upgrade():
    op.execute("ALTER TABLE knowledge_concepts DROP CONSTRAINT IF EXISTS ck_knowledge_concepts_type")
    op.execute(
        f"""
        ALTER TABLE knowledge_concepts
        ADD CONSTRAINT ck_knowledge_concepts_type
        CHECK (concept_type IN ({CONCEPT_TYPES}, 'question'))
        """
    )


def downgrade():
    op.execute("UPDATE knowledge_concepts SET concept_type = 'market_signal' WHERE concept_type = 'question'")
    op.execute("ALTER TABLE knowledge_concepts DROP CONSTRAINT IF EXISTS ck_knowledge_concepts_type")
    op.execute(
        f"""
        ALTER TABLE knowledge_concepts
        ADD CONSTRAINT ck_knowledge_concepts_type
        CHECK (concept_type IN ({CONCEPT_TYPES}))
        """
    )
