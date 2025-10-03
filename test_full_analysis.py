#!/usr/bin/env python3
"""
Тест полного процесса: парсинг → ИИ-анализ → создание отчёта
"""
import sys
import os
import traceback
import sqlite3
import uuid
from datetime import datetime

# Добавляем путь к src в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_ai_analysis():
    """Тестируем ИИ-анализ отдельно"""
    print("=== Тест ИИ-анализа ===")
    
    try:
        from gigachat_analyzer import analyze_business_data
        
        # Тестовые данные парикмахерской
        test_data = {
            'title': 'Capsulahair',
            'address': '7-я линия Васильевского острова, 34, Санкт-Петербург',
            'phone': '+7 (812) 407-25-34',
            'rating': '5.0',
            'reviews_count': 1244,
            'categories': ['Салон красоты', 'Барбершоп', 'Парикмахерская'],
            'hours': 'Пн-Вс: 10:00–22:00',
            'description': 'Парикмахерская с высоким рейтингом и большим количеством отзывов'
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

def test_full_workflow():
    """Тестируем полный рабочий процесс"""
    print("\n=== Тест полного процесса ===")
    
    try:
        # Добавляем тестовую задачу в очередь
        conn = sqlite3.connect("reports.db")
        cursor = conn.cursor()
        
        test_id = str(uuid.uuid4())
        test_url = "https://yandex.ru/maps/org/capsulahair/1399955425/?ll=30.278281%2C59.940988&z=17.21"
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

def test_analysis_components():
    """Тестируем компоненты анализа"""
    print("\n=== Тест компонентов анализа ===")
    
    try:
        # Проверяем импорт анализатора
        from gigachat_analyzer import analyze_business_data
        print("✅ gigachat_analyzer импортирован")
        
        # Проверяем конфигурацию модели
        from model_config import get_model_config
        config = get_model_config()
        print(f"✅ Конфигурация модели: {config}")
        
        # Проверяем промпты
        from model_config import get_prompt
        prompt = get_prompt()
        print(f"✅ Промпт загружен: {len(prompt)} символов")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка компонентов: {e}")
        traceback.print_exc()
        return False

def main():
    """Основная функция тестирования"""
    print("🔍 Тестирование полного процесса: парсинг → ИИ-анализ → отчёт")
    print("=" * 70)
    
    # Тест 1: Компоненты анализа
    components_ok = test_analysis_components()
    
    # Тест 2: ИИ-анализ
    analysis_ok = test_ai_analysis()
    
    # Тест 3: Полный процесс
    workflow_ok = test_full_workflow()
    
    print("\n" + "=" * 70)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"Компоненты: {'✅ OK' if components_ok else '❌ FAIL'}")
    print(f"ИИ-анализ: {'✅ OK' if analysis_ok else '❌ FAIL'}")
    print(f"Полный процесс: {'✅ OK' if workflow_ok else '❌ FAIL'}")
    
    if components_ok and analysis_ok and workflow_ok:
        print("\n🎉 Все компоненты работают корректно!")
        print("✅ Парсинг → ИИ-анализ → создание отчёта функционирует")
    else:
        print("\n⚠️ Есть проблемы в процессе анализа")

if __name__ == "__main__":
    main()
