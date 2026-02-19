
import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database_manager import DatabaseManager

def fix_novamed():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    print("--- 🩹 Fixing Novamed Network Issue ---")
    
    # NOVAMED ID from previous logs
    NOVAMED_ID = '38a11c0e-6eea-4fdc-90d6-66f21af9adce'
    
    # Check current status
    cursor.execute("SELECT id, name, network_id FROM Businesses WHERE id = %s", (NOVAMED_ID,))
    novamed = cursor.fetchone()
    
    if not novamed:
        # Try searching by name if ID changed (unlikely)
        cursor.execute("SELECT id, name, network_id FROM Businesses WHERE name LIKE '%Novamed%' OR name LIKE '%Новамед%'")
        novamed = cursor.fetchone()
        
    if not novamed:
        print("❌ Novamed not found")
        return
        
    print(f"found: {novamed['name']} (ID: {novamed['id']})")
    print(f"Current Network ID: {novamed['network_id']}")
    
    if novamed['network_id']:
        print("Removing from network...")
        cursor.execute("UPDATE Businesses SET network_id = NULL WHERE id = %s", (novamed['id'],))
        db.conn.commit()
        print("✅ Novamed is now independent (network_id = NULL)")
    else:
        print("✅ Novamed is already independent.")

if __name__ == "__main__":
    fix_novamed()
