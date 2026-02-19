
import sys
import os
import sqlite3
import json

# Add module to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database_manager import DatabaseManager

def debug_network(business_id):
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    print(f"--- Debugging Business ID: {business_id} ---")
    
    # 1. Check the business itself
    cursor.execute("SELECT id, name, network_id FROM Businesses WHERE id = %s", (business_id,))
    bus = cursor.fetchone()
    if not bus:
        print("❌ Business not found in DB")
        return
        
    print(f"Business: {bus['name']}")
    print(f"Network ID: {bus['network_id']}")
    
    if not bus['network_id']:
        print("❌ Business has no network_id")
        return

    # 2. Check what get_businesses_by_network returns
    print(f"\n--- Querying network locations for Network ID: {bus['network_id']} ---")
    locations = db.get_businesses_by_network(bus['network_id'])
    print(f"Found {len(locations)} locations via helper method:")
    for loc in locations:
        print(f" - {loc['name']} ({loc['id']})")
        
    # 3. Manual query to see if there are others
    print("\n--- Manual SQL check (SELECT * FROM Businesses WHERE network_id = %s) ---")
    cursor.execute("SELECT id, name, is_active FROM Businesses WHERE network_id = %s", (bus['network_id'],))
    raw_locs = cursor.fetchall()
    print(f"Found {len(raw_locs)} rows in DB:")
    for row in raw_locs:
        status = "Active" if row['is_active'] else "Inactive"
        print(f" - {row['name']} ({status})")

if __name__ == "__main__":
    # Hardcoded ID for one of the Kebab businesses or passed via arg
    # Trying the one from the screenshot/logs if known, otherwise searching for "Master Kebab"
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("SELECT id FROM Businesses WHERE name LIKE '%Master Kebab%' LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        debug_network(row['id'])
    else:
        print("Could not find 'Master Kebab' to auto-test")
