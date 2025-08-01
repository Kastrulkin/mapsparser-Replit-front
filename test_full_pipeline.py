#!/usr/bin/env python3
"""
Тестовый скрипт для проверки полного пайплайна SEO-анализатора
"""
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем src в путь для импорта
sys.path.append('src')

def test_full_pipeline():
    """Тестирует полный пайплайн: парсинг -> AI-анализ -> генерация отчёта"""
    
    print("🧪 Тестирование полного пайплайна SEO-анализатора")
    print("=" * 60)
    
    # Тестовые данные карточки (имитируем результат парсинга)
    test_card_data = {
        "title": "Кафе 'Уютное место'",
        "address": "ул. Ленина, 123, Москва",
        "phone": "+7 (495) 123-45-67",
        "site": "https://uyutnoe-mesto.ru",
        "rating": 4.2,
        "reviews_count": 45,
        "overview": {
            "description": "Уютное кафе с домашней кухней и приятной атмосферой. Идеальное место для семейного ужина и романтических свиданий."
        },
        "categories": ["Кафе", "Рестораны", "Еда и напитки"],
        "hours": "Ежедневно 10:00-23:00",
        "features_full": ["Парковка", "Wi-Fi", "Доставка", "Веранда"],
        "products": ["Завтраки", "Обеды", "Ужины", "Десерты"],
        "photos": ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
    }
    
    print("📊 Тестовые данные карточки:")
    print(f"  Название: {test_card_data['title']}")
    print(f"  Адрес: {test_card_data['address']}")
    print(f"  Рейтинг: {test_card_data['rating']}")
    print(f"  Отзывов: {test_card_data['reviews_count']}")
    print()
    
    # Тест 1: AI-анализ
    print("1️⃣ Тест AI-анализа:")
    try:
        from ai_analyzer import analyze_business_data
        
        print("🔄 Выполняем AI-анализ...")
        analysis_result = analyze_business_data(test_card_data)
        
        print("✅ AI-анализ завершён!")
        print(f"  Оценка SEO: {analysis_result['score']}/100")
        print(f"  Количество рекомендаций: {len(analysis_result['recommendations'])}")
        
        print("📝 Рекомендации:")
        for i, rec in enumerate(analysis_result['recommendations'][:5], 1):
            print(f"  {i}. {rec}")
        
        ai_test = True
        
    except Exception as e:
        print(f"❌ Ошибка AI-анализа: {e}")
        ai_test = False
    
    print()
    
    # Тест 2: Генерация отчёта
    print("2️⃣ Тест генерации отчёта:")
    try:
        from report import generate_html_report
        
        # Подготавливаем данные для отчёта
        analysis_data = {
            'score': analysis_result['score'] if ai_test else 50,
            'recommendations': analysis_result['recommendations'] if ai_test else ["Тестовая рекомендация"],
            'ai_analysis': analysis_result['analysis'] if ai_test else {"generated_text": "Тестовый анализ"}
        }
        
        print("🔄 Генерируем HTML отчёт...")
        report_path = generate_html_report(test_card_data, analysis_data)
        
        print(f"✅ Отчёт сгенерирован: {report_path}")
        
        # Проверяем, что файл создался
        if os.path.exists(report_path):
            file_size = os.path.getsize(report_path)
            print(f"📄 Размер файла: {file_size} байт")
            report_test = True
        else:
            print("❌ Файл отчёта не найден")
            report_test = False
            
    except Exception as e:
        print(f"❌ Ошибка генерации отчёта: {e}")
        report_test = False
    
    print()
    
    # Тест 3: Интеграция с Supabase
    print("3️⃣ Тест интеграции с Supabase:")
    try:
        from supabase import create_client, Client
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            print("❌ Отсутствуют переменные окружения Supabase")
            supabase_test = False
        else:
            supabase: Client = create_client(supabase_url, supabase_key)
            
            # Тестируем подключение
            print("🔄 Тестируем подключение к Supabase...")
            response = supabase.table('Cards').select('count').limit(1).execute()
            
            print("✅ Подключение к Supabase успешно!")
            supabase_test = True
            
    except Exception as e:
        print(f"❌ Ошибка подключения к Supabase: {e}")
        supabase_test = False
    
    print()
    
    # Итоги
    print("=" * 60)
    print("📋 ИТОГИ ТЕСТИРОВАНИЯ ПОЛНОГО ПАЙПЛАЙНА:")
    print(f"AI-анализ: {'✅ УСПЕХ' if ai_test else '❌ ОШИБКА'}")
    print(f"Генерация отчёта: {'✅ УСПЕХ' if report_test else '❌ ОШИБКА'}")
    print(f"Supabase: {'✅ УСПЕХ' if supabase_test else '❌ ОШИБКА'}")
    
    if ai_test and report_test and supabase_test:
        print("\n🎉 Все компоненты работают корректно!")
        print("🚀 Система готова к использованию!")
        return True
    else:
        print("\n⚠️ Есть проблемы с некоторыми компонентами.")
        return False

def test_worker_integration():
    """Тестирует интеграцию с воркером"""
    
    print("\n" + "=" * 60)
    print("🔧 Тест интеграции с воркером:")
    
    try:
        # Импортируем функции воркера
        from worker import process_queue
        
        print("✅ Функции воркера импортированы успешно")
        
        # Проверяем, что можем создать тестовую запись
        from supabase import create_client, Client
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        
        if supabase_url and supabase_key:
            supabase: Client = create_client(supabase_url, supabase_key)
            
            # Создаём тестовую запись в ParseQueue
            test_queue_item = {
                "user_id": "test_user",
                "url": "https://yandex.ru/maps/org/test-cafe/1234567890",
                "status": "pending"
            }
            
            print("🔄 Создаём тестовую запись в очереди...")
            result = supabase.table("ParseQueue").insert(test_queue_item).execute()
            
            if result.data:
                print("✅ Тестовая запись создана")
                
                # Удаляем тестовую запись
                supabase.table("ParseQueue").delete().eq("url", test_queue_item["url"]).execute()
                print("✅ Тестовая запись удалена")
                
                worker_test = True
            else:
                print("❌ Не удалось создать тестовую запись")
                worker_test = False
        else:
            print("❌ Отсутствуют переменные окружения Supabase")
            worker_test = False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования воркера: {e}")
        worker_test = False
    
    return worker_test

if __name__ == "__main__":
    # Тест полного пайплайна
    pipeline_success = test_full_pipeline()
    
    # Тест интеграции с воркером
    worker_success = test_worker_integration()
    
    # Финальные итоги
    print("\n" + "=" * 60)
    print("🏁 ФИНАЛЬНЫЕ ИТОГИ:")
    print(f"Полный пайплайн: {'✅ ГОТОВ' if pipeline_success else '❌ ТРЕБУЕТ ДОРАБОТКИ'}")
    print(f"Интеграция с воркером: {'✅ ГОТОВ' if worker_success else '❌ ТРЕБУЕТ ДОРАБОТКИ'}")
    
    if pipeline_success and worker_success:
        print("\n🎉 ВСЯ СИСТЕМА РАБОТАЕТ КОРРЕКТНО!")
        print("🚀 Можно запускать в продакшн!")
    else:
        print("\n⚠️ Система требует доработки перед запуском в продакшн.") 