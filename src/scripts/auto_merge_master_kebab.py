
import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database_manager import DatabaseManager

def auto_merge():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    print("--- 🤖 Auto-Merging Master Kebab Duplicates ---")
    
    # 1. Find all "Master Kebab" variations
    cursor.execute("""
        SELECT b.id, b.name, b.network_id, b.owner_id, 
               (SELECT COUNT(*) FROM Businesses b2 WHERE b2.network_id = b.network_id) as count
        FROM Businesses b
        WHERE b.name LIKE '%Master%' OR b.name LIKE '%Мастер%'
        ORDER BY count DESC
    """)
    
    candidates = cursor.fetchall()
    
    if not candidates:
        print("❌ No 'Master Kebab' businesses found.")
        return

    # The first one is the "Main" (Target) because we ordered by count DESC
    target = candidates[0]
    print(f"🏆 Main Business: '{target['name']}' (ID: {target['id']}) - Points: {target['count']}")
    
    # All others are duplicates to be merged/deleted
    duplicates = candidates[1:]
    
    if not duplicates:
        print("✅ No duplicates found. Everything looks clean.")
        return
        
    for dup in duplicates:
        print(f"\n🗑 Processing Duplicate: '{dup['name']}' (ID: {dup['id']}) - Points: {dup['count']}")
        
        # 1. Merge points (if any)
        if dup['count'] > 0 and dup['network_id']:
            print(f"   🔄 Moving {dup['count']} points from network {dup['network_id']} to {target['network_id']}...")
            cursor.execute("UPDATE Businesses SET network_id = %s WHERE network_id = %s", 
                           (target['network_id'], dup['network_id']))
        
        # 2. Delete the business entry itself
        print(f"   ❌ Deleting business entry {dup['id']}...")
        cursor.execute("DELETE FROM Businesses WHERE id = %s", (dup['id'],))
        
    db.conn.commit()
    print("\n✅ Merge Complete! All points are now under the Main Business.")

if __name__ == "__main__":
    auto_merge()
