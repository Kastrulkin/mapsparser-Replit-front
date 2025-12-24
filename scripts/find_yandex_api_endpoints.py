#!/usr/bin/env python3
"""
Скрипт для поиска API endpoints Яндекс.Бизнес в HTML странице или через прямые запросы.
"""

import json
import re
import sys
import os
import requests
from typing import List, Dict, Any, Optional

# Загружаем переменные окружения из .env
try:
    from dotenv import load_dotenv
    # Загружаем .env из корня проекта
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(env_path)
    print(f"✅ Загружен .env из {env_path}")
except ImportError:
    print("⚠️ python-dotenv не установлен, переменные окружения не загружены из .env")
except Exception as e:
    print(f"⚠️ Ошибка загрузки .env: {e}")

# Добавляем src в путь для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from auth_encryption import decrypt_auth_data
from database_manager import DatabaseManager


def extract_json_from_html(html_content: str) -> List[Dict[str, Any]]:
    """
    Извлекает JSON данные из HTML (встроенные в <script> теги или window.__INITIAL_STATE__).
    """
    found_data = []
    
    # Ищем window.__INITIAL_STATE__ или подобные глобальные переменные
    patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
        r'window\.__DATA__\s*=\s*({.+?});',
        r'window\.__PRELOADED_STATE__\s*=\s*({.+?});',
        r'window\.initialData\s*=\s*({.+?});',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, html_content, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match.group(1))
                found_data.append({
                    'source': pattern,
                    'data': data
                })
            except json.JSONDecodeError:
                pass
    
    # Ищем JSON в <script> тегах
    script_pattern = r'<script[^>]*>(.*?)</script>'
    scripts = re.finditer(script_pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    for script_match in scripts:
        script_content = script_match.group(1)
        # Пропускаем минифицированный код
        if len(script_content) > 10000:
            continue
        
        # Ищем JSON объекты в скриптах
        json_patterns = [
            r'(\{[^{}]*"reviews"[^{}]*\})',
            r'(\{[^{}]*"statistics"[^{}]*\})',
            r'(\{[^{}]*"stats"[^{}]*\})',
            r'(\{[^{}]*"organization"[^{}]*\})',
        ]
        
        for json_pattern in json_patterns:
            json_matches = re.finditer(json_pattern, script_content, re.DOTALL)
            for json_match in json_matches:
                try:
                    data = json.loads(json_match.group(1))
                    found_data.append({
                        'source': 'script_tag',
                        'data': data
                    })
                except json.JSONDecodeError:
                    pass
    
    return found_data


def find_api_urls_in_html(html_content: str) -> List[str]:
    """
    Ищет URL API endpoints в HTML (в JavaScript коде).
    """
    urls = []
    
    # Паттерны для поиска API URLs
    patterns = [
        r'["\'](https?://[^"\']*api[^"\']*reviews[^"\']*)["\']',
        r'["\'](https?://[^"\']*api[^"\']*statistics?[^"\']*)["\']',
        r'["\'](https?://[^"\']*api[^"\']*stats[^"\']*)["\']',
        r'["\'](https?://[^"\']*api[^"\']*organizations[^"\']*)["\']',
        r'["\'](/api/[^"\']*reviews[^"\']*)["\']',
        r'["\'](/api/[^"\']*statistics?[^"\']*)["\']',
        r'["\'](/api/[^"\']*stats[^"\']*)["\']',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, html_content, re.IGNORECASE)
        for match in matches:
            url = match.group(1)
            if url not in urls:
                urls.append(url)
    
    return urls


def test_endpoint(url: str, cookies_dict: Dict[str, str], org_id: str, use_json_accept: bool = True) -> Optional[Dict[str, Any]]:
    """
    Тестирует endpoint с реальными cookies.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*" if use_json_accept else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": f"https://yandex.ru/sprav/{org_id}/p/edit/reviews/",
        "Origin": "https://yandex.ru",
        "X-Requested-With": "XMLHttpRequest" if use_json_accept else None,
    }
    # Убираем None значения
    headers = {k: v for k, v in headers.items() if v is not None}
    
    # Если относительный URL, делаем его абсолютным
    if url.startswith('/'):
        url = f"https://yandex.ru{url}"
    
    try:
        response = requests.get(url, cookies=cookies_dict, headers=headers, timeout=10)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            try:
                data = response.json()
                return {"json": data, "content_type": content_type}
            except json.JSONDecodeError:
                # Если не JSON, возвращаем первые 1000 символов для анализа
                text = response.text[:1000]
                return {
                    "raw_text": text,
                    "content_type": content_type,
                    "is_html": "<html" in text.lower() or "<!doctype" in text.lower(),
                    "is_json_error": text.strip().startswith("{") or text.strip().startswith("["),
                }
    except Exception as e:
        return {"error": str(e)}
    
    return None


def main():
    print("=" * 60)
    print("🔍 Поиск API endpoints Яндекс.Бизнес")
    print("=" * 60)
    
    # Ручной режим: можно указать cookies и external_id напрямую для тестирования
    # Раскомментируйте и заполните, если нужно протестировать без БД:
    # MANUAL_MODE = True
    # MANUAL_COOKIES = "yandexuid=...; Session_id=...; ..."
    # MANUAL_EXTERNAL_ID = "203293742306"
    
    MANUAL_MODE = False
    MANUAL_COOKIES = ""
    MANUAL_EXTERNAL_ID = ""
    
    if MANUAL_MODE and MANUAL_COOKIES and MANUAL_EXTERNAL_ID:
        print("\n🔧 Ручной режим: используем указанные cookies и external_id")
        external_id = MANUAL_EXTERNAL_ID
        cookies_str = MANUAL_COOKIES
        cookies_dict = {}
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies_dict[key.strip()] = value.strip()
        print(f"   External ID: {external_id}")
        print(f"   Cookies: {len(cookies_dict)}")
    else:
        # Получаем данные из БД
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Находим аккаунт "Оливер"
        cursor.execute("""
            SELECT eb.id, eb.business_id, eb.external_id, eb.auth_data_encrypted, b.name
            FROM ExternalBusinessAccounts eb
            JOIN Businesses b ON eb.business_id = b.id
            WHERE b.name LIKE '%Оливер%' OR b.name LIKE '%Oliver%'
            LIMIT 1
        """)
        
        account = cursor.fetchone()
        if not account:
            print("❌ Не найден аккаунт 'Оливер' в БД")
            print("   Убедитесь, что вы добавили external_id и cookies в админской панели")
            print("\n💡 АЛЬТЕРНАТИВА: Используйте ручной режим в скрипте")
            print("   Раскомментируйте MANUAL_MODE в начале функции main()")
            return
        
        account_id, business_id, external_id, auth_data_encrypted, business_name = account
        
        print(f"\n✅ Найден бизнес: {business_name}")
        print(f"   External ID: {external_id}")
        
        if not external_id:
            print("❌ Нет external_id (ID организации)")
            return
        
        if not auth_data_encrypted:
            print("❌ Нет auth_data (cookies)")
            return
        
        # Проверяем, загружен ли ключ
        secret_key = os.getenv("EXTERNAL_AUTH_SECRET_KEY", "").strip()
        if secret_key:
            print(f"   ✅ EXTERNAL_AUTH_SECRET_KEY загружен (длина: {len(secret_key)})")
        else:
            print(f"   ⚠️ EXTERNAL_AUTH_SECRET_KEY не найден в переменных окружения")
            print(f"      Проверьте .env файл в корне проекта")
        
        # Расшифровываем cookies
        auth_data_plain = decrypt_auth_data(auth_data_encrypted)
        if not auth_data_plain:
            print("❌ Не удалось расшифровать auth_data")
            print("\n💡 ВОЗМОЖНЫЕ РЕШЕНИЯ:")
            print("   1. Проверьте, что EXTERNAL_AUTH_SECRET_KEY установлен в .env файле")
            print("   2. Убедитесь, что ключ тот же, что использовался при шифровании")
            print("   3. Пересохраните cookies в админской панели (чтобы зашифровать с текущим ключом)")
            print("   4. Или используйте ручной режим в скрипте (раскомментируйте MANUAL_MODE)")
            return
        
        try:
            auth_data_dict = json.loads(auth_data_plain)
            cookies_str = auth_data_dict.get("cookies", auth_data_plain)
        except json.JSONDecodeError:
            cookies_str = auth_data_plain
        
        # Парсим cookies
        cookies_dict = {}
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies_dict[key.strip()] = value.strip()
        
        print(f"\n🍪 Найдено cookies: {len(cookies_dict)}")
    
    # Список возможных endpoints для тестирования
    possible_endpoints = [
        # Отзывы
        f"https://yandex.ru/sprav/api/organizations/{external_id}/reviews",
        f"https://business.yandex.ru/api/organizations/{external_id}/reviews",
        f"https://yandex.ru/sprav/{external_id}/p/edit/reviews/api",
        f"https://business.yandex.ru/api/sprav/organizations/{external_id}/reviews",
        f"https://yandex.ru/sprav/api/v1/organizations/{external_id}/reviews",
        f"https://business.yandex.ru/api/v1/organizations/{external_id}/reviews",
        # Статистика
        f"https://yandex.ru/sprav/api/organizations/{external_id}/stats",
        f"https://business.yandex.ru/api/organizations/{external_id}/stats",
        f"https://yandex.ru/sprav/{external_id}/p/edit/stats/api",
        f"https://business.yandex.ru/api/organizations/{external_id}/statistics",
        # Общая информация об организации
        f"https://yandex.ru/sprav/api/organizations/{external_id}",
        f"https://business.yandex.ru/api/organizations/{external_id}",
    ]
    
    print(f"\n🧪 Тестируем {len(possible_endpoints)} возможных endpoints...")
    print("-" * 60)
    
    working_endpoints = []
    
    for url in possible_endpoints:
        print(f"\n🔍 Тестируем: {url}")
        # Пробуем сначала с JSON Accept header
        result = test_endpoint(url, cookies_dict, external_id, use_json_accept=True)
        # Если получили HTML, пробуем без JSON Accept
        if result and result.get("is_html"):
            print(f"   ⚠️ Получен HTML, пробуем без JSON Accept header...")
            result2 = test_endpoint(url, cookies_dict, external_id, use_json_accept=False)
            if result2 and not result2.get("is_html"):
                result = result2
        
        if result:
            print(f"   ✅ Успешно! Получен ответ")
            if isinstance(result, dict):
                if "json" in result:
                    # Это JSON ответ
                    json_data = result["json"]
                    if isinstance(json_data, dict):
                        keys = list(json_data.keys())[:10]
                        print(f"   📋 Ключи в JSON: {keys}")
                        if "reviews" in json_data or "items" in json_data:
                            print(f"   🎯 Похоже на данные отзывов!")
                            if isinstance(json_data.get("reviews") or json_data.get("items"), list):
                                count = len(json_data.get("reviews") or json_data.get("items") or [])
                                print(f"   📊 Найдено отзывов: {count}")
                        if "stats" in json_data or "statistics" in json_data or "metrics" in json_data:
                            print(f"   🎯 Похоже на данные статистики!")
                    elif isinstance(json_data, list):
                        print(f"   📋 Это массив с {len(json_data)} элементами")
                        if len(json_data) > 0:
                            print(f"   📋 Первый элемент: {list(json_data[0].keys())[:5] if isinstance(json_data[0], dict) else type(json_data[0])}")
                elif "raw_text" in result:
                    # Это не JSON, показываем начало
                    raw = result["raw_text"]
                    content_type = result.get("content_type", "unknown")
                    print(f"   📄 Content-Type: {content_type}")
                    if result.get("is_html"):
                        print(f"   ⚠️ Это HTML, не JSON")
                    elif result.get("is_json_error"):
                        print(f"   ⚠️ Похоже на JSON, но ошибка парсинга")
                        print(f"   📝 Начало ответа: {raw[:200]}")
                    else:
                        print(f"   📝 Начало ответа: {raw[:300]}")
                        # Проверяем, может быть это страница с редиректом или ошибкой
                        if "redirect" in raw.lower() or "location" in raw.lower():
                            print(f"   🔄 Возможно редирект")
                        if "error" in raw.lower() or "404" in raw.lower() or "not found" in raw.lower():
                            print(f"   ❌ Возможно ошибка 404")
                        if "login" in raw.lower() or "авториз" in raw.lower():
                            print(f"   🔐 Возможно требуется авторизация")
            working_endpoints.append({
                'url': url,
                'data': result
            })
        else:
            print(f"   ❌ Не удалось получить данные")
    
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ")
    print("=" * 60)
    
    if working_endpoints:
        print(f"\n✅ Найдено рабочих endpoints: {len(working_endpoints)}")
        for ep in working_endpoints:
            print(f"\n   URL: {ep['url']}")
            if isinstance(ep['data'], dict):
                print(f"   Структура: {list(ep['data'].keys())[:10]}")
    else:
        print("\n❌ Не найдено рабочих endpoints")
        print("\n💡 РЕКОМЕНДАЦИИ:")
        print("   1. Откройте страницу отзывов в браузере:")
        print(f"      https://yandex.ru/sprav/{external_id}/p/edit/reviews/")
        print("   2. Откройте DevTools → Network tab")
        print("   3. Обновите страницу (F5)")
        print("   4. Найдите XHR/fetch запросы, которые загружают отзывы")
        print("   5. Скопируйте URL запроса и добавьте его в possible_endpoints")
        print("\n   6. Также проверьте в консоли браузера:")
        print("      console.log(window.__INITIAL_STATE__)")
        print("      console.log(window.__DATA__)")
        print("      console.log(window.initialData)")


if __name__ == "__main__":
    main()

