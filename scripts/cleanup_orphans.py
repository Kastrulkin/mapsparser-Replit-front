import sqlite3
import os

DB_NAME = 'reports.db'

def cleanup_orphans():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print(f"🧹 Starting cleanup on {DB_NAME}...")
    
    try:
        # 1. UserServices with NULL business_id -> Hard Delete
        cursor.execute("SELECT COUNT(*) FROM UserServices WHERE business_id IS NULL")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"🗑️  Deleting {count} UserServices with NULL business_id...")
            cursor.execute("DELETE FROM UserServices WHERE business_id IS NULL")
        else:
            print("✅ No UserServices with NULL business_id found.")

        # 2. UserServices checking invalid business_id (Referential Integrity)
        # Find business_ids in UserServices that don't exist in Businesses
        cursor.execute("""
            SELECT COUNT(*) FROM UserServices 
            WHERE business_id NOT IN (SELECT id FROM Businesses)
        """)
        bad_ref_count = cursor.fetchone()[0]
        if bad_ref_count > 0:
             print(f"🗑️  Deleting {bad_ref_count} UserServices referencing non-existent businesses...")
             cursor.execute("""
                DELETE FROM UserServices 
                WHERE business_id NOT IN (SELECT id FROM Businesses)
             """)
        else:
             print("✅ All UserServices reference valid businesses.")

        # 3. UserServices with NULL user_id -> Try to assign to Business Owner
        cursor.execute("SELECT COUNT(*) FROM UserServices WHERE user_id IS NULL")
        null_user_count = cursor.fetchone()[0]
        
        if null_user_count > 0:
            print(f"🔄 Found {null_user_count} UserServices with NULL user_id. Attempting to fix...")
            
            # Update user_id from Businesses table
            cursor.execute("""
                UPDATE UserServices
                SET user_id = (SELECT owner_id FROM Businesses WHERE Businesses.id = UserServices.business_id)
                WHERE user_id IS NULL 
                AND business_id IN (SELECT id FROM Businesses WHERE owner_id IS NOT NULL)
            """)
            print(f"   updated {cursor.rowcount} records assigned to business owner.")
            
            # Check remaining NULLs (Orphans where Business has no owner)
            cursor.execute("SELECT COUNT(*) FROM UserServices WHERE user_id IS NULL")
            remaining = cursor.fetchone()[0]
            
            if remaining > 0:
                print(f"🗑️  Deleting {remaining} UserServices (Business has no owner too)...")
                cursor.execute("DELETE FROM UserServices WHERE user_id IS NULL")
        else:
            print("✅ No UserServices with NULL user_id found.")

        # 4. Cleanup Businesses with NULL owner_id? (Optional, plan says only Cleanup UserServices orphans)
        # But if we want Strict FKs, businesses without owners are problematic if we add FK owner_id -> Users.id
        # Let's check constraints plan. "Foreign Key: USERSERVICES -> User". Nothing about Business->User yet, but good to check.
        
        conn.commit()
        print("🎉 Cleanup completed successfully.")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during cleanup: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup_orphans()
