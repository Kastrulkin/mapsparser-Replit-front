import sqlite3
import os

# Explicitly point to src/reports.db
DB_PATH = os.path.join(os.getcwd(), 'src', 'reports.db')

print(f"Checking DB at: {DB_PATH}")

if not os.path.exists(DB_PATH):
    print("❌ DB file does not exist!")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables:")
    for t in tables:
        name = t[0]
        cursor.execute(f"SELECT COUNT(*) FROM {name}")
        count = cursor.fetchone()[0]
        print(f"  - {name}: {count}")

    try:
        cursor.execute("SELECT * FROM MapParseResults ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            # Map columns by name
            cols = [d[0] for d in cursor.description]
            res = dict(zip(cols, row))
            print("\nLast Parse Result:")
            print(f"  unanswered_reviews_count: {res.get('unanswered_reviews_count')}")
            print(f"  reviews_count: {res.get('reviews_count')}")
            print(f"  news_count: {res.get('news_count')}")
            print(f"  report_path: {res.get('report_path')}")
        else:
            print("\nNo Parse Results found.")
            
    except Exception as e:
        print(f"  Error reading parse results: {e}")

    print("\nQueue Status:")
    try:
        cursor.execute("SELECT id, status, updated_at FROM ParseQueue ORDER BY updated_at DESC LIMIT 5")
        rows = cursor.fetchall()
        for r in rows:
            print(f"  Task {r[0]}: {r[1]} at {r[2]}")
    except:
        print("  (ParseQueue table not found or error)")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
