#!/usr/bin/env python3
"""
Тест обновленного анализа с новым промптом и моделью t5-large
"""

import os
import sys
from dotenv import load_dotenv

# Добавляем src в путь
sys.path.append('src')

from ai_analyzer import analyze_business_data
from model_config import get_model_config, get_prompt

load_dotenv()

def test_updated_analysis():
    """Тестируем обновленный анализ"""
    
    print("🔍 Тестируем обновленный анализ Яндекс Карт")
    print("=" * 50)
    
    # Проверяем конфигурацию модели
    model_config = get_model_config()
    print(f"📊 Модель: {model_config['name']}")
    print(f"📏 Максимальная длина: {model_config['max_length']}")
    print(f"🌡️ Температура: {model_config['temperature']}")
    
    # Тестовые данные карточки бизнеса
    test_data = {
        "title": "Салон красоты Елена у метро Парк Победы",
        "address": "Москва, ул. Кутузовский проспект, 15",
        "phone": "+7 (495) 123-45-67",
        "website": "https://salon-elena.ru",
        "description": "Салон красоты предлагает стрижки, окрашивание, маникюр",
        "services": [
            "Стрижка женская",
            "Окрашивание волос", 
            "Маникюр",
            "Педикюр"
        ],
        "working_hours": "Пн-Пт 9:00-20:00, Сб-Вс 10:00-18:00",
        "rating": 4.2,
        "reviews_count": 15,
        "photos_count": 8,
        "categories": ["Парикмахерская", "Салон красоты"]
    }
    
    print(f"\n📋 Тестовые данные:")
    print(f"Название: {test_data['title']}")
    print(f"Адрес: {test_data['address']}")
    print(f"Услуги: {', '.join(test_data['services'])}")
    print(f"Рейтинг: {test_data['rating']}/5 ({test_data['reviews_count']} отзывов)")
    print(f"Фото: {test_data['photos_count']} шт.")
    
    try:
        # Выполняем анализ
        print(f"\n🤖 Выполняем ИИ-анализ...")
        result = analyze_business_data(test_data)
        
        print(f"\n✅ Анализ завершен!")
        print(f"📊 SEO-оценка: {result['score']}/10")
        
        print(f"\n📝 Рекомендации:")
        print("-" * 30)
        print(result['analysis'])
        
        print(f"\n🎯 Конкретные советы:")
        print("-" * 30)
        for i, rec in enumerate(result['recommendations'], 1):
            print(f"{i}. {rec}")
            
    except Exception as e:
        print(f"❌ Ошибка при анализе: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_updated_analysis()
    if success:
        print(f"\n🎉 Тест прошел успешно! Анализ работает с новым промптом и моделью.")
    else:
        print(f"\n💥 Тест не прошел. Нужно исправить ошибки.") 