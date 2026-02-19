import os
import sys
import sqlite3

# Add src to path to import utils
sys.path.append(os.path.join(os.getcwd(), 'src'))
try:
    from safe_db_utils import get_db_connection
except ImportError:
    def get_db_connection():
        return sqlite3.connect('src/reports.db')

def fix_permissions():
    print("🔧 Starting permission fix...")
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Get User IDs
    cursor.execute("SELECT id FROM Users WHERE email = 'tislitskaya@yandex.ru'")
    tislitskaya = cursor.fetchone()
    
    cursor.execute("SELECT id FROM Users WHERE email = 'demyanovap@yandex.ru'")
    demyanovap = cursor.fetchone()

    if not tislitskaya:
        print("❌ User tislitskaya@yandex.ru not found")
        return
    if not demyanovap:
        print("❌ User demyanovap@yandex.ru not found")
        return

    tislitskaya_id = tislitskaya['id']
    demyanovap_id = demyanovap['id']

    print(f"👤 Tislitskaya ID: {tislitskaya_id}")
    print(f"👤 Demyanovap ID: {demyanovap_id}")

    # 2. Identify businesses to transfer
    # We want to keep 'Оливер' with Tislitskaya, move everything else to Demyanovap
    print("\n🔍 Analyzing businesses owned by Tislitskaya...")
    
    cursor.execute("SELECT id, name FROM Businesses WHERE owner_id = %s", (tislitskaya_id,))
    businesses = cursor.fetchall()
    
    to_transfer = []
    kept = []

    for b in businesses:
        name_lower = b['name'].lower()
        if 'оливер' in name_lower or 'oliver' in name_lower:
            kept.append(b['name'])
        else:
            to_transfer.append((b['id'], b['name']))

    print(f"✅ Keeping {len(kept)} businesses with Tislitskaya: {', '.join(kept)}")
    print(f"🚀 Moving {len(to_transfer)} businesses to Demyanovap...")

    # 3. Execute Transfer
    if to_transfer:
        ids_to_transfer = [b[0] for b in to_transfer]
        # SQLite doesn't support list parameters directly easily in all versions, iterate or use IN
        placeholders = ','.join(['%s'] * len(ids_to_transfer))
        
        cursor.execute(f"""
            UPDATE Businesses 
            SET owner_id = %s 
            WHERE id IN ({placeholders})
        """, [demyanovap_id] + ids_to_transfer)
        
        affected = cursor.rowcount
        conn.commit()
        print(f"🎉 Successfully transferred {affected} businesses to demyanovap@yandex.ru")
        
        # Verify
        print("\n🔍 Verification:")
        for bid, bname in to_transfer:
             cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (bid,))
             new_owner = cursor.fetchone()[0]
             status = "OK" if new_owner == demyanovap_id else "FAIL"
             print(f"   - {bname}: {status}")

    else:
        print("Nothing to transfer.")

    conn.close()

if __name__ == '__main__':
    fix_permissions()
