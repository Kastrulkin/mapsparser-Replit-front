"""expand userservices for parsed services (source, external_id, price range, raw)

Revision ID: 20250211_002
Revises: 20250211_001
Create Date: 2025-02-11

"""
from alembic import op

revision = "20250211_002"
down_revision = "20250211_001"
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поля для парсинга (идемпотентно; description/category уже есть в таблице)
    for col, typ in [
        ("source", "TEXT"),
        ("external_id", "TEXT"),
        ("price_from", "NUMERIC"),
        ("price_to", "NUMERIC"),
        ("currency", "TEXT"),
        ("unit", "TEXT"),
        ("duration_minutes", "INTEGER"),
        ("raw", "JSONB"),
    ]:
        op.execute(
            f"""
            ALTER TABLE userservices
            ADD COLUMN IF NOT EXISTS {col} {typ}
            """
        )
    # Уникальный индекс для upsert по (business_id, source, external_id)
    # Только для строк с external_id (без NULL)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_userservices_business_source_external
        ON userservices (business_id, source, external_id)
        WHERE external_id IS NOT NULL
        """
    )


def downgrade():
    op.execute(
        "DROP INDEX IF EXISTS idx_userservices_business_source_external"
    )
    for col in ["raw", "duration_minutes", "unit", "currency", "price_to", "price_from", "external_id", "source"]:
        op.execute(f"ALTER TABLE userservices DROP COLUMN IF EXISTS {col}")
