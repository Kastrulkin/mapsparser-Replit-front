"""
parser_interception.py — Парсер Яндекс.Карт через Network Interception

Перехватывает API запросы во время загрузки страницы и извлекает данные из JSON ответов.
Это в 10x быстрее, чем парсинг HTML через Playwright.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import json
import re
import time
import random
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, parse_qs


class YandexMapsInterceptionParser:
    """Парсер Яндекс.Карт через перехват сетевых запросов"""
    
    def __init__(self):
        self.api_responses = {}
        self.org_id = None
        
    def extract_org_id(self, url: str) -> Optional[str]:
        """Извлечь org_id из URL Яндекс.Карт
        
        Поддерживает форматы:
        - /org/123456/ (старый формат)
        - /org/slug/123456/ (новый формат с slug)
        """
        # Сначала пробуем новый формат: /org/slug/123456/
        match = re.search(r'/org/[^/]+/(\d+)', url)
        if match:
            return match.group(1)
        
        # Fallback на старый формат: /org/123456/
        match = re.search(r'/org/(\d+)', url)
        return match.group(1) if match else None
    
    def parse_yandex_card(self, url: str) -> Dict[str, Any]:
        """
        Парсит публичную страницу Яндекс.Карт через Network Interception.
        
        Args:
            url: URL карточки бизнеса (например, https://yandex.ru/maps/org/123456/)
            
        Returns:
            Словарь с данными в том же формате, что и parser.py
        """
        print(f"🔍 Начинаем парсинг через Network Interception: {url}")
        
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError(f"Некорректная ссылка: {url}")
        
        self.org_id = self.extract_org_id(url)
        if not self.org_id:
            raise ValueError(f"Не удалось извлечь org_id из URL: {url}")
        
        print(f"📋 Извлечен org_id: {self.org_id}")
        
        # Cookies для имитации браузера (те же что в оригинальном parser.py)
        cookies = [
            {"name": "_yasc", "value": "+nRgeAgdQvcUzBXmoMj8pj3o4NAMqN+CCHHN8J9/1lgNfV+4kHD1Sh3zeyrGAQw5", "domain": ".yandex.net", "path": "/"},
            {"name": "_yasc", "value": "biwmzqpVhmFOmsUovC7mHXedgeCta8YxIE4/1irJQVFGT+VWqh2xJNmwwC1OtCIXlpDhth57aht1oLEYU3XZbIItFHp3McubCw==", "domain": ".yandex.ru", "path": "/"},
            {"name": "_ym_d", "value": "1752161744", "domain": ".yandex.ru", "path": "/"},
            {"name": "_ym_d", "value": "1742889194", "domain": ".yandex.net", "path": "/"},
            {"name": "_ym_isad", "value": "2", "domain": ".yandex.ru", "path": "/"},
            {"name": "_ym_uid", "value": "1742128615416397392", "domain": ".yandex.ru", "path": "/"},
            {"name": "_ym_uid", "value": "1742889187528829383", "domain": ".yandex.net", "path": "/"},
            {"name": "amcuid", "value": "1494970031742211656", "domain": ".yandex.ru", "path": "/"},
        ]
        
        browser = None
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-images',  # Не загружаем картинки для скорости
                    ]
                )
                
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                )
                
                context.add_cookies(cookies)
                
                # Скрываем webdriver
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    delete navigator.__proto__.webdriver;
                """)
                
                page = context.new_page()
                
                # Очищаем предыдущие ответы
                self.api_responses = {}
                
                # Перехватываем все ответы
                def handle_response(response):
                    """Обработчик для перехвата сетевых запросов"""
                    try:
                        url = response.url
                        
                        # Ищем API запросы Яндекс.Карт
                        if 'yandex.ru' in url or 'yandex.net' in url:
                            # Проверяем, это JSON ответ?
                            content_type = response.headers.get('content-type', '')
                            if 'application/json' in content_type or 'json' in url.lower() or 'ajax=1' in url:
                                try:
                                    # Пытаемся получить JSON
                                    json_data = response.json()
                                    if json_data:
                                        # Сохраняем ответ
                                        self.api_responses[url] = {
                                            'data': json_data,
                                            'status': response.status,
                                            'headers': dict(response.headers)
                                        }
                                        # Показываем только важные запросы
                                        if any(keyword in url for keyword in ['org', 'organization', 'business', 'company', 'reviews', 'feedback', 'location-info']):
                                            print(f"✅ Перехвачен важный API запрос: {url[:120]}...")
                                except:
                                    # Не JSON, пропускаем
                                    pass
                    except Exception as e:
                        print(f"⚠️ Ошибка при перехвате ответа: {e}")
                
                page.on("response", handle_response)
                
                # Загружаем страницу
                print("🌐 Загружаем страницу и перехватываем API запросы...")
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    
                    # Проверяем на капчу
                    page.wait_for_timeout(2000)
                    page_content = page.content()
                    if "captcha" in page_content.lower() or "робот" in page_content.lower() or "Подтвердите" in page_content:
                        print("⚠️ Обнаружена капча! Fallback на HTML парсинг может не сработать.")
                        # Продолжаем, но данные могут быть неполными
                except:
                    # Если не удалось загрузить, продолжаем с тем что есть
                    print("⚠️ Страница не загрузилась полностью, но продолжаем...")
                
                # Ждем, чтобы все запросы успели выполниться
                print("⏳ Ожидаем выполнения API запросов...")
                time.sleep(5)
                
                # Скроллим для подгрузки дополнительного контента (отзывы, фото)
                try:
                    page.mouse.wheel(0, 1000)
                    time.sleep(2)
                    page.mouse.wheel(0, 1000)
                    time.sleep(2)
                except:
                    pass
                
                print(f"📦 Перехвачено {len(self.api_responses)} API запросов")
                
                # Извлекаем данные из перехваченных ответов
                data = self._extract_data_from_responses()
                
                # Если не удалось извлечь данные через API, fallback на HTML парсинг
                if not data.get('title') and not data.get('overview', {}).get('title'):
                    print("⚠️ Не удалось извлечь данные через API, используем HTML парсинг как fallback")
                    data = self._fallback_html_parsing(page, url)
                
                browser.close()
                
                print(f"✅ Парсинг завершен. Найдено: название='{data.get('title', '')}', адрес='{data.get('address', '')}'")
                return data
                
            except PlaywrightTimeoutError as e:
                browser.close()
                raise Exception(f"Тайм-аут при загрузке страницы: {e}")
            except Exception as e:
                browser.close()
                raise Exception(f"Ошибка при парсинге: {e}")
    
    def _extract_data_from_responses(self) -> Dict[str, Any]:
        """Извлекает данные из перехваченных API ответов"""
        data = {
            'url': '',
            'title': '',
            'address': '',
            'phone': '',
            'site': '',
            'description': '',
            'rating': '',
            'ratings_count': 0,
            'reviews_count': 0,
            'reviews': [],
            'news': [],
            'photos': [],
            'photos_count': 0,
            'rubric': '',
            'categories': [],
            'hours': '',
            'hours_full': '',
            'social_links': [],
            'features_full': {},
            'competitors': [],
            'overview': {}
        }
        
        # Ищем данные в перехваченных ответах
        for url, response_info in self.api_responses.items():
            json_data = response_info['data']
            
            # Специальная обработка для fetchReviews API
            if 'fetchReviews' in url or 'reviews' in url.lower():
                reviews = self._extract_reviews_from_api(json_data, url)
                if reviews:
                    print(f"✅ Извлечено {len(reviews)} отзывов из API запроса")
                    data['reviews'] = reviews
                    data['reviews_count'] = len(reviews)
            
            # Специальная обработка для location-info API
            elif 'location-info' in url:
                org_data = self._extract_location_info(json_data)
                if org_data:
                    print(f"✅ Извлечены данные организации из location-info API")
                    data.update(org_data)
            
            # Пытаемся найти данные организации
            elif self._is_organization_data(json_data):
                org_data = self._extract_organization_data(json_data)
                if org_data:
                    data.update(org_data)
            
            # Пытаемся найти отзывы (общий поиск)
            elif self._is_reviews_data(json_data):
                reviews = self._extract_reviews(json_data)
                if reviews:
                    data['reviews'] = reviews
                    data['reviews_count'] = len(reviews)
            
            # Пытаемся найти новости/посты
            elif self._is_posts_data(json_data):
                posts = self._extract_posts(json_data)
                if posts:
                    data['news'] = posts
        
        # Создаем overview
        overview_keys = [
            'title', 'address', 'phone', 'site', 'description',
            'rubric', 'categories', 'hours', 'hours_full', 'rating', 
            'ratings_count', 'reviews_count', 'social_links'
        ]
        data['overview'] = {k: data.get(k, '') for k in overview_keys}
        data['overview']['reviews_count'] = data.get('reviews_count', 0)
        
        return data
    
    def _is_organization_data(self, json_data: Any) -> bool:
        """Проверяет, содержит ли JSON данные об организации"""
        if not isinstance(json_data, dict):
            return False
        
        # Ищем ключевые поля организации
        org_fields = ['name', 'title', 'address', 'rating', 'orgId', 'organizationId', 'company']
        return any(field in json_data for field in org_fields) or \
               any(isinstance(v, dict) and any(f in v for f in org_fields) for v in json_data.values() if isinstance(v, dict))
    
    def _extract_search_api_data(self, json_data: Any) -> Dict[str, Any]:
        """Извлекает данные организации из search API"""
        result = {}
        
        def extract_nested(data):
            if isinstance(data, dict):
                # Ищем данные организации в разных структурах
                if 'data' in data and isinstance(data['data'], dict):
                    data = data['data']
                
                if 'result' in data and isinstance(data['result'], dict):
                    data = data['result']
                
                # Ищем название
                if 'name' in data:
                    result['title'] = data['name']
                elif 'title' in data:
                    result['title'] = data['title']
                
                # Ищем адрес
                if 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        result['address'] = addr.get('formatted', '') or addr.get('full', '') or addr.get('text', '') or str(addr)
                    else:
                        result['address'] = str(addr)
                
                # Ищем рейтинг
                if 'rating' in data:
                    rating = data['rating']
                    if isinstance(rating, (int, float)):
                        result['rating'] = str(rating)
                    elif isinstance(rating, dict):
                        result['rating'] = str(rating.get('value', ''))
                
                # Ищем количество отзывов
                if 'reviewsCount' in data:
                    result['reviews_count'] = int(data['reviewsCount'])
                elif 'reviews_count' in data:
                    result['reviews_count'] = int(data['reviews_count'])
                
                # Рекурсивно обходим вложенные объекты
                for value in data.values():
                    if isinstance(value, (dict, list)):
                        extract_nested(value)
        
        extract_nested(json_data)
        return result
    
    def _extract_location_info(self, json_data: Any) -> Dict[str, Any]:
        """Извлекает данные организации из location-info API"""
        result = {}
        
        def extract_nested(data):
            if isinstance(data, dict):
                # Ищем название
                if 'name' in data:
                    result['title'] = data['name']
                elif 'title' in data:
                    result['title'] = data['title']
                
                # Ищем адрес
                if 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        result['address'] = addr.get('formatted', '') or addr.get('full', '') or addr.get('text', '') or str(addr)
                    else:
                        result['address'] = str(addr)
                
                # Ищем рейтинг
                if 'rating' in data:
                    rating = data['rating']
                    if isinstance(rating, (int, float)):
                        result['rating'] = str(rating)
                    elif isinstance(rating, dict):
                        result['rating'] = str(rating.get('value', ''))
                
                # Ищем количество отзывов
                if 'reviewsCount' in data:
                    result['reviews_count'] = int(data['reviewsCount'])
                elif 'reviews_count' in data:
                    result['reviews_count'] = int(data['reviews_count'])
                
                # Ищем телефон
                if 'phones' in data:
                    phones = data['phones']
                    if isinstance(phones, list) and phones:
                        phone_obj = phones[0]
                        if isinstance(phone_obj, dict):
                            result['phone'] = phone_obj.get('formatted', '') or phone_obj.get('number', '')
                        else:
                            result['phone'] = str(phone_obj)
                    elif isinstance(phones, dict):
                        result['phone'] = phones.get('formatted', '') or phones.get('number', '')
                
                # Рекурсивно обходим вложенные объекты
                for value in data.values():
                    extract_nested(value)
        
        extract_nested(json_data)
        return result
    
    def _extract_organization_data(self, json_data: Any) -> Dict[str, Any]:
        """Извлекает данные организации из JSON"""
        result = {}
        
        def extract_nested(data, path=''):
            """Рекурсивно извлекает данные"""
            if isinstance(data, dict):
                # Прямые поля
                if 'name' in data or 'title' in data:
                    result['title'] = data.get('name') or data.get('title', '')
                
                if 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        result['address'] = addr.get('formatted', '') or addr.get('full', '') or str(addr)
                    else:
                        result['address'] = str(addr)
                
                if 'rating' in data:
                    rating = data['rating']
                    if isinstance(rating, (int, float)):
                        result['rating'] = str(rating)
                    elif isinstance(rating, dict):
                        result['rating'] = str(rating.get('value', ''))
                
                if 'reviewsCount' in data or 'reviews_count' in data:
                    result['reviews_count'] = int(data.get('reviewsCount') or data.get('reviews_count', 0))
                
                if 'phones' in data:
                    phones = data['phones']
                    if isinstance(phones, list) and phones:
                        result['phone'] = phones[0].get('formatted', '') or phones[0].get('number', '')
                    elif isinstance(phones, dict):
                        result['phone'] = phones.get('formatted', '') or phones.get('number', '')
                
                if 'site' in data or 'website' in data:
                    result['site'] = data.get('site') or data.get('website', '')
                
                if 'description' in data or 'about' in data:
                    result['description'] = data.get('description') or data.get('about', '')
                
                # Рекурсивно обходим вложенные объекты
                for key, value in data.items():
                    extract_nested(value, f"{path}.{key}")
            
            elif isinstance(data, list):
                for item in data:
                    extract_nested(item, path)
        
        extract_nested(json_data)
        return result
    
    def _is_reviews_data(self, json_data: Any) -> bool:
        """Проверяет, содержит ли JSON данные об отзывах"""
        if not isinstance(json_data, dict):
            return False
        
        review_fields = ['reviews', 'items', 'feedback', 'comments']
        return any(field in json_data for field in review_fields) or \
               (isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], dict) and 
                any(k in json_data[0] for k in ['text', 'comment', 'rating', 'author']))
    
    def _extract_reviews_from_api(self, json_data: Any, url: str) -> List[Dict[str, Any]]:
        """Извлекает отзывы из API запроса fetchReviews (специфичная структура Яндекс.Карт)"""
        reviews = []
        
        def extract_review_item(item: dict) -> Optional[Dict[str, Any]]:
            """Извлекает один отзыв из структуры API"""
            if not isinstance(item, dict):
                return None
            
            # Извлекаем автора
            author_name = ''
            if 'author' in item:
                author = item['author']
                if isinstance(author, dict):
                    author_name = author.get('name') or author.get('displayName') or author.get('username', '')
                else:
                    author_name = str(author)
            else:
                author_name = item.get('authorName', item.get('author_name', ''))
            
            # Извлекаем рейтинг (может быть числом или строкой)
            rating = item.get('rating') or item.get('score') or item.get('grade') or item.get('stars')
            if rating:
                # Если это число, преобразуем в строку
                if isinstance(rating, (int, float)):
                    rating = str(rating)
                else:
                    rating = str(rating)
            else:
                rating = ''
            
            # Извлекаем текст
            text = item.get('text') or item.get('comment') or item.get('message') or item.get('content', '')
            
            # Извлекаем дату
            date = item.get('date') or item.get('publishedAt') or item.get('published_at') or item.get('createdAt', '')
            
            # Извлекаем ответ организации (проверяем все возможные варианты)
            response_text = None
            response_date = None
            owner_comment = (
                item.get('ownerComment') or 
                item.get('owner_comment') or 
                item.get('response') or 
                item.get('reply') or
                item.get('organizationResponse') or
                item.get('organization_response') or
                item.get('companyResponse') or
                item.get('company_response') or
                item.get('ownerResponse') or
                item.get('owner_response') or
                item.get('answer') or
                item.get('answers')  # Может быть массив
            )
            
            if owner_comment:
                if isinstance(owner_comment, list) and len(owner_comment) > 0:
                    # Если это массив, берем первый элемент
                    owner_comment = owner_comment[0]
                
                if isinstance(owner_comment, dict):
                    response_text = (
                        owner_comment.get('text') or 
                        owner_comment.get('comment') or 
                        owner_comment.get('message') or
                        owner_comment.get('content') or
                        str(owner_comment)
                    )
                    response_date = (
                        owner_comment.get('date') or 
                        owner_comment.get('createdAt') or
                        owner_comment.get('created_at') or
                        owner_comment.get('publishedAt') or
                        owner_comment.get('published_at')
                    )
                else:
                    response_text = str(owner_comment)
            
            if text:
                return {
                    'author': author_name or 'Анонимный пользователь',
                    'rating': rating,
                    'text': text,
                    'date': date,
                    'response_text': response_text,
                    'response_date': response_date,
                    'has_response': bool(response_text)
                }
            return None
        
        # Пытаемся найти массив отзывов в разных структурах
        if isinstance(json_data, dict):
            # Вариант 1: прямой массив в ключе reviews
            if 'reviews' in json_data and isinstance(json_data['reviews'], list):
                for item in json_data['reviews']:
                    review = extract_review_item(item)
                    if review:
                        reviews.append(review)
            
            # Вариант 2: в data.reviews
            elif 'data' in json_data and isinstance(json_data['data'], dict):
                if 'reviews' in json_data['data'] and isinstance(json_data['data']['reviews'], list):
                    for item in json_data['data']['reviews']:
                        review = extract_review_item(item)
                        if review:
                            reviews.append(review)
            
            # Вариант 3: в result.reviews
            elif 'result' in json_data and isinstance(json_data['result'], dict):
                if 'reviews' in json_data['result'] and isinstance(json_data['result']['reviews'], list):
                    for item in json_data['result']['reviews']:
                        review = extract_review_item(item)
                        if review:
                            reviews.append(review)
            
            # Вариант 4: в items
            elif 'items' in json_data and isinstance(json_data['items'], list):
                for item in json_data['items']:
                    review = extract_review_item(item)
                    if review:
                        reviews.append(review)
            
            # Вариант 5: рекурсивный поиск
            else:
                for key, value in json_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict) and any(k in value[0] for k in ['text', 'comment', 'rating', 'author']):
                            for item in value:
                                review = extract_review_item(item)
                                if review:
                                    reviews.append(review)
        
        elif isinstance(json_data, list):
            # Если сам JSON - это массив отзывов
            for item in json_data:
                review = extract_review_item(item)
                if review:
                    reviews.append(review)
        
        return reviews
    
    def _extract_reviews(self, json_data: Any) -> List[Dict[str, Any]]:
        """Извлекает отзывы из JSON (общий метод)"""
        reviews = []
        
        def find_reviews(data):
            if isinstance(data, dict):
                # Ищем массив отзывов
                for key in ['reviews', 'items', 'feedback', 'comments']:
                    if key in data and isinstance(data[key], list):
                        for item in data[key]:
                            if isinstance(item, dict):
                                review = {
                                    'author': item.get('author', {}).get('name', '') if isinstance(item.get('author'), dict) else item.get('author', ''),
                                    'rating': str(item.get('rating', item.get('score', ''))),
                                    'text': item.get('text', item.get('comment', item.get('message', ''))),
                                    'date': item.get('date', item.get('createdAt', ''))
                                }
                                if review['text']:
                                    reviews.append(review)
                
                # Рекурсивно ищем вложенные объекты
                for value in data.values():
                    find_reviews(value)
            
            elif isinstance(data, list):
                for item in data:
                    find_reviews(item)
        
        find_reviews(json_data)
        return reviews
    
    def _is_posts_data(self, json_data: Any) -> bool:
        """Проверяет, содержит ли JSON данные о постах/новостях"""
        if not isinstance(json_data, dict):
            return False
        
        post_fields = ['posts', 'publications', 'news', 'items']
        return any(field in json_data for field in post_fields)
    
    def _extract_posts(self, json_data: Any) -> List[Dict[str, Any]]:
        """Извлекает посты/новости из JSON"""
        posts = []
        
        def find_posts(data):
            if isinstance(data, dict):
                for key in ['posts', 'publications', 'news', 'items']:
                    if key in data and isinstance(data[key], list):
                        for item in data[key]:
                            if isinstance(item, dict):
                                post = {
                                    'title': item.get('title', ''),
                                    'text': item.get('text', item.get('content', item.get('message', ''))),
                                    'date': item.get('date', item.get('publishedAt', item.get('createdAt', ''))),
                                    'url': item.get('url', '')
                                }
                                if post['text'] or post['title']:
                                    posts.append(post)
                
                for value in data.values():
                    find_posts(value)
            
            elif isinstance(data, list):
                for item in data:
                    find_posts(item)
        
        find_posts(json_data)
        return posts
    
    def _fallback_html_parsing(self, page, url: str) -> Dict[str, Any]:
        """Fallback на HTML парсинг, если API не сработал"""
        print("🔄 Используем fallback HTML парсинг...")
        
        # Импортируем функции из оригинального парсера
        try:
            from parser import parse_overview_data, parse_reviews, parse_news, parse_photos, get_photos_count, parse_features, parse_competitors
            
            data = parse_overview_data(page)
            data['url'] = url
            
            reviews_data = parse_reviews(page)
            data['reviews'] = reviews_data.get('items', [])
            data['news'] = parse_news(page)
            data['photos_count'] = get_photos_count(page)
            data['photos'] = parse_photos(page)
            data['features_full'] = parse_features(page)
            data['competitors'] = parse_competitors(page)
            
            overview_keys = [
                'title', 'address', 'phone', 'site', 'description',
                'rubric', 'categories', 'hours', 'hours_full', 'rating', 
                'ratings_count', 'reviews_count', 'social_links'
            ]
            data['overview'] = {k: data.get(k, '') for k in overview_keys}
            data['overview']['reviews_count'] = data.get('reviews_count', '')
            
            return data
        except Exception as e:
            print(f"❌ Ошибка при fallback парсинге: {e}")
            return {'error': str(e), 'url': url}


def parse_yandex_card(url: str) -> Dict[str, Any]:
    """
    Главная функция для парсинга Яндекс.Карт через Network Interception.
    
    Использование:
        from parser_interception import parse_yandex_card
        data = parse_yandex_card("https://yandex.ru/maps/org/123456/")
    """
    parser = YandexMapsInterceptionParser()
    return parser.parse_yandex_card(url)


if __name__ == "__main__":
    # Тестирование
    test_url = "https://yandex.ru/maps/org/gagarin/180566191872/"
    result = parse_yandex_card(test_url)
    print("\n📊 Результат парсинга:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

