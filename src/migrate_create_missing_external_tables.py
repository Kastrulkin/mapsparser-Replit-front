import sqlite3
import os
from safe_db_utils import safe_migrate

def run_migration(cursor):
    """
    Creates missing External Data tables.
    """
    # 1. ExternalBusinessPosts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ExternalBusinessPosts'")
    if not cursor.fetchone():
        print("Creating ExternalBusinessPosts table...")
        cursor.execute("""
            CREATE TABLE ExternalBusinessPosts (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                account_id TEXT,
                source TEXT NOT NULL,
                external_post_id TEXT,
                title TEXT,
                text TEXT,
                published_at TIMESTAMP,
                image_url TEXT,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_posts_business ON ExternalBusinessPosts(business_id)")
        print("✅ ExternalBusinessPosts created.")
    else:
        print("✨ ExternalBusinessPosts already exists.")

    # 2. ExternalBusinessPhotos
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ExternalBusinessPhotos'")
    if not cursor.fetchone():
        print("Creating ExternalBusinessPhotos table...")
        cursor.execute("""
            CREATE TABLE ExternalBusinessPhotos (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                account_id TEXT,
                source TEXT NOT NULL,
                external_photo_id TEXT,
                url TEXT NOT NULL,
                thumbnail_url TEXT,
                uploaded_at TIMESTAMP,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_photos_business ON ExternalBusinessPhotos(business_id)")
        print("✅ ExternalBusinessPhotos created.")
    else:
        print("✨ ExternalBusinessPhotos already exists.")

    # 3. ExternalBusinessStats
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ExternalBusinessStats'")
    if not cursor.fetchone():
        print("Creating ExternalBusinessStats table...")
        cursor.execute("""
            CREATE TABLE ExternalBusinessStats (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                account_id TEXT,
                source TEXT NOT NULL,
                date DATE NOT NULL,
                views_total INTEGER,
                clicks_total INTEGER,
                actions_total INTEGER,
                rating REAL,
                reviews_total INTEGER,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE,
                UNIQUE(business_id, source, date)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_stats_business ON ExternalBusinessStats(business_id)")
        print("✅ ExternalBusinessStats created.")
    else:
        print("✨ ExternalBusinessStats already exists.")

def migrate():
    print("🚀 Starting safe migration for External Data Tables...")
    success = safe_migrate(run_migration, "Create missing External tables")
    
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed!")
        exit(1)

if __name__ == "__main__":
    migrate()
