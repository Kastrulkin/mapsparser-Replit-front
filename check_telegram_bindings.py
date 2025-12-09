#!/usr/bin/env python3
"""
Скрипт для проверки статуса привязки Telegram для каждого бизнеса
"""
import sqlite3
from datetime import datetime

def check_telegram_bindings():
    """Проверить статус привязки Telegram для всех бизнесов"""
    conn = sqlite3.connect('src/reports.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=" * 80)
    print("СТАТУС ПРИВЯЗКИ TELEGRAM ДЛЯ БИЗНЕСОВ")
    print("=" * 80)
    print()
    
    # Проверяем наличие поля business_id
    cursor.execute("PRAGMA table_info(TelegramBindTokens)")
    columns = [row[1] for row in cursor.fetchall()]
    has_business_id = 'business_id' in columns
    
    if not has_business_id:
        print("⚠️  Поле business_id отсутствует в таблице TelegramBindTokens")
        print("   Добавьте его командой: ALTER TABLE TelegramBindTokens ADD COLUMN business_id TEXT;")
        return
    
    # Получаем все бизнесы
    cursor.execute("""
        SELECT id, name, owner_id 
        FROM Businesses 
        ORDER BY name
    """)
    businesses = cursor.fetchall()
    
    # Получаем информацию о пользователях
    cursor.execute("SELECT id, email, telegram_id FROM Users")
    users = {row['id']: row for row in cursor.fetchall()}
    
    print(f"Всего бизнесов: {len(businesses)}")
    print()
    
    for business in businesses:
        business_id = business['id']
        business_name = business['name']
        owner_id = business['owner_id']
        
        owner = users.get(owner_id)
        owner_email = owner['email'] if owner else 'Неизвестно'
        owner_telegram = owner['telegram_id'] if owner else None
        
        # Проверяем токены для этого бизнеса
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN used = 1 THEN 1 ELSE 0 END) as used_count,
                   SUM(CASE WHEN used = 0 THEN 1 ELSE 0 END) as unused_count
            FROM TelegramBindTokens
            WHERE business_id = ?
        """, (business_id,))
        
        token_stats = cursor.fetchone()
        total_tokens = token_stats['total'] if token_stats and token_stats['total'] else 0
        used_tokens = token_stats['used_count'] if token_stats and token_stats['used_count'] is not None else 0
        unused_tokens = token_stats['unused_count'] if token_stats and token_stats['unused_count'] is not None else 0
        
        # Определяем статус
        if owner_telegram and used_tokens > 0:
            status = "✅ ПОДКЛЮЧЕН"
        elif owner_telegram and total_tokens == 0:
            status = "⚠️  Telegram привязан к пользователю, но нет токенов для бизнеса"
        elif total_tokens > 0 and used_tokens == 0:
            status = "⏳ Есть неиспользованные токены"
        else:
            status = "❌ НЕ ПОДКЛЮЧЕН"
        
        print(f"📋 {business_name}")
        print(f"   ID: {business_id}")
        print(f"   Владелец: {owner_email}")
        print(f"   Telegram ID владельца: {owner_telegram if owner_telegram else 'Не привязан'}")
        print(f"   Статус: {status}")
        print(f"   Токенов для бизнеса: {total_tokens} (использовано: {used_tokens}, неиспользовано: {unused_tokens})")
        print()
    
    # Статистика по токенам без business_id
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM TelegramBindTokens
        WHERE business_id IS NULL OR business_id = ''
    """)
    old_tokens = cursor.fetchone()['count']
    
    if old_tokens > 0:
        print("=" * 80)
        print(f"⚠️  Найдено {old_tokens} токенов без business_id (старые токены)")
        print("   Эти токены были созданы до добавления поддержки business_id")
        print()
    
    conn.close()

if __name__ == "__main__":
    check_telegram_bindings()

