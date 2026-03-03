#!/usr/bin/env python3
"""
Парсер для получения данных из личного кабинета Яндекс.Бизнес.

Использует HTTP-запросы с cookie/headers для авторизации в кабинете.
Парсит XHR-эндпоинты кабинета для получения отзывов и статистики.
"""

from __future__ import annotations

import json
import os
import re
import time
import random
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import requests
from external_sources import ExternalReview, ExternalStatsPoint, ExternalPost, ExternalPhoto


_EDITORIAL_SERVICE_PATTERNS = (
    "хорошее место",
    "где можно",
    "выбрали места",
    "рассказываем про",
    "подборка",
    "популярных салонов красоты",
    "салоны красоты на ",
    "салоны красоты в ",
    "салоны красоты около ",
    "салоны красоты у ",
    "салоны красоты с наградой",
    "крафтовые бары",
    "бары для ",
    "бары, в которых ",
    "бары и пабы в ",
    "в районе ",
    "на улице ",
    "рядом с ",
)


def _extract_org_reference(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    for key in (
        "organization_id",
        "organizationId",
        "org_id",
        "orgId",
        "company_id",
        "companyId",
        "business_id",
        "businessId",
        "permalink",
    ):
        raw = payload.get(key)
        if isinstance(raw, dict):
            raw = raw.get("id") or raw.get("permalink") or raw.get("value")
        if raw is None:
            continue
        normalized = str(raw).strip()
        if normalized:
            return normalized
    return None


def _is_editorial_listing(name: Any, description: Any) -> bool:
    title = str(name or "").strip().lower()
    body = str(description or "").strip().lower()
    combined = f"{title} {body}"
    if any(pattern in combined for pattern in _EDITORIAL_SERVICE_PATTERNS):
        return True
    if body.startswith("рассказываем") or body.startswith("выбрали"):
        return True
    if title.startswith("бары ") or title.startswith("бары и пабы "):
        if any(marker in title for marker in ("в районе", "на ", "рядом", "с наградой")):
            return True
    return False


def _service_payload_is_relevant(payload: Any, expected_org_id: Optional[str], *, name: Any = None, description: Any = None) -> bool:
    if _is_editorial_listing(name, description):
        return False
    if not expected_org_id:
        return True
    found_org_id = _extract_org_reference(payload)
    if not found_org_id:
        return True
    return str(found_org_id) == str(expected_org_id)


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
        # Используем те же заголовки, что и в реальном запросе браузера
        self.session_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json; charset=UTF-8",
            "Accept-Language": "ru,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Cache-Control": "no-cache",
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
            
            # Проверяем статус код перед парсингом
            if response.status_code == 401:
                try:
                    error_data = response.json()
                    if error_data.get("error", {}).get("message") == "NEED_RESET":
                        print(f"⚠️ Сессия истекла (401 NEED_RESET) для {url}")
                        print(f"   🔐 Cookies устарели, нужно обновить авторизацию")
                        print(f"   Решение: Обновите cookies в админской панели")
                        print(f"   Redirect: {error_data.get('error', {}).get('redirectPath', 'N/A')}")
                        return None
                except:
                    pass
            
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
                    print(f"   ⚠️ Не авторизован (401) - сессия истекла")
                    try:
                        error_data = e.response.json()
                        if error_data.get("error", {}).get("message") == "NEED_RESET":
                            print(f"   🔐 Cookies устарели (NEED_RESET)")
                            print(f"   Решение: Обновите cookies в админской панели")
                            print(f"   Redirect: {error_data.get('error', {}).get('redirectPath', 'N/A')}")
                    except:
                        print(f"   ⚠️ Возможные причины:")
                        print(f"      1. Cookies устарели (нужно обновить в админской панели)")
                        print(f"      2. Cookies не передаются правильно")
                        print(f"      3. Нужны дополнительные headers")
                elif e.response.status_code == 302:
                    print(f"   ⚠️ Редирект (302) - возможно, сессия истекла")
                    print(f"   Решение: Обновите cookies в админской панели")
                elif e.response.status_code == 403:
                    print(f"   ⚠️ Доступ запрещён (403) - возможно, нужны свежие cookies")
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
        
        # Если включен фейковый режим, возвращаем демо-данные (только для тестирования)
        if os.getenv("YANDEX_BUSINESS_FAKE", "0") == "1":
            return self._fake_fetch_reviews(account_row)
        
        reviews = []
        
        if not external_id:
            print(f"❌ Нет external_id для бизнеса {business_id}")
            print(f"   Решение: Укажите external_id (permalink) в настройках аккаунта")
            return []
        
        # Правильный endpoint для отзывов (найден через Network tab браузера)
        # Формат пагинации: 
        #   Страница 1: ?ranking=by_time
        #   Страница 2: ?ranking=by_time&page=2&source=pagination
        #   Страница 3+: ?ranking=by_time&page=3&type=company&source=pagination
        # Получаем ВСЕ отзывы (не фильтруем по unread) - мы и так увидим, есть ли ответ
        base_url = f"https://yandex.ru/sprav/api/{external_id}/reviews"
        
        # Собираем все отзывы через пагинацию
        all_reviews_data = []
        seen_review_ids = set()  # Для отслеживания дубликатов
        # Проверяем, нужно ли загружать только новые отзывы
        only_new = account_row.get("only_new_reviews", False)
        last_sync_date = account_row.get("last_sync_at")
        
        total_reviews_expected = None  # Общее количество отзывов из pager
        limit = 20  # Лимит на страницу (обычно 20)
        max_pages = 30  # Ограничение на случай бесконечного цикла (30 страниц = ~600 отзывов)
        current_page = 1  # Текущая страница (начинаем с 1)
        
        if only_new and last_sync_date:
            print(f"🔄 Режим: загрузка только новых отзывов (после {last_sync_date})")
        while max_pages > 0 and current_page <= max_pages:
            # Query параметры для получения отзывов
            # Получаем ВСЕ отзывы, не фильтруем по unread - мы увидим наличие ответа по полю response
            params = {
                "ranking": "by_time",
            }
            
            # Начиная со 2 страницы добавляем параметры пагинации
            if current_page > 1:
                params["page"] = current_page
                params["source"] = "pagination"
                # Начиная с 3 страницы добавляется type=company
                if current_page >= 3:
                    params["type"] = "company"
            
            print(f"🔍 Страница {current_page}: Загружаем отзывы...")
            print(f"   Уже получено уникальных: {len(seen_review_ids)}, ожидается всего: {total_reviews_expected or 'неизвестно'}")
            
            # Имитация человека: случайная задержка между запросами (кроме первой страницы)
            # Это важно, чтобы избежать капчи Яндекс
            if current_page > 1:
                page_delay = random.uniform(2.0, 4.0)
                print(f"   ⏳ Пауза {page_delay:.1f} сек (имитация человека, чтобы избежать капчи)...")
                time.sleep(page_delay)
            
            result = self._make_request(base_url, params=params)
            
            if not result:
                print(f"❌ Не удалось получить данные со страницы {current_page}")
                if len(all_reviews_data) == 0:
                    # Если первая страница не загрузилась, возвращаем пустой список
                    print(f"   Возможные причины:")
                    print(f"   1. Cookies устарели - обновите их в админской панели")
                    print(f"   2. Сессия истекла (401 NEED_RESET)")
                    print(f"   3. Проблемы с сетью или API Яндекс изменился")
                    return []
                break
            
            # Логируем структуру ответа для отладки (только для первого запроса)
            if len(all_reviews_data) == 0:
                print(f"📋 Структура ответа (первый запрос):")
                print(f"   Тип: {type(result)}")
                if isinstance(result, dict):
                    print(f"   Ключи верхнего уровня: {list(result.keys())[:10]}")
                    # Показываем первые 500 символов JSON для отладки
                    import json
                    result_str = json.dumps(result, ensure_ascii=False, indent=2)[:500]
                    print(f"   Первые 500 символов JSON:\n{result_str}...")
            
            # Парсим структуру ответа
            # Реальная структура: {"list": {"items": [...], "pager": {"total": 62, "limit": 20, "offset": 0}}}
            page_reviews = []
            if isinstance(result, list):
                page_reviews = result
            elif "list" in result and isinstance(result["list"], dict):
                # Структура: {"list": {"items": [...]}}
                if "items" in result["list"]:
                    page_reviews = result["list"]["items"]
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
                print(f"⚠️ Нет отзывов в ответе")
                if len(all_reviews_data) == 0:
                    # Для первого запроса выводим полную структуру для отладки
                    print(f"🔍 Полная структура ответа (для отладки):")
                    import json
                    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
                break
            
            # Получаем pager для определения общего количества и следующего offset
            pager = None
            if "list" in result and isinstance(result["list"], dict) and "pager" in result["list"]:
                pager = result["list"]["pager"]
                if total_reviews_expected is None:
                    total_reviews_expected = pager.get("total")
                    if total_reviews_expected:
                        print(f"📊 Всего отзывов по API: {total_reviews_expected}")
                # Обновляем limit из pager, если он есть
                if "limit" in pager:
                    limit = pager.get("limit", 20)
            
            # Фильтруем дубликаты по ID
            new_reviews = []
            for review in page_reviews:
                review_id = review.get("id")
                if review_id and review_id not in seen_review_ids:
                    seen_review_ids.add(review_id)
                    new_reviews.append(review)
                elif not review_id:
                    # Если нет ID, добавляем всё равно (но это странно)
                    new_reviews.append(review)
            
            if new_reviews:
                print(f"✅ Получено {len(new_reviews)} новых отзывов (всего на странице: {len(page_reviews)}, дубликатов: {len(page_reviews) - len(new_reviews)})")
                all_reviews_data.extend(new_reviews)
            else:
                print(f"⚠️ Все отзывы на странице - дубликаты, останавливаем загрузку")
                break
            
            # Проверяем, достигли ли мы общего количества отзывов
            if total_reviews_expected:
                if len(seen_review_ids) >= total_reviews_expected:
                    print(f"✅ Загружены все отзывы (достигнут total: {total_reviews_expected})")
                    break
            
            # Если режим "только новые" и мы нашли старый отзыв, останавливаемся
            if only_new and last_sync_date:
                # Проверяем дату последнего отзыва на странице
                oldest_review_date = None
                for review in page_reviews:
                    review_date_str = review.get("published_at")
                    if review_date_str:
                        try:
                            review_date = datetime.fromisoformat(review_date_str.replace("Z", "+00:00"))
                            if oldest_review_date is None or review_date < oldest_review_date:
                                oldest_review_date = review_date
                        except:
                            pass
                
                if oldest_review_date:
                    # Преобразуем last_sync_date в datetime для сравнения
                    if isinstance(last_sync_date, str):
                        try:
                            last_sync_dt = datetime.fromisoformat(last_sync_date.replace("Z", "+00:00"))
                        except:
                            last_sync_dt = None
                    elif isinstance(last_sync_date, datetime):
                        last_sync_dt = last_sync_date
                    else:
                        last_sync_dt = None
                    
                    if last_sync_dt and oldest_review_date < last_sync_dt:
                        print(f"✅ Все новые отзывы загружены (найдены отзывы старше {last_sync_date}) - ПРОДОЛЖАЕМ для проверки ответов")
                        # break  # DISABLE BREAK to check for new replies on old reviews
            
            # Проверяем условия остановки пагинации
            # Если на странице меньше лимита, это последняя страница
            if len(page_reviews) < limit:
                print(f"✅ Загружены все отзывы (последняя страница, меньше лимита: {len(page_reviews)} < {limit})")
                break
            
            # Если достигли общего количества отзывов
            if total_reviews_expected and len(seen_review_ids) >= total_reviews_expected:
                print(f"✅ Загружены все отзывы (достигнут total: {total_reviews_expected})")
                break
            
            # Переходим на следующую страницу
            current_page += 1
            max_pages -= 1
        
        reviews_list = all_reviews_data
        print(f"📊 Всего загружено уникальных отзывов: {len(reviews_list)} (ожидалось: {total_reviews_expected})")
        
        if not reviews_list:
            print(f"❌ Не удалось получить отзывы для {business_id}")
            print(f"   Возможные причины:")
            print(f"   1. Cookies устарели - обновите их в админской панели")
            print(f"   2. Сессия истекла (401 NEED_RESET)")
            print(f"   3. Проблемы с сетью или API Яндекс изменился")
            return []
        
        # Парсим отзывы
        for idx, review_data in enumerate(reviews_list):
            import hashlib
            # Generate stable ID if external ID is missing
            author_data = review_data.get("author") or review_data.get("user") or {}
            author_name_trace = author_data.get("name") if isinstance(author_data, dict) else str(author_data)
            text_trace = review_data.get("text") or review_data.get("snippet") or ""
            date_trace = review_data.get("published_at") or review_data.get("date") or ""
            
            stable_id_str = f"{author_name_trace}_{date_trace}_{text_trace[:30]}"
            stable_hash = hashlib.md5(stable_id_str.encode()).hexdigest()
            
            review_id = review_data.get("id") or f"{business_id}_review_{stable_hash}"
            
            # Логируем raw данные для первых 2 отзывов (для отладки)
            if idx < 2:
                print(f"🔍 RAW данные отзыва #{idx + 1}:", flush=True)
                print(f"   Ключи: {list(review_data.keys())}", flush=True)
                # Показываем все поля, связанные с датой
                date_fields = {k: v for k, v in review_data.items() if 'date' in k.lower() or 'time' in k.lower() or 'created' in k.lower() or 'published' in k.lower()}
                if date_fields:
                    print(f"   Поля с датой: {date_fields}", flush=True)
                else:
                    print(f"   ⚠️ Поля с датой не найдены!", flush=True)
            
            try:
                # Пробуем разные варианты полей с датой
                # ВАЖНО: Яндекс теперь использует updatedTime!
                published_at_str = (
                    review_data.get("updatedTime") or  # NEW: Яндекс API 2026
                    review_data.get("createdTime") or  # Alternative NEW
                    review_data.get("published_at") or
                    review_data.get("publishedAt") or
                    review_data.get("date") or
                    review_data.get("created_at") or
                    review_data.get("createdAt") or
                    review_data.get("time_created") or
                    review_data.get("timestamp")
                )
                published_at = None
                if published_at_str:
                    try:
                        # Если это timestamp в миллисекундах
                        if isinstance(published_at_str, (int, float)) or (isinstance(published_at_str, str) and published_at_str.isdigit()):
                            timestamp_ms = int(published_at_str)
                            published_at = datetime.fromtimestamp(timestamp_ms / 1000.0)
                        else:
                            # ISO формат
                            published_at = datetime.fromisoformat(str(published_at_str).replace("Z", "+00:00"))
                    except Exception as date_err:
                        # Логируем только для первых отзывов
                        if idx < 3:
                            print(f"⚠️ Не удалось распарсить дату '{published_at_str}': {date_err}", flush=True)
                
                # Парсим ответ организации (если есть)
                response_at = None
                response_text = None
                has_response = False
                
                # Проверяем различные варианты структуры ответа
                # ВАЖНО: Яндекс теперь использует businessComment вместо owner_comment!
                response_data = (
                    review_data.get("businessComment") or  # NEW: Яндекс API 2026
                    review_data.get("owner_comment")
                )
                
                # Логируем структуру для отладки (первые 3 отзыва)
                if idx < 3:
                    print(f"   🔍 DEBUG response data для отзыва #{idx + 1}:", flush=True)
                    print(f"      businessComment: {review_data.get('businessComment')}", flush=True)
                    print(f"      Тип: {type(response_data)}", flush=True)
                    print(f"      Значение: {str(response_data)[:200] if response_data else 'None'}", flush=True)
                
                # ВАЖНО: проверяем, что owner_comment не null и не пустой объект
                if response_data is None:
                    # Нет ответа - это нормально
                    response_data = None
                elif isinstance(response_data, dict):
                    # Проверяем, что это не пустой объект {}
                    if not response_data or len(response_data) == 0:
                        if idx < 3:
                            print(f"      ⚠️ owner_comment - пустой объект {{}}", flush=True)
                        response_data = None
                elif isinstance(response_data, str):
                    # Проверяем, что строка не пустая
                    if not response_data.strip():
                        if idx < 3:
                            print(f"      ⚠️ owner_comment - пустая строка", flush=True)
                        response_data = None
                
                # Если owner_comment не найден, пробуем альтернативные поля
                if not response_data:
                    response_data = (
                        review_data.get("response") or 
                        review_data.get("reply") or 
                        review_data.get("organization_response") or
                        review_data.get("company_response") or
                        review_data.get("owner_response") or
                        review_data.get("answer") or
                        review_data.get("answers")  # Может быть массив
                    )
                
                # Если answers - массив, берём первый элемент
                if isinstance(response_data, list) and len(response_data) > 0:
                    response_data = response_data[0]
                
                if response_data:
                    if isinstance(response_data, dict):
                        response_text = (
                            response_data.get("text") or 
                            response_data.get("message") or 
                            response_data.get("content") or
                            response_data.get("body") or
                            response_data.get("comment")
                        )
                        # Для owner_comment время в миллисекундах (time_created)
                        response_at_str = (
                            response_data.get("time_created") or  # timestamp в миллисекундах для owner_comment
                            response_data.get("created_at") or 
                            response_data.get("published_at") or 
                            response_data.get("date") or
                            response_data.get("timestamp")
                        )
                    elif isinstance(response_data, str):
                        response_text = response_data
                    
                    if response_text and response_text.strip():
                        has_response = True
                        if idx < 3:
                            print(f"      ✅ Найден ответ (длина: {len(response_text)})", flush=True)
                        if response_at_str:
                            try:
                                # Если это timestamp в миллисекундах (как в owner_comment)
                                if isinstance(response_at_str, (int, float)) or (isinstance(response_at_str, str) and response_at_str.isdigit()):
                                    timestamp_ms = int(response_at_str)
                                    # Конвертируем из миллисекунд в datetime
                                    response_at = datetime.fromtimestamp(timestamp_ms / 1000.0)
                                else:
                                    # Обычный ISO формат
                                    response_at = datetime.fromisoformat(response_at_str.replace("Z", "+00:00"))
                            except:
                                pass
                    else:
                        if idx < 3 and response_text is not None:
                            print(f"      ⚠️ response_text пустой или только пробелы: '{response_text}'", flush=True)
                
                # Парсим рейтинг (может быть в разных форматах)
                rating = review_data.get("rating") or review_data.get("score") or review_data.get("stars")
                if rating:
                    try:
                        rating = int(rating)
                    except:
                        rating = None
                
                # Парсим автора (ВАЖНО: до логирования!)
                author_name = None
                author_data = review_data.get("author") or review_data.get("user") or review_data.get("reviewer")
                if isinstance(author_data, dict):
                    # В API Яндекс.Бизнес имя автора может быть в поле "user" внутри "author"
                    author_name = author_data.get("user") or author_data.get("name") or author_data.get("display_name") or author_data.get("username")
                    # Если user - это строка, используем её
                    if isinstance(author_name, str):
                        pass  # Уже строка
                    elif isinstance(author_name, dict):
                        author_name = author_name.get("name") or author_name.get("display_name") or author_name.get("username")
                elif isinstance(author_data, str):
                    author_name = author_data
                
                # Логируем структуру только для первых нескольких отзывов (для отладки)
                if idx < 3:
                    print(f"🔍 Отзыв #{idx + 1} (ID: {review_id}):", flush=True)
                    print(f"   Автор: {author_name}", flush=True)
                    print(f"   Рейтинг: {rating}", flush=True)
                    print(f"   Дата публикации: {published_at}", flush=True)
                    if has_response:
                        print(f"   ✅ Найден ответ: {response_text[:100]}...", flush=True)
                        if response_at:
                            print(f"   Дата ответа: {response_at}", flush=True)
                    else:
                        print(f"   ❌ Ответа нет", flush=True)
                
                # Парсим текст отзыва
                # В API Яндекс.Бизнес текст отзыва может быть в разных полях:
                # - full_text (полный текст)
                # - snippet (краткий текст)
                # - text (обычный текст)
                text = review_data.get("full_text") or review_data.get("snippet") or review_data.get("text") or review_data.get("content") or review_data.get("message") or review_data.get("comment")
                
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
        
        # Логируем первые несколько отзывов без ответов для отладки
        reviews_without_response_list = [r for r in reviews if not r.response_text]
        if reviews_without_response_list:
            print(f"   🔍 Первые 5 отзывов БЕЗ ответов (для отладки):")
            for idx, r in enumerate(reviews_without_response_list[:5]):
                print(f"      #{idx + 1}: ID={r.external_review_id}, Рейтинг={r.rating}, Автор={r.author_name}")
                # Проверяем, есть ли owner_comment в raw_payload
                if r.raw_payload and "owner_comment" in r.raw_payload:
                    owner_comment = r.raw_payload.get("owner_comment")
                    print(f"         ⚠️ owner_comment найден в raw_payload: {str(owner_comment)[:100]}")
        
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
        
        # Если включен фейковый режим, возвращаем демо-данные (только для тестирования)
        if os.getenv("YANDEX_BUSINESS_FAKE", "0") == "1":
            return self._fake_fetch_stats(account_row)
        
        stats = []
        
        if not external_id:
            print(f"❌ Нет external_id для бизнеса {business_id}")
            print(f"   Решение: Укажите external_id (permalink) в настройках аккаунта")
            return []
        
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
            print(f"❌ Не удалось получить статистику для {business_id} ни с одного endpoint")
            print(f"   Возможные причины:")
            print(f"   1. Cookies устарели - обновите их в админской панели")
            print(f"   2. Сессия истекла (401 NEED_RESET)")
            print(f"   3. API endpoint изменился - проверьте через DevTools → Network tab")
            return []
        
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
        # Пробуем несколько вариантов endpoints
        possible_org_urls = [
            f"https://yandex.ru/sprav/api/{external_id}",
            f"https://yandex.ru/sprav/api/{external_id}/info",
            f"https://yandex.ru/sprav/api/{external_id}/main",
            f"https://yandex.ru/sprav/{external_id}/p/edit/sidebar?permalink={external_id}",  # Sidebar может содержать статистику
        ]
        
        result = None
        for org_url in possible_org_urls:
            result = self._make_request(org_url)
            if result:
                print(f"✅ Получены данные организации с {org_url}")
                break
        
        def _normalize_rating_value(value: Any) -> Optional[float]:
            """Нормализовать рейтинг в диапазон [0..5], поддерживая значения с запятой."""
            if value is None:
                return None
            if isinstance(value, (int, float)):
                normalized = float(value)
                return normalized if 0.0 <= normalized <= 5.0 else None
            try:
                text = str(value).strip().replace(",", ".")
            except Exception:
                return None
            if not text:
                return None
            match = re.search(r"(\d+(?:\.\d+)?)", text)
            if not match:
                return None
            try:
                normalized = float(match.group(1))
            except (TypeError, ValueError):
                return None
            return normalized if 0.0 <= normalized <= 5.0 else None

        # Также пробуем получить рейтинг со страницы отзывов (более точный)
        reviews_page_url = f"https://yandex.ru/sprav/{external_id}/p/edit/reviews"
        try:
            delay = random.uniform(1.5, 3.5)
            time.sleep(delay)
            
            reviews_headers = {
                **self.session_headers,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            
            response = self.session.get(reviews_page_url, headers=reviews_headers, timeout=30)
            if response.status_code == 200:
                html_content = response.text
                
                # Парсим рейтинг из HTML используя селектор
                # Селектор: #root > div > div.EditPage.EditPage_type_reviews > div.EditPage-Right > div > div.ReviewsPage > div.ReviewsPage-Content > div.ReviewsPage-Right > div.MainCard.MainCard_withoutBorder.RatingCard.ReviewsPage-RatingCardBlock > div > div.MainCard-Content > div > div > div.RatingCard-TopSection > span
                import re
                
                # Ищем рейтинг в HTML - ищем паттерн типа "4.7" рядом с классом RatingCard
                # Селектор: RatingCard-TopSection > span
                rating_patterns = [
                    r'RatingCard-TopSection[^>]*>.*?<span[^>]*>(\d+[.,]\d+)',  # Рейтинг в RatingCard-TopSection > span
                    r'RatingCard[^>]*>.*?(\d+[.,]\d+)\s*★',  # Рейтинг в RatingCard с звездами
                    r'rating["\']?\s*[:=]\s*["\']?(\d+[.,]\d+)',  # rating: "4.7"/"4,7"
                    r'<span[^>]*class[^>]*RatingCard[^>]*>(\d+[.,]\d+)',  # <span class="RatingCard...">4.7
                    r'(\d+[.,]\d+)\s*★',  # 4.7 ★ / 4,7 ★
                ]
                
                for pattern in rating_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                    if match:
                        rating_value = _normalize_rating_value(match.group(1))
                        if rating_value is not None:
                            print(f"   📊 Рейтинг со страницы отзывов: {rating_value}")
                            if not result:
                                result = {}
                            result["rating"] = rating_value
                            break
        except Exception as e:
            print(f"   ⚠️ Не удалось получить рейтинг со страницы отзывов: {e}")
        
        info = {
            "rating": None,
            "reviews_count": 0,
            "news_count": 0,
            "photos_count": 0,
        }
        
        if result:
            # Парсим рейтинг (приоритет: реальный рейтинг из API, затем вычисленный)
            api_rating = result.get("rating") or result.get("average_rating") or result.get("score")
            normalized_api_rating = _normalize_rating_value(api_rating)
            if normalized_api_rating is not None:
                info["rating"] = normalized_api_rating
                print(f"   📊 Рейтинг из API: {info['rating']}")
            
            # Парсим количество отзывов
            info["reviews_count"] = result.get("reviews_count") or result.get("reviews_total") or result.get("total_reviews") or 0
            
            # Парсим количество новостей
            info["news_count"] = result.get("news_count") or result.get("posts_count") or result.get("total_posts") or 0
            
            # Парсим количество фото (пробуем разные варианты ключей)
            info["photos_count"] = (
                result.get("photos_count") or 
                result.get("images_count") or 
                result.get("total_photos") or 
                result.get("photos_total") or
                result.get("media_count") or
                0
            )
            
            # Также проверяем вложенные структуры
            if info["photos_count"] == 0:
                # Может быть в stats или summary
                if "stats" in result and isinstance(result["stats"], dict):
                    info["photos_count"] = result["stats"].get("photos_count") or result["stats"].get("total_photos") or 0
                if "summary" in result and isinstance(result["summary"], dict):
                    info["photos_count"] = result["summary"].get("photos_count") or result["summary"].get("total_photos") or 0
                if "counts" in result and isinstance(result["counts"], dict):
                    info["photos_count"] = result["counts"].get("photos") or result["counts"].get("photos_count") or 0
        
        # Если не получили данные из основного endpoint, пробуем получить из реальных методов
        if info["reviews_count"] == 0:
            reviews = self.fetch_reviews(account_row)
            info["reviews_count"] = len(reviews)
            # Вычисляем средний рейтинг из отзывов ТОЛЬКО если не получили из API
            if not info["rating"] and reviews:
                ratings = [r.rating for r in reviews if r.rating and isinstance(r.rating, (int, float))]
                if ratings:
                    avg_rating = sum(ratings) / len(ratings)
                    # Округляем до 1 знака после запятой
                    info["rating"] = round(avg_rating, 1)
                    print(f"   📊 Вычислен средний рейтинг из {len(ratings)} отзывов: {info['rating']}")
        
        # Если рейтинг всё ещё не найден, пробуем получить из статистики
        if not info["rating"]:
            try:
                stats = self.fetch_stats(account_row)
                if stats and len(stats) > 0:
                    # Ищем последнюю статистику с рейтингом
                    stats.sort(key=lambda x: x.date, reverse=True)
                    for stat in stats:
                        if stat.rating and stat.rating > 0:
                            info["rating"] = stat.rating
                            print(f"   📊 Рейтинг получен из статистики: {info['rating']}")
                            break
            except Exception as e:
                print(f"⚠️ Ошибка получения рейтинга из статистики: {e}")
        
        # Получаем количество новостей и фото из реальных методов
        if info["news_count"] == 0:
            try:
                posts = self.fetch_posts(account_row)
                info["news_count"] = len(posts)
            except Exception as e:
                print(f"⚠️ Ошибка получения постов для подсчёта: {e}")
        
        # Получаем количество фотографий (используем упрощённый метод)
        if info["photos_count"] == 0:
            try:
                photos_count = self.fetch_photos_count(account_row)
                info["photos_count"] = photos_count
            except Exception as e:
                print(f"⚠️ Ошибка получения количества фотографий: {e}")
        
        return info

    def fetch_posts(self, account_row: dict) -> List[ExternalPost]:
        """
        Получить новости/посты из кабинета Яндекс.Бизнес.
        
        Args:
            account_row: Строка из ExternalBusinessAccounts с полями business_id, external_id и т.д.
        
        Returns:
            Список ExternalPost
        """
        business_id = account_row["business_id"]
        external_id = account_row.get("external_id")
        
        # Если включен фейковый режим, возвращаем демо-данные (только для тестирования)
        if os.getenv("YANDEX_BUSINESS_FAKE", "0") == "1":
            return self._fake_fetch_posts(account_row)
        
        posts = []
        
        if not external_id:
            print(f"❌ Нет external_id для бизнеса {business_id}")
            print(f"   Решение: Укажите external_id (permalink) в настройках аккаунта")
            return []
        
        # Endpoint для постов (публикаций/новостей)
        # URL страницы: https://yandex.ru/sprav/{org_id}/p/edit/posts/
        # 
        # ВАЖНО: Реальных API endpoints для постов не найдено в Network tab.
        # Предполагаемые endpoints ниже - это только предположения на основе паттерна отзывов.
        # Поэтому сначала пробуем парсить HTML страницы (более надёжный способ).
        
        import json  # Импортируем json для обработки JSONDecodeError
        
        # Сначала пробуем получить данные из API endpoint sidebar?permalink=...
        # Это реальный endpoint, который видели в Network tab (125 kB ответ)
        # Правильный URL: https://yandex.ru/business/server-components/sidebar?permalink={external_id}
        print(f"🔍 Пробуем получить данные из sidebar API endpoint...")
        sidebar_url = f"https://yandex.ru/business/server-components/sidebar?permalink={external_id}"
        
        result = None
        working_url = None
        
        # Пробуем sidebar endpoint (реальный, видели в Network tab)
        delay = random.uniform(1.5, 3.5)
        time.sleep(delay)
        
        # Для sidebar API может потребоваться специальный Referer
        # Пробуем с разными вариантами headers
        sidebar_headers = {
            **self.session_headers,
            "Referer": f"https://yandex.ru/sprav/{external_id}/p/edit/posts/",
            "Accept": "application/json, text/plain, */*",
        }
        
        try:
            response = self.session.get(sidebar_url, headers=sidebar_headers, timeout=30)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '').lower()
                
                # Пробуем JSON
                if 'application/json' in content_type:
                    try:
                        result = response.json()
                        working_url = sidebar_url
                        print(f"✅ Успешно получены данные из sidebar API (JSON)")
                    except json.JSONDecodeError:
                        result = None
                
                # Если не JSON, пробуем извлечь из HTML/JavaScript
                if not result and ('text/html' in content_type or 'text/javascript' in content_type or 'application/javascript' in content_type):
                    html_content = response.text
                    print(f"🔍 Sidebar API вернул HTML/JavaScript ({len(html_content)} символов), извлекаем данные...")
                    
                    # Ищем упоминания API endpoints в Response (может быть полезно для отладки)
                    import re
                    api_endpoint_patterns = [
                        r'["\']https?://[^"\']*/(?:api|sprav|business)[^"\']*/(?:posts|news|publications|публикац|новост)[^"\']*["\']',
                        r'["\']/api/[^"\']*/(?:posts|news|publications)[^"\']*["\']',
                        r'["\']/sprav/[^"\']*/(?:posts|news|publications)[^"\']*["\']',
                        r'["\']/business/[^"\']*/(?:posts|news|publications)[^"\']*["\']',
                        r'url["\']?\s*[:=]\s*["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']',
                        r'endpoint["\']?\s*[:=]\s*["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']',
                        r'apiUrl["\']?\s*[:=]\s*["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']',
                        r'fetch\(["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']',
                        r'axios\.(?:get|post)\(["\']([^"\']*/(?:posts|news|publications)[^"\']*)["\']',
                    ]
                    found_endpoints = []
                    for pattern in api_endpoint_patterns:
                        matches = re.findall(pattern, html_content, re.IGNORECASE)
                        if matches:
                            found_endpoints.extend(matches)
                    
                    if found_endpoints:
                        unique_endpoints = list(set(found_endpoints))[:10]  # Первые 10 уникальных
                        print(f"   🔍 Найдены потенциальные API endpoints в Response:")
                        for ep in unique_endpoints:
                            print(f"      - {ep}")
                        
                        # Автоматически пробуем найденные endpoints, если они полные URL
                        for endpoint in unique_endpoints:
                            # Проверяем, что это полный URL (начинается с http)
                            if endpoint.startswith('http://') or endpoint.startswith('https://'):
                                full_url = endpoint
                            elif endpoint.startswith('/'):
                                # Относительный путь - делаем полный URL
                                full_url = f"https://yandex.ru{endpoint}"
                            else:
                                # Пропускаем неполные пути
                                continue
                            
                            print(f"   🚀 Пробуем найденный endpoint: {full_url}")
                            try:
                                delay = random.uniform(0.5, 1.5)
                                time.sleep(delay)
                                endpoint_response = self.session.get(full_url, headers=sidebar_headers, timeout=15)
                                if endpoint_response.status_code == 200:
                                    try:
                                        endpoint_data = endpoint_response.json()
                                        if endpoint_data and (isinstance(endpoint_data, dict) or isinstance(endpoint_data, list)):
                                            # Проверяем, есть ли там посты
                                            if isinstance(endpoint_data, list) and len(endpoint_data) > 0:
                                                # Если это список, проверяем первый элемент
                                                if isinstance(endpoint_data[0], dict) and any(k in endpoint_data[0] for k in ['title', 'text', 'content', 'published_at']):
                                                    result = {"posts": endpoint_data} if not isinstance(endpoint_data, dict) else endpoint_data
                                                    working_url = full_url
                                                    print(f"   ✅ Успешно получены данные с найденного endpoint!")
                                                    break
                                            elif isinstance(endpoint_data, dict):
                                                # Проверяем, есть ли ключи, связанные с постами
                                                if any(k in endpoint_data for k in ['posts', 'publications', 'news', 'items', 'data']):
                                                    result = endpoint_data
                                                    working_url = full_url
                                                    print(f"   ✅ Успешно получены данные с найденного endpoint!")
                                                    break
                                    except json.JSONDecodeError:
                                        # Не JSON, пропускаем
                                        pass
                            except Exception as e:
                                print(f"   ⚠️ Ошибка при запросе к найденному endpoint {full_url}: {e}")
                                continue
                    
                    # Сохраняем сырой ответ для отладки (первые 5000 символов)
                    debug_sample = html_content[:5000]
                    print(f"   📝 Первые 5000 символов ответа:")
                    print(f"   {debug_sample[:500]}...")
                    
                    # Ищем любые упоминания URL в ответе (для более широкого поиска)
                    all_urls = re.findall(r'https?://[^\s"\'<>)]+', html_content[:20000])
                    post_related_urls = [url for url in all_urls if any(word in url.lower() for word in ['post', 'publication', 'news', 'публикац', 'новост', 'api', 'sprav'])]
                    if post_related_urls:
                        unique_urls = list(set(post_related_urls))[:15]
                        print(f"   🔍 Найдены URL, связанные с постами/API:")
                        for url in unique_urls:
                            print(f"      - {url[:100]}")
                    
                    # Ищем window.__INITIAL__.sidebar в JavaScript коде
                    import re
                    initial_patterns = [
                        # Приоритет 1: window.__INITIAL__.sidebar = {...} (многострочное присваивание)
                        r'window\.__INITIAL__\s*=\s*window\.__INITIAL__\s*\|\|\s*\{\};\s*window\.__INITIAL__\.sidebar\s*=\s*({.+?});',
                        # Приоритет 2: window.__INITIAL__.sidebar = {...} (однострочное)
                        r'window\.__INITIAL__\.sidebar\s*=\s*({.+?});',
                        # Приоритет 3: const STATE = {...}
                        r'const\s+STATE\s*=\s*({.+?});',
                        # Приоритет 4: window.__INITIAL__ = {...}
                        r'window\.__INITIAL__\s*=\s*({.+?});',
                        # Приоритет 5: __INITIAL__ = {...} (без window.)
                        r'__INITIAL__\s*=\s*({.+?});',
                        # Приоритет 6: Альтернативные варианты
                        r'__INITIAL_STATE__\s*=\s*({.+?});',
                        r'window\.__DATA__\s*=\s*({.+?});',
                    ]
                    
                    for pattern_idx, pattern in enumerate(initial_patterns):
                        match = re.search(pattern, html_content, re.DOTALL)
                        if match:
                            try:
                                json_str = match.group(1)
                                print(f"   🔍 Паттерн #{pattern_idx + 1} найден, длина JSON: {len(json_str)} символов")
                                
                                # Пробуем распарсить JSON
                                initial_data = json.loads(json_str)
                                print(f"   ✅ Успешно распарсен JSON из паттерна #{pattern_idx + 1}")
                                
                                # Извлекаем sidebar данные
                                if isinstance(initial_data, dict):
                                    # Если это STATE, ищем company или другие ключи
                                    if "company" in initial_data or "tld" in initial_data:
                                        # Это STATE объект, ищем посты внутри него
                                        print(f"   📊 Найден STATE объект, ищем посты внутри...")
                                        # STATE может содержать посты в разных местах
                                        sidebar_data = (
                                            initial_data.get("sidebar") or
                                            initial_data.get("posts") or
                                            initial_data.get("publications") or
                                            initial_data.get("news") or
                                            initial_data.get("data") or
                                            initial_data  # Если весь объект - это данные
                                        )
                                    else:
                                        # Пробуем разные пути к данным
                                        sidebar_data = (
                                            initial_data.get("sidebar") or 
                                            initial_data.get("data") or
                                            initial_data.get("posts") or
                                            initial_data.get("publications") or
                                            initial_data.get("news") or
                                            initial_data  # Если весь объект - это данные
                                        )
                                    
                                    if sidebar_data:
                                        result = sidebar_data if isinstance(sidebar_data, dict) else {"data": sidebar_data}
                                        working_url = sidebar_url
                                        print(f"   ✅ Извлечены данные sidebar из JavaScript")
                                        print(f"   📊 Структура данных: {list(result.keys())[:10] if isinstance(result, dict) else type(result)}")
                                        # Показываем ключи, связанные с постами
                                        if isinstance(result, dict):
                                            post_keys = [k for k in result.keys() if any(word in k.lower() for word in ['post', 'publication', 'news', 'публикац', 'новост'])]
                                            if post_keys:
                                                print(f"   🔍 Найдены ключи, связанные с постами: {post_keys}")
                                        break
                            except json.JSONDecodeError as e:
                                # Пробуем найти JSON более гибко - ищем незакрытые скобки
                                try:
                                    # Ищем JSON объект, который может быть неполным из-за вложенности
                                    # Пробуем найти баланс скобок (учитываем строки и экранирование)
                                    bracket_count = 0
                                    json_end = 0
                                    in_string = False
                                    escape_next = False
                                    
                                    for i, char in enumerate(json_str):
                                        if escape_next:
                                            escape_next = False
                                            continue
                                        
                                        if char == '\\':
                                            escape_next = True
                                            continue
                                        
                                        if char == '"' and not escape_next:
                                            in_string = not in_string
                                            continue
                                        
                                        if not in_string:
                                            if char == '{':
                                                bracket_count += 1
                                            elif char == '}':
                                                bracket_count -= 1
                                                if bracket_count == 0:
                                                    json_end = i + 1
                                                    break
                                    
                                    if json_end > 0 and json_end < len(json_str):
                                        balanced_json = json_str[:json_end]
                                        initial_data = json.loads(balanced_json)
                                        print(f"   ✅ Найден сбалансированный JSON (длина: {len(balanced_json)})")
                                        
                                        if isinstance(initial_data, dict):
                                            # Если это STATE, ищем посты внутри
                                            if "company" in initial_data or "tld" in initial_data:
                                                sidebar_data = (
                                                    initial_data.get("sidebar") or
                                                    initial_data.get("posts") or
                                                    initial_data.get("publications") or
                                                    initial_data.get("news") or
                                                    initial_data.get("data") or
                                                    initial_data
                                                )
                                            else:
                                                sidebar_data = (
                                                    initial_data.get("sidebar") or 
                                                    initial_data.get("data") or
                                                    initial_data.get("posts") or
                                                    initial_data.get("publications") or
                                                    initial_data.get("news") or
                                                    initial_data
                                                )
                                            if sidebar_data:
                                                result = sidebar_data if isinstance(sidebar_data, dict) else {"data": sidebar_data}
                                                working_url = sidebar_url
                                                print(f"   ✅ Извлечены данные sidebar (сбалансированный JSON)")
                                                break
                                    
                                    # Если не получилось, пробуем найти JSON с постами напрямую
                                    json_match = re.search(r'\{.*?["\']posts["\']\s*:\s*\[.*?\].*?\}', json_str, re.DOTALL)
                                    if json_match:
                                        initial_data = json.loads(json_match.group(0))
                                        if "posts" in initial_data or "publications" in initial_data or "news" in initial_data:
                                            result = initial_data
                                            working_url = sidebar_url
                                            print(f"   ✅ Найден JSON с постами (частичный парсинг)")
                                            break
                                except Exception as e2:
                                    print(f"   ⚠️ Не удалось распарсить JSON даже после балансировки: {e2}")
                                    pass
                                continue
                            except Exception as e:
                                print(f"   ⚠️ Ошибка при парсинге паттерна #{pattern_idx + 1}: {e}")
                                continue
                    
                    if not result:
                        print(f"⚠️ Не удалось извлечь данные из HTML/JavaScript sidebar API")
                        # Пробуем найти любые JSON объекты в тексте
                        print(f"   🔍 Пробуем найти любые JSON объекты в ответе...")
                        json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', html_content[:10000], re.DOTALL)
                        print(f"   📊 Найдено потенциальных JSON объектов: {len(json_objects)}")
                        for idx, json_obj in enumerate(json_objects[:5]):  # Проверяем первые 5
                            try:
                                parsed = json.loads(json_obj)
                                if isinstance(parsed, dict):
                                    # Проверяем, есть ли что-то связанное с постами
                                    keys_str = str(list(parsed.keys())).lower()
                                    if any(word in keys_str for word in ['post', 'publication', 'news', 'публикац', 'новост']):
                                        print(f"   ✅ Найден JSON объект #{idx + 1} с ключами, связанными с постами: {list(parsed.keys())[:5]}")
                                        result = parsed
                                        working_url = sidebar_url
                                        break
                            except:
                                pass
                else:
                    print(f"⚠️ Sidebar API вернул неожиданный Content-Type: {content_type}")
            else:
                print(f"⚠️ Sidebar API вернул статус {response.status_code}, пробуем HTML страницу...")
                result = None
        except Exception as e:
            print(f"⚠️ Ошибка запроса к sidebar API: {e}, пробуем HTML страницу...")
            result = None
        
        if not result:
            # Пробуем через _make_request как fallback (может вернуть HTML)
            response_data = self._make_request(sidebar_url)
            if response_data:
                # Если это строка (HTML), пробуем извлечь из неё
                if isinstance(response_data, str):
                    html_content = response_data
                    import re
                    match = re.search(r'window\.__INITIAL__\.sidebar\s*=\s*({.+?});', html_content, re.DOTALL)
                    if match:
                        try:
                            result = json.loads(match.group(1))
                            working_url = sidebar_url
                            print(f"✅ Успешно извлечены данные из sidebar API (через _make_request + парсинг HTML)")
                        except:
                            result = None
                else:
                    result = response_data
                    working_url = sidebar_url
                    print(f"✅ Успешно получены данные из sidebar API (через _make_request)")
        
        # Пробуем извлечь данные из HTML страницы (приоритет - здесь реальные посты)
        print(f"🔍 Пробуем получить посты/новости из HTML страницы...")
        posts_page_url = f"https://yandex.ru/sprav/{external_id}/p/edit/posts/"
        
        # Делаем запрос к HTML странице
        html_parsed = False
        html_posts = []  # Объявляем вне try блока
        
        try:
            delay = random.uniform(1.5, 3.5)
            time.sleep(delay)
            
            # Обновляем headers для получения HTML (не JSON)
            html_headers = {
                **self.session_headers,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            
            response = self.session.get(posts_page_url, headers=html_headers, timeout=30)
            response.raise_for_status()
            html_content = response.text
            
            # Пытаемся извлечь window.__INITIAL__.sidebar из HTML
            # Ищем паттерн window.__INITIAL__ = {...} или window.__INITIAL__.sidebar = {...}
            # Также ищем другие варианты: __INITIAL_STATE__, __DATA__, window.__DATA__
            initial_patterns = [
                r'window\.__INITIAL__\s*=\s*({.+?});',
                r'window\.__INITIAL__\.sidebar\s*=\s*({.+?});',
                r'__INITIAL__\.sidebar\s*=\s*({.+?});',
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                r'window\.__DATA__\s*=\s*({.+?});',
                r'__DATA__\s*=\s*({.+?});',
                # Ищем JSON в script тегах
                r'<script[^>]*>.*?({["\']posts["\']\s*:\s*\[.*?\]|["\']publications["\']\s*:\s*\[.*?\]|["\']news["\']\s*:\s*\[.*?\]}).*?</script>',
            ]
            
            for pattern in initial_patterns:
                match = re.search(pattern, html_content, re.DOTALL)
                if match:
                    try:
                        import json
                        json_str = match.group(1)
                        # Пробуем распарсить JSON
                        initial_data = json.loads(json_str)
                        print(f"   ✅ Найден window.__INITIAL__ в HTML")
                        
                        # Ищем sidebar в initial_data
                        sidebar_data = None
                        if isinstance(initial_data, dict):
                            sidebar_data = (
                                initial_data.get("sidebar") or 
                                initial_data.get("data") or
                                initial_data.get("posts") or
                                initial_data.get("publications") or
                                initial_data.get("news")
                            )
                        
                        if sidebar_data:
                            print(f"   ✅ Найден sidebar/data в window.__INITIAL__")
                            result = sidebar_data if isinstance(sidebar_data, dict) else {"data": sidebar_data}
                            html_parsed = True
                            break
                    except json.JSONDecodeError as e:
                        # Пробуем найти JSON более гибко
                        try:
                            # Ищем JSON объект, который может быть неполным
                            json_match = re.search(r'\{.*?["\']posts["\']\s*:\s*\[.*?\].*?\}', json_str, re.DOTALL)
                            if json_match:
                                initial_data = json.loads(json_match.group(0))
                                if "posts" in initial_data or "publications" in initial_data or "news" in initial_data:
                                    result = initial_data
                                    html_parsed = True
                                    print(f"   ✅ Найден JSON с постами (частичный парсинг)")
                                    break
                        except:
                            pass
                        print(f"   ⚠️ Не удалось распарсить JSON из window.__INITIAL__: {e}")
                        continue
                    except Exception as e:
                        print(f"   ⚠️ Ошибка при извлечении window.__INITIAL__: {e}")
                        continue
            
            # Парсим HTML с помощью BeautifulSoup (приоритет - здесь реальные посты)
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                print(f"   ✅ BeautifulSoup установлен, парсим HTML...")
                
                # Ищем реальные посты по селектору .Post (из структуры страницы)
                post_elements = soup.select('div.Post')
                print(f"   🔍 Найдено элементов .Post: {len(post_elements)}")
                if post_elements:
                    print(f"   ✅ Найдено постов в HTML: {len(post_elements)}")
                    # html_posts уже объявлен выше
                    html_posts.clear()  # Очищаем, если был заполнен ранее
                    
                    for idx, post_elem in enumerate(post_elements):
                            try:
                                # Извлекаем заголовок (название организации)
                                title_elem = post_elem.select_one('.Post-Title')
                                title = title_elem.get_text(strip=True) if title_elem else None
                                
                                # Извлекаем текст поста
                                text_elem = post_elem.select_one('.Post-Text, .PostText')
                                text = text_elem.get_text(strip=True) if text_elem else None
                                
                                # Извлекаем дату публикации
                                date_elem = post_elem.select_one('.Post-Hint')
                                date_str = date_elem.get_text(strip=True) if date_elem else None
                                
                                # Парсим дату (формат: "15.12.2025, 19:49")
                                published_at = None
                                if date_str:
                                    try:
                                        # Пробуем разные форматы даты
                                        date_formats = [
                                            "%d.%m.%Y, %H:%M",
                                            "%d.%m.%Y",
                                            "%Y-%m-%d %H:%M:%S",
                                        ]
                                        for fmt in date_formats:
                                            try:
                                                published_at = datetime.strptime(date_str, fmt)
                                                break
                                            except:
                                                continue
                                    except:
                                        pass
                                
                                # Извлекаем изображение
                                image_url = None
                                img_elem = post_elem.select_one('.PostPhotos .Thumb-Image, .PostPhotos img')
                                if img_elem:
                                    image_url = img_elem.get('src') or img_elem.get('style', '')
                                    # Извлекаем URL из style="background-image: url(...)"
                                    if 'background-image' in image_url:
                                        match = re.search(r'url\(["\']?([^"\']+)["\']?\)', image_url)
                                        if match:
                                            image_url = match.group(1)
                                
                                # Если есть хотя бы текст или заголовок - это пост
                                if text or title:
                                    # Generates stable ID
                                    import hashlib
                                    id_str = f"{title or ''}_{date_str or ''}_{text[:20] if text else ''}"
                                    post_hash = hashlib.md5(id_str.encode()).hexdigest()
                                    
                                    html_posts.append({
                                        "id": f"html_post_{post_hash}",
                                        "title": title,
                                        "text": text,
                                        "published_at": published_at.isoformat() if published_at else None,
                                        "date": date_str,
                                        "image_url": image_url,
                                    })
                                    print(f"      Пост #{idx + 1}: {title or 'Без заголовка'} - {text[:50] if text else 'Без текста'}...")
                            except Exception as e:
                                print(f"      ⚠️ Ошибка парсинга поста #{idx + 1}: {e}")
                                continue
                    
                    if html_posts:
                        posts_data = html_posts
                        result = {"posts": html_posts}
                        html_parsed = True
                        print(f"   ✅ Успешно извлечено {len(html_posts)} постов из HTML")
                
                # Если не нашли посты, ищем количество постов
                if not html_posts:
                    for selector in ['.PostsPage-Description', '.NewsPage-Description', '[class*="PostsPage"]', '[class*="NewsPage"]', '[class*="post"]', '[class*="news"]']:
                        elements = soup.select(selector)
                        for elem in elements:
                            text = elem.get_text()
                            # Ищем паттерны типа "5 новостей" или "5 публикаций"
                            match = re.search(r'(\d+)\s*(?:новост|публикац|пост|news|post)', text, re.IGNORECASE)
                            if match:
                                posts_count = int(match.group(1))
                                print(f"   ✅ Найдено количество постов/новостей (селектор {selector}): {posts_count}")
                                html_parsed = True
                                break
                        if html_parsed:
                            break
            except ImportError:
                # Если BeautifulSoup не установлен, используем регулярные выражения
                print(f"   ⚠️ BeautifulSoup не установлен, используем регулярные выражения")
                # Ищем паттерны типа "5 новостей" или "5 публикаций" в HTML
                post_count_patterns = [
                    r'(\d+)\s*(?:новост|публикац|пост|news|post)',
                    r'(?:новост|публикац|пост|news|post)[^0-9]*(\d+)',
                ]
                for pattern in post_count_patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    if matches:
                        try:
                            posts_count = max(int(m) for m in matches)
                            print(f"   ✅ Найдено количество постов/новостей (regex): {posts_count}")
                            html_parsed = True
                            break
                        except:
                            pass
            except Exception as e:
                print(f"   ⚠️ Ошибка при парсинге HTML: {e}")
            
        except Exception as e:
            print(f"   ⚠️ Ошибка при запросе HTML страницы: {e}")
        
        # Если нашли посты в HTML, используем их (приоритет над sidebar)
        if html_posts:
            posts_data = html_posts
            result = {"posts": html_posts}
            print(f"✅ Используем посты из HTML страницы: {len(posts_data)} постов")
        
        # Если не получили данные, пробуем другие API endpoints (предположения)
        if not result and not html_posts:
            print(f"⚠️ Не удалось получить данные из sidebar/HTML, пробуем другие API endpoints (предположения)...")
            possible_urls = [
                # Правильный endpoint по аналогии с price-lists
                f"https://yandex.ru/sprav/api/company/{external_id}/posts",
                f"https://yandex.ru/sprav/api/company/{external_id}/news",
                f"https://yandex.ru/sprav/api/company/{external_id}/publications",
                # Старые варианты (на случай если правильный не работает)
                f"https://yandex.ru/sprav/api/{external_id}/posts",
                f"https://yandex.ru/sprav/api/{external_id}/news",
                f"https://yandex.ru/sprav/api/{external_id}/publications",
                f"https://yandex.ru/sprav/{external_id}/p/edit/posts/api",
            ]
            
            for url in possible_urls:
                print(f"🔍 Пробуем endpoint постов (предположение): {url}")
                
                # Имитация человека: случайная задержка перед запросом
                delay = random.uniform(1.5, 3.5)
                time.sleep(delay)
                
                result = self._make_request(url)
                if result:
                    working_url = url
                    print(f"✅ Успешно получены данные постов с {url}")
                    break
        
        if not result:
            print(f"❌ Не удалось получить посты для {business_id} ни с одного endpoint")
            print(f"   Возможные причины:")
            print(f"   1. Cookies устарели - обновите их в админской панели")
            print(f"   2. Сессия истекла (401 NEED_RESET)")
            print(f"   3. API endpoint изменился - проверьте через DevTools → Network tab")
            return []
        
        # Парсим структуру ответа
        # Возможные варианты для sidebar: 
        # - {"posts": [...]}, {"publications": [...]}, {"news": [...]}
        # - {"data": {"posts": [...]}}, {"data": {"publications": [...]}}
        # - {"list": {"items": [...]}}
        # - Вложенные структуры внутри sidebar
        posts_data = []
        
        # Рекурсивная функция для поиска постов в структуре
        def find_posts_in_structure(obj, path="", depth=0, max_depth=10):
            """Рекурсивно ищет массив постов в структуре данных"""
            if depth > max_depth:
                return None
                
            if isinstance(obj, list):
                # Если это список, проверяем, похож ли он на список постов
                if len(obj) > 0 and isinstance(obj[0], dict):
                    # Проверяем, есть ли в первом элементе типичные поля поста
                    first_item = obj[0]
                    post_fields = ["id", "title", "text", "content", "published_at", "created_at", "date", "name", "header", "message", "body", "description"]
                    # Также проверяем ключи, связанные с постами в названии
                    post_indicators = ["post", "publication", "news", "публикац", "новост"]
                    key_names = [k.lower() for k in first_item.keys()]
                    
                    has_post_fields = any(field in first_item for field in post_fields)
                    has_post_indicators = any(any(indicator in key for indicator in post_indicators) for key in key_names)
                    
                    # ИСКЛЮЧАЕМ метаданные - если это factors или другие метаданные структуры
                    metadata_indicators_in_path = ["factors", "counters", "extensions", "companyBonus", "leds", "accounts", "rubricsInfo"]
                    is_metadata_path = any(indicator in path.lower() for indicator in metadata_indicators_in_path)
                    
                    # Также проверяем содержимое - если только метаданные ключи, это не посты
                    metadata_keys_in_item = ["strength", "active", "status", "days_from_update", "isMain", "rubricId"]
                    has_only_metadata = all(key in metadata_keys_in_item or key in ["name"] for key in first_item.keys() if key not in post_fields)
                    
                    if (has_post_fields or has_post_indicators) and not is_metadata_path and not has_only_metadata:
                        print(f"   ✅ Найден массив постов в {path} (проверено {len(obj)} элементов)")
                        return obj
                    elif is_metadata_path or has_only_metadata:
                        print(f"   ⚠️ Пропущен массив в {path} - это метаданные, не посты")
                return None
            elif isinstance(obj, dict):
                # ИСКЛЮЧАЕМ известные структуры метаданных
                metadata_structures = ["factors", "counters", "extensions", "companyBonus", "leds", "accounts", "company", "rubricsInfo"]
                
                # Проверяем прямые ключи (приоритет)
                priority_keys = ["posts", "publications", "news", "items", "list", "data"]
                for key in priority_keys:
                    if key in obj:
                        found = find_posts_in_structure(obj[key], f"{path}.{key}" if path else key, depth + 1, max_depth)
                        if found:
                            return found
                
                # Проверяем ключи, содержащие слова, связанные с постами
                post_related_keys = [k for k in obj.keys() if any(word in k.lower() for word in ['post', 'publication', 'news', 'публикац', 'новост', 'публик'])]
                for key in post_related_keys:
                    found = find_posts_in_structure(obj[key], f"{path}.{key}" if path else key, depth + 1, max_depth)
                    if found:
                        print(f"   ✅ Найдены посты через ключ '{key}' в {path}")
                        return found
                
                # Проверяем вложенные структуры (если не нашли в приоритетных ключах)
                # НО пропускаем структуры метаданных
                for key, value in obj.items():
                    # Пропускаем метаданные
                    if key in metadata_structures:
                        continue
                    # Пропускаем, если путь содержит метаданные (например, "factors.factors")
                    if "factors" in path.lower() or "counter" in path.lower():
                        continue
                    
                    if isinstance(value, (dict, list)) and key not in priority_keys:
                        found = find_posts_in_structure(value, f"{path}.{key}" if path else key, depth + 1, max_depth)
                        if found:
                            return found
            return None
        
        # Ищем посты в структуре
        posts_data = find_posts_in_structure(result) or []
        
        # Если не нашли рекурсивно, пробуем стандартные пути
        if not posts_data:
            if isinstance(result, list):
                posts_data = result
            elif "list" in result and isinstance(result["list"], dict):
                if "items" in result["list"]:
                    posts_data = result["list"]["items"]
            elif "posts" in result:
                posts_data = result["posts"] if isinstance(result["posts"], list) else []
            elif "publications" in result:
                posts_data = result["publications"] if isinstance(result["publications"], list) else []
            elif "news" in result:
                posts_data = result["news"] if isinstance(result["news"], list) else []
            elif "data" in result:
                if isinstance(result["data"], list):
                    posts_data = result["data"]
                elif isinstance(result["data"], dict):
                    posts_data = result["data"].get("posts") or result["data"].get("publications") or result["data"].get("news") or []
            
            # Дополнительные варианты поиска в sidebar структуре
            if not posts_data and isinstance(result, dict):
                # Пробуем найти в компонентах sidebar
                for key in ["components", "widgets", "blocks", "sections", "content"]:
                    if key in result and isinstance(result[key], dict):
                        nested_posts = result[key].get("posts") or result[key].get("publications") or result[key].get("news")
                        if nested_posts and isinstance(nested_posts, list):
                            posts_data = nested_posts
                            print(f"   ✅ Найдены посты в {key}")
                            break
                
                # Пробуем найти в любых вложенных объектах, которые содержат массивы
                if not posts_data:
                    def find_any_posts_array(obj, depth=0, max_depth=5):
                        """Ищет любой массив, похожий на список постов"""
                        if depth > max_depth:
                            return None
                        if isinstance(obj, list) and len(obj) > 0:
                            first = obj[0]
                            if isinstance(first, dict):
                                # Проверяем, есть ли типичные поля поста
                                post_indicators = ["title", "text", "content", "published_at", "created_at", "date", "header", "message", "body"]
                                # Исключаем метаданные - это НЕ посты
                                metadata_indicators = ["working_intervals", "urls", "phone", "photos", "price_lists", "logo", "features", "english_name", "strength", "active", "status", "days_from_update"]
                                
                                # Проверяем, что это НЕ метаданные
                                has_metadata = any(indicator in first for indicator in metadata_indicators)
                                if has_metadata:
                                    return None  # Это метаданные, не посты
                                
                                # Проверяем, что это похоже на пост
                                has_post_fields = any(indicator in first for indicator in post_indicators)
                                if has_post_fields:
                                    return obj
                        elif isinstance(obj, dict):
                            # Пропускаем известные структуры метаданных
                            skip_keys = ["factors", "counters", "extensions", "companyBonus", "leds", "accounts", "company"]
                            for key, value in obj.items():
                                if key in skip_keys:
                                    continue  # Пропускаем метаданные
                                found = find_any_posts_array(value, depth + 1, max_depth)
                                if found:
                                    return found
                        return None
                    
                    found_posts = find_any_posts_array(result)
                    if found_posts:
                        posts_data = found_posts
                        print(f"   ✅ Найдены посты через глубокий поиск")
        
        print(f"📊 Найдено постов в ответе: {len(posts_data)}")
        
        # Если список пустой, пробуем найти посты в HTML странице напрямую
        if not posts_data:
            print(f"⚠️ Посты не найдены в sidebar ответе, пробуем парсить HTML страницу напрямую...")
            try:
                posts_page_url = f"https://yandex.ru/sprav/{external_id}/p/edit/posts/"
                delay = random.uniform(1.5, 3.5)
                time.sleep(delay)
                
                html_headers = {
                    **self.session_headers,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
                
                response = self.session.get(posts_page_url, headers=html_headers, timeout=30)
                if response.status_code == 200:
                    html_content = response.text
                    
                    # Ищем все возможные упоминания постов в HTML
                    # Ищем fetch/axios вызовы к API endpoints
                    import re
                    api_calls = re.findall(r'(?:fetch|axios\.(?:get|post))\(["\']([^"\']*/(?:posts|publications|news|публикац|новост)[^"\']*)["\']', html_content, re.IGNORECASE)
                    if api_calls:
                        print(f"   🔍 Найдены API вызовы для постов: {api_calls[:5]}")
                        # Пробуем вызвать найденные endpoints
                        for api_url in api_calls[:3]:  # Пробуем первые 3
                            if not api_url.startswith('http'):
                                if api_url.startswith('/'):
                                    api_url = f"https://yandex.ru{api_url}"
                                else:
                                    api_url = f"https://yandex.ru/sprav/{external_id}/{api_url}"
                            
                            print(f"   🚀 Пробуем endpoint: {api_url}")
                            try:
                                delay = random.uniform(0.5, 1.5)
                                time.sleep(delay)
                                api_response = self.session.get(api_url, headers=html_headers, timeout=15)
                                if api_response.status_code == 200:
                                    try:
                                        api_data = api_response.json()
                                        if isinstance(api_data, (dict, list)):
                                            # Проверяем, есть ли там посты
                                            if isinstance(api_data, list) and len(api_data) > 0:
                                                if isinstance(api_data[0], dict) and any(k in api_data[0] for k in ['title', 'text', 'content', 'published_at']):
                                                    posts_data = api_data
                                                    print(f"   ✅ Найдены посты через API endpoint!")
                                                    break
                                            elif isinstance(api_data, dict):
                                                if any(k in api_data for k in ['posts', 'publications', 'news', 'items']):
                                                    posts_data = api_data.get('posts') or api_data.get('publications') or api_data.get('news') or api_data.get('items') or []
                                                    if posts_data:
                                                        print(f"   ✅ Найдены посты через API endpoint!")
                                                        break
                                    except json.JSONDecodeError:
                                        pass
                            except Exception as e:
                                print(f"   ⚠️ Ошибка при запросе к {api_url}: {e}")
                                continue
            except Exception as e:
                print(f"   ⚠️ Ошибка при парсинге HTML страницы: {e}")
        
        # Если список пустой, выводим структуру для отладки
        if not posts_data:
            print(f"⚠️ Список постов пуст. Структура ответа:")
            print(f"   Тип: {type(result)}")
            if isinstance(result, dict):
                print(f"   Ключи верхнего уровня: {list(result.keys())[:30]}")
                
                # Показываем все ключи, которые могут содержать посты (даже вложенные)
                def find_all_post_keys(obj, path="", depth=0, max_depth=3):
                    keys = []
                    if depth > max_depth:
                        return keys
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if any(word in key.lower() for word in ['post', 'publication', 'news', 'публикац', 'новост']):
                                keys.append(f"{path}.{key}" if path else key)
                            if isinstance(value, (dict, list)) and depth < max_depth:
                                keys.extend(find_all_post_keys(value, f"{path}.{key}" if path else key, depth + 1, max_depth))
                    return keys
                
                all_post_keys = find_all_post_keys(result)
                if all_post_keys:
                    print(f"   🔍 Найдены ключи, связанные с постами (включая вложенные): {all_post_keys[:20]}")
                
                # Ищем любые ключи, связанные с постами/новостями
                post_related_keys = [k for k in result.keys() if any(word in k.lower() for word in ['post', 'publication', 'news', 'публикац', 'новост', 'публик'])]
                if post_related_keys:
                    print(f"   🔍 Найдены ключи, связанные с постами: {post_related_keys}")
                    for key in post_related_keys:
                        value = result[key]
                        value_str = str(value)[:200] if not isinstance(value, (dict, list)) else f'{type(value).__name__} с {len(value) if isinstance(value, (list, dict)) else "данными"}'
                        print(f"      {key}: тип={type(value)}, значение={value_str}")
                
                # Показываем первые 3000 символов JSON для отладки
                result_str = json.dumps(result, ensure_ascii=False, indent=2)[:3000]
                print(f"   Первые 3000 символов JSON:\n{result_str}...")
                
                # Также пробуем найти любые вложенные массивы
                def find_arrays(obj, path="", max_depth=4):
                    """Находит все массивы в структуре для отладки"""
                    arrays = []
                    if isinstance(obj, list):
                        arrays.append((path, len(obj), type(obj[0]).__name__ if obj and len(obj) > 0 else "empty"))
                    elif isinstance(obj, dict) and max_depth > 0:
                        for key, value in obj.items():
                            arrays.extend(find_arrays(value, f"{path}.{key}" if path else key, max_depth - 1))
                    return arrays
                arrays = find_arrays(result)
                if arrays:
                    print(f"   Найдены массивы в структуре:")
                    for arr_path, arr_len, arr_type in arrays[:15]:
                        print(f"      {arr_path}: {arr_len} элементов (тип: {arr_type})")
                        
                        # Если это массив с постами, показываем структуру первого элемента
                        if arr_len > 0 and any(word in arr_path.lower() for word in ['post', 'publication', 'news', 'публикац', 'новост']):
                            arr_value = result
                            for part in arr_path.split('.'):
                                if isinstance(arr_value, dict):
                                    arr_value = arr_value.get(part)
                                elif isinstance(arr_value, list) and part.isdigit():
                                    arr_value = arr_value[int(part)]
                                else:
                                    break
                            if isinstance(arr_value, list) and len(arr_value) > 0:
                                first_item = arr_value[0]
                                if isinstance(first_item, dict):
                                    print(f"         Структура первого элемента: {list(first_item.keys())[:10]}")
        
        # Парсим посты
        for idx, post_data in enumerate(posts_data):
            # Пропускаем метаданные - проверяем, что это действительно пост
            # Но НЕ пропускаем, если есть хотя бы одно поле поста
            metadata_keys = ["working_intervals", "urls", "phone", "photos", "price_lists", "logo", "features", "english_name", "strength", "active", "status", "days_from_update"]
            post_fields = ["title", "text", "content", "published_at", "created_at", "header", "message", "body", "description"]
            
            # Если есть поля поста - это пост, даже если есть метаданные
            has_post_fields = any(key in post_data for key in post_fields)
            
            # Пропускаем ТОЛЬКО если это чисто метаданные (нет полей поста) И есть специфичные метаданные
            if not has_post_fields:
                # Проверяем, не является ли это метаданными
                is_metadata = any(key in post_data for key in metadata_keys) and len(post_data) <= 3
                if is_metadata:
                    print(f"   ⚠️ Пропущен элемент #{idx + 1} - это метаданные, не пост: {list(post_data.keys())[:5]}")
                    continue
            
            post_id = post_data.get("id") or f"{business_id}_post_{idx}"
            try:
                published_at_str = post_data.get("published_at") or post_data.get("created_at") or post_data.get("date")
                published_at = None
                if published_at_str:
                    try:
                        published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                    except:
                        pass
                
                # Парсим заголовок и текст
                title = post_data.get("title") or post_data.get("name") or post_data.get("header")
                text = post_data.get("text") or post_data.get("content") or post_data.get("message") or post_data.get("description")
                
                # Если нет ни заголовка, ни текста - это не пост
                if not title and not text:
                    print(f"   ⚠️ Пропущен элемент #{idx + 1} - нет заголовка и текста")
                    continue
                
                # Парсим изображение
                image_url = None
                image_data = post_data.get("image") or post_data.get("photo") or post_data.get("image_url")
                if isinstance(image_data, dict):
                    image_url = image_data.get("url") or image_data.get("src") or image_data.get("original")
                elif isinstance(image_data, str):
                    image_url = image_data
                
                post = ExternalPost(
                    id=f"{business_id}_yandex_business_post_{post_id}",
                    business_id=business_id,
                    source="yandex_business",
                    external_post_id=post_id,
                    title=title,
                    text=text,
                    published_at=published_at,
                    image_url=image_url,
                    raw_payload=post_data,
                )
                posts.append(post)
            except Exception as e:
                print(f"⚠️ Ошибка парсинга поста {post_id}: {e}")
                continue
        
        if not posts:
            print("[fetch_posts] API returned empty, trying HTML fallback...")
            posts = self._fetch_posts_from_html(account_row)

        print(f"✅ Получено постов: {len(posts)}")
        return posts

    def _fetch_posts_from_html(self, account_row: dict) -> List[ExternalPost]:
        """Парсит посты из HTML страницы /p/edit/posts/."""
        business_id = account_row["business_id"]
        external_id = account_row.get("external_id")
        if not external_id:
            return []

        url = f"https://yandex.ru/sprav/{external_id}/p/edit/posts/"
        headers = {
            **self.session_headers,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")
            post_elements = soup.select("div.Post")
            html_posts: List[ExternalPost] = []
            for idx, post_elem in enumerate(post_elements):
                title_el = post_elem.select_one(".Post-Title")
                text_el = post_elem.select_one(".Post-Text, .PostText")
                date_el = post_elem.select_one(".Post-Hint")

                title = title_el.get_text(strip=True) if title_el else None
                text = text_el.get_text(strip=True) if text_el else None
                if not title and not text:
                    continue

                published_at = None
                date_str = date_el.get_text(strip=True) if date_el else None
                if date_str:
                    try:
                        published_at = datetime.strptime(date_str, "%d.%m.%Y, %H:%M")
                    except Exception:
                        try:
                            published_at = datetime.strptime(date_str, "%d.%m.%Y")
                        except Exception:
                            published_at = None

                external_post_id = f"html_{idx}_{business_id}"
                html_posts.append(
                    ExternalPost(
                        id=f"{business_id}_yandex_business_post_{external_post_id}",
                        business_id=business_id,
                        source="yandex_business",
                        external_post_id=external_post_id,
                        title=title,
                        text=text,
                        published_at=published_at,
                        image_url=None,
                        raw_payload={
                            "title": title,
                            "text": text,
                            "date": date_str,
                            "source": "html_fallback",
                        },
                    )
                )
            if html_posts:
                print(f"[_fetch_posts_from_html] parsed posts: {len(html_posts)}")
            return html_posts
        except Exception as e:
            print(f"[_fetch_posts_from_html] Error: {e}")
            return []

    def fetch_photos_count(self, account_row: dict) -> int:
        """
        Получить только количество фотографий из кабинета Яндекс.Бизнес.
        Не парсим детали каждой фотографии - только общее количество.
        
        Args:
            account_row: Строка из ExternalBusinessAccounts с полями business_id, external_id и т.д.
        
        Returns:
            Количество фотографий (int)
        """
        business_id = account_row["business_id"]
        external_id = account_row.get("external_id")
        
        if not external_id:
            print(f"⚠️ Нет external_id для бизнеса {business_id}")
            return 0
        
        # Endpoint для фотографий
        # URL страницы: https://yandex.ru/sprav/{org_id}/p/edit/photos/
        # 
        # Правильный API endpoint (найден в Network tab):
        # https://yandex.ru/business/server-components/sidebar?permalink={external_id}
        # Тот же endpoint используется и для публикаций/новостей
        
        # Сначала пробуем получить данные из API endpoint sidebar?permalink=...
        # Это реальный endpoint, который видели в Network tab
        print(f"🔍 Пробуем получить количество фотографий из sidebar API endpoint...")
        sidebar_url = f"https://yandex.ru/business/server-components/sidebar?permalink={external_id}"
        
        result = None
        working_url = None
        
        # Пробуем sidebar endpoint (реальный, видели в Network tab)
        delay = random.uniform(1.5, 3.5)
        time.sleep(delay)
        
        result = self._make_request(sidebar_url)
        if result:
            working_url = sidebar_url
            print(f"✅ Успешно получены данные из sidebar API")
            
            # Парсим структуру ответа и ищем количество фотографий
            # Рекурсивно ищем поля: photos_count, total, count, photos (массив)
            def find_photos_count_in_structure(obj, path=""):
                """Рекурсивно ищет количество фотографий в структуре данных"""
                if isinstance(obj, dict):
                    # Проверяем прямые ключи
                    for key in ["photos_count", "total", "count"]:
                        if key in obj and isinstance(obj[key], (int, float)):
                            return int(obj[key])
                    
                    # Проверяем массив фотографий
                    if "photos" in obj and isinstance(obj["photos"], list):
                        return len(obj["photos"])
                    
                    # Проверяем вложенные структуры
                    for key, value in obj.items():
                        if isinstance(value, (dict, list)):
                            found = find_photos_count_in_structure(value, f"{path}.{key}")
                            if found:
                                return found
                elif isinstance(obj, list):
                    # Если это список фотографий, возвращаем его длину
                    if len(obj) > 0:
                        # Проверяем, похож ли первый элемент на фото
                        first_item = obj[0]
                        if isinstance(first_item, dict):
                            photo_fields = ["url", "image", "photo", "src", "original"]
                            if any(field in first_item for field in photo_fields):
                                return len(obj)
                return None
            
            photos_count = find_photos_count_in_structure(result)
            if photos_count is not None:
                print(f"✅ Количество фотографий из sidebar API: {photos_count}")
                return photos_count
            else:
                print(f"⚠️ Не удалось найти количество фотографий в структуре sidebar API")
        
        # Если sidebar API не сработал или не нашёл количество, пробуем HTML страницу
        if not result:
            print(f"⚠️ Не удалось получить данные из sidebar API, пробуем HTML страницу...")
        
        print(f"🔍 Пробуем получить количество фотографий из HTML страницы...")
        photos_page_url = f"https://yandex.ru/sprav/{external_id}/p/edit/photos/"
        
        # Делаем запрос к HTML странице
        html_parsed = False
        try:
            delay = random.uniform(1.5, 3.5)
            time.sleep(delay)
            
            # Обновляем headers для получения HTML (не JSON)
            html_headers = {
                **self.session_headers,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            
            response = self.session.get(photos_page_url, headers=html_headers, timeout=30)
            response.raise_for_status()
            html_content = response.text
            
            # Парсим HTML с помощью BeautifulSoup
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Ищем элемент по селектору: .PhotosPage-Description
                # Селектор: #root > div > div.EditPage.EditPage_type_photos > div.EditPage-Right > div > div.PhotosPage > div.PhotosPage-Description
                description_elem = soup.select_one('.PhotosPage-Description')
                if description_elem:
                    text = description_elem.get_text()
                    print(f"   📄 Найден элемент PhotosPage-Description: {text[:100]}")
                    
                    # Ищем числа в тексте (количество фотографий)
                    import re
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        # Берём максимальное число (скорее всего это общее количество)
                        photos_count = max(int(n) for n in numbers)
                        print(f"   ✅ Количество фотографий из HTML (селектор): {photos_count}")
                        return photos_count
                    
                    # Также ищем паттерны типа "62 фото" или "62 фотографий"
                    match = re.search(r'(\d+)\s*(?:фото|photo|photograph)', text, re.IGNORECASE)
                    if match:
                        photos_count = int(match.group(1))
                        print(f"   ✅ Найдено количество фотографий: {photos_count}")
                        return photos_count
                
                # Также пробуем найти по другим селекторам
                for selector in ['.PhotosPage-Description', '[class*="PhotosPage"]', '[class*="photo"]']:
                    elements = soup.select(selector)
                    for elem in elements:
                        text = elem.get_text()
                        # Ищем паттерны типа "62 фото" или "62 фотографий"
                        import re
                        match = re.search(r'(\d+)\s*(?:фото|photo|photograph)', text, re.IGNORECASE)
                        if match:
                            photos_count = int(match.group(1))
                            print(f"   ✅ Найдено количество фотографий (селектор {selector}): {photos_count}")
                            return photos_count
                
                html_parsed = True
                
            except ImportError:
                # Если BeautifulSoup не установлен, используем регулярные выражения
                print(f"   ⚠️ BeautifulSoup не установлен, используем регулярные выражения")
                import re
                
                # Ищем селектор .PhotosPage-Description в HTML
                description_match = re.search(
                    r'<[^>]*class="[^"]*PhotosPage-Description[^"]*"[^>]*>([^<]+)</',
                    html_content,
                    re.IGNORECASE
                )
                if description_match:
                    text = description_match.group(1)
                    print(f"   📄 Найден текст из PhotosPage-Description: {text[:100]}")
                    
                    # Ищем числа в тексте
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        photos_count = max(int(n) for n in numbers)
                        print(f"   ✅ Количество фотографий из HTML (regex): {photos_count}")
                        return photos_count
                
                # Ищем паттерны типа "62 фото" или "62 фотографий" в HTML
                photo_count_patterns = [
                    r'(\d+)\s*(?:фото|photo|photograph)',
                    r'(?:фото|photo|photograph)[^0-9]*(\d+)',
                ]
                for pattern in photo_count_patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    if matches:
                        try:
                            photos_count = max(int(m) for m in matches)
                            print(f"   ✅ Найдено количество фотографий (regex): {photos_count}")
                            return photos_count
                        except:
                            pass
                
                html_parsed = True
            
            except Exception as e:
                print(f"   ⚠️ Ошибка при парсинге HTML: {e}")
        
        except Exception as e:
            print(f"   ⚠️ Ошибка при запросе HTML страницы: {e}")
        
        # Если не получили данные из HTML, пробуем другие API endpoints (предположения)
        if not result or (result and not html_parsed):
            if not html_parsed:
                print(f"⚠️ Не удалось получить данные из HTML, пробуем другие API endpoints (предположения)...")
            else:
                print(f"⚠️ HTML страница загружена, но количество не найдено. Пробуем другие API endpoints (предположения)...")
            
            # Fallback endpoints (предположения, если sidebar не сработал)
            possible_urls = [
                f"https://yandex.ru/sprav/api/{external_id}/photos",
                f"https://yandex.ru/sprav/api/{external_id}/media",
                f"https://yandex.ru/sprav/api/{external_id}/images",
                f"https://yandex.ru/sprav/api/{external_id}/gallery",
                f"https://yandex.ru/sprav/api/{external_id}/photos/categories",
                f"https://yandex.ru/sprav/{external_id}/p/edit/photos/api",
                f"https://yandex.ru/sprav/api/{external_id}?fields=photos_count,photos",
            ]
            
            for url in possible_urls:
                print(f"🔍 Пробуем endpoint фотографий (предположение): {url}")
                
                # Имитация человека: случайная задержка перед запросом
                delay = random.uniform(1.5, 3.5)
                time.sleep(delay)
                
                api_result = self._make_request(url)
                if api_result:
                    result = api_result
                    working_url = url
                    print(f"✅ Успешно получены данные фотографий с {url}")
                    break
        
        # Если не получили данные через API, возвращаем 0
        if not result:
            print(f"   ❌ Не удалось получить количество фотографий ни через sidebar API, ни через HTML, ни через другие API endpoints")
            return 0
        
        # Парсим структуру ответа и считаем количество
        # Возможные варианты:
        # 1. {"total": 62} - прямое количество
        # 2. {"list": {"items": [...], "total": 62}} - список с total
        # 3. {"categories": [{"count": 9}, {"count": 2}, ...]} - категории с количеством
        # 4. {"photos": [...]} - список фотографий
        photos_count = 0
        
        # Вариант 1: Прямое поле total
        if isinstance(result, dict):
            if "total" in result:
                photos_count = result.get("total", 0)
                print(f"📊 Найдено total в ответе: {photos_count}")
            # Вариант 2: Сумма по категориям (как на скриншоте)
            elif "categories" in result:
                categories = result.get("categories", [])
                photos_count = sum(cat.get("count", 0) for cat in categories if isinstance(cat, dict))
                print(f"📊 Найдено категорий: {len(categories)}, сумма фото: {photos_count}")
            # Вариант 3: Список фотографий - считаем длину
            elif "list" in result and isinstance(result["list"], dict):
                if "total" in result["list"]:
                    photos_count = result["list"].get("total", 0)
                    print(f"📊 Найдено total в list: {photos_count}")
                elif "items" in result["list"]:
                    photos_count = len(result["list"]["items"])
                    print(f"📊 Найдено items в list: {photos_count}")
            elif "photos" in result:
                if isinstance(result["photos"], list):
                    photos_count = len(result["photos"])
                    print(f"📊 Найдено photos в списке: {photos_count}")
                elif isinstance(result["photos"], dict) and "total" in result["photos"]:
                    photos_count = result["photos"].get("total", 0)
                    print(f"📊 Найдено total в photos: {photos_count}")
            elif "data" in result:
                if isinstance(result["data"], list):
                    photos_count = len(result["data"])
                    print(f"📊 Найдено data в списке: {photos_count}")
                elif isinstance(result["data"], dict):
                    if "total" in result["data"]:
                        photos_count = result["data"].get("total", 0)
                        print(f"📊 Найдено total в data: {photos_count}")
                    elif "photos" in result["data"]:
                        photos_list = result["data"]["photos"]
                        photos_count = len(photos_list) if isinstance(photos_list, list) else 0
                        print(f"📊 Найдено photos в data: {photos_count}")
        
        # Если список пустой, выводим структуру для отладки
        if photos_count == 0:
            print(f"⚠️ Не удалось определить количество фотографий. Структура ответа:")
            print(f"   Тип: {type(result)}")
            if isinstance(result, dict):
                print(f"   Ключи верхнего уровня: {list(result.keys())[:10]}")
                # Показываем первые 1000 символов JSON для отладки
                result_str = json.dumps(result, ensure_ascii=False, indent=2)[:1000]
                print(f"   Первые 1000 символов JSON:\n{result_str}...")
        
        print(f"✅ Общее количество фотографий: {photos_count}")
        return photos_count

    def fetch_services(self, account_row: dict) -> List[Dict[str, Any]]:
        """
        Получить услуги/прайс-лист из кабинета Яндекс.Бизнес.
        
        Args:
            account_row: Строка из ExternalBusinessAccounts с полями business_id, external_id и т.д.
        
        Returns:
            Список словарей с услугами: [{"category": "...", "name": "...", "description": "...", "price": "..."}, ...]
        """
        business_id = account_row["business_id"]
        external_id = account_row.get("external_id")
        
        services = []
        
        if not external_id:
            print(f"❌ Нет external_id для бизнеса {business_id}")
            return []
        
        # API endpoint для прайс-листов (услуг)
        # URL: https://yandex.ru/sprav/api/company/{external_id}/price-lists?page={page}
        base_url = f"https://yandex.ru/sprav/api/company/{external_id}/price-lists"
        
        all_services_data = []
        current_page = 1
        max_pages = 20  # Ограничение на случай бесконечного цикла
        
        while current_page <= max_pages:
            params = {"page": current_page}
            
            print(f"🔍 Страница {current_page}: Загружаем услуги...")
            
            # Имитация человека: случайная задержка между запросами (кроме первой страницы)
            if current_page > 1:
                page_delay = random.uniform(2.0, 4.0)
                print(f"   ⏳ Пауза {page_delay:.1f} сек (имитация человека, чтобы избежать капчи)...")
                time.sleep(page_delay)
            
            result = self._make_request(base_url, params=params)
            
            if not result:
                print(f"❌ Не удалось получить данные со страницы {current_page}")
                if len(all_services_data) == 0:
                    print(f"   Возможные причины:")
                    print(f"   1. Cookies устарели - обновите их в админской панели")
                    print(f"   2. Капча (SmartCaptcha) - нужно обновить cookies или увеличить задержки")
                    print(f"   3. Проблемы с сетью или API Яндекс изменился")
                    return []
                break
            
            # Парсим структуру ответа
            # Предполагаемая структура: {"list": {"items": [...], "pager": {"total": 10, "page": 1}}}
            page_services = []
            if isinstance(result, list):
                page_services = result
            elif "list" in result and isinstance(result["list"], dict):
                if "items" in result["list"]:
                    page_services = result["list"]["items"]
            elif "items" in result:
                page_services = result["items"]
            elif "data" in result:
                if isinstance(result["data"], list):
                    page_services = result["data"]
                elif isinstance(result["data"], dict) and "items" in result["data"]:
                    page_services = result["data"]["items"]
            
            if not page_services:
                print(f"⚠️ Нет услуг на странице {current_page}")
                if len(all_services_data) == 0:
                    # Для первого запроса выводим полную структуру для отладки
                    print(f"🔍 Полная структура ответа (для отладки):")
                    result_str = json.dumps(result, ensure_ascii=False, indent=2)[:2000]
                    print(f"{result_str}...")
                break
            
            print(f"✅ Получено {len(page_services)} услуг на странице {current_page}")
            all_services_data.extend(page_services)
            
            # Проверяем, есть ли следующая страница
            has_next_page = False
            if "list" in result and isinstance(result["list"], dict):
                pager = result["list"].get("pager", {})
                total = pager.get("total", 0)
                limit = pager.get("limit", 20)
                if total > len(all_services_data):
                    has_next_page = True
            elif "pager" in result:
                pager = result["pager"]
                total = pager.get("total", 0)
                if total > len(all_services_data):
                    has_next_page = True
            
            if not has_next_page:
                print(f"✅ Все услуги загружены (всего: {len(all_services_data)})")
                break
            
            current_page += 1
        
        # Парсим услуги из данных
        for service_data in all_services_data:
            try:
                # Парсим категорию (пробуем разные варианты)
                category = (
                    service_data.get("category") or 
                    service_data.get("category_name") or 
                    service_data.get("categoryName") or
                    service_data.get("group") or 
                    service_data.get("group_name") or
                    service_data.get("groupName") or
                    service_data.get("section") or
                    service_data.get("section_name") or
                    service_data.get("sectionName") or
                    # Если категория вложена в объект
                    (service_data.get("category_obj", {}).get("name") if isinstance(service_data.get("category_obj"), dict) else None) or
                    (service_data.get("group_obj", {}).get("name") if isinstance(service_data.get("group_obj"), dict) else None) or
                    (service_data.get("section_obj", {}).get("name") if isinstance(service_data.get("section_obj"), dict) else None) or
                    "Общие услуги"  # Значение по умолчанию
                )
                
                # Парсим название
                name = (
                    service_data.get("name") or 
                    service_data.get("title") or 
                    service_data.get("service_name") or
                    service_data.get("serviceName") or
                    service_data.get("item_name") or
                    service_data.get("itemName") or
                    ""
                )
                if not name:
                    continue  # Пропускаем услуги без названия
                
                # Парсим описание
                description = (
                    service_data.get("description") or 
                    service_data.get("text") or 
                    service_data.get("comment") or
                    service_data.get("details") or
                    service_data.get("content") or
                    ""
                )
                # Если description - это dict, извлекаем текст
                if isinstance(description, dict):
                    description = description.get("text") or description.get("value") or description.get("content") or str(description)
                elif not isinstance(description, str):
                    description = str(description) if description else ""
                
                # Парсим цену
                price = None
                price_data = (
                    service_data.get("price") or 
                    service_data.get("cost") or 
                    service_data.get("amount") or
                    service_data.get("price_value") or
                    service_data.get("priceValue")
                )
                if price_data:
                    if isinstance(price_data, (int, float)):
                        price = str(price_data)
                    elif isinstance(price_data, dict):
                        price = str(price_data.get("value") or price_data.get("amount") or price_data.get("price") or "")
                    else:
                        price = str(price_data)
                
                # Парсим ключевые слова (если есть)
                keywords = service_data.get("keywords") or service_data.get("tags") or service_data.get("tag_list") or []
                if isinstance(keywords, str):
                    keywords = [k.strip() for k in keywords.split(",") if k.strip()]
                elif not isinstance(keywords, list):
                    keywords = []
                
                # Логируем первую услугу для отладки структуры
                if len(services) == 0:
                    print(f"🔍 Пример структуры услуги (для отладки):")
                    print(f"   Ключи верхнего уровня: {list(service_data.keys())[:15]}")
                    print(f"   Извлечённая категория: {category}")
                    print(f"   Извлечённое название: {name}")

                if not _service_payload_is_relevant(
                    service_data,
                    external_id,
                    name=name,
                    description=description,
                ):
                    print(f"⚠️ Пропускаем нерелевантную услугу/подборку: {name}")
                    continue
                
                services.append({
                    "category": category,
                    "name": name,
                    "description": description,
                    "price": price or "",
                    "keywords": keywords,
                })
            except Exception as e:
                print(f"⚠️ Ошибка парсинга услуги: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"✅ Всего спарсено услуг: {len(services)}")
        return services

    def fetch_photos(self, account_row: dict) -> List[ExternalPhoto]:
        """
        Получить фотографии из кабинета Яндекс.Бизнес.
        Для простоты используем только количество - детали не нужны.
        
        Args:
            account_row: Строка из ExternalBusinessAccounts с полями business_id, external_id и т.д.
        
        Returns:
            Пустой список (детали фотографий не сохраняем, только количество)
        """
        # Просто получаем количество, детали не нужны
        count = self.fetch_photos_count(account_row)
        return []  # Возвращаем пустой список, т.к. нужен только счётчик

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

    def _fake_fetch_posts(self, account_row: dict) -> List[ExternalPost]:
        """Демо-данные для постов (используется при ошибках или в dev-режиме)."""
        today = datetime.utcnow()
        pid = f"{account_row['business_id']}_demo_post"
        return [
            ExternalPost(
                id=pid,
                business_id=account_row["business_id"],
                source="yandex_business",
                external_post_id=pid,
                title="Демо-новость",
                text="Это демо-новость из Яндекс.Бизнес (заглушка).",
                published_at=today,
                image_url=None,
                raw_payload={"demo": True},
            )
        ]

    def _fake_fetch_photos(self, account_row: dict) -> List[ExternalPhoto]:
        """Демо-данные для фотографий (используется при ошибках или в dev-режиме)."""
        today = datetime.utcnow()
        pid = f"{account_row['business_id']}_demo_photo"
        return [
            ExternalPhoto(
                id=pid,
                business_id=account_row["business_id"],
                source="yandex_business",
                external_photo_id=pid,
                url="https://example.com/demo-photo.jpg",
                thumbnail_url="https://example.com/demo-photo-thumb.jpg",
                uploaded_at=today,
                raw_payload={"demo": True},
            )
        ]


    def fetch_products(self, account_row: dict) -> List[Dict[str, Any]]:
        """
        Получить товары/услуги из кабинета Яндекс.Бизнес.
        
        Args:
            account_row: Строка из ExternalBusinessAccounts
        
        Returns:
            Список словарей с данными о товарах/услугах (категории и товары)
        """
        business_id = account_row["business_id"]
        external_id = account_row.get("external_id")
        
        if not external_id:
            return []
            
        print(f"🔍 Пробуем получить товары/услуги для {business_id}...")
        
        # Endpoints для товаров/услуг (Goods / Price Lists)
        possible_urls = [
            f"https://yandex.ru/sprav/api/{external_id}/goods",
            f"https://yandex.ru/sprav/api/{external_id}/price-lists",
            f"https://yandex.ru/sprav/api/company/{external_id}/goods",
            f"https://business.yandex.ru/api/organizations/{external_id}/goods",
        ]
        
        data = None
        for url in possible_urls:
            # Имитация
            delay = random.uniform(1.0, 3.0)
            time.sleep(delay)
            
            result = self._make_request(url)
            if result:
                data = result
                print(f"✅ Успешно получены данные товаров с {url}")
                break
                
        if not data:
            print(f"⚠️ Не удалось получить товары через API endpoints.")
            return []
            
        # Парсим ответ
        # Ожидаемая структура: {"categories": [...]} или список категорий
        categories = []
        
        if isinstance(data, list):
            categories = data
        elif isinstance(data, dict):
            categories = data.get("categories") or data.get("groups") or data.get("goods") or []
            
        parsed_products = []
        
        for category in categories:
            if not _service_payload_is_relevant(category, external_id):
                continue
            cat_name = category.get("name", "Разное")
            items = category.get("items") or category.get("goods") or []
            
            parsed_items = []
            for item in items:
                # Извлекаем цену
                price = item.get("price")
                if isinstance(price, dict):
                    price_val = price.get("value")
                    currency = price.get("currency", "RUB")
                    price_str = f"{price_val} {currency}" if price_val else ""
                else:
                    price_str = str(price) if price else ""
                
                item_name = item.get("name") or item.get("title") or item.get("text") or ""
                item_description = item.get("description") or item.get("text") or item.get("details") or item.get("content") or ""
                if not _service_payload_is_relevant(
                    item,
                    external_id,
                    name=item_name,
                    description=item_description,
                ):
                    print(f"⚠️ Пропускаем нерелевантный товар/подборку: {item_name}")
                    continue

                parsed_items.append({
                    "name": item_name,
                    "description": item_description,
                    "price": price_str,
                    "photo_url": item.get("photos", [{}])[0].get("url") if item.get("photos") else None
                })
                
            if parsed_items:
                parsed_products.append({
                    "category": cat_name,
                    "items": parsed_items
                })
                
        print(f"✅ Получено {len(parsed_products)} категорий товаров")
        return parsed_products
