
import sqlite3
import os

DB_PATH = 'src/reports.db'

def dump_schema():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cursor.fetchall()
    
    print(f"--- TABLES IN {DB_PATH} ---")
    for table in tables:
        table_name = table[0]
        print(f"Table: {table_name}")
        
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            cid, name, type, notnull, dflt_value, pk = col
            print(f"  - {name} ({type})")
        print("")
        
    conn.close()

if __name__ == "__main__":
    dump_schema()
