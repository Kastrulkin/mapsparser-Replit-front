#!/usr/bin/env python3
"""
Скрипт для проверки auth_data в БД для Яндекс.Бизнес аккаунтов.
Помогает диагностировать проблемы с расшифровкой.
"""

import os
import sys
import json
import base64

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database_manager import DatabaseManager
from auth_encryption import decrypt_auth_data, encrypt_auth_data


def check_auth_data(business_id: str = None):
    """Проверяет auth_data для всех или конкретного бизнеса."""
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        
        if business_id:
            cursor.execute(
                """
                SELECT id, business_id, external_id, source, auth_data_encrypted, created_at
                FROM ExternalBusinessAccounts
                WHERE business_id = ? AND source = 'yandex_business'
                """,
                (business_id,)
            )
        else:
            cursor.execute(
                """
                SELECT id, business_id, external_id, source, auth_data_encrypted, created_at
                FROM ExternalBusinessAccounts
                WHERE source = 'yandex_business'
                """
            )
        
        rows = cursor.fetchall()
        
        if not rows:
            print(f"❌ Аккаунты Яндекс.Бизнес не найдены")
            return
        
        print(f"✅ Найдено аккаунтов: {len(rows)}\n")
        
        for row in rows:
            account_id, bid, external_id, source, auth_data_encrypted, created_at = row
            
            print("="*60)
            print(f"Аккаунт ID: {account_id}")
            print(f"Бизнес ID: {bid}")
            print(f"External ID: {external_id}")
            print(f"Создан: {created_at}")
            print("-"*60)
            
            if not auth_data_encrypted:
                print("❌ auth_data_encrypted пустое")
                continue
            
            print(f"Длина зашифрованных данных: {len(auth_data_encrypted)} символов")
            print(f"Первые 100 символов: {auth_data_encrypted[:100]}")
            
            # Пробуем расшифровать
            print("\n🔐 Попытка расшифровки...")
            auth_data_plain = decrypt_auth_data(auth_data_encrypted)
            
            if auth_data_plain:
                print(f"✅ Расшифровка успешна!")
                print(f"   Длина расшифрованных данных: {len(auth_data_plain)} символов")
                print(f"   Первые 200 символов: {auth_data_plain[:200]}")
                
                # Пробуем распарсить как JSON
                try:
                    auth_data_dict = json.loads(auth_data_plain)
                    print(f"✅ Данные в формате JSON")
                    print(f"   Ключи: {list(auth_data_dict.keys())}")
                    
                    # Проверяем cookies
                    cookies_str = auth_data_dict.get("cookies", "")
                    if cookies_str:
                        cookies_count = len([c for c in cookies_str.split(";") if "=" in c])
                        print(f"   Cookies: {cookies_count} штук")
                        print(f"   Примеры cookie ключей: {[c.split('=')[0].strip() for c in cookies_str.split(';')[:5] if '=' in c]}")
                    else:
                        print(f"   ⚠️ Поле 'cookies' отсутствует")
                except json.JSONDecodeError:
                    print(f"⚠️ Данные не в формате JSON (возможно, просто строка cookies)")
                    if "yandexuid" in auth_data_plain.lower() or "session" in auth_data_plain.lower():
                        print(f"   ✅ Похоже на строку cookies")
                    else:
                        print(f"   ⚠️ Не похоже на cookies")
            else:
                print(f"❌ Расшифровка не удалась")
                print(f"\n💡 Возможные причины:")
                print(f"   1. EXTERNAL_AUTH_SECRET_KEY не установлен или неверный")
                print(f"   2. Данные были зашифрованы другим ключом")
                print(f"   3. Данные повреждены")
                print(f"\n💡 Попробуйте:")
                print(f"   1. Проверить .env файл на наличие EXTERNAL_AUTH_SECRET_KEY")
                print(f"   2. Если ключ изменился, нужно пересохранить данные")
                print(f"   3. Проверить, что данные сохранены правильно")
                
                # Пробуем определить формат данных
                print(f"\n🔍 Анализ формата данных...")
                try:
                    # Может быть это base64 без Fernet?
                    decoded = base64.b64decode(auth_data_encrypted.encode())
                    print(f"   ✅ Это base64 (длина декодированных байт: {len(decoded)})")
                    try:
                        text = decoded.decode('utf-8')
                        print(f"   ✅ Декодируется как UTF-8 текст")
                        print(f"   Первые 200 символов: {text[:200]}")
                    except:
                        print(f"   ⚠️ Не декодируется как UTF-8 (возможно, бинарные данные)")
                except:
                    print(f"   ⚠️ Не base64 формат")
            
            print()
    
    finally:
        db.close()


def main():
    """Основная функция."""
    business_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    if business_id:
        print(f"🔍 Проверка auth_data для бизнеса: {business_id}\n")
    else:
        print(f"🔍 Проверка auth_data для всех Яндекс.Бизнес аккаунтов\n")
    
    check_auth_data(business_id)


if __name__ == "__main__":
    main()

