#!/usr/bin/env python3
"""
Тесты для ChatGPT API endpoints
"""
import json
import os
import time
from datetime import datetime, timedelta

import pytest
import requests

# Конфигурация
BASE_URL = os.getenv("CHATGPT_API_BASE_URL", "http://localhost:8000").rstrip("/")
CHATGPT_USER_ID = "test_user_123"
ADMIN_TOKEN = None  # Установите токен администратора для тестов статистики
pytestmark = pytest.mark.skipif(
    os.getenv("CHATGPT_API_INTEGRATION") != "1",
    reason="set CHATGPT_API_INTEGRATION=1 for live HTTP integration tests",
)

def print_test(name):
    """Вывести название теста"""
    print(f"\n{'='*60}")
    print(f"🧪 Тест: {name}")
    print(f"{'='*60}")

def print_success(message):
    """Вывести успешное сообщение"""
    print(f"✅ {message}")

def print_error(message):
    """Вывести сообщение об ошибке"""
    print(f"❌ {message}")

def print_info(message):
    """Вывести информационное сообщение"""
    print(f"ℹ️  {message}")

def test_search_salons():
    """Тест поиска салонов"""
    print_test("Поиск салонов")
    
    # Тест 1: Базовый поиск
    print_info("Тест 1: Базовый поиск")
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/search",
        params={
            "city": "Москва",
            "service": "стрижка"
        },
        headers={
            "X-ChatGPT-User-ID": CHATGPT_USER_ID
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print_success(f"Поиск выполнен: найдено {data.get('count', 0)} результатов")
        print_info(f"Сетей: {data.get('networks_count', 0)}, Отдельных салонов: {data.get('standalone_count', 0)}")
    else:
        print_error(f"Ошибка поиска: {response.status_code} - {response.text}")
        return False
    
    # Тест 2: Поиск с геолокацией
    print_info("Тест 2: Поиск с геолокацией")
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/search",
        params={
            "city": "Москва",
            "service": "стрижка",
            "latitude": 55.7558,
            "longitude": 37.6173
        },
        headers={
            "X-ChatGPT-User-ID": CHATGPT_USER_ID
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print_success("Поиск с геолокацией выполнен")
        if data.get('standalone_salons'):
            first_salon = data['standalone_salons'][0]
            if 'distance' in first_salon:
                print_info(f"Расстояние до ближайшего салона: {first_salon['distance']} км")
    else:
        print_error(f"Ошибка поиска с геолокацией: {response.status_code}")
        return False
    
    # Тест 3: Поиск с фильтрами
    print_info("Тест 3: Поиск с фильтрами")
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/search",
        params={
            "city": "Москва",
            "service": "стрижка",
            "min_rating": 4.0,
            "budget": 2000,
            "keywords": "маникюр"
        },
        headers={
            "X-ChatGPT-User-ID": CHATGPT_USER_ID
        }
    )
    
    if response.status_code == 200:
        print_success("Поиск с фильтрами выполнен")
    else:
        print_error(f"Ошибка поиска с фильтрами: {response.status_code}")
        return False
    
    # Тест 4: Ошибка - отсутствуют обязательные параметры
    print_info("Тест 4: Обработка ошибок - отсутствуют параметры")
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/search",
        params={"city": "Москва"}
    )
    
    if response.status_code == 400:
        print_success("Ошибка корректно обработана: отсутствует параметр service")
    else:
        print_error(f"Ожидалась ошибка 400, получен статус {response.status_code}")
        return False
    
    return True

def test_get_salon_details():
    """Тест получения информации о салоне"""
    print_test("Получение информации о салоне")
    
    # Сначала найдем салон
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/search",
        params={"city": "Москва", "service": "стрижка"},
        headers={"X-ChatGPT-User-ID": CHATGPT_USER_ID}
    )
    
    if response.status_code != 200:
        print_error("Не удалось найти салон для теста")
        return False
    
    data = response.json()
    salon_id = None
    
    # Ищем первый салон
    if data.get('standalone_salons'):
        salon_id = data['standalone_salons'][0]['id']
    elif data.get('networks'):
        if data['networks'][0].get('salons'):
            salon_id = data['networks'][0]['salons'][0]['id']
    
    if not salon_id:
        print_info("Салонов не найдено, пропускаем тест")
        return True
    
    # Тест 1: Получение информации о салоне
    print_info(f"Тест 1: Получение информации о салоне {salon_id}")
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/salon/{salon_id}"
    )
    
    if response.status_code == 200:
        data = response.json()
        salon = data.get('salon', {})
        print_success(f"Информация получена: {salon.get('name', 'N/A')}")
        print_info(f"Рейтинг: {salon.get('rating', 'N/A')}, Отзывов: {salon.get('reviews_count', 'N/A')}")
        print_info(f"Услуг: {len(salon.get('services', []))}")
    else:
        print_error(f"Ошибка получения информации: {response.status_code}")
        return False
    
    # Тест 2: Несуществующий салон
    print_info("Тест 2: Обработка ошибок - несуществующий салон")
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/salon/00000000-0000-0000-0000-000000000000"
    )
    
    if response.status_code == 404:
        print_success("Ошибка корректно обработана: салон не найден")
    else:
        print_error(f"Ожидалась ошибка 404, получен статус {response.status_code}")
        return False
    
    return True

