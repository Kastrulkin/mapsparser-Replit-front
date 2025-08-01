#!/usr/bin/env python3
"""
Тест полного анализа с найденной моделью
"""

import os
import sys
from dotenv import load_dotenv

# Добавляем src в путь
sys.path.append('src')
load_dotenv()

def test_ai_analysis():
    """Тестируем ИИ анализ"""
    try:
        from ai_analyzer import call_huggingface_analysis
        
        # Тестовые данные
        test_data = """
        Салон красоты "Елена" у метро Парк Победы
        Адрес: Московский район, ул. Ленина, 123
        Услуги: Стрижка, маникюр, педикюр
        Часы работы: 9:00-20:00
        Оплата: наличные, карты
        Фото: 8 штук
        Отзывы: 15 отзывов, рейтинг 4.2
        """
        
        print("🔍 Тест ИИ анализа")
        print("=" * 50)
        print(f"📝 Тестовые данные:\n{test_data}")
        print()
        
        # Вызываем анализ
        print("🤖 Запускаем ИИ анализ...")
        result = call_huggingface_analysis(test_data)
        
        print("📊 Результат анализа:")
        print("=" * 30)
        
        if "error" in result:
            print(f"❌ Ошибка: {result['error']}")
            return False
        else:
            print(f"✅ Тип анализа: {result.get('analysis_type', 'unknown')}")
            print(f"🤖 Модель: {result.get('model_used', 'unknown')}")
            print()
            print("📝 Рекомендации:")
            print(result.get('generated_text', 'Нет текста'))
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False

def test_supabase_integration():
    """Тестируем интеграцию с Supabase"""
    try:
        from save_to_supabase import save_analysis_result
        
        # Тестовые данные
        test_analysis = {
            "business_name": "Салон красоты Елена",
            "analysis_text": "Тестовый анализ ИИ",
            "model_used": "ainize/bart-base-cnn",
            "analysis_type": "ai_model"
        }
        
        print("\n🔍 Тест интеграции с Supabase")
        print("=" * 40)
        
        result = save_analysis_result(test_analysis)
        
        if result:
            print("✅ Анализ сохранен в Supabase")
            return True
        else:
            print("❌ Ошибка сохранения в Supabase")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка Supabase: {e}")
        return False

def main():
    """Основной тест"""
    print("🧪 Полный тест системы анализа")
    print("=" * 60)
    
    # Тест ИИ анализа
    ai_success = test_ai_analysis()
    
    # Тест Supabase (опционально)
    if ai_success:
        print("\n" + "="*60)
        print("💾 Тестируем сохранение в базу данных...")
        supabase_success = test_supabase_integration()
    else:
        supabase_success = False
    
    # Итоговый результат
    print("\n" + "="*60)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print(f"🤖 ИИ анализ: {'✅ РАБОТАЕТ' if ai_success else '❌ НЕ РАБОТАЕТ'}")
    print(f"💾 Supabase: {'✅ РАБОТАЕТ' if supabase_success else '❌ НЕ РАБОТАЕТ'}")
    
    if ai_success:
        print("\n🎉 Система ИИ анализа готова к работе!")
        print("💡 Теперь можно:")
        print("   1. Добавить запрос в очередь Supabase")
        print("   2. Запустить воркер для обработки")
        print("   3. Получить готовый отчет")
    else:
        print("\n⚠️ Требуется доработка ИИ анализа")

if __name__ == "__main__":
    main() 