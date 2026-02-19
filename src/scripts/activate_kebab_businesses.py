import os
import sys
import sqlite3

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
try:
    from safe_db_utils import get_db_connection
except ImportError:
    def get_db_connection():
        return sqlite3.connect('src/reports.db')

def activate_kebabs():
    print("🔌 Checking Kebab Businesses Activity Status...")
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Check current status
    cursor.execute("""
        SELECT id, name, is_active, owner_id 
        FROM Businesses 
        WHERE name LIKE '%kebab%' OR name LIKE '%кебаб%'
    """)
    businesses = cursor.fetchall()
    
    if not businesses:
        print("❌ No Kebab businesses found!")
        return

    inactive_count = 0
    active_count = 0
    
    print(f"📦 Found {len(businesses)} Kebab businesses.")
    
    ids_to_activate = []
    
    for b in businesses:
        is_active = b['is_active']
        # Проверяем на 0, False, None (если None считаем активным в коде, но лучше явно проставить 1)
        if is_active == 0 or is_active == '0':
            print(f"   🔴 Inactive: {b['name']} (ID: {b['id']})")
            inactive_count += 1
            ids_to_activate.append(b['id'])
        else:
            active_count += 1
            # print(f"   🟢 Active: {b['name']}")

    print(f"\n📊 Stats: {active_count} active, {inactive_count} inactive.")

    # 2. Activate if needed
    if ids_to_activate:
        print(f"\n⚡ Activating {len(ids_to_activate)} businesses...")
        for b_id in ids_to_activate:
            cursor.execute("UPDATE Businesses SET is_active = 1 WHERE id = %s", (b_id,))
        
        conn.commit()
        print("✅ Activation complete.")
    else:
        print("✨ All Kebabs are already active.")

    conn.close()

if __name__ == '__main__':
    activate_kebabs()
