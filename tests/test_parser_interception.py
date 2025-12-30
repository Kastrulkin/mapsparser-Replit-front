#!/usr/bin/env python3
"""
Тест для Network Interception парсера Яндекс.Карт
"""

import sys
import os

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from parser_interception import parse_yandex_card
import json

def test_parser_interception():
    """Тестирование Network Interception парсера"""
    
    # Тестовый URL
    test_url = "https://yandex.ru/maps/org/feniks/1058063126/?ll=30.259485%2C59.990665&z=16.49"
    
    print("🧪 Тестирование Network Interception парсера")
    print(f"📋 URL: {test_url}")
    print("-" * 60)
    
    try:
        result = parse_yandex_card(test_url)
        
        print("\n✅ Парсинг успешен!")
        print(f"📊 Найдено данных:")
        print(f"  - Название: {result.get('title', 'Не найдено')}")
        print(f"  - Адрес: {result.get('address', 'Не найден')}")
        print(f"  - Телефон: {result.get('phone', 'Не найден')}")
        print(f"  - Рейтинг: {result.get('rating', 'Не найден')}")
        print(f"  - Отзывов: {result.get('reviews_count', 0)}")
        print(f"  - Новостей: {len(result.get('news', []))}")
        print(f"  - Фото: {result.get('photos_count', 0)}")
        
        # Сохраняем результат в файл для анализа
        with open('test_parser_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print("\n💾 Результат сохранен в test_parser_result.json")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при парсинге: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_parser_interception()
    sys.exit(0 if success else 1)

