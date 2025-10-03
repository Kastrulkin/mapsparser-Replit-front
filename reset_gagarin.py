import sqlite3

def reset_gagarin():
    conn = sqlite3.connect("reports.db")
    cur = conn.cursor()
    
    # Сбрасываем конкретную заявку gagarin в pending
    cur.execute("UPDATE ParseQueue SET status='pending' WHERE id='135e9c9b-597b-44ef-b277-a67cb4ed06d2'")
    updated = cur.rowcount
    conn.commit()
    
    print(f"Updated rows: {updated}")
    
    # Проверяем статус
    cur.execute("SELECT id, status FROM ParseQueue WHERE id='135e9c9b-597b-44ef-b277-a67cb4ed06d2'")
    result = cur.fetchone()
    if result:
        print(f"Status now: {result[1]}")
    
    conn.close()

if __name__ == "__main__":
    reset_gagarin()
