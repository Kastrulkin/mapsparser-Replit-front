import os
import sys
import sqlite3

# Add src to path to import utils
sys.path.append(os.path.join(os.getcwd(), 'src'))
try:
    from safe_db_utils import get_db_connection
except ImportError:
    # Fallback manual connection if imports fail
    def get_db_connection():
        return sqlite3.connect('src/reports.db')

def inspect_access():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("🔍 Inspecting Tislitskaya...")
    cursor.execute("SELECT id, email, is_superadmin, name FROM Users WHERE email = 'tislitskaya@yandex.ru'")
    user = cursor.fetchone()
    
    if not user:
        print("❌ User not found")
        return

    print(f"User ID: {user['id']}")
    print(f"Email: {user['email']}")
    print(f"Is Superadmin: {user['is_superadmin']}")
    print(f"Name: {user['name']}")

    print("\n🔍 Inspecting 'Мастер Кебаб' / 'Кебаб' businesses...")
    cursor.execute("SELECT id, name, owner_id FROM Businesses WHERE name LIKE '%Кебаб%'")
    businesses = cursor.fetchall()

    for b in businesses:
        print(f"\nBusiness: {b['name']} (ID: {b['id']})")
        print(f"Owner ID: {b['owner_id']}")
        
        if b['owner_id'] == user['id']:
            print("⚠️  OWNED BY TISLITSKAYA")
        else:
            print("✅ Owned by someone else")

    conn.close()

if __name__ == '__main__':
    inspect_access()
