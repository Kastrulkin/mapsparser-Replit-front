#!/usr/bin/env python3
"""
Финальный тест системы SEO-анализатора
"""
import os
import sys
import uuid
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем src в путь для импорта
sys.path.append('src')

def test_complete_system():
    """Тестирует полную систему с исправленным UUID"""
    
    print("🎯 ФИНАЛЬНЫЙ ТЕСТ СИСТЕМЫ SEO-АНАЛИЗАТОРА")
    print("=" * 60)
    
    # Тест 1: Hugging Face API
    print("1️⃣ Тест Hugging Face API:")
    try:
        from ai_analyzer import call_huggingface_analysis
        
        test_text = "Кафе 'Уютное место' с рейтингом 4.2 и 45 отзывами"
        result = call_huggingface_analysis(test_text)
        
        if 'error' not in result:
            print("✅ Hugging Face API работает")
            hf_test = True
        else:
            print(f"❌ Ошибка Hugging Face: {result}")
            hf_test = False
            
    except Exception as e:
        print(f"❌ Ошибка Hugging Face: {e}")
        hf_test = False
    
    print()
    
    # Тест 2: AI-анализ с реальными данными
    print("2️⃣ Тест AI-анализа:")
    try:
        from ai_analyzer import analyze_business_data
        
        test_data = {
            "title": "Ресторан 'Престиж'",
            "address": "пр. Мира, 15, Санкт-Петербург",
            "rating": 4.8,
            "reviews_count": 127,
            "overview": {
                "description": "Элитный ресторан с авторской кухней и изысканным интерьером"
            },
            "categories": ["Рестораны", "Авторская кухня"]
        }
        
        analysis = analyze_business_data(test_data)
        
        print(f"✅ AI-анализ завершён")
        print(f"  Оценка: {analysis['score']}/100")
        print(f"  Рекомендаций: {len(analysis['recommendations'])}")
        
        ai_test = True
        
    except Exception as e:
        print(f"❌ Ошибка AI-анализа: {e}")
        ai_test = False
    
    print()
    
    # Тест 3: Supabase с правильным UUID
    print("3️⃣ Тест Supabase с UUID:")
    try:
        from supabase import create_client, Client
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        
        if supabase_url and supabase_key:
            supabase: Client = create_client(supabase_url, supabase_key)
            
            # Создаём правильный UUID
            test_user_id = str(uuid.uuid4())
            
            test_queue_item = {
                "user_id": test_user_id,
                "url": "https://yandex.ru/maps/org/test-restaurant/1234567890",
                "status": "pending"
            }
            
            print(f"🔄 Создаём тестовую запись с UUID: {test_user_id[:8]}...")
            result = supabase.table("ParseQueue").insert(test_queue_item).execute()
            
            if result.data:
                print("✅ Тестовая запись создана")
                
                # Удаляем тестовую запись
                supabase.table("ParseQueue").delete().eq("user_id", test_user_id).execute()
                print("✅ Тестовая запись удалена")
                
                supabase_test = True
            else:
                print("❌ Не удалось создать тестовую запись")
                supabase_test = False
        else:
            print("❌ Отсутствуют переменные окружения Supabase")
            supabase_test = False
            
    except Exception as e:
        print(f"❌ Ошибка Supabase: {e}")
        supabase_test = False
    
    print()
    
    # Тест 4: Генерация отчёта
    print("4️⃣ Тест генерации отчёта:")
    try:
        from report import generate_html_report
        
        test_card = {
            "title": "Кафе 'Солнышко'",
            "address": "ул. Пушкина, 10, Москва",
            "rating": 4.5,
            "reviews_count": 89
        }
        
        analysis_data = {
            'score': 75,
            'recommendations': [
                "Добавьте больше фотографий блюд",
                "Улучшите описание услуг",
                "Попросите клиентов оставлять отзывы"
            ],
            'ai_analysis': {
                'generated_text': 'Хороший рейтинг и достаточное количество отзывов. Есть потенциал для улучшения.'
            }
        }
        
        report_path = generate_html_report(test_card, analysis_data)
        
        if os.path.exists(report_path):
            file_size = os.path.getsize(report_path)
            print(f"✅ Отчёт сгенерирован: {file_size} байт")
            report_test = True
        else:
            print("❌ Файл отчёта не найден")
            report_test = False
            
    except Exception as e:
        print(f"❌ Ошибка генерации отчёта: {e}")
        report_test = False
    
    print()
    
    # Итоги
    print("=" * 60)
    print("📋 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ:")
    print(f"Hugging Face API: {'✅ РАБОТАЕТ' if hf_test else '❌ ОШИБКА'}")
    print(f"AI-анализ: {'✅ РАБОТАЕТ' if ai_test else '❌ ОШИБКА'}")
    print(f"Supabase: {'✅ РАБОТАЕТ' if supabase_test else '❌ ОШИБКА'}")
    print(f"Генерация отчётов: {'✅ РАБОТАЕТ' if report_test else '❌ ОШИБКА'}")
    
    success_count = sum([hf_test, ai_test, supabase_test, report_test])
    total_count = 4
    
    print(f"\n📊 Успешных тестов: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 ВСЯ СИСТЕМА РАБОТАЕТ ИДЕАЛЬНО!")
        print("🚀 Готово к продакшн!")
        return True
    elif success_count >= 3:
        print("\n✅ СИСТЕМА В ОСНОВНОМ РАБОТАЕТ!")
        print("⚠️ Есть небольшие проблемы, но можно использовать")
        return True
    else:
        print("\n❌ СИСТЕМА ТРЕБУЕТ ДОРАБОТКИ!")
        return False

if __name__ == "__main__":
    success = test_complete_system()
    
    if success:
        print("\n🎯 РЕКОМЕНДАЦИИ:")
        print("1. Запустите воркер: python3 src/worker.py")
        print("2. Запустите фронтенд: cd frontend && npm run dev")
        print("3. Добавьте ссылки на Яндекс.Карты через веб-интерфейс")
        print("4. Система автоматически обработает запросы и создаст отчёты")
    else:
        print("\n🔧 НЕОБХОДИМО ИСПРАВИТЬ ПРОБЛЕМЫ ПЕРЕД ЗАПУСКОМ") 