import sys
import os
import sqlite3
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from safe_db_utils import get_db_path

def reset_stuck_tasks():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"📦 Resetting stuck tasks in: {db_path}")
    
    try:
        # Find stuck tasks (processing for > 15 minutes)
        # Assuming tasks older than 15 mins are stuck due to crash/restart
        time_threshold = (datetime.now() - timedelta(minutes=15)).isoformat()
        
        cursor.execute("""
            SELECT id, url, created_at, updated_at 
            FROM ParseQueue 
            WHERE status = 'processing'
        """)
        stuck_tasks = cursor.fetchall()
        
        if not stuck_tasks:
            print("✅ No stuck tasks found.")
            return

        print(f"⚠️ Found {len(stuck_tasks)} stuck tasks:")
        for task in stuck_tasks:
            print(f"  - ID: {task[0]}, URL: {task[1]}, Updated: {task[3]}")
            
        # Reset them to pending
        print("🔄 Resetting status to 'pending'...")
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'pending', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'processing'
        """)
        conn.commit()
        print(f"✅ Reset {cursor.rowcount} tasks to pending.")
        
    except Exception as e:
        print(f"❌ Failed to reset tasks: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    reset_stuck_tasks()
