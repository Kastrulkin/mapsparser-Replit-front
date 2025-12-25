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
from external_sources import ExternalReview, ExternalStatsPoint, ExternalPost, ExternalPhoto


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
                        print(f"✅ Все новые отзывы загружены (найдены отзывы старше {last_sync_date})")
                        break
            
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
                # В реальном API ответ находится в поле "owner_comment"
                response_data = (
                    review_data.get("owner_comment") or  # Основное поле в реальном API
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
                
                # Логируем структуру только для первых нескольких отзывов с ответами (для отладки)
                if idx < 3 and has_response:
                    print(f"✅ Отзыв #{idx + 1} (ID: {review_id}): найден ответ")
                    print(f"   Текст ответа: {response_text[:100]}...")
                    if response_at:
                        print(f"   Дата ответа: {response_at}")
                
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
            # Вычисляем средний рейтинг из отзывов
            if reviews:
                ratings = [r.rating for r in reviews if r.rating]
                if ratings:
                    info["rating"] = sum(ratings) / len(ratings)
        
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
                try:
                    result = response.json()
                    working_url = sidebar_url
                    print(f"✅ Успешно получены данные из sidebar API")
                except json.JSONDecodeError:
                    # Может быть HTML
                    print(f"⚠️ Sidebar API вернул не JSON, пробуем HTML страницу...")
                    result = None
            else:
                print(f"⚠️ Sidebar API вернул статус {response.status_code}, пробуем HTML страницу...")
                result = None
        except Exception as e:
            print(f"⚠️ Ошибка запроса к sidebar API: {e}, пробуем HTML страницу...")
            result = None
        
        if not result:
            # Пробуем через _make_request как fallback
            result = self._make_request(sidebar_url)
            if result:
                working_url = sidebar_url
                print(f"✅ Успешно получены данные из sidebar API (через _make_request)")
        
        # Если sidebar API не сработал, пробуем извлечь данные из HTML страницы
        if not result:
            print(f"🔍 Пробуем получить посты/новости из HTML страницы...")
            posts_page_url = f"https://yandex.ru/sprav/{external_id}/p/edit/posts/"
            
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
                
                response = self.session.get(posts_page_url, headers=html_headers, timeout=30)
                response.raise_for_status()
                html_content = response.text
                
                # Пытаемся извлечь window.__INITIAL__.sidebar из HTML
                import re
                # Ищем паттерн window.__INITIAL__ = {...} или window.__INITIAL__.sidebar = {...}
                initial_patterns = [
                    r'window\.__INITIAL__\s*=\s*({.+?});',
                    r'window\.__INITIAL__\.sidebar\s*=\s*({.+?});',
                    r'__INITIAL__\.sidebar\s*=\s*({.+?});',
                ]
                
                for pattern in initial_patterns:
                    match = re.search(pattern, html_content, re.DOTALL)
                    if match:
                        try:
                            import json
                            initial_data = json.loads(match.group(1))
                            print(f"   ✅ Найден window.__INITIAL__ в HTML")
                            
                            # Ищем sidebar в initial_data
                            sidebar_data = None
                            if isinstance(initial_data, dict):
                                sidebar_data = initial_data.get("sidebar") or initial_data.get("data")
                            
                            if sidebar_data:
                                print(f"   ✅ Найден sidebar в window.__INITIAL__")
                                result = sidebar_data
                                html_parsed = True
                                break
                        except json.JSONDecodeError as e:
                            print(f"   ⚠️ Не удалось распарсить JSON из window.__INITIAL__: {e}")
                            continue
                        except Exception as e:
                            print(f"   ⚠️ Ошибка при извлечении window.__INITIAL__: {e}")
                            continue
                
                # Если не нашли window.__INITIAL__, пробуем парсить HTML с помощью BeautifulSoup
                if not html_parsed:
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html_content, 'html.parser')
                        
                        # Ищем элементы с постами/новостями
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
        
        # Если не получили данные, пробуем другие API endpoints (предположения)
        if not result:
            print(f"⚠️ Не удалось получить данные из sidebar/HTML, пробуем другие API endpoints (предположения)...")
            possible_urls = [
                # Предполагаемые endpoints по аналогии с отзывами
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
        def find_posts_in_structure(obj, path=""):
            """Рекурсивно ищет массив постов в структуре данных"""
            if isinstance(obj, list):
                # Если это список, проверяем, похож ли он на список постов
                if len(obj) > 0 and isinstance(obj[0], dict):
                    # Проверяем, есть ли в первом элементе типичные поля поста
                    first_item = obj[0]
                    post_fields = ["id", "title", "text", "content", "published_at", "created_at", "date", "name", "header", "message"]
                    if any(field in first_item for field in post_fields):
                        return obj
                return None
            elif isinstance(obj, dict):
                # Проверяем прямые ключи
                for key in ["posts", "publications", "news", "items"]:
                    if key in obj:
                        found = find_posts_in_structure(obj[key], f"{path}.{key}")
                        if found:
                            return found
                
                # Проверяем вложенные структуры
                for key, value in obj.items():
                    if isinstance(value, (dict, list)):
                        found = find_posts_in_structure(value, f"{path}.{key}")
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
        
        print(f"📊 Найдено постов в ответе: {len(posts_data)}")
        
        # Если список пустой, выводим структуру для отладки
        if not posts_data:
            print(f"⚠️ Список постов пуст. Структура ответа:")
            print(f"   Тип: {type(result)}")
            if isinstance(result, dict):
                print(f"   Ключи верхнего уровня: {list(result.keys())[:20]}")
                # Показываем первые 2000 символов JSON для отладки
                result_str = json.dumps(result, ensure_ascii=False, indent=2)[:2000]
                print(f"   Первые 2000 символов JSON:\n{result_str}...")
                # Также пробуем найти любые вложенные массивы
                def find_arrays(obj, path="", max_depth=3):
                    """Находит все массивы в структуре для отладки"""
                    arrays = []
                    if isinstance(obj, list):
                        arrays.append((path, len(obj), type(obj[0]).__name__ if obj else "empty"))
                    elif isinstance(obj, dict) and max_depth > 0:
                        for key, value in obj.items():
                            arrays.extend(find_arrays(value, f"{path}.{key}" if path else key, max_depth - 1))
                    return arrays
                arrays = find_arrays(result)
                if arrays:
                    print(f"   Найдены массивы в структуре:")
                    for arr_path, arr_len, arr_type in arrays[:10]:
                        print(f"      {arr_path}: {arr_len} элементов (тип: {arr_type})")
        
        # Парсим посты
        for idx, post_data in enumerate(posts_data):
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
        
        print(f"✅ Получено постов: {len(posts)}")
        return posts

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

