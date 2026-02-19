
import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database_manager import DatabaseManager

def fix_networks_final():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    print("--- 🚀 Final Network Fix ---")
    
    # CONSTANTS from inspection
    BIG_NET_ID = '55602996-cc00-4f1e-b017-38fa3b4d5965' # Мастер Кебаб (163)
    SMALL_NET_ID = 'b1c19649-80a2-4a4a-97f9-81e913551d1c' # Сеть Мастер Кебаб (1)
    SUPERADMIN_ID = 'a453a8b3-3b26-4c4e-81e3-1b973d4b8755'
    
    # 1. Transfer Big Network ownership to SuperAdmin
    print(f"1️⃣ Transferring Big Network ({BIG_NET_ID}) to SuperAdmin...")
    cursor.execute("UPDATE Networks SET owner_id = %s WHERE id = %s", (SUPERADMIN_ID, BIG_NET_ID))
    
    # 2. Move businesses from Small Network to Big Network
    print(f"2️⃣ Moving businesses from Small Network ({SMALL_NET_ID}) to Big Network...")
    cursor.execute("UPDATE Businesses SET network_id = %s WHERE network_id = %s", (BIG_NET_ID, SMALL_NET_ID))
    
    # 3. Delete Small Network
    print(f"3️⃣ Deleting Small Network ({SMALL_NET_ID})...")
    cursor.execute("DELETE FROM Networks WHERE id = %s", (SMALL_NET_ID,))
    
    # 4. Rename Big Network to "Сеть Мастер Кебаб" (optional, looks better)
    print("4️⃣ Renaming Big Network to 'Сеть Мастер Кебаб'...")
    cursor.execute("UPDATE Networks SET name = 'Сеть Мастер Кебаб' WHERE id = %s", (BIG_NET_ID,))
    
    db.conn.commit()
    print("\n✅ Verification:")
    
    cursor.execute("SELECT name, owner_id FROM Networks WHERE id = %s", (BIG_NET_ID,))
    row = cursor.fetchone()
    if row:
        print(f"   Network '{row['name']}' owner: {row['owner_id']}")
    
    cursor.execute("SELECT COUNT(*) as c FROM Businesses WHERE network_id = %s", (BIG_NET_ID,))
    count = cursor.fetchone()['c']
    print(f"   Total businesses in network: {count}")
    
    cursor.execute("SELECT COUNT(*) as c FROM Networks WHERE id = %s", (SMALL_NET_ID,))
    small_exists = cursor.fetchone()['c']
    print(f"   Small network exists: {small_exists > 0}")

if __name__ == "__main__":
    fix_networks_final()