def test_available_slots():
    """Тест получения доступных слотов"""
    print_test("Получение доступных слотов")
    
    # Найдем салон
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/search",
        params={"city": "Москва", "service": "стрижка"},
        headers={"X-ChatGPT-User-ID": CHATGPT_USER_ID}
    )
    
    if response.status_code != 200:
        print_error("Не удалось найти салон для теста")
        return False
    
    data = response.json()
    salon_id = None
    
    if data.get('standalone_salons'):
        salon_id = data['standalone_salons'][0]['id']
    elif data.get('networks'):
        if data['networks'][0].get('salons'):
            salon_id = data['networks'][0]['salons'][0]['id']
    
    if not salon_id:
        print_info("Салонов не найдено, пропускаем тест")
        return True
    
    # Тест 1: Получение доступных слотов
    print_info(f"Тест 1: Получение доступных слотов для салона {salon_id}")
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/salon/{salon_id}/available-slots",
        params={"days": 7}
    )
    
    if response.status_code == 200:
        data = response.json()
        slots_count = len(data.get('slots', []))
        print_success(f"Доступных слотов: {slots_count}")
        if slots_count > 0:
            print_info(f"Первый слот: {data['slots'][0].get('datetime_local', 'N/A')}")
    else:
        print_error(f"Ошибка получения слотов: {response.status_code}")
        return False
    
    # Тест 2: Слоты с указанием услуги
    print_info("Тест 2: Слоты с указанием услуги")
    salon_data = requests.get(f"{BASE_URL}/api/chatgpt/salon/{salon_id}").json()
    service_id = None
    if salon_data.get('salon', {}).get('services'):
        service_id = salon_data['salon']['services'][0]['id']
    
    if service_id:
        response = requests.get(
            f"{BASE_URL}/api/chatgpt/salon/{salon_id}/available-slots",
            params={"serviceId": service_id, "days": 7}
        )
        if response.status_code == 200:
            print_success("Слоты с учетом услуги получены")
        else:
            print_error(f"Ошибка: {response.status_code}")
            return False
    
    return True

def test_booking():
    """Тест создания бронирования"""
    print_test("Создание бронирования")
    
    # Найдем салон
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/search",
        params={"city": "Москва", "service": "стрижка"},
        headers={"X-ChatGPT-User-ID": CHATGPT_USER_ID}
    )
    
    if response.status_code != 200:
        print_error("Не удалось найти салон для теста")
        return False
    
    data = response.json()
    salon_id = None
    service_id = None
    
    if data.get('standalone_salons'):
        salon_id = data['standalone_salons'][0]['id']
        if data['standalone_salons'][0].get('services'):
            service_id = data['standalone_salons'][0]['services'][0]['id']
    
    if not salon_id:
        print_info("Салонов не найдено, пропускаем тест")
        return True
    
    # Тест 1: Создание бронирования
    print_info(f"Тест 1: Создание бронирования в салоне {salon_id}")
    booking_time = (datetime.now() + timedelta(days=1)).isoformat() + "Z"
    
    booking_data = {
        "salonId": salon_id,
        "clientName": "Тестовый Клиент",
        "clientPhone": "+7-900-123-45-67",
        "clientEmail": "test@example.com",
        "bookingTime": booking_time,
        "notes": "Тестовое бронирование"
    }
    
    if service_id:
        booking_data["serviceId"] = service_id
    
    response = requests.post(
        f"{BASE_URL}/api/chatgpt/book",
        json=booking_data,
        headers={
            "Content-Type": "application/json",
            "X-ChatGPT-User-ID": CHATGPT_USER_ID
        }
    )
    
    if response.status_code == 201:
        data = response.json()
        print_success(f"Бронирование создано: {data.get('bookingId', 'N/A')}")
    else:
        print_error(f"Ошибка создания бронирования: {response.status_code} - {response.text}")
        return False
    
    # Тест 2: Ошибка - отсутствуют обязательные поля
    print_info("Тест 2: Обработка ошибок - отсутствуют обязательные поля")
    response = requests.post(
        f"{BASE_URL}/api/chatgpt/book",
        json={"salonId": salon_id},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 400:
        print_success("Ошибка корректно обработана: отсутствуют обязательные поля")
    else:
        print_error(f"Ожидалась ошибка 400, получен статус {response.status_code}")
        return False
    
    return True

def test_user_preferences():
    """Тест получения предпочтений пользователя"""
    print_test("Получение предпочтений пользователя")
    
    # Сначала сделаем несколько поисков для создания истории
    print_info("Создание истории поисков...")
    for i in range(3):
        requests.get(
            f"{BASE_URL}/api/chatgpt/search",
            params={"city": "Москва", "service": f"услуга{i}"},
            headers={"X-ChatGPT-User-ID": CHATGPT_USER_ID}
        )
        time.sleep(0.5)
    
    # Тест 1: Получение предпочтений
    print_info("Тест 1: Получение предпочтений")
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/user/preferences",
        headers={"X-ChatGPT-User-ID": CHATGPT_USER_ID}
    )
    
    if response.status_code == 200:
        data = response.json()
        prefs = data.get('preferences', {})
        print_success("Предпочтения получены")
        print_info(f"Предпочтительный город: {prefs.get('preferred_city', 'N/A')}")
        print_info(f"Всего взаимодействий: {prefs.get('total_interactions', 0)}")
        print_info(f"Последних поисков: {len(prefs.get('recent_searches', []))}")
    else:
        print_error(f"Ошибка получения предпочтений: {response.status_code}")
        return False
    
    # Тест 2: Ошибка - отсутствует заголовок
    print_info("Тест 2: Обработка ошибок - отсутствует заголовок")
    response = requests.get(f"{BASE_URL}/api/chatgpt/user/preferences")
    
    if response.status_code == 400:
        print_success("Ошибка корректно обработана: отсутствует заголовок X-ChatGPT-User-ID")
    else:
        print_error(f"Ожидалась ошибка 400, получен статус {response.status_code}")
        return False
    
    return True

