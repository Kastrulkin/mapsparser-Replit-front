"""version agent runtime settings

Revision ID: 20260813_002
Revises: 20260813_001
Create Date: 2026-08-13
"""

from alembic import op


revision = "20260813_002"
down_revision = "20260813_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE agent_blueprint_versions
            ADD COLUMN IF NOT EXISTS execution_mode TEXT NOT NULL DEFAULT 'manual',
            ADD COLUMN IF NOT EXISTS trigger TEXT NOT NULL DEFAULT 'manual.run',
            ADD COLUMN IF NOT EXISTS schedule_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS required_integration_bindings_json JSONB NOT NULL DEFAULT '[]'::jsonb
        """
    )
    op.execute(
        """
        UPDATE agent_blueprint_versions AS version
        SET trigger = COALESCE(
                NULLIF(blueprint.metadata_json->'custom_process'->>'trigger', ''),
                CASE
                    WHEN COALESCE(blueprint.metadata_json->>'execution_mode', '') = 'scheduled'
                    THEN 'schedule.daily'
                    ELSE 'manual.run'
                END
            ),
            execution_mode = CASE
                WHEN COALESCE(blueprint.metadata_json->>'execution_mode', '') IN ('one_off', 'manual', 'scheduled')
                THEN blueprint.metadata_json->>'execution_mode'
                WHEN COALESCE(blueprint.metadata_json->'custom_process'->>'trigger', '') = 'schedule.daily'
                THEN 'scheduled'
                ELSE 'manual'
            END,
            schedule_json = COALESCE(
                blueprint.metadata_json->'custom_process'->'schedule',
                '{}'::jsonb
            ),
            limits_json = COALESCE(blueprint.metadata_json->'limits', '{}'::jsonb),
            required_integration_bindings_json = COALESCE(
                blueprint.metadata_json->'required_integration_bindings',
                '[]'::jsonb
            )
        FROM agent_blueprints AS blueprint
        WHERE version.blueprint_id = blueprint.id
          AND version.trigger = 'manual.run'
          AND version.schedule_json = '{}'::jsonb
          AND version.limits_json = '{}'::jsonb
          AND version.required_integration_bindings_json = '[]'::jsonb
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE agent_blueprint_versions
            DROP COLUMN IF EXISTS required_integration_bindings_json,
            DROP COLUMN IF EXISTS limits_json,
            DROP COLUMN IF EXISTS schedule_json,
            DROP COLUMN IF EXISTS trigger,
            DROP COLUMN IF EXISTS execution_mode
        """
    )
