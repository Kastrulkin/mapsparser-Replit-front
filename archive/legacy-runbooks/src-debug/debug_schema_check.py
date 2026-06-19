
import sqlite3
import os

DB_PATH = 'src/reports.db'

def check_schema():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Check for ANY table looking like MapParse...
    print("--- Searching for tables like 'MapPars%' ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'MapPars%';")
    tables = cursor.fetchall()
    
    for t in tables:
        table_name = t[0]
        print(f"\nTABLE: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        col_names = [c[1] for c in columns]
        print(f"Columns: {col_names}")
        
        if 'title' in col_names:
            print("✅ 'title' column EXISTS.")
        else:
            print("❌ 'title' column MISSING!")

    conn.close()

if __name__ == "__main__":
    check_schema()
