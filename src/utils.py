"""
utils.py — Вспомогательные функции для антибана (User-Agent, прокси)
"""
from fake_useragent import UserAgent
import os

def get_random_user_agent() -> str:
    return UserAgent().random

# Пример функции для получения прокси из переменных окружения

def get_proxy() -> str | None:
    return os.getenv('PROXY')  # пример: http://user:pass@host:port 