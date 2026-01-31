
import sys
import os
import sqlite3
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database_manager import DatabaseManager

def inspect_conflicts():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    print("--- Searching for businesses with 'Master' or 'Мастер' in name ---")
    
    cursor.execute("""
        SELECT b.id, b.name, b.network_id, b.owner_id, u.email as owner_email, u.name as owner_name, 
               (SELECT COUNT(*) FROM Businesses b2 WHERE b2.network_id = b.network_id) as network_count
        FROM Businesses b
        LEFT JOIN Users u ON b.owner_id = u.id
        WHERE b.name LIKE '%Master%' OR b.name LIKE '%Мастер%'
    """)
    
    rows = cursor.fetchall()
    
    for row in rows:
        print(f"\nBusiness: {row['name']}")
        print(f"  ID: {row['id']}")
        print(f"  Owner: {row['owner_name']} ({row['owner_email']})")
        print(f"  Network ID: {row['network_id']}")
        print(f"  Points in Network: {row['network_count']}")

if __name__ == "__main__":
    inspect_conflicts()
