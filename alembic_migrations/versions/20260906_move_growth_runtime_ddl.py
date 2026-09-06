"""Move growth-plan schema and default taxonomy into Alembic.

Revision ID: 20260906_006
Revises: 20260906_005
"""

from alembic import op


revision = "20260906_006"
down_revision = "20260906_005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS businesstypes (
            id TEXT PRIMARY KEY,
            type_key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            alert_threshold_news_days INTEGER DEFAULT 30,
            alert_threshold_photos_days INTEGER DEFAULT 90,
            alert_threshold_reviews_days INTEGER DEFAULT 7,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("ALTER TABLE businesstypes ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE businesstypes ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1")
    op.execute("ALTER TABLE businesstypes ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    op.execute("ALTER TABLE businesstypes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    op.execute("ALTER TABLE businesstypes ADD COLUMN IF NOT EXISTS alert_threshold_news_days INTEGER DEFAULT 30")
    op.execute("ALTER TABLE businesstypes ADD COLUMN IF NOT EXISTS alert_threshold_photos_days INTEGER DEFAULT 90")
    op.execute("ALTER TABLE businesstypes ADD COLUMN IF NOT EXISTS alert_threshold_reviews_days INTEGER DEFAULT 7")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS growthstages (
            id TEXT PRIMARY KEY,
            business_type_id TEXT NOT NULL,
            stage_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            goal TEXT,
            expected_result TEXT,
            duration TEXT,
            is_permanent INTEGER DEFAULT 0,
            tasks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_type_id) REFERENCES businesstypes(id) ON DELETE CASCADE,
            UNIQUE(business_type_id, stage_number)
        )
        """
    )
    op.execute("ALTER TABLE growthstages ADD COLUMN IF NOT EXISTS tasks TEXT")
    op.execute("ALTER TABLE growthstages ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS growthtasks (
            id TEXT PRIMARY KEY,
            stage_id TEXT NOT NULL,
            task_number INTEGER NOT NULL,
            task_text TEXT NOT NULL,
            check_logic TEXT,
            reward_value INTEGER DEFAULT 0,
            reward_type TEXT DEFAULT 'points',
            tooltip TEXT,
            link_url TEXT,
            link_text TEXT,
            is_auto_verifiable INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stage_id) REFERENCES growthstages(id) ON DELETE CASCADE,
            UNIQUE(stage_id, task_number)
        )
        """
    )
    op.execute("ALTER TABLE growthtasks ADD COLUMN IF NOT EXISTS check_logic TEXT")
    op.execute("ALTER TABLE growthtasks ADD COLUMN IF NOT EXISTS reward_value INTEGER DEFAULT 0")
    op.execute("ALTER TABLE growthtasks ADD COLUMN IF NOT EXISTS reward_type TEXT DEFAULT 'points'")
    op.execute("ALTER TABLE growthtasks ADD COLUMN IF NOT EXISTS tooltip TEXT")
    op.execute("ALTER TABLE growthtasks ADD COLUMN IF NOT EXISTS link_url TEXT")
    op.execute("ALTER TABLE growthtasks ADD COLUMN IF NOT EXISTS link_text TEXT")
    op.execute("ALTER TABLE growthtasks ADD COLUMN IF NOT EXISTS is_auto_verifiable INTEGER DEFAULT 0")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS businessoptimizationwizard (
            id TEXT PRIMARY KEY,
            business_id TEXT UNIQUE NOT NULL,
            step INTEGER DEFAULT 1,
            data TEXT,
            completed INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("ALTER TABLE businessoptimizationwizard ADD COLUMN IF NOT EXISTS data TEXT")
    op.execute("ALTER TABLE businessoptimizationwizard ADD COLUMN IF NOT EXISTS completed INTEGER DEFAULT 0")
    op.execute("ALTER TABLE businessoptimizationwizard ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    op.execute(
        """
        INSERT INTO businesstypes (
            id, type_key, label, description,
            alert_threshold_news_days, alert_threshold_photos_days, alert_threshold_reviews_days
        ) VALUES
            ('bt_beauty_salon', 'beauty_salon', 'Салон красоты', 'Салон красоты с полным спектром услуг', 30, 90, 7),
            ('bt_barbershop', 'barbershop', 'Барбершоп', 'Мужской барбершоп', 30, 90, 7),
            ('bt_spa', 'spa', 'SPA/Wellness', 'SPA и wellness центр', 30, 90, 7),
            ('bt_nail_studio', 'nail_studio', 'Ногтевая студия', 'Студия маникюра и педикюра', 30, 90, 7),
            ('bt_cosmetology', 'cosmetology', 'Косметология', 'Косметологический кабинет', 30, 90, 7),
            ('bt_massage', 'massage', 'Массаж', 'Массажный салон', 30, 90, 7),
            ('bt_brows_lashes', 'brows_lashes', 'Брови и ресницы', 'Студия бровей и ресниц', 30, 90, 7),
            ('bt_makeup', 'makeup', 'Макияж', 'Студия макияжа', 30, 90, 7),
            ('bt_tanning', 'tanning', 'Солярий', 'Студия загара', 30, 90, 7),
            ('bt_other', 'other', 'Другое', 'Другой тип бизнеса', 30, 90, 7)
        ON CONFLICT (type_key) DO NOTHING
        """
    )


def downgrade():
    # Existing growth plans and an administrator's taxonomy survive rollback.
    pass
