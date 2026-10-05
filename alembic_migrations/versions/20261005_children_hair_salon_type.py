"""Add the children's hair salon business type.

Revision ID: 20261005_children_hair_salon_type
Revises: 20260907_001
Create Date: 2026-10-05
"""

from alembic import op


revision = "20261005_children_hair_salon_type"
down_revision = "20260907_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        INSERT INTO businesstypes (id, type_key, label, description)
        VALUES (
            'bt_children_hair_salon',
            'children_hair_salon',
            'Детская парикмахерская',
            'Парикмахерская для детей и семей с детьми'
        )
        ON CONFLICT (type_key) DO NOTHING
        """
    )


def downgrade():
    # Preserve a type that may already be assigned to an existing business.
    pass
