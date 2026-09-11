"""Versioned internal partnership agreements on the existing workstream."""
from alembic import op
revision = "20260911_partner_agreements"
down_revision = "20260910_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE lead_workstreams ADD COLUMN IF NOT EXISTS agreement_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("""WITH saved AS (
        SELECT DISTINCT ON (entity_id) entity_id, id, payload_json, user_id, completed_at
        FROM journey_actions WHERE flow_type='partnership' AND entity_type='lead_workstream'
          AND action_type='define_terms' AND status='completed'
          AND NULLIF(TRIM(payload_json->>'details'), '') IS NOT NULL
        ORDER BY entity_id, completed_at DESC NULLS LAST, id DESC
    ) UPDATE lead_workstreams w SET agreement_json=jsonb_build_object(
        'revision', 1, 'terms_version', 1, 'status', 'needs_confirmation',
        'terms', jsonb_build_object('details', saved.payload_json->>'details'),
        'provenance', jsonb_build_object('source', 'journey_actions', 'id', saved.id, 'user_id', saved.user_id, 'at', saved.completed_at)
    ) FROM saved WHERE w.id::text=saved.entity_id AND w.agreement_json='{}'::jsonb
      AND w.workstream_type='client_partnership'""")


def downgrade():
    op.execute("ALTER TABLE lead_workstreams DROP COLUMN IF EXISTS agreement_json")
