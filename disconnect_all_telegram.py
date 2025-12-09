#!/usr/bin/env python3
"""
Скрипт для отключения всех Telegram-ботов
Очищает привязки и удаляет использованные токены
"""
import sqlite3
from datetime import datetime

def disconnect_all_telegram():
    """Отключить всех Telegram-ботов"""
    conn = sqlite3.connect('src/reports.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=" * 80)
    print("ОТКЛЮЧЕНИЕ ВСЕХ TELEGRAM-БОТОВ")
    print("=" * 80)
    print()
    
    # Проверяем текущее состояние
    cursor.execute("""
        SELECT u.id, u.email, u.telegram_id, COUNT(tbt.id) as tokens_count
        FROM Users u
        LEFT JOIN TelegramBindTokens tbt ON u.id = tbt.user_id AND tbt.used = 1
        WHERE u.telegram_id IS NOT NULL AND u.telegram_id != ''
        GROUP BY u.id, u.email, u.telegram_id
    """)
    users_with_telegram = cursor.fetchall()
    
    if not users_with_telegram:
        print("✅ Нет пользователей с привязанным Telegram")
        conn.close()
        return
    
    print(f"Найдено {len(users_with_telegram)} пользователей с привязанным Telegram:")
    for user in users_with_telegram:
        print(f"  - {user['email']}: Telegram ID {user['telegram_id']}, токенов: {user['tokens_count']}")
    print()
    
    # Подсчитываем использованные токены
    cursor.execute("SELECT COUNT(*) FROM TelegramBindTokens WHERE used = 1")
    used_tokens_count = cursor.fetchone()[0]
    print(f"Использованных токенов: {used_tokens_count}")
    print()
    
    response = input("Продолжить отключение всех ботов? (yes/no): ")
    
    if response.lower() != 'yes':
        print("❌ Отключение отменено")
        conn.close()
        return
    
    # Очищаем telegram_id у всех пользователей
    print("\n🔄 Очищаю telegram_id у пользователей...")
    cursor.execute("""
        UPDATE Users 
        SET telegram_id = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE telegram_id IS NOT NULL AND telegram_id != ''
    """)
    cleared_users = cursor.rowcount
    print(f"✅ Очищено telegram_id у {cleared_users} пользователей")
    
    # Удаляем все использованные токены
    print("\n🔄 Удаляю использованные токены...")
    cursor.execute("DELETE FROM TelegramBindTokens WHERE used = 1")
    deleted_tokens = cursor.rowcount
    print(f"✅ Удалено {deleted_tokens} использованных токенов")
    
    # Оставляем неиспользованные токены (они могут быть еще действительными)
    cursor.execute("SELECT COUNT(*) FROM TelegramBindTokens WHERE used = 0")
    unused_tokens = cursor.fetchone()[0]
    print(f"ℹ️  Осталось {unused_tokens} неиспользованных токенов (будут удалены автоматически при истечении)")
    
    conn.commit()
    conn.close()
    
    print()
    print("=" * 80)
    print("✅ Все Telegram-боты отключены!")
    print("=" * 80)
    print()
    print("Теперь вы можете подключить ботов заново для каждого бизнеса отдельно.")

if __name__ == "__main__":
    disconnect_all_telegram()

