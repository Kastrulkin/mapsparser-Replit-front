"""
parser.py — Модуль для парсинга публичной страницы Яндекс.Карт с помощью requests и BeautifulSoup
"""
import time
import re
import random
import requests
from bs4 import BeautifulSoup

def parse_yandex_card_fallback(url: str) -> dict:
    """
    Упрощенный парсинг через requests + BeautifulSoup (fallback)
    """
    print("Используем fallback-метод через requests...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    data = {}
    data['url'] = url
    
    # Базовая информация
    title_el = soup.find('h1')
    data['title'] = title_el.get_text().strip() if title_el else ''
    
    # Адрес (упрощенно)
    addr_el = soup.find('a', {'class': lambda x: x and 'address' in x})
    data['address'] = addr_el.get_text().strip() if addr_el else ''
    
    # Телефон (упрощенно)
    phone_el = soup.find('a', href=lambda x: x and x.startswith('tel:'))
    data['phone'] = phone_el.get_text().strip() if phone_el else ''
    
    # Заполняем пустые поля
    data.update({
        'site': '',
        'hours': '',
        'hours_full': [],
        'categories': [],
        'rating': '',
        'ratings_count': '',
        'reviews_count': '',
        'description': '',
        'photos_count': 0,
        'social_links': [],
        'nearest_metro': {'name': '', 'distance': ''},
        'nearest_stop': {'name': '', 'distance': ''},
        'products': [],
        'product_categories': [],
        'news': [],
        'photos': [],
        'reviews': {'items': [], 'rating': '', 'reviews_count': ''},
        'features': [],
        'features_full': {"bool": [], "valued": [], "prices": [], "categories": []},
        'competitors': []
    })
    
    # Формируем overview для отчёта
    data['overview'] = {
        'title': data.get('title', ''),
        'address': data.get('address', ''),
        'phone': data.get('phone', ''),
        'site': data.get('site', ''),
        'description': data.get('description', ''),
        'categories': data.get('categories', []),
        'hours': data.get('hours', ''),
        'hours_full': data.get('hours_full', []),
        'rating': data.get('rating', ''),
        'ratings_count': data.get('ratings_count', ''),
        'reviews_count': data.get('reviews_count', ''),
        'social_links': data.get('social_links', [])
    }
    
    return data

def parse_yandex_card(url: str) -> dict:
    """
    Парсит публичную страницу Яндекс.Карт и возвращает данные в виде словаря.
    """
    print(f"Начинаем парсинг: {url}")
    
    if not url or not url.startswith(('http://', 'https://')):
        raise ValueError(f"Некорректная ссылка: {url}")
    
    # Используем requests как основной метод парсинга
    return parse_yandex_card_fallback(url)
             