def test_statistics():
    """Тест получения статистики"""
    print_test("Получение статистики")
    
    if not ADMIN_TOKEN:
        print_info("Токен администратора не установлен, пропускаем тест")
        return True
    
    # Тест 1: Получение статистики
    print_info("Тест 1: Получение статистики")
    response = requests.get(
        f"{BASE_URL}/api/chatgpt/stats",
        params={"days": 30},
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        stats = data.get('statistics', {})
        print_success("Статистика получена")
        print_info(f"Всего запросов: {stats.get('total_requests', 0)}")
        print_info(f"Уникальных пользователей: {stats.get('unique_users', 0)}")
        print_info(f"Успешность: {stats.get('success_rate', 0)}%")
    else:
        print_error(f"Ошибка получения статистики: {response.status_code}")
        return False
    
    # Тест 2: Ошибка - нет авторизации
    print_info("Тест 2: Обработка ошибок - нет авторизации")
    response = requests.get(f"{BASE_URL}/api/chatgpt/stats")
    
    if response.status_code == 401:
        print_success("Ошибка корректно обработана: требуется авторизация")
    else:
        print_error(f"Ожидалась ошибка 401, получен статус {response.status_code}")
        return False
    
    return True

def run_all_tests():
    """Запустить все тесты"""
    print("\n" + "="*60)
    print("🚀 ЗАПУСК ТЕСТОВ ChatGPT API")
    print("="*60)
    
    tests = [
        ("Поиск салонов", test_search_salons),
        ("Информация о салоне", test_get_salon_details),
        ("Доступные слоты", test_available_slots),
        ("Создание бронирования", test_booking),
        ("Предпочтения пользователя", test_user_preferences),
        ("Статистика", test_statistics),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Критическая ошибка в тесте '{name}': {e}")
            results.append((name, False))
    
    # Итоги
    print("\n" + "="*60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{status}: {name}")
    
    print(f"\nВсего тестов: {total}")
    print(f"Успешно: {passed}")
    print(f"Провалено: {total - passed}")
    print(f"Успешность: {passed/total*100:.1f}%")
    
    return passed == total

if __name__ == "__main__":
    import sys
    
    # Проверка доступности сервера
    try:
        # Проверяем доступность через endpoint поиска (более надежно)
        response = requests.get(f"{BASE_URL}/api/chatgpt/search?city=test&service=test", timeout=5)
        print("✅ Сервер доступен")
    except requests.exceptions.ConnectionError:
        print("❌ Сервер недоступен. Убедитесь, что Flask сервер запущен на порту 8000")
        sys.exit(1)
    except Exception as e:
        # Если сервер отвечает, но endpoint возвращает ошибку - это нормально
        print("✅ Сервер доступен")
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
