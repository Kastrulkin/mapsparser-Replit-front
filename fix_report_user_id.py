#!/usr/bin/env python3
import sqlite3

def fix_report_user_id():
    conn = sqlite3.connect('reports.db')
    cursor = conn.cursor()
    
    try:
        # Находим текущего пользователя
        cursor.execute("SELECT id FROM Users WHERE email = 'demyanovap@gmail.com'")
        current_user = cursor.fetchone()
        
        if not current_user:
            print("Current user not found")
            return
            
        current_user_id = current_user[0]
        print(f"Current user ID: {current_user_id}")
        
        # Обновляем user_id для отчёта Гагарин
        cursor.execute("""
            UPDATE Cards 
            SET user_id = ? 
            WHERE url LIKE '%gagarin%' 
            AND report_path IS NOT NULL
        """, (current_user_id,))
        
        conn.commit()
        print(f"Updated {cursor.rowcount} reports to current user")
        
        # Проверяем результат
        cursor.execute("SELECT id, url, user_id FROM Cards WHERE url LIKE '%gagarin%'")
        cards = cursor.fetchall()
        print("\nUpdated cards:")
        for card in cards:
            print(f"Card: {card}")
            
    except Exception as e:
        print(f'Error: {e}')
    finally:
        conn.close()

if __name__ == "__main__":
    fix_report_user_id()
