
import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database_manager import DatabaseManager

def inspect_all():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    print("--- 🔍 Searching for ALL 'Master'/'Мастер' businesses ---")
    
    cursor.execute("""
        SELECT b.id, b.name, b.network_id, b.owner_id, u.email,
               (SELECT COUNT(*) FROM Businesses b2 WHERE b2.network_id = b.network_id) as net_count
        FROM Businesses b
        LEFT JOIN Users u ON b.owner_id = u.id
        WHERE b.name LIKE '%Master%' OR b.name LIKE '%Мастер%'
    """)
    
    rows = cursor.fetchall()
    
    for row in rows:
        # sqlite3.Row access requires iterating or by index if factory not set custom in script
        # But DatabaseManager might set it. Let's try to be safe.
        try:
            name = row['name']
            bid = row['id']
            net_id = row['network_id']
            owner = row['email']
            count = row['net_count']
        except:
            # Fallback for tuple
            bid = row[0]
            name = row[1]
            net_id = row[2]
            owner = row[4]
            count = row[5]
            
        print(f"\n🏢 Business: {name}")
        print(f"   ID: {bid}")
        print(f"   Owner: {owner}")
        print(f"   Network ID: {net_id}")
        print(f"   Network Size: {count}")

if __name__ == "__main__":
    inspect_all()
