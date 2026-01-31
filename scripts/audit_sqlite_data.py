import sqlite3
import os

DB_PATH = 'src/reports.db'  # Actual path from safe_db_utils

def audit_database():
    global DB_PATH
    if not os.path.exists(DB_PATH):
        # Try finding it in current dir or common locations if exact path unknown
        potential_paths = ['reports.db', 'data/reports.db', 'instance/reports.db']
        found = False
        for p in potential_paths:
            if os.path.exists(p):
                DB_PATH = p
                found = True
                break
        if not found:
            print(f"❌ Database not found at {DB_PATH}")
            return

    print(f"🔍 Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    found_issues = False

    print(f"📋 Scanning {len(tables)} tables for '?' character in TEXT columns...")
    
    for table in tables:
        # Get TEXT columns
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        text_cols = [col[1] for col in columns if 'TEXT' in col[2].upper()]
        
        if not text_cols:
            continue

        for col in text_cols:
            query = f"SELECT rowid, {col} FROM {table} WHERE {col} LIKE '%?%'"
            try:
                cursor.execute(query)
                rows = cursor.fetchall()
                if rows:
                    if not found_issues:
                        print("\n⚠️  POTENTIAL ISSUES FOUND:")
                        found_issues = True
                    print(f"  [Table: {table}, Column: {col}] -> {len(rows)} rows contain '?'")
                    # Print sample
                    sample = rows[0][1]
                    if len(sample) > 50:
                        sample = sample[:50] + "..."
                    print(f"    Sample: \"{sample}\"")
            except Exception as e:
                print(f"  Error scanning {table}.{col}: {e}")

    if not found_issues:
        print("\n✅ No '?' characters found in text columns (Safe for naive adaptation).")
    else:
        print("\n❌ Issues found! Adaptation must handle string literals carefully.")

    conn.close()

if __name__ == "__main__":
    audit_database()
