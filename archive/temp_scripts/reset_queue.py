import sqlite3
import os

# Explicitly point to src/reports.db
DB_PATH = os.path.join(os.getcwd(), 'src', 'reports.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    print("Reseting stuck tasks...")
    cursor.execute("UPDATE ParseQueue SET status='pending' WHERE status='processing'")
    print(f"Reset {cursor.rowcount} tasks to pending.")
    conn.commit()
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
