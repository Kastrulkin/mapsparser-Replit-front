#!/usr/bin/env python3
"""
Автоматический тест парсера без интерактивности
"""
import sys
import os
import traceback
from datetime import datetime

# Добавляем путь к src в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_parser_quick():
    """Быстрый тест парсера с таймаутом"""
    print("=== Быстрый тест парсера ===")
    
    try:
        from parser import parse_yandex_card
        
        # Тестовый URL
        test_url = "https://yandex.ru/maps/org/gagarin/180566191872/?ll=30.338344%2C59.858729&z=16.88"
        print(f"Тестируем парсинг: {test_url}")
        
        # Запускаем парсинг с коротким таймаутом
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Парсинг превысил время ожидания")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30 секунд таймаут
        
        try:
            result = parse_yandex_card(test_url)
            signal.alarm(0)  # Отключаем таймаут
            
            print(f"✅ Парсинг завершен успешно")
            print(f"Результат содержит ключи: {list(result.keys())}")
            
            if 'error' in result:
                print(f"❌ Ошибка в результате: {result['error']}")
                return False
            else:
                print(f"✅ Парсинг прошел без ошибок")
                print(f"Название: {result.get('title', 'Не найдено')}")
                print(f"Адрес: {result.get('address', 'Не найден')}")
                print(f"Телефон: {result.get('phone', 'Не найден')}")
                return True
                
        except TimeoutError:
            signal.alarm(0)
            print("❌ Парсинг превысил время ожидания (30 сек)")
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

def test_worker():
    """Тестируем worker"""
    print("\n=== Тестирование worker ===")
    
    try:
        from worker import process_queue
        
        print("Запускаем process_queue()...")
        result = process_queue()
        
        print(f"✅ Worker выполнен: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка worker: {e}")
        traceback.print_exc()
        return False

def test_full_workflow():
    """Тестируем полный рабочий процесс"""
    print("\n=== Тестирование полного процесса ===")
    
    try:
        import sqlite3
        import uuid
        
        # Добавляем тестовую задачу в очередь
        conn = sqlite3.connect("reports.db")
        cursor = conn.cursor()
        
        test_id = str(uuid.uuid4())
        test_url = "https://yandex.ru/maps/org/gagarin/180566191872/?ll=30.338344%2C59.858729&z=16.88"
        test_user_id = "f2123626-71b1-4424-8b2a-0bc93ab8f2eb"  # Тестовый пользователь
        
        cursor.execute("""
            INSERT INTO ParseQueue (id, url, user_id, status)
            VALUES (?, ?, ?, 'pending')
        """, (test_id, test_url, test_user_id))
        
        conn.commit()
        print(f"✅ Добавлена тестовая задача: {test_id}")
        
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
                # Проверяем, создался ли отчёт
                cursor.execute("SELECT id FROM Cards WHERE user_id = ?", (test_user_id,))
                cards = cursor.fetchall()
                print(f"✅ Создано отчётов: {len(cards)}")
            elif status[0] == 'error':
                print("❌ Задача завершилась с ошибкой")
            elif status[0] == 'captcha_required':
                print("⚠️ Требуется капча")
            else:
                print(f"⚠️ Неожиданный статус: {status[0]}")
        else:
            print("❌ Задача не найдена")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка полного процесса: {e}")
        traceback.print_exc()
        return False

def main():
    """Основная функция тестирования"""
    print("🔍 Автоматическое тестирование парсера")
    print("=" * 50)
    
    # Тест 1: Быстрый парсинг
    parser_ok = test_parser_quick()
    
    # Тест 2: Worker
    worker_ok = test_worker()
    
    # Тест 3: Полный процесс
    workflow_ok = test_full_workflow()
    
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"Парсер: {'✅ OK' if parser_ok else '❌ FAIL'}")
    print(f"Worker: {'✅ OK' if worker_ok else '❌ FAIL'}")
    print(f"Полный процесс: {'✅ OK' if workflow_ok else '❌ FAIL'}")
    
    if parser_ok and worker_ok and workflow_ok:
        print("\n🎉 Все тесты прошли успешно!")
    else:
        print("\n⚠️ Есть проблемы, требующие внимания")

if __name__ == "__main__":
    main()
