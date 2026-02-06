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

def refine_network():
    print("🧹 Refining Master Kebab Network...")
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Find the network
    cursor.execute("SELECT id FROM Networks WHERE name LIKE '%Master Kebab%' OR name LIKE '%Мастер Кебаб%'")
    network = cursor.fetchone()
    
    if not network:
        print("❌ Network not found")
        return
        
    network_id = network['id']
    print(f"🌐 Network ID: {network_id}")

    # 2. Get all businesses in this network
    cursor.execute("SELECT id, name FROM Businesses WHERE network_id = ?", (network_id,))
    businesses = cursor.fetchall()
    
    removed_count = 0
    kept_count = 0
    
    for b in businesses:
        name = b['name'].lower()
        if 'kebeb' in name or 'kebab' in name or 'кебаб' in name:
            kept_count += 1
        else:
            print(f"   ⚠️  Removing non-kebab business from network: {b['name']}")
            cursor.execute("UPDATE Businesses SET network_id = NULL WHERE id = ?", (b['id'],))
            removed_count += 1
            
    conn.commit()
    conn.close()
    
    print("\n🎉 Done:")
    print(f"   - Kept: {kept_count}")
    print(f"   - Removed: {removed_count}")

if __name__ == '__main__':
    refine_network()
