"""
Конфигурация парсера - выбор между старым и новым парсером
"""

import os
import inspect
from typing import Any, Callable, Dict

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
            from yandex_maps_scraper import parse_yandex_card
            return parse_yandex_card
    else:
        from yandex_maps_scraper import parse_yandex_card
        print("✅ Используется Legacy парсер (HTML парсинг)")
        return parse_yandex_card

def _supports_kwargs(fn: Callable[..., Dict[str, Any]]) -> bool:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return False
    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return False


def _allowed_kwargs(fn: Callable[..., Dict[str, Any]]) -> set[str]:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return set()
    allowed = set()
    for name, param in sig.parameters.items():
        if name == "url":
            continue
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
            allowed.add(name)
    return allowed


_PARSER_FN = get_parser()
_PARSER_SUPPORTS_VAR_KW = _supports_kwargs(_PARSER_FN)
_PARSER_ALLOWED_KW = _allowed_kwargs(_PARSER_FN)


def parse_yandex_card(url: str, **kwargs):
    """
    Единая точка вызова парсера с совместимостью по сигнатуре:
    - interception-парсер принимает расширенные kwargs;
    - legacy-парсер принимает только url.
    """
    if _PARSER_SUPPORTS_VAR_KW:
        result = _PARSER_FN(url, **kwargs)
    elif kwargs:
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in _PARSER_ALLOWED_KW}
        result = _PARSER_FN(url, **filtered_kwargs) if filtered_kwargs else _PARSER_FN(url)
    else:
        result = _PARSER_FN(url)

    if isinstance(result, dict) and result.get("error") == "captcha_detected" and not result.get("captcha_url"):
        # Legacy parser returns {"error":"captcha_detected","url":...}
        result["captcha_url"] = result.get("url") or url

    return result
