#!/usr/bin/env python3
import sqlite3
import os
import sys
from datetime import datetime

# Add src to path if needed (though running from src/ usually works)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import get_db_connection

def check_queue():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("\n=== ParseQueue Statistics ===")
        cursor.execute("SELECT status, COUNT(*) FROM ParseQueue GROUP BY status")
        rows = cursor.fetchall()
        for row in rows:
            print(f"Status '{row[0]}': {row[1]} tasks")
            
        print("\n=== Top 5 Pending Tasks (Next to process) ===")
        cursor.execute("""
            SELECT id, url, created_at, status, retry_after 
            FROM ParseQueue 
            WHERE status = 'pending' 
            ORDER BY created_at ASC 
            LIMIT 5
        """)
        rows = cursor.fetchall()
        if not rows:
            print("No pending tasks.")
        for row in rows:
            print(f"ID: {row[0][:8]}... | Created: {row[2]} | Status: {row[3]} | RetryAfter: {row[4]}")
            print(f"   URL: {row[1][:60]}...")
            
        print("\n=== Tasks in Processing (Potential blockers) ===")
        cursor.execute("""
            SELECT id, url, created_at, updated_at 
            FROM ParseQueue 
            WHERE status = 'processing'
            ORDER BY updated_at DESC
        """)
        rows = cursor.fetchall()
        if not rows:
            print("No tasks currently processing.")
        for row in rows:
            print(f"ID: {row[0][:8]}... | Updated: {row[3]} | Logged duration: (Check server time)")
        
        print("\n=== Server Time ===")
        print(datetime.now().isoformat())
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error checking DB: {e}")

if __name__ == "__main__":
    check_queue()
