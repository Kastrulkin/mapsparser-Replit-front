#!/usr/bin/env python3
"""
Парсер для получения данных из личного кабинета Яндекс.Бизнес.

Использует HTTP-запросы с cookie/headers для авторизации в кабинете.
Парсит XHR-эндпоинты кабинета для получения отзывов и статистики.
"""

from __future__ import annotations

import json
import os
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
        
        # Базовые headers для запросов к кабинету
        self.session_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": "https://business.yandex.ru/",
            **self.headers,
        }
        
        # Парсим cookies в словарь для requests
        self.cookies_dict = self._parse_cookies(self.cookies_str)

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

    def _make_request(self, url: str, method: str = "GET", **kwargs) -> Optional[Dict[str, Any]]:
        """
        Выполняет HTTP-запрос к кабинету Яндекс.Бизнес.
        
        Args:
            url: URL для запроса
            method: HTTP метод (GET, POST)
            **kwargs: Дополнительные параметры для requests
        
        Returns:
            JSON ответ или None при ошибке
        """
        try:
            response = requests.request(
                method,
                url,
                cookies=self.cookies_dict,
                headers=self.session_headers,
                timeout=30,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к {url}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON ответа от {url}: {e}")
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
        
        # Пример URL для получения отзывов (нужно уточнить реальный эндпоинт)
        # Обычно это что-то вроде: https://business.yandex.ru/api/organizations/{org_id}/reviews
        if not external_id:
            print(f"⚠️ Нет external_id для бизнеса {business_id}, используем демо-данные")
            return self._fake_fetch_reviews(account_row)
        
        # TODO: Заменить на реальный URL эндпоинта отзывов
        reviews_url = f"https://business.yandex.ru/api/organizations/{external_id}/reviews"
        
        data = self._make_request(reviews_url)
        
        if not data:
            print(f"⚠️ Не удалось получить отзывы для {business_id}, используем демо-данные")
            return self._fake_fetch_reviews(account_row)
        
        # Парсим ответ (структура зависит от реального API)
        # Примерная структура:
        # {
        #   "reviews": [
        #     {
        #       "id": "...",
        #       "rating": 5,
        #       "author": {"name": "..."},
        #       "text": "...",
        #       "published_at": "2024-01-01T00:00:00Z",
        #       "response": {"text": "...", "created_at": "..."}
        #     }
        #   ]
        # }
        
        reviews_list = data.get("reviews", [])
        
        for idx, review_data in enumerate(reviews_list):
            review_id = review_data.get("id") or f"{business_id}_review_{idx}"
            try:
                published_at_str = review_data.get("published_at")
                published_at = None
                if published_at_str:
                    published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                
                response_at = None
                response_text = None
                if review_data.get("response"):
                    response_text = review_data["response"].get("text")
                    response_at_str = review_data["response"].get("created_at")
                    if response_at_str:
                        response_at = datetime.fromisoformat(response_at_str.replace("Z", "+00:00"))
                
                review = ExternalReview(
                    id=f"{business_id}_yandex_business_{review_id}",
                    business_id=business_id,
                    source="yandex_business",
                    external_review_id=review_id,
                    rating=review_data.get("rating"),
                    author_name=review_data.get("author", {}).get("name"),
                    text=review_data.get("text"),
                    published_at=published_at,
                    response_text=response_text,
                    response_at=response_at,
                    raw_payload=review_data,
                )
                reviews.append(review)
            except Exception as e:
                print(f"⚠️ Ошибка парсинга отзыва {review_id}: {e}")
                continue
        
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
        
        # TODO: Заменить на реальный URL эндпоинта статистики
        stats_url = f"https://business.yandex.ru/api/organizations/{external_id}/stats"
        
        data = self._make_request(stats_url)
        
        if not data:
            print(f"⚠️ Не удалось получить статистику для {business_id}, используем демо-данные")
            return self._fake_fetch_stats(account_row)
        
        # Парсим ответ (структура зависит от реального API)
        # Примерная структура:
        # {
        #   "stats": [
        #     {
        #       "date": "2024-01-01",
        #       "views": 100,
        #       "clicks": 10,
        #       "actions": 5,
        #       "rating": 4.8,
        #       "reviews_count": 123
        #     }
        #   ]
        # }
        
        stats_list = data.get("stats", [])
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

