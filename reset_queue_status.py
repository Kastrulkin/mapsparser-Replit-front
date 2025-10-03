import sqlite3

def reset_queue_status():
    conn = sqlite3.connect("reports.db")
    cur = conn.cursor()
    
    print("=== Сбрасываем статусы проблемных задач ===")
    cur.execute("UPDATE ParseQueue SET status='pending' WHERE status IN ('error', 'captcha_required')")
    updated = cur.rowcount
    conn.commit()
    
    print(f"✅ Сброшено {updated} задач в pending")
    
    print("\n=== Статусы в очереди ===")
    cur.execute("SELECT status, COUNT(*) FROM ParseQueue GROUP BY status")
    for status, count in cur.fetchall():
        print(f"  {status}: {count}")
    
    conn.close()

if __name__ == "__main__":
    reset_queue_status()