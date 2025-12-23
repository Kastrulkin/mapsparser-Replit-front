#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения Яндекс.Бизнес к конкретному бизнесу.

Использование:
    python src/test_yandex_business_connection.py <business_id>
    
Пример:
    python src/test_yandex_business_connection.py eae57c62-7f56-46b2-aba1-8e82b3b2dcf3
"""

import sys
import os
from datetime import datetime

# Добавляем src в путь (тест находится в tests/, а модули в src/)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

from database_manager import DatabaseManager
from auth_encryption import decrypt_auth_data
from yandex_business_parser import YandexBusinessParser
import json


def test_business_connection(business_id: str):
    """Тестирует подключение Яндекс.Бизнес для конкретного бизнеса."""
    print(f"=" * 60)
    print(f"🧪 Тест подключения Яндекс.Бизнес для бизнеса: {business_id}")
    print(f"=" * 60)
    
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        
        # Проверяем, существует ли бизнес
        cursor.execute("SELECT id, name FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        if not business:
            print(f"❌ Бизнес с ID {business_id} не найден в БД")
            return
        print(f"✅ Бизнес найден: {business[1]}")
        
        # Ищем аккаунт Яндекс.Бизнес для этого бизнеса
        cursor.execute(
            """
            SELECT id, external_id, display_name, auth_data_encrypted, is_active, last_sync_at, last_error
            FROM ExternalBusinessAccounts
            WHERE business_id = ? AND source = 'yandex_business'
            """,
            (business_id,),
        )
        account = cursor.fetchone()
        
        if not account:
            print(f"❌ Аккаунт Яндекс.Бизнес не найден для бизнеса {business_id}")
            print(f"   Добавьте данные через админскую панель (кнопка 'Настройки')")
            return
        
        account_id, external_id, display_name, auth_data_encrypted, is_active, last_sync_at, last_error = account
        
        print(f"✅ Аккаунт найден:")
        print(f"   ID аккаунта: {account_id}")
        print(f"   External ID: {external_id or 'не указан'}")
        print(f"   Display Name: {display_name or 'не указано'}")
        print(f"   Активен: {'Да' if is_active else 'Нет'}")
        if last_sync_at:
            print(f"   Последняя синхронизация: {last_sync_at}")
        if last_error:
            print(f"   Последняя ошибка: {last_error}")
        
        if not is_active:
            print(f"⚠️ Аккаунт неактивен. Включите его в админской панели.")
            return
        
        if not auth_data_encrypted:
            print(f"❌ Нет данных авторизации (auth_data_encrypted пусто)")
            print(f"   Добавьте cookies через админскую панель")
            return
        
        # Расшифровываем auth_data
        print(f"\n🔓 Расшифровка auth_data...")
        auth_data_plain = decrypt_auth_data(auth_data_encrypted)
        if not auth_data_plain:
            print(f"❌ Не удалось расшифровать auth_data")
            print(f"   Проверьте EXTERNAL_AUTH_SECRET_KEY в .env")
            return
        
        print(f"✅ auth_data расшифрован успешно")
        
        # Парсим JSON
        try:
            auth_data_dict = json.loads(auth_data_plain)
            print(f"✅ auth_data в формате JSON")
        except json.JSONDecodeError:
            auth_data_dict = {"cookies": auth_data_plain}
            print(f"⚠️ auth_data не JSON, используем как строку cookies")
        
        cookies = auth_data_dict.get("cookies", "")
        if not cookies:
            print(f"❌ Нет cookies в auth_data")
            return
        
        print(f"✅ Cookies найдены (длина: {len(cookies)} символов)")
        
        # Создаём парсер
        print(f"\n🔧 Создание парсера...")
        account_row = {
            "id": account_id,
            "business_id": business_id,
            "external_id": external_id,
        }
        
        parser = YandexBusinessParser(auth_data_dict)
        print(f"✅ Парсер создан")
        
        # Проверяем режим (фейковый или реальный)
        fake_mode = os.getenv("YANDEX_BUSINESS_FAKE", "0") == "1"
        if fake_mode:
            print(f"\n⚠️ Режим: ДЕМО-ДАННЫЕ (YANDEX_BUSINESS_FAKE=1)")
        else:
            print(f"\n✅ Режим: РЕАЛЬНЫЕ ЗАПРОСЫ (YANDEX_BUSINESS_FAKE не установлен или =0)")
        
        # Пробуем получить отзывы
        print(f"\n📥 Получение отзывов...")
        try:
            reviews = parser.fetch_reviews(account_row)
            print(f"✅ Получено отзывов: {len(reviews)}")
            if reviews:
                print(f"\n   Первый отзыв:")
                r = reviews[0]
                print(f"   - ID: {r.external_review_id}")
                print(f"   - Рейтинг: {r.rating}")
                print(f"   - Автор: {r.author_name}")
                print(f"   - Текст: {r.text[:100] if r.text else 'нет'}...")
                print(f"   - Дата: {r.published_at}")
        except Exception as e:
            print(f"❌ Ошибка при получении отзывов: {e}")
            import traceback
            traceback.print_exc()
        
        # Пробуем получить статистику
        print(f"\n📊 Получение статистики...")
        try:
            stats = parser.fetch_stats(account_row)
            print(f"✅ Получено точек статистики: {len(stats)}")
            if stats:
                print(f"\n   Последняя точка:")
                s = stats[-1]
                print(f"   - Дата: {s.date}")
                print(f"   - Показы: {s.views_total}")
                print(f"   - Клики: {s.clicks_total}")
                print(f"   - Действия: {s.actions_total}")
                print(f"   - Рейтинг: {s.rating}")
                print(f"   - Отзывов: {s.reviews_total}")
        except Exception as e:
            print(f"❌ Ошибка при получении статистики: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n" + "=" * 60)
        print(f"✅ Тест завершён")
        print(f"=" * 60)
        
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python src/test_yandex_business_connection.py <business_id>")
        print("\nПример:")
        print("  python src/test_yandex_business_connection.py eae57c62-7f56-46b2-aba1-8e82b3b2dcf3")
        sys.exit(1)
    
    business_id = sys.argv[1]
    test_business_connection(business_id)

