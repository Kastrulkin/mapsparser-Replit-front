#!/usr/bin/env python3
"""
Скрипт для диагностики проблем с парсером
"""
import sys
import os
import traceback
from datetime import datetime

# Добавляем путь к src в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Тестируем импорты основных модулей"""
    print("=== Тестирование импортов ===")
    
    try:
        from parser import parse_yandex_card
        print("✅ parser.py импортирован успешно")
    except Exception as e:
        print(f"❌ Ошибка импорта parser.py: {e}")
        traceback.print_exc()
        return False
    
    try:
        from gigachat_analyzer import analyze_business_data
        print("✅ gigachat_analyzer.py импортирован успешно")
    except Exception as e:
        print(f"❌ Ошибка импорта gigachat_analyzer.py: {e}")
        traceback.print_exc()
        return False
    
    try:
        from worker import process_queue
        print("✅ worker.py импортирован успешно")
    except Exception as e:
        print(f"❌ Ошибка импорта worker.py: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_database():
    """Тестируем подключение к базе данных"""
    print("\n=== Тестирование базы данных ===")
    
    try:
        import sqlite3
        conn = sqlite3.connect("reports.db")
        cursor = conn.cursor()
        
        # Проверяем структуру таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"✅ Найдены таблицы: {[t[0] for t in tables]}")
        
        # Проверяем очередь
        cursor.execute("SELECT COUNT(*) FROM ParseQueue")
        queue_count = cursor.fetchone()[0]
        print(f"✅ Записей в очереди: {queue_count}")
        
        # Проверяем статусы
        cursor.execute("SELECT status, COUNT(*) FROM ParseQueue GROUP BY status")
        statuses = cursor.fetchall()
        print(f"✅ Статусы в очереди: {dict(statuses)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка работы с базой данных: {e}")
        traceback.print_exc()
        return False

def test_parser_simple():
    """Тестируем парсер на простом примере"""
    print("\n=== Тестирование парсера ===")
    
    try:
        from parser import parse_yandex_card
        
        # Тестовый URL
        test_url = "https://yandex.ru/maps/org/gagarin/180566191872/?ll=30.338344%2C59.858729&z=16.88"
        print(f"Тестируем парсинг: {test_url}")
        
        # Запускаем парсинг с таймаутом
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Парсинг превысил время ожидания")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(60)  # 60 секунд таймаут
        
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
                return True
                
        except TimeoutError:
            signal.alarm(0)
            print("❌ Парсинг превысил время ожидания (60 сек)")
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

def test_analyzer():
    """Тестируем анализатор"""
    print("\n=== Тестирование анализатора ===")
    
    try:
        from gigachat_analyzer import analyze_business_data
        
        # Тестовые данные
        test_data = {
            'title': 'Тестовая компания',
            'address': 'Тестовый адрес',
            'phone': '+7 (999) 123-45-67',
            'rating': '4.5',
            'reviews_count': 10
        }
        
        print("Тестируем анализ с тестовыми данными...")
        result = analyze_business_data(test_data)
        
        print(f"✅ Анализ завершен успешно")
        print(f"Результат содержит ключи: {list(result.keys())}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка анализатора: {e}")
        traceback.print_exc()
        return False

def main():
    """Основная функция диагностики"""
    print("🔍 Диагностика парсера и анализатора")
    print("=" * 50)
    
    # Тестируем импорты
    if not test_imports():
        print("\n❌ Критические ошибки импорта. Остановка.")
        return
    
    # Тестируем базу данных
    if not test_database():
        print("\n❌ Ошибки базы данных. Проверьте подключение.")
        return
    
    # Тестируем анализатор (быстрый тест)
    if not test_analyzer():
        print("\n⚠️ Проблемы с анализатором, но продолжаем...")
    
    # Тестируем парсер (может занять время)
    print("\n⚠️ Внимание: тест парсера может занять до 60 секунд...")
    user_input = input("Продолжить тест парсера? (y/n): ")
    if user_input.lower() == 'y':
        test_parser_simple()
    
    print("\n✅ Диагностика завершена")

if __name__ == "__main__":
    main()
