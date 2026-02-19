import os
import sys
import sqlite3
import uuid
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
try:
    from safe_db_utils import get_db_connection
except ImportError:
    def get_db_connection():
        # Fallback
        for p in ['src/reports.db', 'reports.db', '../reports.db']:
            if os.path.exists(p):
                return sqlite3.connect(p)
        return sqlite3.connect('src/reports.db')

def fix_network():
    print("🌐 Starting Network Fix for Demyanovap...")
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Get Owner ID
    cursor.execute("SELECT id FROM Users WHERE email = 'demyanovap@yandex.ru'")
    user = cursor.fetchone()
    if not user:
        print("❌ User demyanovap@yandex.ru not found")
        return
    owner_id = user['id']
    print(f"👤 Owner ID: {owner_id}")

    # 2. Check/Create Network
    network_name = "Сеть Мастер Кебаб"
    cursor.execute("SELECT id FROM Networks WHERE owner_id = %s AND name = %s", (owner_id, network_name))
    network = cursor.fetchone()

    network_id = None
    if network:
        network_id = network['id']
        print(f"✅ Found existing network: {network_name} ({network_id})")
    else:
        print(f"⚠️  Network '{network_name}' not found. Creating...")
        network_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO Networks (id, name, owner_id, description, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (network_id, network_name, owner_id, "Автоматически созданная сеть для Кебабов", 
              datetime.now().isoformat(), datetime.now().isoformat()))
        print(f"✨ Created network: {network_id}")

    # 3. Find businesses to link
    # We link ALL businesses owned by this user because they are all Kebabs based on previous context
    cursor.execute("SELECT id, name, network_id FROM Businesses WHERE owner_id = %s", (owner_id,))
    businesses = cursor.fetchall()
    
    count_linked = 0
    count_updated = 0
    
    print(f"\n📦 Found {len(businesses)} businesses owned by user.")
    
    for b in businesses:
        # SAFETY CHECK: Only link if name contains "Kebab" or "Кебаб"
        name_lower = b['name'].lower()
        if 'kebab' not in name_lower and 'кебаб' not in name_lower:
            print(f"⚠️ SKIPPING non-kebab business: {b['name']} (ID: {b['id']})")
            continue

        if b['network_id'] == network_id:
            count_linked += 1
        else:
            # Update network_id
            cursor.execute("UPDATE Businesses SET network_id = %s WHERE id = %s", (network_id, b['id']))
            count_updated += 1
            print(f"🔗 Linked: {b['name']}")

    conn.commit()
    conn.close()
    
    print(f"\n🎉 Summary:")
    print(f"   - Already linked: {count_linked}")
    print(f"   - Updated/Linked: {count_updated}")
    print(f"   - Total in Network: {count_linked + count_updated}")

if __name__ == '__main__':
    fix_network()
