
import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database_manager import DatabaseManager

def fix_ownership():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    print("--- 🛠 Fixing Master Kebab Ownership ---")
    
    # 1. Find SuperAdmin ID
    cursor.execute("SELECT id FROM Users WHERE email = 'demyanovap@yandex.ru'")
    admin = cursor.fetchone()
    if not admin:
        print("❌ SuperAdmin not found!")
        return
    admin_id = admin['id']
    print(f"✅ Found SuperAdmin ID: {admin_id}")

    # 2. Find "Мастер Кебаб" (The big network)
    # We look for the one with many network items OR specific name
    cursor.execute("""
        SELECT b.id, b.network_id, b.owner_id, 
               (SELECT COUNT(*) FROM Businesses b2 WHERE b2.network_id = b.network_id) as count
        FROM Businesses b
        WHERE b.name = 'Мастер Кебаб'
    """)
    big_business = cursor.fetchone()
    
    if not big_business:
        print("❌ 'Мастер Кебаб' not found")
        return

    print(f"Found 'Мастер Кебаб': ID={big_business['id']}, Owner={big_business['owner_id']}, Points={big_business['count']}")

    # 3. Find "Сеть Мастер Кебаб" (The small duplicate)
    cursor.execute("SELECT id, network_id FROM Businesses WHERE name = 'Сеть Мастер Кебаб'")
    small_business = cursor.fetchone()
    
    if small_business:
        print(f"Found 'Сеть Мастер Кебаб' (Duplicate): ID={small_business['id']}")
        
        # Merge logic: Move the single point from small network to big network
        small_net_id = small_business['network_id']
        big_net_id = big_business['network_id']
        
        if small_net_id and big_net_id:
             cursor.execute("UPDATE Businesses SET network_id = %s WHERE network_id = %s", (big_net_id, small_net_id))
             print(f"🔄 Merged points from small network {small_net_id} to big {big_net_id}")
             
        # Delete the duplicate business listing itself
        cursor.execute("DELETE FROM Businesses WHERE id = %s", (small_business['id'],))
        print("🗑 Deleted duplicate business 'Сеть Мастер Кебаб'")
    
    # 4. Transfer ownership of the Big Business to SuperAdmin
    if big_business['owner_id'] != admin_id:
        cursor.execute("UPDATE Businesses SET owner_id = %s WHERE id = %s", (admin_id, big_business['id']))
        print(f"👑 Transferred ownership of 'Мастер Кебаб' to SuperAdmin")
        
    db.conn.commit()
    print("\n✅ Verification:")
    cursor.execute("SELECT name, owner_id FROM Businesses WHERE id = %s", (big_business['id'],))
    res = cursor.fetchone()
    print(f"Business '{res['name']}' is now owned by {res['owner_id']}")
    
    cursor.execute("SELECT COUNT(*) as c FROM Businesses WHERE network_id = %s", (big_business['network_id'],))
    count = cursor.fetchone()['count']
    print(f"Total points in network: {count}")

if __name__ == "__main__":
    fix_ownership()
