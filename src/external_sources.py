"""
Общий слой абстракции для внешних источников данных о бизнесе
(Яндекс.Бизнес, Google Business Profile, 2ГИС и публичные карты).

Задачи:
- единый enum для source
- базовый интерфейс адаптеров
- утилиты для генерации идентификаторов
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Protocol, List


class ExternalSource(str):
    """Поддерживаемые внешние источники."""

    YANDEX_BUSINESS = "yandex_business"
    YANDEX_MAPS = "yandex_maps"
    GOOGLE_BUSINESS = "google_business"
    TWO_GIS = "2gis"


@dataclass
class ExternalAccount:
    id: str
    business_id: str
    source: str
    external_id: Optional[str]
    display_name: Optional[str]
    is_active: bool = True
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None


@dataclass
class ExternalReview:
    id: str
    business_id: str
    source: str
    external_review_id: Optional[str]
    rating: Optional[int]
    author_name: Optional[str]
    text: Optional[str]
    published_at: Optional[datetime]
    response_text: Optional[str] = None
    response_at: Optional[datetime] = None
    raw_payload: Optional[Dict[str, Any]] = None


@dataclass
class ExternalStatsPoint:
    id: str
    business_id: str
    source: str
    date: str  # YYYY-MM-DD
    views_total: Optional[int] = None
    clicks_total: Optional[int] = None
    actions_total: Optional[int] = None
    rating: Optional[float] = None
    reviews_total: Optional[int] = None
    unanswered_reviews_count: Optional[int] = None
    raw_payload: Optional[Dict[str, Any]] = None


@dataclass
class ExternalPost:
    """Новость/пост организации из внешнего источника."""
    id: str
    business_id: str
    source: str
    external_post_id: Optional[str]
    title: Optional[str]
    text: Optional[str]
    published_at: Optional[datetime]
    image_url: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


@dataclass
class ExternalPhoto:
    """Фотография организации из внешнего источника."""
    id: str
    business_id: str
    source: str
    external_photo_id: Optional[str]
    url: Optional[str]
    thumbnail_url: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    raw_payload: Optional[Dict[str, Any]] = None


class ExternalSourceAdapter(Protocol):
    """
    Базовый протокол для адаптеров внешних источников.

    Каждый конкретный источник (Яндекс.Бизнес, Google, 2ГИС) реализует
    эти методы, возвращая нормализованные структуры.
    """

    source: str

    def fetch_reviews(self, account_row: dict) -> List[ExternalReview]:
        ...

    def fetch_stats(self, account_row: dict) -> List[ExternalStatsPoint]:
        ...


def make_stats_id(business_id: str, source: str, date_str: str) -> str:
    """Утилита для генерации id записи статистики."""
    return f"{business_id}_{source}_{date_str}"



