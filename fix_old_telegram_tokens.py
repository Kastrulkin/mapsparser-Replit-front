#!/usr/bin/env python3
"""
Скрипт для исправления старых токенов Telegram с пустым business_id
Привязывает их к первому бизнесу пользователя
"""
import sqlite3
import sys
import os

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from safe_db_utils import get_db_connection

def fix_old_telegram_tokens():
    """Исправить старые токены с пустым business_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("=" * 80)
    print("ИСПРАВЛЕНИЕ СТАРЫХ TELEGRAM ТОКЕНОВ")
    print("=" * 80)
    print()
    
    # Проверяем наличие поля business_id
    cursor.execute("PRAGMA table_info(TelegramBindTokens)")
    columns = [row[1] for row in cursor.fetchall()]
    has_business_id = 'business_id' in columns
    
    if not has_business_id:
        print("❌ Поле business_id отсутствует в таблице TelegramBindTokens")
        conn.close()
        return
    
    # Находим токены с пустым business_id, но использованные
    cursor.execute("""
        SELECT id, user_id, used 
        FROM TelegramBindTokens 
        WHERE (business_id IS NULL OR business_id = '') AND used = 1
    """)
    old_tokens = cursor.fetchall()
    
    if not old_tokens:
        print("✅ Нет старых токенов с пустым business_id")
        conn.close()
        return
    
    print(f"Найдено {len(old_tokens)} старых токенов с пустым business_id")
    print()
    
    fixed_count = 0
    for token_id, user_id, used in old_tokens:
        # Находим первый бизнес пользователя
        cursor.execute("""
            SELECT id, name FROM Businesses 
            WHERE owner_id = ? 
            ORDER BY created_at ASC 
            LIMIT 1
        """, (user_id,))
        business_row = cursor.fetchone()
        
        if business_row:
            business_id, business_name = business_row
            # Обновляем токен, привязывая к первому бизнесу
            cursor.execute("""
                UPDATE TelegramBindTokens 
                SET business_id = ? 
                WHERE id = ?
            """, (business_id, token_id))
            fixed_count += 1
            print(f"✅ Токен {token_id[:8]}... привязан к бизнесу '{business_name}'")
        else:
            print(f"⚠️  У пользователя {user_id} нет бизнесов, токен {token_id[:8]}... не обновлен")
    
    conn.commit()
    conn.close()
    
    print()
    print("=" * 80)
    print(f"✅ Исправлено токенов: {fixed_count}")
    print("=" * 80)

if __name__ == "__main__":
    fix_old_telegram_tokens()

