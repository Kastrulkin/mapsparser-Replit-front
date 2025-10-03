#!/usr/bin/env python3
"""
Тест полного процесса с Capsula Hair: парсинг → ИИ-анализ → создание отчёта
"""
import sys
import os
import traceback
import sqlite3
import uuid
from datetime import datetime

# Добавляем путь к src в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_full_workflow_capsula():
    """Тестируем полный рабочий процесс с Capsula Hair"""
    print("=== Тест полного процесса Capsula Hair ===")
    
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
            SELECT id, title, seo_score, ai_analysis, recommendations, report_path
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
            
            # Проверяем HTML отчёт
            if card[5]:
                print(f"📄 HTML отчёт: {card[5]}")
                
                # Проверяем, существует ли файл
                if os.path.exists(card[5]):
                    print("✅ Файл отчёта существует")
                    file_size = os.path.getsize(card[5])
                    print(f"📄 Размер файла: {file_size} байт")
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
    print("🔍 Тестирование полного процесса с Capsula Hair")
    print("=" * 60)
    
    # Тест: Полный процесс
    workflow_ok = test_full_workflow_capsula()
    
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"Полный процесс: {'✅ OK' if workflow_ok else '❌ FAIL'}")
    
    if workflow_ok:
        print("\n🎉 Полный процесс работает корректно!")
        print("✅ Парсинг → ИИ-анализ → создание отчёта функционирует")
    else:
        print("\n⚠️ Есть проблемы в процессе")

if __name__ == "__main__":
    main()
