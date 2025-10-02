#!/usr/bin/env python3
import sqlite3

def check_cards_structure():
    conn = sqlite3.connect('reports.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('PRAGMA table_info(Cards)')
        columns = cursor.fetchall()
        
        print("=== Cards table structure ===")
        for col in columns:
            print(f'Column: {col}')
            
        # Проверяем данные в Cards
        cursor.execute('SELECT * FROM Cards LIMIT 1')
        sample = cursor.fetchone()
        if sample:
            print(f"\nSample data: {sample}")
        else:
            print("\nNo data in Cards table")
            
    except Exception as e:
        print(f'Error: {e}')
    finally:
        conn.close()

if __name__ == "__main__":
    check_cards_structure()
