"""allow MAX as a manual social post channel

Revision ID: 20260828_001
Revises: 20260827_002
Create Date: 2026-08-28 11:15:00.000000
"""

from alembic import op


revision = "20260828_001"
down_revision = "20260827_002"
branch_labels = None
depends_on = None


PLATFORMS_WITH_MAX = (
    "'yandex_maps', 'two_gis', 'google_business', 'telegram', 'vk', "
    "'max', 'instagram', 'facebook'"
)

PLATFORMS_WITHOUT_MAX = (
    "'yandex_maps', 'two_gis', 'google_business', 'telegram', 'vk', "
    "'instagram', 'facebook'"
)


def upgrade():
    op.execute("ALTER TABLE social_posts DROP CONSTRAINT IF EXISTS chk_social_posts_platform")
    op.execute(
        f"""
        ALTER TABLE social_posts
        ADD CONSTRAINT chk_social_posts_platform
        CHECK (platform IN ({PLATFORMS_WITH_MAX}))
        """
    )


def downgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM social_posts WHERE platform = 'max') THEN
                RAISE EXCEPTION 'Cannot remove MAX platform while MAX social posts exist';
            END IF;
        END
        $$
        """
    )
    op.execute("ALTER TABLE social_posts DROP CONSTRAINT IF EXISTS chk_social_posts_platform")
    op.execute(
        f"""
        ALTER TABLE social_posts
        ADD CONSTRAINT chk_social_posts_platform
        CHECK (platform IN ({PLATFORMS_WITHOUT_MAX}))
        """
    )
