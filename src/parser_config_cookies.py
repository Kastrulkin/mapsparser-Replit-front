"""
Конфигурация cookies для парсинга Яндекс.Карт
Можно переопределить через переменную окружения YANDEX_COOKIES_JSON
"""
import os
import json

# Cookies по умолчанию для парсинга Яндекс.Карт
DEFAULT_YANDEX_COOKIES = [
    {"name": "_yasc", "value": "+nRgeAgdQvcUzBXmoMj8pj3o4NAMqN+CCHHN8J9/1lgNfV+4kHD1Sh3zeyrGAQw5", "domain": ".yandex.net", "path": "/"},
    {"name": "_yasc", "value": "biwmzqpVhmFOmsUovC7mHXedgeCta8YxIE4/1irJQVFGT+VWqh2xJNmwwC1OtCIXlpDhth57aht1oLEYU3XZbIItFHp3McubCw==", "domain": ".yandex.ru", "path": "/"},
    {"name": "_ym_d", "value": "1752161744", "domain": ".yandex.ru", "path": "/"},
    {"name": "_ym_d", "value": "1742889194", "domain": ".yandex.net", "path": "/"},
    {"name": "_ym_isad", "value": "2", "domain": ".yandex.ru", "path": "/"},
    {"name": "_ym_uid", "value": "1742128615416397392", "domain": ".yandex.ru", "path": "/"},
    {"name": "_ym_uid", "value": "1742889187528829383", "domain": ".yandex.net", "path": "/"},
    {"name": "amcuid", "value": "1494970031742211656", "domain": ".yandex.ru", "path": "/"},
    {"name": "bh", "value": "ElAiQ2hyb21pdW0iO3Y9IjEzNiIsICJZYUJyb3dzZXIiO3Y9IjI1LjYiLCAiTm90LkEvQnJhbmQiO3Y9Ijk5IiwgIllvd3NlciI7dj0iMi41IhoFImFybSIiDSIyNS42LjAuMjM4MSIqAj8wMgIiIjoHIm1hY09TIkIIIjE1LjMuMSJKBCI2NCJSaSJDaHJvbWl1bSI7dj0iMTM2LjAuNzEwMy4yMzgxIiwgIllhQnJvd3NlciI7dj0iMjUuNi4wLjIzODEiLCAiTm90LkEvQnJhbmQiO3Y9Ijk5LjAuMC4wIiwgIllvd3NlciI7dj0iMi41IloCPzBgpYX+wwZqI9zK0bYBu/GfqwT61obMCNLR7esD/Lmv/wff/YeOBcKlzIcI", "domain": ".yandex.ru", "path": "/"},
    {"name": "cycada", "value": "FosWRl/CE9m7GuKD+HrY+nNWP8IsOjyDVzRQaymebfk=", "domain": ".yandex.ru", "path": "/"},
    {"name": "font_loaded", "value": "YSv1", "domain": ".yandex.ru", "path": "/"},
    {"name": "gdpr", "value": "0", "domain": ".yandex.ru", "path": "/"},
    {"name": "i", "value": "aUPEF2oX0tZg/pdYAB08PPX6cSczTEPRPXOJHjU4k0wRamyoxN7AT6XaGe6acYjbSYS8hD4v9LLj18HP0fT2ILylX28=", "domain": ".yandex.ru", "path": "/"},
    {"name": "is_gdpr", "value": "0", "domain": ".yandex.ru", "path": "/"},
    {"name": "is_gdpr", "value": "0", "domain": ".yandex.net", "path": "/"},
    {"name": "is_gdpr_b", "value": "COOeNhDMygIoAg==", "domain": ".yandex.ru", "path": "/"},
    {"name": "is_gdpr_b", "value": "CK6UEBCCwgI=", "domain": ".yandex.net", "path": "/"},
    {"name": "isa", "value": "NrR3LcEnhMF7StFQ7o6IlzJvY2zvv52CT0KeFeVcja/oWGdOEojoUfHf9w4n/H3FaU/E2EXCaHkRoLtT9Dp4XOhCQKY=", "domain": ".yandex.ru", "path": "/"},
    {"name": "k50lastvisit", "value": "db546baba3acb079f91946f80b9078ffa565e36d.204463680202e2ff8a52dd1d44716571487046c7.db546baba3acb079f91946f80b9078ffa565e36d.da39a3ee5e6b4b0d3255bfef95601890afd80709.1753094226494", "domain": ".yandex.ru", "path": "/"},
    {"name": "k50uuid", "value": "261bec41-f700-4cb3-88b8-a00ca484a1cb", "domain": ".yandex.ru", "path": "/"},
    {"name": "L", "value": "dVJ7AH1TY1JSQgt4TVhYQg1mAFxaRlNEMFMhMi5YCCEuGQ==.1752481335.16216.32052.a8e12b98e09951e444fe0b55b0f54db1", "domain": ".yandex.ru", "path": "/"},
    {"name": "maps_routes_travel_mode", "value": "pedestrian", "domain": "yandex.ru", "path": "/"},
    {"name": "maps_session_id", "value": "1753186801799142-17085193336313386887-balancer-l7leveler-kubr-yp-sas-249-BAL", "domain": ".yandex.ru", "path": "/"},
    {"name": "my", "value": "YwA=", "domain": ".yandex.ru", "path": "/"},
    {"name": "sae", "value": "0:8A53C863-815A-4C63-9430-588B5324FAAF:p:25.6.0.2381:m:d:RU:20220309", "domain": ".yandex.ru", "path": "/"},
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

