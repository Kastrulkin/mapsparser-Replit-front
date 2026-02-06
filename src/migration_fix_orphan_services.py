
import os
import sys

# Add src to path just in case
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from safe_db_utils import get_db_connection, backup_database

def fix_orphan_services():
    print("🚀 Starting data migration: Fix Orphan UserServices")
    
    # 1. Backup
    backup_path = backup_database()
    if not backup_path:
        print("❌ Backup failed, aborting migration.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 2. Find orphans
        cursor.execute("SELECT id, business_id FROM UserServices WHERE user_id IS NULL")
        orphans = cursor.fetchall()
        
        print(f"📊 Found {len(orphans)} orphan services.")
        
        fixed_count = 0
        skipped_count = 0
        
        for row in orphans:
            service_id = row['id']
            business_id = row['business_id']
            
            # 3. Find owner
            cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
            owner_row = cursor.fetchone()
            
            if owner_row and owner_row['owner_id']:
                owner_id = owner_row['owner_id']
                cursor.execute("UPDATE UserServices SET user_id = ? WHERE id = ?", (owner_id, service_id))
                fixed_count += 1
            else:
                print(f"⚠️ Could not find owner for business {business_id} (Service ID: {service_id})")
                skipped_count += 1
                
        conn.commit()
        print(f"✅ Migration complete. Fixed: {fixed_count}, Skipped: {skipped_count}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_orphan_services()
