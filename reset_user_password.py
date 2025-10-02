#!/usr/bin/env python3
import sqlite3
import sys

def reset_user_password(email):
    conn = sqlite3.connect('reports.db')
    cursor = conn.cursor()
    
    try:
        # Сбрасываем пароль пользователя (устанавливаем NULL)
        cursor.execute('UPDATE Users SET password_hash = NULL WHERE email = ?', (email,))
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f'Password reset for user: {email}')
            print('User can now set a new password via /set-password page')
        else:
            print(f'User not found: {email}')
            
    except Exception as e:
        print(f'Error: {e}')
    finally:
        conn.close()

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else 'demyanovap@gmail.com'
    reset_user_password(email)
