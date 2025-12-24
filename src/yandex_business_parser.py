#!/usr/bin/env python3
"""
Парсер для получения данных из личного кабинета Яндекс.Бизнес.

Использует HTTP-запросы с cookie/headers для авторизации в кабинете.
Парсит XHR-эндпоинты кабинета для получения отзывов и статистики.
"""

from __future__ import annotations

import json
import os
import time
import random
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import requests
from external_sources import ExternalReview, ExternalStatsPoint


class YandexBusinessParser:
    """Парсер для личного кабинета Яндекс.Бизнес."""

    def __init__(self, auth_data: Dict[str, Any]):
        """
        Инициализация парсера с данными авторизации.
        
        Args:
            auth_data: Словарь с ключами:
                - cookies: строка с cookies (например, "yandexuid=...; Session_id=...")
                - headers: опциональные дополнительные headers
        """
        self.auth_data = auth_data
        self.cookies_str = auth_data.get("cookies", "")
        self.headers = auth_data.get("headers", {})
        
        # Базовые headers для запросов к кабинету (имитируем браузер, чтобы избежать капчи)
        self.session_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://yandex.ru/sprav/",
            "Origin": "https://yandex.ru",
            "X-Requested-With": "XMLHttpRequest",
            **self.headers,
        }
        
        # Парсим cookies в словарь для requests
        self.cookies_dict = self._parse_cookies(self.cookies_str)
        
        print(f"🍪 Парсер инициализирован с {len(self.cookies_dict)} cookies")
        if self.cookies_dict:
            print(f"   Ключи cookies: {', '.join(list(self.cookies_dict.keys())[:10])}")
        
        # Создаём сессию requests для сохранения cookies между запросами
        self.session = requests.Session()
        self.session.cookies.update(self.cookies_dict)
        self.session.headers.update(self.session_headers)
        
        # Убеждаемся, что cookies действительно установлены в сессии
        if len(self.session.cookies) == 0 and len(self.cookies_dict) > 0:
            print(f"⚠️ Предупреждение: cookies не установлены в сессии, устанавливаем вручную")
            for key, value in self.cookies_dict.items():
                self.session.cookies.set(key, value)

    def _parse_cookies(self, cookies_str: str) -> Dict[str, str]:
        """Парсит строку cookies в словарь."""
        cookies = {}
        if not cookies_str:
            return cookies
        
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key.strip()] = value.strip()
        return cookies

    def _make_request(self, url: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Выполняет HTTP-запрос к кабинету Яндекс.Бизнес.
        
        Args:
            url: URL для запроса
            method: HTTP метод (GET, POST)
            params: Query параметры для URL
            **kwargs: Дополнительные параметры для requests
        
        Returns:
            JSON ответ или None при ошибке
        """
        try:
            # Извлекаем org_id из URL для правильного Referer
            org_id = None
            if "/api/" in url:
                try:
                    parts = url.split("/api/")[1].split("/")
                    if parts:
                        org_id = parts[0]
                except:
                    pass
            
            # Обновляем headers для имитации браузера (чтобы избежать капчи)
            headers = {
                **self.session_headers,
            }
            
            if org_id:
                headers["Referer"] = f"https://yandex.ru/sprav/{org_id}/p/edit/reviews/"
            
            # Имитация человека: случайная задержка перед запросом
            delay = random.uniform(1.5, 3.5)
            time.sleep(delay)
            
            # Логируем cookies для отладки (только ключи, не значения)
            if self.cookies_dict:
                cookie_keys = list(self.cookies_dict.keys())
                print(f"   🍪 Используем cookies: {len(cookie_keys)} ключей ({', '.join(cookie_keys[:5])}{'...' if len(cookie_keys) > 5 else ''})")
            
            # Используем сессию для сохранения cookies
            response = self.session.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=30,
                **kwargs,
            )
            
            # Проверяем на капчу
            response_text_lower = response.text.lower()
            if "captcha" in response_text_lower or "робот" in response_text_lower or "smartcaptcha" in response_text_lower:
                print(f"⚠️ Яндекс показал капчу для {url}")
                print(f"   Это означает, что запросы похожи на автоматические")
                print(f"   Решения:")
                print(f"   1. Обновить cookies в админской панели")
                print(f"   2. Использовать сессию requests для сохранения cookies между запросами")
                print(f"   3. Добавить задержки между запросами")
                return None
            
            response.raise_for_status()
            
            # Пробуем распарсить JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                # Если не JSON, проверяем, может это HTML с ошибкой
                if response.text.strip().startswith("<!DOCTYPE") or response.text.strip().startswith("<html"):
                    print(f"⚠️ Получен HTML вместо JSON от {url}")
                    print(f"   Возможно, требуется авторизация или cookies устарели")
                    print(f"   Начало ответа: {response.text[:200]}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Статус код: {e.response.status_code}")
                if e.response.status_code == 401:
                    print(f"   ⚠️ Не авторизован - возможно:")
                    print(f"      1. Cookies устарели (нужно обновить в админской панели)")
                    print(f"      2. Cookies не передаются правильно")
                    print(f"      3. Нужны дополнительные headers")
                    # Показываем начало ответа для отладки
                    try:
                        response_text = e.response.text[:200]
                        if "captcha" in response_text.lower() or "робот" in response_text.lower():
                            print(f"   🔐 Яндекс показал капчу")
                    except:
                        pass
                elif e.response.status_code == 403:
                    print(f"   ⚠️ Доступ запрещён - возможно, нужны свежие cookies")
            return None
        except Exception as e:
            print(f"❌ Неожиданная ошибка при запросе к {url}: {e}")
            return None

    def fetch_reviews(self, account_row: dict) -> List[ExternalReview]:
        """
        Получить отзывы из кабинета Яндекс.Бизнес.
        
        Args:
            account_row: Строка из ExternalBusinessAccounts с полями business_id, external_id и т.д.
        
        Returns:
            Список ExternalReview
        """
        business_id = account_row["business_id"]
        external_id = account_row.get("external_id")
        
        # Если включен фейковый режим, возвращаем демо-данные
        if os.getenv("YANDEX_BUSINESS_FAKE", "0") == "1":
            return self._fake_fetch_reviews(account_row)
        
        reviews = []
        
        if not external_id:
            print(f"⚠️ Нет external_id для бизнеса {business_id}, используем демо-данные")
            return self._fake_fetch_reviews(account_row)
        
        # Правильный endpoint для отзывов (найден через Network tab браузера)
        # Формат: https://yandex.ru/sprav/api/{org_id}/reviews?ranking=by_time&page=1&type=company&unread=false
        base_url = f"https://yandex.ru/sprav/api/{external_id}/reviews"
        
        # Собираем все отзывы через пагинацию
        all_reviews_data = []
        page = 1
        continue_token = None
        max_pages = 50  # Ограничение на случай бесконечного цикла
        
        while page <= max_pages:
            # Query параметры для получения отзывов
            params = {
                "ranking": "by_time",
                "page": page,
                "type": "company",
                "unread": "false",  # Все отзывы, не только непрочитанные
            }
            
            # Если есть токен продолжения, добавляем его
            if continue_token:
                params["continue_token"] = continue_token
            
            print(f"🔍 Загружаем страницу {page} отзывов...")
            
            # Имитация человека: случайная задержка между страницами
            if page > 1:
                page_delay = random.uniform(2.0, 4.0)
                print(f"   ⏳ Пауза {page_delay:.1f} сек (имитация человека)...")
                time.sleep(page_delay)
            
            result = self._make_request(base_url, params=params)
            
            if not result:
                print(f"⚠️ Не удалось получить данные для страницы {page}")
                if page == 1:
                    # Если первая страница не загрузилась, возвращаем демо-данные
                    return self._fake_fetch_reviews(account_row)
                break
            
            # Парсим структуру ответа
            page_reviews = []
            if isinstance(result, list):
                page_reviews = result
            elif "reviews" in result:
                page_reviews = result["reviews"]
            elif "items" in result:
                page_reviews = result["items"]
            elif "data" in result:
                if isinstance(result["data"], list):
                    page_reviews = result["data"]
                elif isinstance(result["data"], dict) and "reviews" in result["data"]:
                    page_reviews = result["data"]["reviews"]
            
            if not page_reviews:
                print(f"⚠️ На странице {page} нет отзывов")
                break
            
            print(f"✅ Получено {len(page_reviews)} отзывов со страницы {page}")
            all_reviews_data.extend(page_reviews)
            
            # Проверяем, есть ли следующая страница
            continue_token = result.get("continue_token") or result.get("next_token")
            if not continue_token:
                # Если нет токена, проверяем, есть ли ещё страницы
                total = result.get("total") or result.get("count")
                if total and len(all_reviews_data) >= total:
                    print(f"✅ Загружены все отзывы (всего: {total})")
                    break
                # Если нет total, предполагаем что это последняя страница
                if len(page_reviews) < 20:  # Обычно на странице 20 отзывов
                    print(f"✅ Загружены все отзывы (последняя страница)")
                    break
            
            page += 1
        
        reviews_list = all_reviews_data
        print(f"📊 Всего загружено отзывов: {len(reviews_list)}")
        
        if not reviews_list:
            print(f"⚠️ Не удалось получить отзывы для {business_id}")
            return self._fake_fetch_reviews(account_row)
        
        # Парсим отзывы
        for idx, review_data in enumerate(reviews_list):
            review_id = review_data.get("id") or f"{business_id}_review_{idx}"
            try:
                published_at_str = review_data.get("published_at")
                published_at = None
                if published_at_str:
                    published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                
                # Парсим ответ организации (если есть)
                response_at = None
                response_text = None
                has_response = False
                
                # Проверяем различные варианты структуры ответа
                response_data = review_data.get("response") or review_data.get("reply") or review_data.get("organization_response")
                if response_data:
                    if isinstance(response_data, dict):
                        response_text = response_data.get("text") or response_data.get("message") or response_data.get("content")
                        response_at_str = response_data.get("created_at") or response_data.get("published_at") or response_data.get("date")
                    elif isinstance(response_data, str):
                        response_text = response_data
                    
                    if response_text and response_text.strip():
                        has_response = True
                        if response_at_str:
                            try:
                                response_at = datetime.fromisoformat(response_at_str.replace("Z", "+00:00"))
                            except:
                                pass
                
                # Парсим рейтинг (может быть в разных форматах)
                rating = review_data.get("rating") or review_data.get("score") or review_data.get("stars")
                if rating:
                    try:
                        rating = int(rating)
                    except:
                        rating = None
                
                # Парсим автора
                author_name = None
                author_data = review_data.get("author") or review_data.get("user") or review_data.get("reviewer")
                if isinstance(author_data, dict):
                    author_name = author_data.get("name") or author_data.get("display_name") or author_data.get("username")
                elif isinstance(author_data, str):
                    author_name = author_data
                
                # Парсим текст отзыва
                text = review_data.get("text") or review_data.get("content") or review_data.get("message") or review_data.get("comment")
                
                review = ExternalReview(
                    id=f"{business_id}_yandex_business_{review_id}",
                    business_id=business_id,
                    source="yandex_business",
                    external_review_id=review_id,
                    rating=rating,
                    author_name=author_name,
                    text=text,
                    published_at=published_at,
                    response_text=response_text if has_response else None,
                    response_at=response_at if has_response else None,
                    raw_payload=review_data,
                )
                reviews.append(review)
            except Exception as e:
                print(f"⚠️ Ошибка парсинга отзыва {review_id}: {e}")
                continue
        
        # Подсчитываем статистику по отзывам
        total_reviews = len(reviews)
        reviews_with_response = sum(1 for r in reviews if r.response_text)
        reviews_without_response = total_reviews - reviews_with_response
        
        print(f"   📊 Статистика по отзывам:")
        print(f"      - Всего: {total_reviews}")
        print(f"      - С ответами: {reviews_with_response}")
        print(f"      - Без ответов: {reviews_without_response}")
        
        return reviews

    def fetch_stats(self, account_row: dict) -> List[ExternalStatsPoint]:
        """
        Получить статистику из кабинета Яндекс.Бизнес.
        
        Args:
            account_row: Строка из ExternalBusinessAccounts
        
        Returns:
            Список ExternalStatsPoint
        """
        business_id = account_row["business_id"]
        external_id = account_row.get("external_id")
        
        # Если включен фейковый режим, возвращаем демо-данные
        if os.getenv("YANDEX_BUSINESS_FAKE", "0") == "1":
            return self._fake_fetch_stats(account_row)
        
        stats = []
        
        if not external_id:
            print(f"⚠️ Нет external_id для бизнеса {business_id}, используем демо-данные")
            return self._fake_fetch_stats(account_row)
        
        # Пробуем несколько возможных вариантов endpoints
        possible_urls = [
            f"https://business.yandex.ru/api/organizations/{external_id}/stats",
            f"https://business.yandex.ru/api/organizations/{external_id}/statistics",
            f"https://business.yandex.ru/api/sprav/organizations/{external_id}/stats",
            f"https://yandex.ru/sprav/api/organizations/{external_id}/stats",
            f"https://yandex.ru/sprav/{external_id}/p/edit/stats/api",
            f"https://business.yandex.ru/api/v1/organizations/{external_id}/stats",
        ]
        
        data = None
        working_url = None
        
        for url in possible_urls:
            print(f"🔍 Пробуем endpoint статистики: {url}")
            result = self._make_request(url)
            if result:
                data = result
                working_url = url
                print(f"✅ Успешно получены данные статистики с {url}")
                break
        
        if not data:
            print(f"⚠️ Не удалось получить статистику для {business_id} ни с одного endpoint")
            print(f"   Попробуйте найти правильный URL через DevTools → Network tab")
            return self._fake_fetch_stats(account_row)
        
        # Парсим ответ (структура зависит от реального API)
        # Возможные варианты структуры:
        # 1. {"stats": [...]}
        # 2. {"data": {"stats": [...]}}
        # 3. {"metrics": [...]}
        # 4. Прямой массив [...]
        
        stats_list = []
        if isinstance(data, list):
            stats_list = data
        elif "stats" in data:
            stats_list = data["stats"]
        elif "statistics" in data:
            stats_list = data["statistics"]
        elif "metrics" in data:
            stats_list = data["metrics"]
        elif "data" in data and isinstance(data["data"], dict):
            if "stats" in data["data"]:
                stats_list = data["data"]["stats"]
            elif "metrics" in data["data"]:
                stats_list = data["data"]["metrics"]
        
        print(f"📊 Найдено точек статистики в ответе: {len(stats_list)}")
        
        # Если список пустой, выводим структуру для отладки
        if not stats_list:
            print(f"⚠️ Список статистики пуст. Структура ответа:")
            print(f"   Тип: {type(data)}")
            if isinstance(data, dict):
                print(f"   Ключи верхнего уровня: {list(data.keys())[:10]}")
        today_str = date.today().isoformat()
        
        # Если нет данных за сегодня, создаём точку с текущей датой
        if not stats_list:
            stats_list = [{"date": today_str}]
        
        for stat_data in stats_list:
            date_str = stat_data.get("date", today_str)
            stat_id = f"{business_id}_yandex_business_{date_str}"
            
            stat_point = ExternalStatsPoint(
                id=stat_id,
                business_id=business_id,
                source="yandex_business",
                date=date_str,
                views_total=stat_data.get("views"),
                clicks_total=stat_data.get("clicks"),
                actions_total=stat_data.get("actions"),
                rating=stat_data.get("rating"),
                reviews_total=stat_data.get("reviews_count"),
                raw_payload=stat_data,
            )
            stats.append(stat_point)
        
        return stats

    def fetch_organization_info(self, account_row: dict) -> Dict[str, Any]:
        """
        Получить общую информацию об организации:
        - Рейтинг
        - Количество отзывов
        - Количество новостей
        - Количество фото
        
        Args:
            account_row: Строка из ExternalBusinessAccounts
        
        Returns:
            Словарь с информацией об организации
        """
        business_id = account_row["business_id"]
        external_id = account_row.get("external_id")
        
        if not external_id:
            return {
                "rating": None,
                "reviews_count": 0,
                "news_count": 0,
                "photos_count": 0,
            }
        
        # Пробуем получить информацию об организации
        org_url = f"https://yandex.ru/sprav/api/{external_id}"
        
        result = self._make_request(org_url)
        
        info = {
            "rating": None,
            "reviews_count": 0,
            "news_count": 0,
            "photos_count": 0,
        }
        
        if result:
            # Парсим рейтинг
            info["rating"] = result.get("rating") or result.get("average_rating") or result.get("score")
            
            # Парсим количество отзывов
            info["reviews_count"] = result.get("reviews_count") or result.get("reviews_total") or result.get("total_reviews") or 0
            
            # Парсим количество новостей
            info["news_count"] = result.get("news_count") or result.get("posts_count") or result.get("total_posts") or 0
            
            # Парсим количество фото
            info["photos_count"] = result.get("photos_count") or result.get("images_count") or result.get("total_photos") or 0
        
        # Если не получили данные из основного endpoint, пробуем получить из отзывов
        if info["reviews_count"] == 0:
            reviews = self.fetch_reviews(account_row)
            info["reviews_count"] = len(reviews)
            # Вычисляем средний рейтинг из отзывов
            if reviews:
                ratings = [r.rating for r in reviews if r.rating]
                if ratings:
                    info["rating"] = sum(ratings) / len(ratings)
        
        return info

    def _fake_fetch_reviews(self, account_row: dict) -> List[ExternalReview]:
        """Демо-данные для отзывов (используется при ошибках или в dev-режиме)."""
        today = datetime.utcnow()
        rid = f"{account_row['business_id']}_demo_review"
        return [
            ExternalReview(
                id=rid,
                business_id=account_row["business_id"],
                source="yandex_business",
                external_review_id=rid,
                rating=5,
                author_name="Demo Author",
                text="Это демо-отзыв из Яндекс.Бизнес (заглушка).",
                published_at=today,
                response_text=None,
                response_at=None,
                raw_payload={"demo": True},
            )
        ]

    def _fake_fetch_stats(self, account_row: dict) -> List[ExternalStatsPoint]:
        """Демо-данные для статистики (используется при ошибках или в dev-режиме)."""
        today_str = date.today().isoformat()
        sid = f"{account_row['business_id']}_yandex_business_{today_str}"
        return [
            ExternalStatsPoint(
                id=sid,
                business_id=account_row["business_id"],
                source="yandex_business",
                date=today_str,
                views_total=100,
                clicks_total=10,
                actions_total=5,
                rating=4.8,
                reviews_total=123,
                raw_payload={"demo": True},
            )
        ]

