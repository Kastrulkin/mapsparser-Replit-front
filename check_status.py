import sqlite3

def check_status():
    conn = sqlite3.connect("reports.db")
    cur = conn.cursor()
    
    print("=== Статус заявок gagarin и mob_barbershop ===")
    cur.execute("SELECT id, url, status, created_at FROM ParseQueue WHERE url LIKE '%gagarin%' OR url LIKE '%mob_barbershop%' ORDER BY created_at DESC")
    
    for r in cur.fetchall():
        print(f"ID: {r[0][:8]}...")
        print(f"URL: {r[1][:50]}...")
        print(f"Status: {r[2]}")
        print(f"Created: {r[3]}")
        print("-" * 40)
    
    conn.close()

if __name__ == "__main__":
    check_status()
