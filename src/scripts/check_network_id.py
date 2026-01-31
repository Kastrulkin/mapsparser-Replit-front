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

def check_network_ids():
    print("🔍 Checking network_id for Kebab businesses...")
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, network_id, is_active 
        FROM Businesses 
        WHERE name LIKE '%Kebab%' OR name LIKE '%Кебаб%'
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("❌ No Kebab businesses found")
        return

    print(f"📦 Found {len(rows)} businesses:")
    for row in rows:
        nid = row['network_id']
        print(f"   - {row['name']} (Active: {row['is_active']}) -> NetworkID: {nid if nid else '❌ NULL'}")

    conn.close()

if __name__ == '__main__':
    check_network_ids()
