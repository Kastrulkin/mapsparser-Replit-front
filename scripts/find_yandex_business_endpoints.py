#!/usr/bin/env python3
"""
Скрипт для поиска правильных API endpoints Яндекс.Бизнес.

Помогает найти реальные URL для получения отзывов и статистики.
"""

import os
import sys
import json
import requests
from typing import Dict, Any, Optional

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from auth_encryption import decrypt_auth_data
from database_manager import DatabaseManager


def test_endpoint(url: str, cookies: Dict[str, str], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Тестирует один endpoint и возвращает результат."""
    try:
        response = requests.get(
            url,
            cookies=cookies,
            headers=headers,
            timeout=10,
            allow_redirects=False
        )
        content_type = response.headers.get('Content-Type', '').lower()
        print(f"  {response.status_code} {url}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"    ✅ JSON ответ получен, ключи: {list(data.keys())[:5]}")
                return data
            except:
                size = len(response.text)
                # Проверяем, является ли ответ HTML
                is_html = content_type.startswith('text/html') or response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html')
                
                if is_html:
                    print(f"    ⚠️ HTML ответ (размер: {size} байт) - вероятно страница входа/редиректа")
                    # Пробуем найти редирект в HTML
                    if 'location' in response.text.lower() or 'redirect' in response.text.lower():
                        print(f"    💡 Содержит редирект")
                else:
                    print(f"    ⚠️ Не JSON ответ (размер: {size} байт, Content-Type: {content_type})")
                    if size < 500:
                        print(f"    Текст: {response.text[:200]}")
        elif response.status_code == 401:
            print(f"    ❌ 401 Unauthorized - нужна авторизация")
        elif response.status_code == 404:
            print(f"    ❌ 404 Not Found")
        elif response.status_code == 403:
            print(f"    ❌ 403 Forbidden")
        elif response.status_code == 302:
            location = response.headers.get('Location', '')
            print(f"    ⚠️ 302 Redirect → {location[:80]}")
        else:
            print(f"    ⚠️ Статус: {response.status_code}")
    except Exception as e:
        print(f"    ❌ Ошибка: {e}")
    return None


def find_reviews_endpoints(external_id: str, cookies: Dict[str, str], headers: Dict[str, str]):
    """Пробует различные варианты endpoints для отзывов."""
    print("\n" + "="*60)
    print("🔍 Поиск endpoints для ОТЗЫВОВ")
    print("="*60)
    
    base_urls = [
        "https://business.yandex.ru",
        "https://yandex.ru",
    ]
    
    endpoint_patterns = [
        # Варианты для business.yandex.ru
        f"/api/organizations/{external_id}/reviews",
        f"/api/sprav/organizations/{external_id}/reviews",
        f"/sprav/api/organizations/{external_id}/reviews",
        f"/api/v1/organizations/{external_id}/reviews",
        f"/api/organizations/{external_id}/reviews/list",
        f"/api/reviews?organization_id={external_id}",
        
        # Варианты для yandex.ru/sprav
        f"/sprav/api/organizations/{external_id}/reviews",
        f"/sprav/api/v1/organizations/{external_id}/reviews",
        f"/sprav/organizations/{external_id}/reviews/api",
        f"/sprav/{external_id}/p/edit/reviews/api",
        f"/sprav/{external_id}/p/edit/reviews/data",
        
        # GraphQL варианты
        f"/api/graphql",
    ]
    
    working_endpoints = []
    
    for base in base_urls:
        for pattern in endpoint_patterns:
            url = base + pattern
            result = test_endpoint(url, cookies, headers)
            if result:
                working_endpoints.append((url, result))
    
    return working_endpoints


def find_stats_endpoints(external_id: str, cookies: Dict[str, str], headers: Dict[str, str]):
    """Пробует различные варианты endpoints для статистики."""
    print("\n" + "="*60)
    print("🔍 Поиск endpoints для СТАТИСТИКИ")
    print("="*60)
    
    base_urls = [
        "https://business.yandex.ru",
        "https://yandex.ru",
    ]
    
    endpoint_patterns = [
        f"/api/organizations/{external_id}/stats",
        f"/api/organizations/{external_id}/statistics",
        f"/api/sprav/organizations/{external_id}/stats",
        f"/api/sprav/organizations/{external_id}/statistics",
        f"/sprav/api/organizations/{external_id}/stats",
        f"/sprav/api/organizations/{external_id}/statistics",
        f"/api/v1/organizations/{external_id}/stats",
        f"/sprav/{external_id}/p/edit/stats/api",
        f"/sprav/{external_id}/p/edit/statistics/api",
    ]
    
    working_endpoints = []
    
    for base in base_urls:
        for pattern in endpoint_patterns:
            url = base + pattern
            result = test_endpoint(url, cookies, headers)
            if result:
                working_endpoints.append((url, result))
    
    return working_endpoints


def check_html_embedded_data(external_id: str, cookies: Dict[str, str], headers: Dict[str, str]):
    """Проверяет, есть ли данные, встроенные в HTML страницы."""
    print("\n" + "="*60)
    print("🔍 Проверка встроенных данных в HTML")
    print("="*60)
    
    pages = [
        f"https://yandex.ru/sprav/{external_id}/p/edit/reviews/",
        f"https://business.yandex.ru/organizations/{external_id}/reviews",
    ]
    
    for url in pages:
        try:
            response = requests.get(url, cookies=cookies, headers=headers, timeout=10)
            if response.status_code == 200:
                html = response.text
                # Ищем JSON данные в script тегах
                import re
                # Паттерны для поиска JSON данных
                patterns = [
                    r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                    r'window\.__DATA__\s*=\s*({.+?});',
                    r'var\s+reviews\s*=\s*(\[.+?\]);',
                    r'"reviews"\s*:\s*(\[.+?\])',
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, html, re.DOTALL)
                    if matches:
                        print(f"  ✅ Найдены данные в {url}")
                        print(f"     Паттерн: {pattern[:50]}...")
                        try:
                            data = json.loads(matches[0])
                            print(f"     Ключи: {list(data.keys())[:10]}")
                        except:
                            print(f"     Данные найдены, но не JSON")
        except Exception as e:
            print(f"  ❌ Ошибка при проверке {url}: {e}")


def main():
    """Основная функция."""
    if len(sys.argv) < 2:
        print("Использование: python find_yandex_business_endpoints.py <business_id> [--cookies COOKIES_STRING]")
        print("\nПримеры:")
        print("  python find_yandex_business_endpoints.py eae57c62-7f56-46b2-aba1-8e82b3b2dcf3")
        print("  python find_yandex_business_endpoints.py eae57c62-7f56-46b2-aba1-8e82b3b2dcf3 --cookies 'yandexuid=...; Session_id=...'")
        sys.exit(1)
    
    business_id = sys.argv[1]
    
    # Проверяем, переданы ли cookies напрямую
    cookies_override = None
    if len(sys.argv) > 2 and sys.argv[2] == "--cookies":
        if len(sys.argv) > 3:
            cookies_override = sys.argv[3]
        else:
            print("❌ Ошибка: после --cookies нужно указать строку с cookies")
            sys.exit(1)
    
    print("="*60)
    print("🔍 Поиск API endpoints Яндекс.Бизнес")
    print("="*60)
    
    # Загружаем данные из БД
    db = DatabaseManager()
    try:
        # Если cookies переданы напрямую, используем их
        if cookies_override:
            print(f"\n✅ Используются cookies, переданные напрямую")
            print(f"   Длина: {len(cookies_override)} символов")
            
            # Получаем external_id из БД
            cursor = db.conn.cursor()
            cursor.execute(
                """
                SELECT external_id
                FROM ExternalBusinessAccounts
                WHERE business_id = ? AND source = 'yandex_business'
                LIMIT 1
                """,
                (business_id,)
            )
            row = cursor.fetchone()
            if not row:
                print(f"❌ Аккаунт Яндекс.Бизнес не найден для бизнеса {business_id}")
                print(f"   Нужен external_id для формирования URL")
                sys.exit(1)
            external_id = row[0]
            
            # Используем переданные cookies
            auth_data_dict = {"cookies": cookies_override}
        else:
            # Загружаем данные из БД
            cursor = db.conn.cursor()
            cursor.execute(
                """
                SELECT id, external_id, auth_data_encrypted
                FROM ExternalBusinessAccounts
                WHERE business_id = ? AND source = 'yandex_business'
                LIMIT 1
                """,
                (business_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                print(f"❌ Аккаунт Яндекс.Бизнес не найден для бизнеса {business_id}")
                sys.exit(1)
            
            account_id, external_id, auth_data_encrypted = row
            
            if not auth_data_encrypted:
                print(f"❌ Нет auth_data для аккаунта {account_id}")
                sys.exit(1)
        
            # Расшифровываем auth_data
            print(f"\n🔐 Расшифровка auth_data...")
            print(f"   Длина зашифрованных данных: {len(auth_data_encrypted)} символов")
            print(f"   Первые 50 символов: {auth_data_encrypted[:50]}...")
            
            auth_data_plain = decrypt_auth_data(auth_data_encrypted)
            
            # Если расшифровка не удалась, пробуем использовать данные как есть (может быть plain text)
            if not auth_data_plain:
                print(f"⚠️ Расшифровка не удалась. Пробуем использовать данные как есть (plain text)...")
                # Пробуем использовать как plain text
                try:
                    # Может быть это уже JSON?
                    auth_data_dict = json.loads(auth_data_encrypted)
                    auth_data_plain = auth_data_encrypted
                    print(f"✅ Данные уже в формате JSON")
                except json.JSONDecodeError:
                    # Может быть это просто строка с cookies?
                    auth_data_plain = auth_data_encrypted
                    print(f"✅ Используем данные как plain text (строка с cookies)")
            
            if not auth_data_plain:
                print(f"❌ Не удалось получить auth_data")
                print(f"\n💡 Решения:")
                print(f"   1. Пересохраните cookies через админ-панель (рекомендуется)")
                print(f"   2. Или используйте --cookies для передачи cookies напрямую:")
                print(f"      python {sys.argv[0]} {business_id} --cookies 'ваши_cookies'")
                sys.exit(1)
            
            # Парсим auth_data
            print(f"   Длина расшифрованных данных: {len(auth_data_plain)} символов")
            try:
                auth_data_dict = json.loads(auth_data_plain)
                print(f"✅ Данные успешно распарсены как JSON")
            except json.JSONDecodeError:
                # Если не JSON, предполагаем что это просто cookies строка
                auth_data_dict = {"cookies": auth_data_plain}
                print(f"✅ Данные интерпретированы как строка cookies")
        
        # Парсим cookies
        cookies_str = auth_data_dict.get("cookies", "")
        if not cookies_str:
            print(f"⚠️ В auth_data нет поля 'cookies'")
            print(f"   Доступные ключи: {list(auth_data_dict.keys())}")
            # Может быть данные сохранены в другом формате?
            if isinstance(auth_data_dict, str):
                cookies_str = auth_data_dict
            else:
                print(f"❌ Не удалось найти cookies в auth_data")
                sys.exit(1)
        
        cookies = {}
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key.strip()] = value.strip()
        
        if not cookies:
            print(f"⚠️ Не удалось распарсить cookies из строки")
            print(f"   Строка cookies: {cookies_str[:100]}...")
            print(f"\n💡 ВАЖНО: Без правильных cookies сервер будет возвращать HTML страницы вместо JSON API")
            print(f"   Для получения реальных cookies:")
            print(f"   1. Откройте https://yandex.ru/sprav/{external_id}/p/edit/reviews/ в браузере")
            print(f"   2. Убедитесь, что вы авторизованы")
            print(f"   3. Откройте DevTools (F12) → Application → Cookies → https://yandex.ru")
            print(f"   4. Скопируйте все cookies в формате: ключ1=значение1; ключ2=значение2; ...")
            print(f"   5. Запустите скрипт снова с --cookies 'ваши_реальные_cookies'")
        
        # Headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": "https://business.yandex.ru/",
            **auth_data_dict.get("headers", {}),
        }
        
        print(f"\n✅ Загружены данные для организации: {external_id}")
        print(f"   Cookies: {len(cookies)} штук")
        if cookies:
            print(f"   Примеры cookie ключей: {list(cookies.keys())[:5]}")
        
        # Ищем endpoints
        reviews_endpoints = find_reviews_endpoints(external_id, cookies, headers)
        stats_endpoints = find_stats_endpoints(external_id, cookies, headers)
        check_html_embedded_data(external_id, cookies, headers)
        
        # Выводим результаты
        print("\n" + "="*60)
        print("📊 РЕЗУЛЬТАТЫ")
        print("="*60)
        
        if reviews_endpoints:
            print(f"\n✅ Найдено {len(reviews_endpoints)} рабочих endpoints для отзывов:")
            for url, data in reviews_endpoints:
                print(f"   {url}")
                print(f"      Структура: {list(data.keys())[:5]}")
        else:
            print("\n❌ Рабочие endpoints для отзывов не найдены")
            print("   💡 Попробуйте:")
            print("      1. Открыть DevTools → Network tab")
            print("      2. Перейти на страницу отзывов")
            print("      3. Найти XHR/fetch запросы, которые загружают отзывы")
            print("      4. Скопировать URL из запроса")
        
        if stats_endpoints:
            print(f"\n✅ Найдено {len(stats_endpoints)} рабочих endpoints для статистики:")
            for url, data in stats_endpoints:
                print(f"   {url}")
                print(f"      Структура: {list(data.keys())[:5]}")
        else:
            print("\n❌ Рабочие endpoints для статистики не найдены")
    
    finally:
        db.close()


if __name__ == "__main__":
    main()

