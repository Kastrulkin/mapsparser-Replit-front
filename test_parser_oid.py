#!/usr/bin/env python3
"""
Тестовый скрипт для проверки парсинга с проверкой OID
"""
import sys
import os
sys.path.append('src')

from parser_interception import parse_yandex_card
import json

def test_parsing(url: str):
    """Тестирует парсинг и выводит результаты"""
    print(f"🔍 Тестируем парсинг: {url}")
    print("=" * 80)
    
    try:
        result = parse_yandex_card(url)
        
        # Извлекаем ключевые данные
        expected_oid = result.get('expected_oid', 'unknown')
        extracted_oid = result.get('oid', 'unknown')
        parse_status = result.get('parse_status', 'unknown')
        missing_sections = result.get('missing_sections', [])
        
        organization = result.get('organization', {})
        title = organization.get('title') or organization.get('title_normalized', 'N/A')
        address = organization.get('address', 'N/A')
        source_endpoint = organization.get('source_endpoint', 'unknown')
        
        stats = result.get('stats', {})
        reviews_total = stats.get('reviews_total', 0)
        reviews_loaded = stats.get('reviews_loaded', 0)
        reviews_fully_loaded = stats.get('reviews_fully_loaded', True)
        services_total = stats.get('services_total', 0)
        news_total = stats.get('news_total', 0)
        
        # Выводим результаты
        print(f"\n📊 РЕЗУЛЬТАТЫ ПАРСИНГА:")
        print(f"   Expected OID: {expected_oid}")
        print(f"   Extracted OID: {extracted_oid}")
        print(f"   OID Match: {'✅' if str(expected_oid) == str(extracted_oid) else '❌'}")
        print(f"   Parse Status: {parse_status}")
        print(f"   Missing Sections: {missing_sections if missing_sections else 'None'}")
        print(f"\n🏢 ОРГАНИЗАЦИЯ:")
        print(f"   Title: {title}")
        print(f"   Address: {address}")
        print(f"   Source Endpoint: {source_endpoint}")
        print(f"\n📈 СТАТИСТИКА:")
        print(f"   Reviews Total: {reviews_total}")
        print(f"   Reviews Loaded: {reviews_loaded}")
        print(f"   Reviews Fully Loaded: {reviews_fully_loaded}")
        print(f"   Services Total: {services_total}")
        print(f"   News Total: {news_total}")
        
        # Проверка на ошибки
        if parse_status == 'fail':
            print(f"\n❌ ПАРСИНГ ПРОВАЛЕН: {result.get('missing_sections', [])}")
            if 'oid_mismatch' in missing_sections:
                print(f"   ⚠️ КРИТИЧЕСКАЯ ОШИБКА: OID не совпадает!")
        elif parse_status == 'partial':
            print(f"\n⚠️ ПАРСИНГ ЧАСТИЧНЫЙ: отсутствуют секции {missing_sections}")
        else:
            print(f"\n✅ ПАРСИНГ УСПЕШЕН")
        
        # Сохраняем результат в файл
        output_file = f"test_parse_result_{expected_oid}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Полный результат сохранён в: {output_file}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ ОШИБКА ПАРСИНГА: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Тестовый URL для "Оливер"
    test_url = "https://yandex.com/maps/org/oliver/203293742306/?ll=30.219413%2C59.987283&z=13"
    
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    
    test_parsing(test_url)
