import os
import sys
import sqlite3

sys.path.append(os.path.join(os.getcwd(), 'src'))
try:
    from safe_db_utils import get_db_connection
except ImportError:
    def get_db_connection():
        return sqlite3.connect('src/reports.db')

def list_admins():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("🔍 Searching for superadmins...")
    cursor.execute("SELECT id, email, name, is_superadmin FROM Users WHERE is_superadmin = 1")
    admins = cursor.fetchall()
    
    if admins:
        for a in admins:
            print(f"✅ FOUND SUPERADMIN: {a['email']} (ID: {a['id']}, Name: {a['name']})")
    else:
        print("❌ No superadmins found.")

    print("\n🔍 Searching for users like 'demyanov'...")
    cursor.execute("SELECT id, email, name, is_superadmin FROM Users WHERE email LIKE '%demyanov%'")
    users = cursor.fetchall()
    
    for u in users:
        print(f"👤 USER: {u['email']} (ID: {u['id']}, Superadmin: {u['is_superadmin']})")

    conn.close()

if __name__ == '__main__':
    list_admins()
