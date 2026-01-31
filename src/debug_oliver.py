
import sqlite3
import os

DB_PATH = 'reports.db'

def inspect_data():
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
            oliver_id = None
        else:
            print(dict(oliver))
            oliver_id = oliver['id']

        # 2. Dump all Networks
        print("\n--- ALL Networks ---")
        cursor.execute("SELECT * FROM Networks")
        networks = cursor.fetchall()
        for n in networks:
            print(dict(n))

        # 3. Check for other relationship tables
        print("\n--- Checking for link tables ---")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for t in tables:
            if 'User' in t[0] or 'Network' in t[0]:
                print(f"Table: {t[0]}")

        # 4. Dump all businesses for Oliver again
        print(f"\n--- Businesses owned by Oliver ({oliver_id}) ---")
        cursor.execute("SELECT * FROM Businesses WHERE owner_id = ?", (oliver_id,))
        businesses = cursor.fetchall()
        for b in businesses:
            print(f"ID: {b['id']}, Name: {b['name']}, NetworkID: {b['network_id']}")

        # 5. Fuzzy search for Kebab
        print("\n--- Fuzzy Search for 'Kebab' or 'Кебаб' ---")
        cursor.execute("SELECT * FROM Businesses WHERE name LIKE '%Kebab%' OR name LIKE '%Кебаб%'")
        kebabs = cursor.fetchall()
        for b in kebabs:
            print(f"BUSINESS: ID: {b['id']}, Name: {b['name']}, NetID: {b['network_id']}")

        cursor.execute("SELECT * FROM Users WHERE email LIKE '%kebab%'")
        u_kebabs = cursor.fetchall()
        for u in u_kebabs:
            print(f"USER: ID: {u['id']}, Email: {u['email']}")

        cursor.execute("SELECT * FROM Networks WHERE name LIKE '%Kebab%' OR name LIKE '%Кебаб%'")
        n_kebabs = cursor.fetchall()
        for n in n_kebabs:
            print(f"NETWORK: ID: {n['id']}, Name: {n['name']}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_data()
