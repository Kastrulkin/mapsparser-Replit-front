"""Keep only confirmed locations in client networks.

Revision ID: 20260814_002
Revises: 20260814_001
"""

from alembic import op


revision = "20260814_002"
down_revision = "20260814_001"
branch_labels = None
depends_on = None


CONFIRMED_CLIENT_NETWORK_BUSINESS_IDS = (
    # Весёлая расчёска: representative plus two locations.
    "ab26362f-9d63-4025-b721-9a8cb29015ef",
    "0f67ac22-132f-41e7-b473-667c46f364fa",
    "cb674174-8b3d-41a3-8277-525c849935f2",
    # Кафе Кебаб: representative plus the client location. The other
    # legacy rows are map-search discoveries, not managed client locations.
    "55602996-cc00-4f1e-b017-38fa3b4d5965",
    "8b47e9fa-1084-4f36-a733-ac4fd908498c",
    # Шансик: representative plus five confirmed locations.
    "a65a56c3-26a4-5921-a894-d36eb142ff72",
    "0efe3f0d-d32c-5ea9-84e8-e9387418cec1",
    "12c19fd1-e1a3-51f5-9980-eb75f0a5234a",
    "17ff72b6-a542-5fac-b67c-f710ee4fc828",
    "46bb9a2f-bd03-5930-9644-76315016d471",
    "72e5811d-bdda-5ec7-ad74-5f728fb6c11d",
)

CLIENT_NETWORK_IDS = (
    "ab26362f-9d63-4025-b721-9a8cb29015ef",
    "55602996-cc00-4f1e-b017-38fa3b4d5965",
    "a65a56c3-26a4-5921-a894-d36eb142ff72",
)


def _quoted(values):
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


def upgrade():
    op.execute(
        f"""
        UPDATE businesses
        SET entity_group = CASE
            WHEN id IN ({_quoted(CONFIRMED_CLIENT_NETWORK_BUSINESS_IDS)}) THEN 'client'
            ELSE 'lead'
        END
        WHERE network_id IN ({_quoted(CLIENT_NETWORK_IDS)})
        """
    )


def downgrade():
    # Restores the broad classification used by the preceding migration.
    op.execute(
        f"UPDATE businesses SET entity_group = 'client' "
        f"WHERE network_id IN ({_quoted(CLIENT_NETWORK_IDS)})"
    )
