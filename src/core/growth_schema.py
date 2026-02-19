from database_manager import DatabaseManager


DEFAULT_BUSINESS_TYPES = [
    ("beauty_salon", "Салон красоты", "Салон красоты с полным спектром услуг"),
    ("barbershop", "Барбершоп", "Мужской барбершоп"),
    ("spa", "SPA/Wellness", "SPA и wellness центр"),
    ("nail_studio", "Ногтевая студия", "Студия маникюра и педикюра"),
    ("cosmetology", "Косметология", "Косметологический кабинет"),
    ("massage", "Массаж", "Массажный салон"),
    ("brows_lashes", "Брови и ресницы", "Студия бровей и ресниц"),
    ("makeup", "Макияж", "Студия макияжа"),
    ("tanning", "Солярий", "Студия загара"),
    ("other", "Другое", "Другой тип бизнеса"),
]


def ensure_growth_schema(db: DatabaseManager) -> None:
    cursor = db.conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS BusinessTypes (
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
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS GrowthStages (
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
            FOREIGN KEY (business_type_id) REFERENCES BusinessTypes(id) ON DELETE CASCADE,
            UNIQUE(business_type_id, stage_number)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS GrowthTasks (
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
            FOREIGN KEY (stage_id) REFERENCES GrowthStages(id) ON DELETE CASCADE,
            UNIQUE(stage_id, task_number)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS BusinessOptimizationWizard (
            id TEXT PRIMARY KEY,
            business_id TEXT UNIQUE NOT NULL,
            step INTEGER DEFAULT 1,
            data TEXT,
            completed INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("ALTER TABLE BusinessTypes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    cursor.execute("ALTER TABLE BusinessTypes ADD COLUMN IF NOT EXISTS alert_threshold_news_days INTEGER DEFAULT 30")
    cursor.execute("ALTER TABLE BusinessTypes ADD COLUMN IF NOT EXISTS alert_threshold_photos_days INTEGER DEFAULT 90")
    cursor.execute("ALTER TABLE BusinessTypes ADD COLUMN IF NOT EXISTS alert_threshold_reviews_days INTEGER DEFAULT 7")
    cursor.execute("ALTER TABLE GrowthStages ADD COLUMN IF NOT EXISTS tasks TEXT")
    cursor.execute("ALTER TABLE GrowthStages ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    cursor.execute("ALTER TABLE GrowthTasks ADD COLUMN IF NOT EXISTS check_logic TEXT")
    cursor.execute("ALTER TABLE GrowthTasks ADD COLUMN IF NOT EXISTS reward_value INTEGER DEFAULT 0")
    cursor.execute("ALTER TABLE GrowthTasks ADD COLUMN IF NOT EXISTS reward_type TEXT DEFAULT 'points'")
    cursor.execute("ALTER TABLE GrowthTasks ADD COLUMN IF NOT EXISTS tooltip TEXT")
    cursor.execute("ALTER TABLE GrowthTasks ADD COLUMN IF NOT EXISTS link_url TEXT")
    cursor.execute("ALTER TABLE GrowthTasks ADD COLUMN IF NOT EXISTS link_text TEXT")
    cursor.execute("ALTER TABLE GrowthTasks ADD COLUMN IF NOT EXISTS is_auto_verifiable INTEGER DEFAULT 0")
    cursor.execute("ALTER TABLE BusinessOptimizationWizard ADD COLUMN IF NOT EXISTS data TEXT")
    cursor.execute("ALTER TABLE BusinessOptimizationWizard ADD COLUMN IF NOT EXISTS completed INTEGER DEFAULT 0")
    cursor.execute("ALTER TABLE BusinessOptimizationWizard ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    for type_key, label, description in DEFAULT_BUSINESS_TYPES:
        cursor.execute(
            """
            INSERT INTO BusinessTypes (id, type_key, label, description, alert_threshold_news_days, alert_threshold_photos_days, alert_threshold_reviews_days)
            VALUES (%s, %s, %s, %s, 30, 90, 7)
            ON CONFLICT (type_key) DO NOTHING
            """,
            (f"bt_{type_key}", type_key, label, description),
        )

    db.conn.commit()
