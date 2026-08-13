"""version agent runtime configuration

Revision ID: 20260813_003
Revises: 20260813_002
Create Date: 2026-08-13
"""

from alembic import op


revision = "20260813_003"
down_revision = "20260813_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE agent_blueprint_versions
            ADD COLUMN IF NOT EXISTS runtime_config_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        UPDATE agent_blueprint_versions AS version
        SET runtime_config_json = COALESCE(blueprint.metadata_json->'custom_process', '{}'::jsonb)
        FROM agent_blueprints AS blueprint
        WHERE version.blueprint_id = blueprint.id
          AND version.runtime_config_json = '{}'::jsonb
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE agent_blueprint_versions
            DROP COLUMN IF EXISTS runtime_config_json
        """
    )
