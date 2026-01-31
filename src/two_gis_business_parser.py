"""
Парсер данных из личного кабинета 2ГИС, используя Playwright.
Мы перехватываем внутренние API запросы, эмулируя поведение пользователя в браузере.
"""
import logging
import json
from typing import List, Optional, Dict, Any, Union
from playwright.sync_api import sync_playwright, Page, Response

from external_sources import ExternalReview, ExternalStatsPoint, ExternalPost

logger = logging.getLogger(__name__)

class TwoGisBusinessParser:
    """
    Парсит данные из ЛК 2ГИС через Playwright.
    Использует cookies пользователя для авторизации.
    """
    
    BASE_URL = "https://account.2gis.com"
    
    # URL паттерны для перехвата (нужно уточнить при реальном использовании)
    # Обычно это что-то вроде /api/reviews/list или https://account.2gis.com/api/...
    # Пока ставим достаточно широкие фильтры для логгирования того, что мы поймаем
    REVIEWS_API_PATTERN = "**/api/*/reviews*" 
    STATS_API_PATTERN = "**/api/*/statistics*"

    def __init__(self, auth_data: Dict[str, Any]):
        """
        :param auth_data: Словарь с cookies (ключ 'cookies') и другими параметрами.
        """
        self.auth_data = auth_data
        self.cookies = self._parse_cookies(auth_data.get("cookies", ""))
        self.user_agent = auth_data.get("user_agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    def _parse_cookies(self, cookie_str: str) -> List[Dict[str, Any]]:
        """Преобразует строку cookies в формат списка словарей для Playwright"""
        if not cookie_str:
            return []
            
        cookies_list = []
        # Простейший парсинг: key=value; key2=value2
        for item in cookie_str.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookies_list.append({
                    "name": k,
                    "value": v,
                    "domain": ".2gis.com",  # Важно: правильный домен
                    "path": "/"
                })
        return cookies_list

    def fetch_reviews(self, account: Dict[str, Any]) -> List[ExternalReview]:
        """
        Переходит на страницу отзывов и перехватывает JSON с отзывами.
        """
        external_id = account.get('external_id') # Это может быть ID филиала
        reviews_url = f"{self.BASE_URL}/filials/{external_id}/reviews" # Предположительный URL
        
        fetched_reviews: List[ExternalReview] = []

        logger.info(f"Navigating to {reviews_url} to fetch reviews via Playwright...")
        
        with sync_playwright() as p:
            # Запуск браузера (можно headless=True для продакшена)
            browser = p.chromium.launch(headless=True) 
            context = browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1280, "height": 720}
            )
            
            # Установка cookies
            if self.cookies:
                context.add_cookies(self.cookies)
            
            page = context.new_page()

            # Обработчик ответа
            def handle_response(response: Response):
                # Фильтруем ответы, похожие на API отзывов
                # Здесь логика "охоты": ищем JSON, в котором есть список отзывов
                if "application/json" in response.headers.get("content-type", ""):
                    try:
                        # Поскольку мы не знаем точный URL, мы можем попытаться анализировать размер или структуру
                        # Но лучше, если мы будем знать часть URL
                        if "reviews" in response.url and "list" in response.url:
                            logger.info(f"Captured reviews response from: {response.url}")
                            data = response.json()
                            # TODO: Написать маппер из JSON 2ГИС в ExternalReview
                            # Пока просто логгируем структуру для отладки
                            logger.info(f"Reviews Data Preview: {str(data)[:200]}")
                            
                            # MOCK PARSING for now until we see real data structure
                            # fetched_reviews.extend(self._mock_parse_reviews(data))
                    except Exception as e:
                        logger.error(f"Error parsing response {response.url}: {e}")

            page.on("response", handle_response)
            
            try:
                page.goto(reviews_url, timeout=60000)
                page.wait_for_load_state("networkidle", timeout=60000)
                # Можно добавить задержку или ожидание конкретного элемента
                # page.wait_for_timeout(5000) 
            except Exception as e:
                logger.error(f"Error during navigation: {e}")
            finally:
                browser.close()
                
        return fetched_reviews

    def fetch_stats(self, account: Dict[str, Any]) -> List[ExternalStatsPoint]:
        """
        Получение статистики через Playwright.
        """
        # Аналогичная логика перехвата
        logger.warning("TwoGisBusinessParser.fetch_stats: Not implemented fully yet")
        return []

    def fetch_posts(self, account: Dict[str, Any]) -> List[ExternalPost]:
        return []

    def _mock_parse_reviews(self, data: Any) -> List[ExternalReview]:
        # Временная функция для тестирования
        return []
