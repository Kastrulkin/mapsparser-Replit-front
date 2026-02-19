
import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database_manager import DatabaseManager

def inspect_networks():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    print("--- 🌐 Inspecting Networks Table ---")
    
    # Check if table exists
    try:
        cursor.execute("SELECT * FROM Networks")
        networks = cursor.fetchall()
        
        print(f"Found {len(networks)} networks:")
        for net in networks:
            # Handle row/tuple
            try:
                nid = net['id']
                name = net['name']
                owner = net['owner_id']
            except:
                nid = net[0]
                name = net[1]
                owner = net[2] # Assuming owner_id is 3rd column, might need adjustment
                
            print(f"  🔗 Network: '{name}' (ID: {nid}) - Owner: {owner}")
            
            # Check active businesses in this network
            cursor.execute("SELECT COUNT(*) as c FROM Businesses WHERE network_id = %s", (nid,))
            count = cursor.fetchone()['c']
            print(f"     -> Linked Businesses: {count}")

    except sqlite3.OperationalError:
        print("❌ Table 'Networks' does not exist?")

    print("\n--- 🏢 Checking Master Kebab Business Network Link ---")
    cursor.execute("SELECT id, name, network_id FROM Businesses WHERE name LIKE '%Master%' OR name LIKE '%Мастер%'")
    rows = cursor.fetchall()
    for row in rows:
        print(f"  Business '{row['name']}' (ID: {row['id']}) uses Network ID: {row['network_id']}")

if __name__ == "__main__":
    inspect_networks()
