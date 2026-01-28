
import sqlite3
import os
import sys

DB_PATH = 'reports.db'

def fix_oliver():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Find user Oliver
        print("--- Finding User: tislitskaya@yandex.ru ---")
        cursor.execute("SELECT id, email FROM Users WHERE email = ?", ('tislitskaya@yandex.ru',))
        oliver = cursor.fetchone()
        
        if not oliver:
            print("User tislitskaya@yandex.ru NOT FOUND")
            return

        oliver_id = oliver['id']
        print(f"User Found: {oliver_id}")

        # 2. Find Business
        cursor.execute("SELECT id, name, network_id FROM Businesses WHERE owner_id = ?", (oliver_id,))
        businesses = cursor.fetchall()
        
        for b in businesses:
            print(f"Checking Business: {b['name']} (ID: {b['id']})")
            print(f"Current Network ID: {b['network_id']}")
            
            if b['network_id'] is not None:
                print(f"⚠️ FIXED: Removing from network...")
                cursor.execute("UPDATE Businesses SET network_id = NULL WHERE id = ?", (b['id'],))
                conn.commit()
                print("✅ Successfully unlinked from network.")
            else:
                print("✅ Already independent (Network ID is NULL).")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_oliver()
