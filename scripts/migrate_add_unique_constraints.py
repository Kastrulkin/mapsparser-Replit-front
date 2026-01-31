import os
import sys
import psycopg2
from psycopg2 import sql

# Add src to path to import database_manager if needed, 
# but for this script we might just use psycopg2 directly or DatabaseManager
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database_manager import DatabaseManager

def cleanup_duplicates_and_add_constraints():
    print("🚀 Starting migration: Unique Constraints Validation...")
    
    db = DatabaseManager()
    conn = db.conn
    cursor = conn.cursor()

    try:
        # 1. ExternalBusinessReviews
        print("\nCanalysing ExternalBusinessReviews for duplicates...")
        
        # Check current duplicates
        cursor.execute("""
            SELECT business_id, source, external_review_id, COUNT(*)
            FROM ExternalBusinessReviews
            WHERE external_review_id IS NOT NULL
            GROUP BY business_id, source, external_review_id
            HAVING COUNT(*) > 1;
        """)
        duplicates = cursor.fetchall()
        print(f"Found {len(duplicates)} groups of duplicates in ExternalBusinessReviews.")

        if duplicates:
            print("Cleaning up duplicates (keeping the latest updated_at)...")
            # Logic: Delete records that are NOT the latest for their group
            cursor.execute("""
                DELETE FROM ExternalBusinessReviews a
                USING ExternalBusinessReviews b
                WHERE a.business_id = b.business_id
                  AND a.source = b.source
                  AND a.external_review_id = b.external_review_id
                  AND a.updated_at < b.updated_at;
            """)
            print(f"Deleted {cursor.rowcount} duplicate rows.")

        print("Adding UNIQUE CONSTRAINT to ExternalBusinessReviews...")
        # We use a unique index with NULLs distinct? No, external_review_id should be unique per source/business.
        # Postgres allows multiple NULLs in UNIQUE constraint, but we specifically care about non-null external IDs.
        
        # Drop old index if exists (to be safe)
        cursor.execute("DROP INDEX IF EXISTS idx_ext_reviews_unique;")
        
        # Add Constraint
        # Note: We can't easily add a conditional unique constraint as a Table Constraint in standard SQL 
        # without partial index. But typical Unique Constraint is for all rows.
        # If external_review_id is NULL, we don't care about uniqueness? 
        # Let's assume external_review_id IS NULL implies it's not an external review we can track.
        # Best practice: Create a UNIQUE INDEX.
        
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ext_reviews_unique 
            ON ExternalBusinessReviews (business_id, source, external_review_id);
        """)
        print("✅ Unique Index `idx_ext_reviews_unique` created.")


        # 2. ExternalBusinessStats
        print("\nCanalysing ExternalBusinessStats for duplicates...")
        
        # Stats are usually identified by (business_id, source, date) or (business_id, source, id)
        # The schema says: 
        # id TEXT PRIMARY KEY,
        # business_id TEXT ...
        # source TEXT ...
        # date DATE ... 
        
        # We probably want uniqueness on (business_id, source, date)
        cursor.execute("""
            SELECT business_id, source, date, COUNT(*)
            FROM ExternalBusinessStats
            WHERE date IS NOT NULL
            GROUP BY business_id, source, date
            HAVING COUNT(*) > 1;
        """)
        duplicates_stats = cursor.fetchall()
        print(f"Found {len(duplicates_stats)} groups of duplicates in ExternalBusinessStats.")
        
        if duplicates_stats:
            print("Cleaning up duplicates (keeping the latest updated_at)...")
            cursor.execute("""
                DELETE FROM ExternalBusinessStats a
                USING ExternalBusinessStats b
                WHERE a.business_id = b.business_id
                  AND a.source = b.source
                  AND a.date = b.date
                  AND a.updated_at < b.updated_at;
            """)
            print(f"Deleted {cursor.rowcount} duplicate rows.")
            
        print("Adding UNIQUE CONSTRAINT to ExternalBusinessStats...")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ext_stats_unique 
            ON ExternalBusinessStats (business_id, source, date);
        """)
        print("✅ Unique Index `idx_ext_stats_unique` created.")
        
        # 3. UserServices (Optional but requested: "ExternalBusinessReviews and UserServices lack unique constraints")
        print("\nCanalysing UserServices for duplicates...")
        # UserServices: (business_id, name) should probably be unique?
        
        cursor.execute("""
            SELECT business_id, name, COUNT(*)
            FROM UserServices
            WHERE business_id IS NOT NULL AND name IS NOT NULL
            GROUP BY business_id, name
            HAVING COUNT(*) > 1;
        """)
        duplicates_services = cursor.fetchall()
        print(f"Found {len(duplicates_services)} groups of duplicates in UserServices.")
        
        if duplicates_services:
             print("Cleaning up duplicates (keeping the latest updated_at)...")
             cursor.execute("""
                DELETE FROM UserServices a
                USING UserServices b
                WHERE a.business_id = b.business_id
                  AND a.name = b.name
                  AND a.updated_at < b.updated_at;
            """)
             print(f"Deleted {cursor.rowcount} duplicate rows.")
        
        print("Adding UNIQUE CONSTRAINT to UserServices...")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_services_unique 
            ON UserServices (business_id, name);
        """)
        print("✅ Unique Index `idx_user_services_unique` created.")

        conn.commit()
        print("\n🎉 Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_duplicates_and_add_constraints()
