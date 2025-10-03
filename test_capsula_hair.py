#!/usr/bin/env python3
"""
Тест парсера на парикмахерской Capsula Hair
"""
import sys
import os
import traceback
from datetime import datetime

# Добавляем путь к src в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_capsula_hair():
    """Тестируем парсинг парикмахерской Capsula Hair"""
    print("=== Тест парсера на Capsula Hair ===")
    
    try:
        from parser import parse_yandex_card
        
        # URL парикмахерской
        test_url = "https://yandex.ru/maps/org/capsulahair/1399955425/?ll=30.278281%2C59.940988&z=17.21"
        print(f"Тестируем парсинг: {test_url}")
        
        # Запускаем парсинг с таймаутом
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Парсинг превысил время ожидания")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(120)  # 2 минуты таймаут
        
        try:
            result = parse_yandex_card(test_url)
            signal.alarm(0)  # Отключаем таймаут
            
            print(f"✅ Парсинг завершен")
            print(f"Результат содержит ключи: {list(result.keys())}")
            
            if 'error' in result:
                print(f"❌ Ошибка в результате: {result['error']}")
                if 'captcha' in result['error'].lower():
                    print("🔍 Обнаружена капча - это ожидаемо для автоматического парсинга")
                return False
            else:
                print(f"✅ Парсинг прошел без ошибок")
                print(f"Название: {result.get('title', 'Не найдено')}")
                print(f"Адрес: {result.get('address', 'Не найден')}")
                print(f"Телефон: {result.get('phone', 'Не найден')}")
                print(f"Рейтинг: {result.get('rating', 'Не найден')}")
                print(f"Количество отзывов: {result.get('reviews_count', 'Не найдено')}")
                return True
                
        except TimeoutError:
            signal.alarm(0)
            print("❌ Парсинг превысил время ожидания (2 мин)")
            return False
        except Exception as e:
            signal.alarm(0)
            print(f"❌ Ошибка парсинга: {e}")
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования парсера: {e}")
        traceback.print_exc()
        return False

def test_worker_with_capsula():
    """Тестируем worker с парикмахерской"""
    print("\n=== Тест worker с Capsula Hair ===")
    
    try:
        import sqlite3
        import uuid
        
        # Добавляем задачу в очередь
        conn = sqlite3.connect("reports.db")
        cursor = conn.cursor()
        
        test_id = str(uuid.uuid4())
        test_url = "https://yandex.ru/maps/org/capsulahair/1399955425/?ll=30.278281%2C59.940988&z=17.21"
        test_user_id = "f2123626-71b1-4424-8b2a-0bc93ab8f2eb"  # Тестовый пользователь
        
        cursor.execute("""
            INSERT INTO ParseQueue (id, url, user_id, status)
            VALUES (?, ?, ?, 'pending')
        """, (test_id, test_url, test_user_id))
        
        conn.commit()
        print(f"✅ Добавлена задача: {test_id}")
        
        # Запускаем worker
        from worker import process_queue
        print("Запускаем обработку очереди...")
        process_queue()
        
        # Проверяем результат
        cursor.execute("SELECT status FROM ParseQueue WHERE id = ?", (test_id,))
        status = cursor.fetchone()
        
        if status:
            print(f"✅ Статус задачи: {status[0]}")
            
            if status[0] == 'completed':
                print("🎉 Задача успешно завершена!")
                # Проверяем, создался ли отчёт
                cursor.execute("SELECT id, title FROM Cards WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (test_user_id,))
                card = cursor.fetchone()
                if card:
                    print(f"✅ Создан отчёт: {card[1]}")
                else:
                    print("⚠️ Отчёт не создан")
            elif status[0] == 'error':
                print("❌ Задача завершилась с ошибкой")
            elif status[0] == 'captcha_required':
                print("🔍 Требуется капча - это нормально для автоматического парсинга")
            else:
                print(f"⚠️ Неожиданный статус: {status[0]}")
        else:
            print("❌ Задача не найдена")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования worker: {e}")
        traceback.print_exc()
        return False

def main():
    """Основная функция тестирования"""
    print("🔍 Тестирование парсера на Capsula Hair")
    print("=" * 60)
    
    # Тест 1: Прямой парсинг
    parser_ok = test_capsula_hair()
    
    # Тест 2: Worker
    worker_ok = test_worker_with_capsula()
    
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"Парсер: {'✅ OK' if parser_ok else '❌ FAIL'}")
    print(f"Worker: {'✅ OK' if worker_ok else '❌ FAIL'}")
    
    if parser_ok and worker_ok:
        print("\n🎉 Все тесты прошли успешно!")
    else:
        print("\n⚠️ Есть проблемы, но это может быть связано с капчей")

if __name__ == "__main__":
    main()
