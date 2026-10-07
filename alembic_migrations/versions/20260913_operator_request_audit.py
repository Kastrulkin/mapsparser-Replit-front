"""Index durable Operator receipts in the existing audit ledger."""
from alembic import op

revision = '20260913_operator_request_audit'
down_revision = '20260912_work_journal'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE INDEX IF NOT EXISTS idx_operator_request_audio ON agent_action_ledger (business_id,(metadata_json->>'transcription_id')) WHERE action_type='operator_request_received'")
    op.execute("CREATE INDEX IF NOT EXISTS idx_operator_request_actor ON agent_action_ledger (business_id,(metadata_json->>'operator_user_id'),created_at DESC) WHERE action_type='operator_request_received'")
    op.execute("CREATE INDEX IF NOT EXISTS idx_operator_request_feedback ON agent_action_ledger (business_id,(metadata_json->>'receipt_id')) WHERE action_type='operator_request_feedback'")


def downgrade():
    # Disabling the pilot must preserve receipts and feedback.
    op.execute('DROP INDEX IF EXISTS idx_operator_request_feedback')
    op.execute('DROP INDEX IF EXISTS idx_operator_request_actor')
    op.execute('DROP INDEX IF EXISTS idx_operator_request_audio')
