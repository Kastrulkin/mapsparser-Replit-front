"""
Конфигурация cookies для парсинга Яндекс.Карт
Можно переопределить через переменную окружения YANDEX_COOKIES_JSON
"""
import os
import json

# Cookies по умолчанию для парсинга Яндекс.Карт
DEFAULT_YANDEX_COOKIES = [
    {"domain": ".yandex.ru", "name": "yandexuid", "path": "/", "value": "3206183751768392749"},
    {"domain": ".yandex.ru", "name": "yuidss", "path": "/", "value": "3206183751768392749"},
    {"domain": ".yandex.ru", "name": "ymex", "path": "/", "value": "2083752749.yrts.1768392749#2083752749.yrtsi.1768392749"},
    {"domain": ".yandex.ru", "name": "is_gdpr", "path": "/", "value": "0"},
    {"domain": ".yandex.ru", "name": "is_gdpr_b", "path": "/", "value": "CIOlWBCE7wI="},
    {"domain": ".yandex.ru", "name": "yandex_expboxes", "path": "/", "value": "745328%2C0%2C55%3B1396453%2C0%2C97%3B46451%2C0%2C27%3B1467535%2C0%2C57%3B1435769%2C0%2C82%3B663874%2C0%2C34%3B663860%2C0%2C58%3B1257223%2C0%2C37"},
    {"domain": ".yandex.ru", "name": "gdpr", "path": "/", "value": "0"},
    {"domain": ".yandex.ru", "name": "_ym_uid", "path": "/", "value": "1768729637782861934"},
    {"domain": ".yandex.ru", "name": "_ym_d", "path": "/", "value": "1768729638"},
    {"domain": ".yandex.ru", "name": "_ym_isad", "path": "/", "value": "2"},
    {"domain": ".yandex.ru", "name": "_ym_visorc", "path": "/", "value": "b"},
    {"domain": ".yandex.ru", "name": "spravka", "path": "/", "value": "dD0xNzY4NzI5NzE3O2k9MTg4LjE4Ny4xNi4yMjY7RD1ENTMxODY0NTk4MTk2NDYzMEQ5MTIzNzRCNzc3MkE4NDM1RUY0QjQ4NkIzRkVDOTEwNUIyN0UzQjIxMTY4ODcxMzVCMDYyOUFBQUM3NEVFRjM1NkIzQjJERTQxOTFENTA2REU4REQxQjc2MjQyMDA1RkNDRjgxMzkzNjVBNDU4RDUyM0NDRjNEN0Y7dT0xNzY4NzI5NzE3NTYwMTg1NzYzO2g9ZjNkOTQwYzM4MjViMWFjMzgxYmMzNDUyZjYwZWQ1OTQ="},
    {"domain": ".yandex.ru", "name": "_yasc", "path": "/", "value": "Ei228gMfabyEhWb0KTSTPt0pLGRp2bKglWOL3P7qppGqBHvbo2tLuNUqRsEXXJ9kZDcPdZgD50u0w9mG"},
    {"domain": ".yandex.ru", "name": "maps_session_id", "path": "/", "value": "1768730514756704-11686061647231100943-balancer-l7leveler-kubr-yp-vla-23-BAL"},
    {"domain": ".yandex.ru", "name": "bh", "path": "/", "value": "EkEiR29vZ2xlIENocm9tZSI7dj0iMTQzIiwgIkNocm9taXVtIjt2PSIxNDMiLCAiTm90IEEoQnJhbmQiO3Y9IjI0IhoFImFybSIiECIxNDMuMC43NDk5LjE5MyIqAj8wMgIiIjoHIm1hY09TIkIIIjE1LjMuMSJKBCI2NCJSXSJHb29nbGUgQ2hyb21lIjt2PSIxNDMuMC43NDk5LjE5MyIsICJDaHJvbWl1bSI7dj0iMTQzLjAuNzQ5OS4xOTMiLCAiTm90IEEoQnJhbmQiO3Y9IjI0LjAuMC4wIloCPzBgld+yywZqIdzK0bYBu/GfqwT61obMCNLR7esD/Lmv/wff/e+zBvOBAg=="}
]

def get_yandex_cookies():
    """
    Получить cookies для парсинга Яндекс.Карт
    
    Приоритет:
    1. Переменная окружения YANDEX_COOKIES_JSON (JSON строка)
    2. Файл yandex_cookies.json в корне проекта
    3. DEFAULT_YANDEX_COOKIES
    """
    # Проверяем переменную окружения
    cookies_json = os.getenv('YANDEX_COOKIES_JSON')
    if cookies_json:
        try:
            return json.loads(cookies_json)
        except json.JSONDecodeError:
            print("⚠️ Не удалось распарсить YANDEX_COOKIES_JSON, используем значения по умолчанию")
    
    # Проверяем файл
    cookies_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'yandex_cookies.json')
    if os.path.exists(cookies_file):
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Не удалось загрузить cookies из файла: {e}, используем значения по умолчанию")
    
    return DEFAULT_YANDEX_COOKIES

