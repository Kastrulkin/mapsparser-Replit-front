#!/usr/bin/env python3
import sqlite3
import sys

def check_user(email):
    conn = sqlite3.connect('reports.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT id, email, name, password_hash, created_at FROM Users WHERE email = ?', (email,))
        user = cursor.fetchone()
        
        if user:
            print(f'User found: {user}')
            print(f'Has password: {user[3] is not None}')
            print(f'Password hash: {user[3]}')
        else:
            print('User not found')
            
    except Exception as e:
        print(f'Error: {e}')
    finally:
        conn.close()

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else 'demyanovap@gmail.com'
    check_user(email)
