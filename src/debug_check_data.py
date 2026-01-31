import sqlite3
import os

# Пытаемся найти правильную БД
POSSIBLE_PATHS = [
    "/var/www/html/src/reports.db",
    "src/reports.db",
    "reports.db"
]

DB_NAME = "/var/www/html/src/reports.db"
if not os.path.exists(DB_NAME):
    print(f"❌ '{DB_NAME}' does not exist. Falling back to local.")
    DB_NAME = "src/reports.db"

print(f"📁 Checking DB: {DB_NAME}")

if not DB_NAME:
    print("❌ Cannot find reports.db in standard locations")
    exit(1)
    
print(f"📁 Checking DB: {DB_NAME}")

def check_services(business_id):
    if not os.path.exists(DB_NAME):
        print(f"❌ Database {DB_NAME} not found!")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check Services
    cursor.execute("SELECT COUNT(*) FROM UserServices WHERE business_id = ?", (business_id,))
    count = cursor.fetchone()[0]
    print(f"📦 Services found in DB for {business_id}: {count}")
    
    if count > 0:
        cursor.execute("SELECT name, price FROM UserServices WHERE business_id = ? LIMIT 5", (business_id,))
        rows = cursor.fetchall()
        print("🔹 Sample services:")
        for r in rows:
            print(f"   - {r[0]}: {r[1]}")
            
    # Check External Stats
    cursor.execute("SELECT COUNT(*) FROM ExternalBusinessStats WHERE business_id = ?", (business_id,))
    stats_count = cursor.fetchone()[0]
    print(f"📊 Stats entries in DB: {stats_count}")

    cursor.execute("SELECT id, name, owner_id FROM Businesses")
    rows = cursor.fetchall()
    print(f"📋 Total Businesses in DB: {len(rows)}")
    found = False
    for r in rows:
        print(f"   - {r[0]}: {r[1]} (Owner: {r[2]})")
        if r[0] == business_id:
            found = True
            
    if not found:
        print(f"❌ '{business_id}' NOT found in the list above.")
    else:
        print(f"✅ '{business_id}' FOUND.")

    conn.close()

if __name__ == "__main__":
    check_services("533c1300-8a54-43a8-aa1f-69a8ed9c24ba")
