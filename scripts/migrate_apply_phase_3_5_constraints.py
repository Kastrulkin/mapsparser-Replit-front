import os
import sys
import sqlite3

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from database_manager import DatabaseManager

def migrate_constraints():
    print("🚀 Starting Phase 3.5 Constraints Migration...")
    
    db = DatabaseManager()
    conn = db.conn
    cursor = conn.cursor()
    
    is_sqlite = isinstance(conn, sqlite3.Connection)
    print(f"📦 DB Type: {'SQLite' if is_sqlite else 'Postgres'}")

    try:
        if is_sqlite:
            # === SQLite Implementation ===
            print("🔧 Applying SQLite Constraints (Recreating Tables)...")
            
            # 1. ExternalBusinessReviews Unique Index
            print("1️⃣  Creating Unique Index for ExternalBusinessReviews...")
            # We don't strictly need to recreate table for Index, just CREATE UNIQUE INDEX
            # But we need to handle duplicates first (cleaning script should have handled this, but we use IGNORE just in case)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_reviews_unique 
                ON ExternalBusinessReviews(business_id, author_name, published_at, text);
            """)
            print("   ✅ Index idx_reviews_unique created.")

            # 2. UserServices Foreign Key & Unique Constraint
            print("2️⃣  Recreating UserServices with FK and Unique Constraints...")
            
            # Rename old
            cursor.execute("ALTER TABLE UserServices RENAME TO UserServices_old;")
            
            # Create new with constraints
            cursor.execute("""
                CREATE TABLE UserServices (
                    id TEXT PRIMARY KEY,
                    user_id TEXT REFERENCES Users(id) ON DELETE RESTRICT,
                    business_id TEXT REFERENCES Businesses(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    price REAL,
                    duration INTEGER,
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    currency TEXT DEFAULT 'RUB',
                    CONSTRAINT uq_service_name UNIQUE (business_id, name)
                );
            """)
            
            # Copy data
            # Using INSERT OR IGNORE to handle any remaining duplicates in UserServices
            print("   🔄 Copying data...")
            cursor.execute("""
                INSERT OR IGNORE INTO UserServices 
                SELECT * FROM UserServices_old;
            """)
            row_count = cursor.rowcount
            print(f"   Rows copied: {row_count}")
            
            # Drop old
            cursor.execute("DROP TABLE UserServices_old;")
            print("   ✅ UserServices recreated successfully.")
            
        else:
            # === Postgres Implementation ===
            print("🐘 Applying Postgres Constraints...")
            
            # 1. ExternalBusinessReviews Unique Index
            # Uses CONCURRENTLY which cannot run in a transaction block usually, 
            # but psycopg2 might handle it if autocommit is set.
            # Here we assume standard execution.
            print("1️⃣  Creating Unique Index (CONCURRENTLY)...")
            cursor.execute("COMMIT;") # End current transaction to allow CONCURRENTLY
            cursor.execute("""
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_reviews_unique 
                ON ExternalBusinessReviews(business_id, author_name, published_at, text);
            """)
            
            # 2. UserServices FK
            print("2️⃣  Adding FK to UserServices...")
            cursor.execute("""
                ALTER TABLE UserServices 
                ADD CONSTRAINT fk_user 
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE RESTRICT;
            """)
            
            # 3. UserServices Unique Name
            print("3️⃣  Adding Unique Name constraint to UserServices...")
            cursor.execute("COMMIT;")
            cursor.execute("""
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_service_name 
                ON UserServices(business_id, name);
            """)
            
        conn.commit()
        print("\n🎉 Phase 3.5 Constraints Applied Successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        # If SQLite table swap failed, manual recovery might be needed from _old
        if is_sqlite:
            print("⚠️  Check if UserServices_old exists if restoration is needed.")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    migrate_constraints()
