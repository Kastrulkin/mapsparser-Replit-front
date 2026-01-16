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

def force_activate():
    print("🚀 Force Activating ALL Businesses...")
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Activate ALL businesses
    cursor.execute("SELECT count(*) FROM Businesses WHERE is_active = 0 OR is_active IS NULL")
    count = cursor.fetchone()[0]
    print(f"found {count} inactive businesses.")
    
    cursor.execute("UPDATE Businesses SET is_active = 1 WHERE is_active = 0 OR is_active IS NULL")
    print(f"✅ Activated {cursor.rowcount} businesses.")

    # 2. Double check network for Immer Jung and Organika
    print("\n🧹 Ensuring independence of non-Kebab businesses...")
    
    # List of known independents
    independents = ['Immer Jung', 'Organika', 'Органика', 'Шььук Огтпб']
    
    for name in independents:
        cursor.execute("UPDATE Businesses SET network_id = NULL WHERE name LIKE ?", (f'%{name}%',))
        if cursor.rowcount > 0:
            print(f"   - Decoupled {name} from networks.")

    # 3. Ensure Master Kebab IS in a network
    # Start by finding or creating the network
    cursor.execute("SELECT id FROM Users WHERE email = 'demyanovap@yandex.ru'")
    user = cursor.fetchone()
    if user:
        owner_id = user[0]
        cursor.execute("SELECT id FROM Networks WHERE name LIKE '%Master Kebab%' OR name LIKE '%Мастер Кебаб%'")
        nw = cursor.fetchone()
        if nw:
            nw_id = nw[0]
            cursor.execute("""
                UPDATE Businesses 
                SET network_id = ? 
                WHERE (name LIKE '%Kebab%' OR name LIKE '%Кебаб%') 
                AND (network_id IS NULL OR network_id != ?)
            """, (nw_id, nw_id))
            print(f"   - Linked {cursor.rowcount} Kebab businesses to network.")

    conn.commit()
    conn.close()
    print("\n✨ Done. Please refresh the dashboard.")

if __name__ == '__main__':
    force_activate()
