"""Store explicitly confirmed business city alongside versioned input defaults."""
from alembic import op

revision = '20260914_business_input_city'
down_revision = '20260913_operator_request_audit'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE business_finance_settings ADD COLUMN IF NOT EXISTS city TEXT')


def downgrade():
    # Retain user-supplied city and its audit history on application rollback.
    pass
