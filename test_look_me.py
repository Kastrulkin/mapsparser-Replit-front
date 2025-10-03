#!/usr/bin/env python3
"""
Тест полного процесса с Look Me: парсинг → ИИ-анализ → создание отчёта
"""
import sys
import os
import traceback
import sqlite3
import uuid
from datetime import datetime

# Добавляем путь к src в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_look_me_parsing():
    """Тестируем парсинг Look Me"""
    print("=== Тест парсинга Look Me ===")
    
    try:
        from parser import parse_yandex_card
        
        # URL Look Me
        test_url = "https://yandex.ru/maps/org/look_me/195175604971/?ll=30.353829%2C59.924713&z=17.21"
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

def test_ai_analysis_look_me():
    """Тестируем ИИ-анализ для Look Me"""
    print("\n=== Тест ИИ-анализа Look Me ===")
    
    try:
        from gigachat_analyzer import analyze_business_data
        
        # Тестовые данные Look Me (предполагаемые)
        test_data = {
            'title': 'Look Me',
            'address': 'Адрес Look Me',
            'phone': '+7 (xxx) xxx-xx-xx',
            'rating': '4.5',
            'reviews_count': 100,
            'categories': ['Салон красоты', 'Парикмахерская'],
            'hours': 'Пн-Пт: 10:00–20:00',
            'description': 'Салон красоты Look Me'
        }
        
        print("Запускаем ИИ-анализ...")
        result = analyze_business_data(test_data)
        
        print(f"✅ ИИ-анализ завершён")
        print(f"Результат содержит ключи: {list(result.keys())}")
        
        if 'analysis' in result:
            print(f"📊 Анализ: {result['analysis']}")
        
        if 'score' in result:
            print(f"⭐ SEO-оценка: {result['score']}/100")
        
        if 'recommendations' in result:
            print(f"💡 Рекомендации: {result['recommendations']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка ИИ-анализа: {e}")
        traceback.print_exc()
        return False

def test_full_workflow_look_me():
    """Тестируем полный рабочий процесс с Look Me"""
    print("\n=== Тест полного процесса Look Me ===")
    
    try:
        # Добавляем тестовую задачу в очередь
        conn = sqlite3.connect("reports.db")
        cursor = conn.cursor()
        
        test_id = str(uuid.uuid4())
        test_url = "https://yandex.ru/maps/org/look_me/195175604971/?ll=30.353829%2C59.924713&z=17.21"
        test_user_id = "f2123626-71b1-4424-8b2a-0bc93ab8f2eb"  # Тестовый пользователь
        
        # Очищаем предыдущие тестовые задачи
        cursor.execute("DELETE FROM ParseQueue WHERE user_id = ?", (test_user_id,))
        cursor.execute("DELETE FROM Cards WHERE user_id = ?", (test_user_id,))
        
        # Добавляем новую задачу
        cursor.execute("""
            INSERT INTO ParseQueue (id, url, user_id, status)
            VALUES (?, ?, ?, 'pending')
        """, (test_id, test_url, test_user_id))
        
        conn.commit()
        print(f"✅ Добавлена тестовая задача: {test_id}")
        
        # Запускаем worker
        from worker import process_queue
        print("Запускаем полный процесс обработки...")
        process_queue()
        
        # Проверяем результат в ParseQueue
        cursor.execute("SELECT status FROM ParseQueue WHERE id = ?", (test_id,))
        queue_status = cursor.fetchone()
        
        if queue_status:
            print(f"✅ Статус в очереди: {queue_status[0]}")
            
            if queue_status[0] == 'completed':
                print("🎉 Задача успешно завершена!")
            elif queue_status[0] == 'error':
                print("❌ Задача завершилась с ошибкой")
            elif queue_status[0] == 'captcha_required':
                print("🔍 Требуется капча - это нормально для автоматического парсинга")
            else:
                print(f"⚠️ Неожиданный статус: {queue_status[0]}")
        else:
            print("❌ Задача не найдена в очереди")
        
        # Проверяем созданную карточку
        cursor.execute("""
            SELECT id, title, seo_score, ai_analysis, recommendations 
            FROM Cards 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (test_user_id,))
        
        card = cursor.fetchone()
        
        if card:
            print(f"✅ Создана карточка: {card[1]}")
            print(f"📊 SEO-оценка: {card[2]}")
            print(f"🤖 ИИ-анализ: {'Есть' if card[3] else 'Нет'}")
            print(f"💡 Рекомендации: {'Есть' if card[4] else 'Нет'}")
            
            # Проверяем, создался ли HTML отчёт
            cursor.execute("SELECT report_path FROM Cards WHERE id = ?", (card[0],))
            report_path = cursor.fetchone()
            
            if report_path and report_path[0]:
                print(f"📄 HTML отчёт: {report_path[0]}")
                
                # Проверяем, существует ли файл
                if os.path.exists(report_path[0]):
                    print("✅ Файл отчёта существует")
                else:
                    print("⚠️ Файл отчёта не найден по пути")
            else:
                print("❌ HTML отчёт не создан")
            
            return True
        else:
            print("❌ Карточка не создана")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка полного процесса: {e}")
        traceback.print_exc()
        return False

def main():
    """Основная функция тестирования"""
    print("🔍 Тестирование полного процесса с Look Me")
    print("=" * 60)
    
    # Тест 1: Парсинг
    parsing_ok = test_look_me_parsing()
    
    # Тест 2: ИИ-анализ
    analysis_ok = test_ai_analysis_look_me()
    
    # Тест 3: Полный процесс
    workflow_ok = test_full_workflow_look_me()
    
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"Парсинг: {'✅ OK' if parsing_ok else '❌ FAIL'}")
    print(f"ИИ-анализ: {'✅ OK' if analysis_ok else '❌ FAIL'}")
    print(f"Полный процесс: {'✅ OK' if workflow_ok else '❌ FAIL'}")
    
    if parsing_ok and analysis_ok and workflow_ok:
        print("\n🎉 Все компоненты работают корректно!")
        print("✅ Парсинг → ИИ-анализ → создание отчёта функционирует")
    else:
        print("\n⚠️ Есть проблемы в процессе анализа")

if __name__ == "__main__":
    main()
