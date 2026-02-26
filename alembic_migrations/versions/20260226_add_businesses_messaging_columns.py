"""add messaging columns to businesses for reminders/callback channels

Revision ID: 20260226_001
Revises: 20260224_003
Create Date: 2026-02-26
"""

from alembic import op


revision = "20260226_001"
down_revision = "20260224_004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS waba_phone_id TEXT")
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS waba_access_token TEXT")
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS telegram_bot_token TEXT")
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS whatsapp_phone TEXT")
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS whatsapp_verified BOOLEAN DEFAULT FALSE")
    op.execute("CREATE INDEX IF NOT EXISTS idx_businesses_waba_phone_id ON businesses(waba_phone_id)")


def downgrade():
    # Безопасный downgrade: удаляем только индекс, данные в колонках не трогаем.
    op.execute("DROP INDEX IF EXISTS idx_businesses_waba_phone_id")
