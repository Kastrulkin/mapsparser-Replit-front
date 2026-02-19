#!/usr/bin/env python3
"""
Тест для Network Interception парсера Яндекс.Карт
"""

import sys
import os

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from parser_interception import parse_yandex_card, YandexMapsInterceptionParser
import json


def test_location_info_org_bound_validation():
    """
    Сценарий: location-info вернул area-based данные (Эрмитаж), org_id (Оливер) не в ответе.
    Core-поля не должны загрязняться.
    """
    parser = YandexMapsInterceptionParser()
    parser.org_id = "203293742306"  # Оливер

    # area-based: в ответе только Эрмитаж и др., нет 203293742306
    area_based_response = {
        "data": {
            "toponymSearchResult": {
                "items": [{
                    "title": "Государственный Эрмитаж",
                    "uri": "ymapsbm1://org?oid=1057721048",
                }],
            }
        }
    }
    assert parser._is_location_info_org_bound(area_based_response) is False

    # org-bound: в ответе есть showcase с нашей организацией
    org_bound_response = {
        "data": {
            "toponymSearchResult": {
                "items": [{
                    "toponymDiscovery": {
                        "categories": [{
                            "showcase": [{
                                "id": "203293742306",
                                "title": "Оливер",
                            }]
                        }]
                    }
                }],
            }
        }
    }
    assert parser._is_location_info_org_bound(org_bound_response) is True

    # org-bound через uri oid=
    org_bound_via_uri = {
        "data": {
            "items": [{"uri": "ymapsbm1://org?oid=203293742306", "title": "Оливер"}]
        }
    }
    assert parser._is_location_info_org_bound(org_bound_via_uri) is True

    print("✅ test_location_info_org_bound_validation passed")


def test_location_info_org_bound_recursive():
    """Рекурсивная валидация: org_id глубоко, в oid= строке, не найден."""
    parser = YandexMapsInterceptionParser()
    parser.org_id = "203293742306"

    # org_id глубоко вложен
    deep = {"a": {"b": {"c": {"d": {"id": "203293742306"}}}}}
    assert parser._is_location_info_org_bound(deep) is True

    # org_id в строке oid=...
    oid_in_string = {"meta": {"link": "https://yandex.ru/maps/org/oliver/203293742306/"}}
    assert parser._is_location_info_org_bound(oid_in_string) is True

    oid_in_uri = {"items": [{"uri": "ymapsbm1://org?oid=203293742306"}]}
    assert parser._is_location_info_org_bound(oid_in_uri) is True

    # org_id нигде не встречается
    no_org = {"data": {"items": [{"id": "999", "title": "Другой"}]}}
    assert parser._is_location_info_org_bound(no_org) is False

    print("✅ test_location_info_org_bound_recursive passed")


def test_extract_org_object_from_location_info():
    """Извлечение объекта организации из location-info."""
    parser = YandexMapsInterceptionParser()
    parser.org_id = "203293742306"

    # Массив объектов, только один соответствует org_id
    multi = {
        "data": {
            "items": [
                {"id": "111", "title": "Чужой 1"},
                {"id": "203293742306", "title": "Оливер", "address": "СПб"},
                {"id": "333", "title": "Чужой 2"},
            ]
        }
    }
    obj = parser._extract_org_object_from_location_info(multi)
    assert obj is not None
    assert obj.get("id") == "203293742306"
    assert obj.get("title") == "Оливер"

    # org_id в строке, но объекта с id/oid нет
    string_only = {"meta": {"ref": "oid=203293742306"}, "items": []}
    obj2 = parser._extract_org_object_from_location_info(string_only)
    assert obj2 is None

    print("✅ test_extract_org_object_from_location_info passed")


def test_score_location_info_payload():
    """Выбор лучшего org-bound по score."""
    parser = YandexMapsInterceptionParser()

    empty = {}
    assert parser._score_location_info_payload(empty) == 0

    full = {"phone": "+7", "site": "x.ru", "hours": "9-18", "rating": "4.5", "description": "text"}
    assert parser._score_location_info_payload(full) == 5

    partial = {"phone": "+7", "rating": "4.5"}
    assert parser._score_location_info_payload(partial) == 2

    print("✅ test_score_location_info_payload passed")


def test_extract_ll_z_and_build_overview_url():
    """Проверка извлечения ll,z и сборки overview URL."""
    parser = YandexMapsInterceptionParser()
    url = "https://yandex.ru/maps/org/oliver/203293742306/?ll=30.219413%2C59.987283&z=13"
    ll, z = parser._extract_ll_z_from_url(url)
    assert ll == "30.219413,59.987283"
    assert z == "13"

    overview = parser._build_overview_url(url, ll, z)
    assert "/prices/" not in overview
    assert "ll=30.219413" in overview or "ll=30.219413%2C59.987283" in overview
    assert "z=13" in overview

    # С /prices/ в URL
    prices_url = "https://yandex.com/maps/org/oliver/203293742306/prices/?ll=131.757804%2C63.857119&z=3"
    overview2 = parser._build_overview_url(prices_url, "30.219413,59.987283", "13")
    assert "/prices/" not in overview2
    assert "30.219413" in overview2

    print("✅ test_extract_ll_z_and_build_overview_url passed")


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

def test_wait_for_goods_logic():
    """Harness: логика ожидания goods (имитация products_pages)."""
    products = []
    n0 = len(products)
    # Имитация: после 2 итераций добавляем goods
    for i in range(5):
        if i == 2:
            products.append({"items": []})
        n = len(products)
        if n > n0:
            n0 = n
        elif n0 > 0:
            break
    assert len(products) == 1
    assert n0 == 1
    print("✅ test_wait_for_goods_logic passed")


if __name__ == "__main__":
    # Unit-тесты без браузера
    test_location_info_org_bound_validation()
    test_location_info_org_bound_recursive()
    test_extract_org_object_from_location_info()
    test_score_location_info_payload()
    test_extract_ll_z_and_build_overview_url()
    test_wait_for_goods_logic()
    # Интеграционный тест (требует браузер) — пропустить при --unit-only
    if "--unit-only" not in sys.argv:
        success = test_parser_interception()
        sys.exit(0 if success else 1)
    print("✅ Unit tests OK (integration skipped)")

