"""
Конфигурация парсера - выбор между старым и новым парсером
"""

import os

# Переменная окружения для выбора парсера
# Значения: 'interception' (новый, быстрый) или 'legacy' (старый, надежный)
PARSER_MODE = os.getenv('PARSER_MODE', 'interception').lower()

def get_parser():
    """
    Возвращает функцию парсинга в зависимости от конфигурации.
    
    Returns:
        Функция parse_yandex_card(url: str) -> dict
    """
    if PARSER_MODE == 'interception':
        try:
            from parser_interception import parse_yandex_card
            print("✅ Используется Network Interception парсер (быстрый)")
            return parse_yandex_card
        except ImportError as e:
            print(f"⚠️ Не удалось импортировать interception парсер: {e}")
            print("🔄 Переключаемся на legacy парсер...")
            from parser import parse_yandex_card
            return parse_yandex_card
    else:
        from parser import parse_yandex_card
        print("✅ Используется Legacy парсер (HTML парсинг)")
        return parse_yandex_card

# Экспортируем функцию парсинга
parse_yandex_card = get_parser()

