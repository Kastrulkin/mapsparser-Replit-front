import sqlite3
import os
import hashlib
import secrets

DB_PATH = 'src/reports.db'

def hash_password(password: str) -> str:
    """Хеширование пароля (PBKDF2 SHA256)"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}:{pwd_hash.hex()}"

def update_email():
    if not os.path.exists(DB_PATH):
        print(f"❌ База данных не найдена: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Находим владельца бизнеса "Оливер"
        print("🔍 Поиск владельца бизнеса 'Оливер'...")
        cursor.execute("SELECT id, name, owner_id FROM Businesses WHERE name LIKE '%Оливер%'")
        businesses = cursor.fetchall()
        
        if not businesses:
            print("❌ Бизнес 'Оливер' не найден!")
            return

        for b_id, b_name, owner_id in businesses:
            print(f"   Бизнес: {b_name} (ID: {b_id}), Владелец: {owner_id}")
            
            # 2. Обновляем email и устанавливаем пароль
            new_email = 'tislitskaya@yandex.ru'
            new_password = '123456'
            pwd_hash = hash_password(new_password)
            
            print(f"🔄 Обновление email на '{new_email}' и установка пароля для пользователя {owner_id}...")
            cursor.execute("""
                UPDATE Users 
                SET email = %s, password_hash = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (new_email, pwd_hash, owner_id))
            
            if cursor.rowcount > 0:
                print(f"✅ Пользователь {owner_id}: Email обновлен, пароль установлен.")
            else:
                print(f"⚠️ Пользователь {owner_id} не найден в таблице Users")
        
        conn.commit()

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_email()
