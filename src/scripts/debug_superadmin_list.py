import os
import sys
import sqlite3
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
try:
    from safe_db_utils import get_db_connection
    from database_manager import DatabaseManager
except ImportError:
    print("Failed imports")
    sys.exit(1)

def debug_superadmin_visibility():
    print("🔍 Debugging Superadmin Business Visibility...")
    
    # 1. Check User Status
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, is_superadmin, email FROM Users WHERE email = 'demyanovap@yandex.ru'")
    user = cursor.fetchone()
    if not user:
        print("❌ User not found")
        return
    
    print(f"👤 User: {user[2]} (ID: {user[0]})")
    print(f"👑 Is Superadmin: {user[1]}")
    
    user_id = user[0]
    
    # 2. Mimic Logic likely used in /api/auth/me for superadmin
    db = DatabaseManager()
    
    print("\n--- Method 1: get_all_businesses (Likely used) ---")
    try:
        all_businesses = db.get_all_businesses()
        print(f"📦 Total businesses found: {len(all_businesses)}")
        kebab_count = 0
        for b in all_businesses:
            if 'kebab' in b['name'].lower() or 'кебаб' in b['name'].lower():
                kebab_count += 1
                if kebab_count <= 5:
                    print(f"   - Found Kebab: {b['name']} (Owner: {b['owner_name']}, Network: {b.get('network_id')})")
        print(f"   Total Kebab businesses in list: {kebab_count}")
    except Exception as e:
        print(f"❌ Error in get_all_businesses: {e}")

    print("\n--- Method 2: get_all_users_with_businesses (Used in admin panel) ---")
    try:
        data = db.get_all_users_with_businesses()
        # Find demyanovap
        demyanov = next((u for u in data if u['email'] == 'demyanovap@yandex.ru'), None)
        if demyanov:
            print(f"   Found demyanovap in list.")
            print(f"   Direct businesses: {len(demyanov.get('direct_businesses', []))}")
            for b in demyanov.get('direct_businesses', []):
                 print(f"     - Direct: {b['name']}")
                 
            networks = demyanov.get('networks', [])
            print(f"   Networks: {len(networks)}")
            for n in networks:
                print(f"     - Network: {n['name']} (Businesses: {len(n['businesses'])})")
    except Exception as e:
        print(f"❌ Error in get_all_users_with_businesses: {e}")

    db.close()

if __name__ == '__main__':
    debug_superadmin_visibility()
