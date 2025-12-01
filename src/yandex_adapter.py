"""
Адаптер для получения публичных данных о бизнесе из Яндекс.Карт.

ВАЖНО: сейчас это заглушка со структурой и минимальной логикой.
Реальный способ получения данных (официальное API или парсинг HTML)
нужно будет доработать отдельно, чтобы не ломать прод.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Dict


@dataclass
class YandexBusinessStatsPayload:
    """Структура для данных о бизнесе из Яндекс.Карт."""

    rating: Optional[float]
    reviews_total: Optional[int]
    reviews_30d: Optional[int]
    last_review_date: Optional[date]


class YandexAdapter:
    """
    Минимальный адаптер для получения данных из Яндекс.Карт.

    Сейчас реализован как заглушка:
    - парсит org_id из URL;
    - метод fetch_business_stats() возвращает None.
    """

    ORG_ID_REGEX = re.compile(r"/org/(\\d+)", re.IGNORECASE)

    def parse_org_id_from_url(self, yandex_url: str) -> Optional[str]:
        """
        Извлечь org_id из URL Яндекс.Карт.

        Пример:
            https://yandex.ru/maps/org/123456789/ -> "123456789"
        """
        if not yandex_url:
            return None
        match = self.ORG_ID_REGEX.search(yandex_url)
        return match.group(1) if match else None

    def fetch_business_stats(self, yandex_org_id: str) -> Optional[YandexBusinessStatsPayload]:
        """
        Получить данные о рейтинге и отзывах бизнеса из Яндекс.Карт.

        Сейчас это заглушка, которая всегда возвращает None.
        Реальную реализацию (API/парсинг) добавим отдельным этапом.
        """
        if not yandex_org_id:
            return None

        # TODO: реализовать реальный запрос к Яндекс.Картам
        # Здесь сознательно не делаем сетевые вызовы, чтобы
        # не ломать локальную разработку и прод-окружение.
        return None



