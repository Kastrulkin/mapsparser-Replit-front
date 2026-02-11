"""
parser_interception.py — Парсер Яндекс.Карт через Network Interception

Перехватывает API запросы во время загрузки страницы и извлекает данные из JSON ответов.
Это в 10x быстрее, чем парсинг HTML через Playwright.
"""

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import json
import re
import time
import random
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, parse_qs
import os
from datetime import datetime

from browser_session import BrowserSession, BrowserSessionManager

DEBUG_DIR = os.getenv("DEBUG_DIR", "/app/debug_data")

# Только ключи, передаваемые в manager.open_session (parser_interception) или используемые воркером.
ALLOWED_SESSION_KWARGS = {
    "headless",
    "cookies",
    "user_agent",
    "viewport",
    "locale",
    "timezone_id",
    "proxy",
    "launch_args",
    "init_scripts",
    "geolocation",
}

def _find_paths(obj: Any, target_keys: List[str], max_depth: int = 6, max_preview_len: int = 120,
                max_results_per_key: int = 20) -> Dict[str, List[Dict[str, str]]]:
    """
    Dev-only утилита: найти пути к ключам target_keys в произвольном JSON (dict/list).

    Возвращает словарь:
      { key: [ { "path": "payload.company.rubrics[0].name", "preview": "..." }, ... ] }
    """
    targets = set(target_keys)
    results: Dict[str, List[Dict[str, str]]] = {k: [] for k in targets}

    def _add_result(key: str, path: str, value: Any) -> None:
        bucket = results.setdefault(key, [])
        if len(bucket) >= max_results_per_key:
            return
        try:
            if isinstance(value, (dict, list)):
                preview = json.dumps(value, ensure_ascii=False)
            else:
                preview = str(value)
        except Exception:
            preview = repr(value)
        if len(preview) > max_preview_len:
            preview = preview[:max_preview_len] + "…"
        bucket.append({"path": path, "preview": preview})

    def _walk(node: Any, path: str, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                new_path = f"{path}.{k}" if path else k
                if k in targets:
                    _add_result(k, new_path, v)
                _walk(v, new_path, depth + 1)
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                new_path = f"{path}[{idx}]" if path else f"[{idx}]"
                _walk(item, new_path, depth + 1)

    _walk(obj, "", 0)
    return {k: v for k, v in results.items() if v}


def _set_if_empty(result: Dict[str, Any], key: str, value: Any) -> None:
    """
    Поставить result[key] только если там сейчас "пусто" и value осмысленное.
    Пусто: None, '', [], {}.
    """
    if value is None:
        return
    if isinstance(value, str) and not value.strip():
        return

    current = result.get(key)
    if current is None or current == "" or current == [] or current == {}:
        result[key] = value


def _extend_unique(result: Dict[str, Any], key: str, items: List[Any]) -> None:
    """
    Добавить строки в список result[key] без дублей, не затирая существующее.
    """
    if not items:
        return

    # Для categories храним только список строк (имен/меток), без dict и других типов.
    if key == "categories":
        def _cat_str_from_item(it: Any) -> Optional[str]:
            if isinstance(it, str):
                s = it.strip()
                return s or None
            if isinstance(it, dict):
                for k in ("name", "label", "text", "title"):
                    v = it.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
            return None

        existing_raw = result.get(key)
        existing_list: List[str] = []
        if isinstance(existing_raw, list):
            for it in existing_raw:
                s = _cat_str_from_item(it)
                if s and s not in existing_list:
                    existing_list.append(s)
        elif isinstance(existing_raw, str) and existing_raw.strip():
            existing_list = [existing_raw.strip()]

        seen = set(existing_list)
        for item in items:
            s = _cat_str_from_item(item)
            if not s or s in seen:
                continue
            existing_list.append(s)
            seen.add(s)

        result[key] = existing_list
        return

    # Общий случай: сохраняем типы как есть, но избегаем дублей по строковому представлению.
    existing = result.get(key)
    if existing is None:
        existing_list: List[Any] = []
    elif isinstance(existing, list):
        existing_list = existing
    else:
        existing_list = [existing]

    seen = {str(x) for x in existing_list}
    for item in items:
        s = str(item)
        if s in seen:
            continue
        existing_list.append(item)
        seen.add(s)

    result[key] = existing_list


def _get_nested(obj: Any, path: str) -> Any:
    """
    Достать значение по пути вида "payload.company.rubrics[0].name"
    с поддержкой индексов [0].
    """
    if not path:
        return obj

    # Разбиваем по точкам, внутри каждой части могут быть индексы [0]
    for part in path.split("."):
        if not part:
            continue
        # Выделяем ключ и индексы.
        # Пример part: "rubrics[0][1]"
        i = 0
        key = ""
        # Собираем буквенно-цифровую часть до первой скобки
        while i < len(part) and part[i] != "[":
            key += part[i]
            i += 1

        if key:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
            if obj is None:
                return None

        # Обрабатываем индексы вида [0]
        while i < len(part):
            if part[i] != "[":
                return None
            j = part.find("]", i)
            if j == -1:
                return None
            index_str = part[i + 1 : j]
            try:
                idx = int(index_str)
            except ValueError:
                return None
            if not isinstance(obj, list) or idx < 0 or idx >= len(obj):
                return None
            obj = obj[idx]
            i = j + 1

    return obj


class YandexMapsInterceptionParser:
    """Парсер Яндекс.Карт через перехват сетевых запросов"""
    
    def __init__(self, debug_bundle_id: Optional[str] = None):
        self.api_responses: Dict[str, Any] = {}
        self.org_id: Optional[str] = None
        self.debug_bundle_id: Optional[str] = debug_bundle_id
        _base = os.getenv("DEBUG_DIR", "/app/debug_data")
        self.debug_bundle_dir: Optional[str] = os.path.join(_base, debug_bundle_id) if debug_bundle_id else None
        
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
    
    def parse_yandex_card(self, url: str, session: BrowserSession) -> Dict[str, Any]:
        """
        Парсит публичную страницу Яндекс.Карт через Network Interception.
        
        Args:
            url: URL карточки бизнеса (например, https://yandex.ru/maps/org/123456/)
            
        Returns:
            Словарь с данными в том же формате, что и parser.py
        """
        print(f"🔍 Начинаем парсинг через Network Interception: {url}")
        print("DEBUG: VERSION 2026-01-29 REDIRECT FIX + TIMEOUTS")
        
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError(f"Некорректная ссылка: {url}")
        
        self.org_id = self.extract_org_id(url)
        if not self.org_id:
            raise ValueError(f"Не удалось извлечь org_id из URL: {url}")
        
        print(f"📋 Извлечен org_id: {self.org_id}")

        # Инициализируем bundle-директорию для этого прогона (если ещё не задана в __init__)
        if not self.debug_bundle_id:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.debug_bundle_id = f"yandex_{self.org_id}_{ts}"
        if not self.debug_bundle_dir:
            self.debug_bundle_dir = os.path.join(os.getenv("DEBUG_DIR", "/app/debug_data"), self.debug_bundle_id)
        try:
            if self.debug_bundle_dir:
                os.makedirs(self.debug_bundle_dir, exist_ok=True)
        except Exception as e:
            print(f"⚠️ Не удалось создать debug bundle dir {self.debug_bundle_dir}: {e}")
        else:
            if self.debug_bundle_dir:
                print(f"[DEBUG_BUNDLE] {self.debug_bundle_dir}")

        context = session.context
        page = session.page

        # Базовая информация для debug bundle
        initial_url = url
        main_http_status: Optional[int] = None

        # Очищаем предыдущие ответы
        self.api_responses = {}

        # Перехватываем все ответы
        def handle_response(response):
            """Обработчик для перехвата сетевых запросов"""
            try:
                url = response.url

                # Ищем API запросы Яндекс.Карт
                if "yandex.ru" in url or "yandex.net" in url:
                    # Проверяем, это JSON ответ?
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type or "json" in url.lower() or "ajax=1" in url:
                        try:
                            # Пытаемся получить JSON
                            json_data = response.json()

                            # DEBUG: Save to file for inspection (только при наличии bundle)
                            if self.debug_bundle_dir:
                                try:
                                    os.makedirs(self.debug_bundle_dir, exist_ok=True)
                                    clean_url = url.split("?")[0].replace("/", "_").replace(":", "")[-50:]
                                    timestamp = int(time.time() * 1000)
                                    filename = f"{timestamp}_{clean_url}.json"
                                    filepath = os.path.join(self.debug_bundle_dir, filename)
                                    with open(filepath, "w", encoding="utf-8") as f:
                                        json.dump(json_data, f, ensure_ascii=False, indent=2)
                                except Exception as e:
                                    print(f"Failed to save debug json: {e}")

                            # Check for organization data (search or location-info)
                            if json_data:
                                # Сохраняем ответ
                                self.api_responses[url] = {
                                    "data": json_data,
                                    "status": response.status,
                                    "headers": dict(response.headers),
                                }
                                # Показываем только важные запросы
                                if any(
                                    keyword in url
                                    for keyword in [
                                        "org",
                                        "organization",
                                        "business",
                                        "company",
                                        "reviews",
                                        "feedback",
                                        "location-info",
                                    ]
                                ):
                                    print(f"✅ Перехвачен важный API запрос: {url[:100]}...")
                        except Exception:
                            # Не JSON, пропускаем
                            pass
            except Exception:
                # Поглощаем ошибки перехватчика, чтобы не ломать главный поток
                pass

        page.on("response", handle_response)

        # Загружаем страницу
        print("🌐 Загружаем страницу и перехватываем API запросы...")
        try:
            main_response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                if main_response is not None:
                    main_http_status = main_response.status
            except Exception:
                main_http_status = None

            # Проверяем на капчу с ожиданием решения
            for _ in range(24):  # Ждем до 120 секунд
                try:
                    # Более точная проверка капчи
                    title = page.title()
                    # Проверяем заголовок, текст и наличие элементов SmartCaptcha
                    is_captcha = (
                        "Ой!" in title
                        or "Captcha" in title
                        or "Robot" in title
                        or page.get_by_text("Подтвердите, что вы не робот").is_visible()
                        or page.locator(".smart-captcha").count() > 0
                        or page.locator("input[name='smart-token']").count() > 0
                    )

                    if is_captcha:
                        print("⚠️ Обнаружена капча! Ждем 15 секунд... (не трогаем страницу)")
                        page.wait_for_timeout(15000)
                    else:
                        break
                except Exception:
                    break
        except PlaywrightTimeoutError:
            print("⚠️ Страница не загрузилась полностью (таймаут), но продолжаем...")
        except Exception:
            print("⚠️ Страница не загрузилась полностью, но продолжаем...")

        # Double check if we are still stuck on Captcha
        title = page.title()
        if "Ой!" in title or "Captcha" in title or "Robot" in title or "Вы не робот" in title:
            print(f"❌ Капча не была решена за отведённое время. Заголовок: {title}")
            # Возвращаем специальную ошибку, чтобы воркер знал о капче
            return {"error": "captcha_detected", "captcha_url": page.url}

        try:
            print("⏳ Ожидание загрузки карточки организации...")
            # Ждем заголовок или название организации (добавлен user selector)
            page.wait_for_selector(
                "h1, div.business-card-title-view, div.card-title-view__title, "
                "div.orgpage-header-view__header, div.orgpage-header-view__header-wrapper > h1",
                timeout=15000,
            )
            print("✅ Карточка загружена")
        except PlaywrightTimeoutError:
            print("⚠️ Не удалось дождаться загрузки карточки. Возможно, капча не решена или бан.")

        # Проверка редиректа на главную или другую страницу
        current_url = page.url
        title = page.title()
        print(f"📍 Текущий URL: {current_url}, Заголовок: {title}")

        # Более строгая проверка: ищем заголовок организации
        is_business_card = False
        try:
            # Селекторы именно заголовка организации (добавлен user selector)
            is_business_card = (
                page.locator(
                    "h1.orgpage-header-view__header, "
                    "div.business-title-view, "
                    "div.card-title-view__title, "
                    "div.orgpage-header-view__header-wrapper > h1"
                ).count()
                > 0
            )
        except Exception:
            pass

        if (not is_business_card) or ("yandex.ru" in current_url and "/org/" not in current_url):
            print("⚠️ Не похоже на карточку организации! (Редирект?). Пробуем перейти по ссылке снова...")

            # Debug: Save bad page (только при наличии bundle)
            if self.debug_bundle_dir:
                try:
                    html_redirect = page.content()
                    os.makedirs(self.debug_bundle_dir, exist_ok=True)
                    with open(os.path.join(self.debug_bundle_dir, "redirect_page.html"), "w", encoding="utf-8") as f:
                        f.write(html_redirect or "")
                except Exception:
                    pass

            page.goto(url, wait_until="domcontentloaded")
            try:
                print("⏳ Повторное ожидание заголовка организации...")
                page.wait_for_selector(
                    "h1.orgpage-header-view__header, "
                    "div.business-title-view, "
                    "div.card-title-view__title, "
                    "h1[itemprop='name'], "
                    "div.orgpage-header-view__header-wrapper > h1",
                    timeout=20000,
                )
                print("✅ Карточка загружена (после повторного перехода)")
            except PlaywrightTimeoutError:
                print("❌ Не удалось загрузить карточку даже после повторного перехода. Возможно бан.")
                if self.debug_bundle_dir:
                    try:
                        html_failed = page.content()
                        os.makedirs(self.debug_bundle_dir, exist_ok=True)
                        with open(os.path.join(self.debug_bundle_dir, "failed_page_final.html"), "w", encoding="utf-8") as f:
                            f.write(html_failed or "")
                    except Exception:
                        pass
        else:
            print("✅ Страница похожа на карточку организации.")

        # Вспомогательная функция для прокрутки
        def scroll_page(times: int = 5) -> None:
            for _ in range(times):
                page.mouse.wheel(0, 1000)
                time.sleep(random.uniform(0.5, 1.0))

        extra_photos_count = 0

        # 1. Скроллим основную страницу
        print("📜 Скроллим основную страницу...")
        scroll_page(3)

        # 2. Кликаем и скроллим Отзывы (Reviews)
        try:
            reviews_tab = page.query_selector("div.tabs-select-view__title._name_reviews")
            if reviews_tab:
                print("💬 Переходим во вкладку Отзывы...")
                reviews_tab.click(force=True)
                time.sleep(2)

                # Скроллим отзывы (очень агрессивно)
                print("📜 Скроллим отзывы (глубокий скролл - загрузка всех)...")
                for i in range(80):  # Increased to 80
                    # Random scroll amount
                    delta = random.randint(2000, 4000)
                    page.mouse.wheel(0, delta)
                    page.evaluate(f"window.scrollBy(0, {delta//2})")  # JS scroll helper

                    time.sleep(random.uniform(0.5, 1.2))

                    # Small "wobble" (scroll up slightly) to trigger intersection observers
                    if i % 5 == 0:
                        page.mouse.wheel(0, -500)
                        time.sleep(0.5)
                        page.mouse.wheel(0, 500)

                    # Move mouse to trigger hover events
                    page.mouse.move(random.randint(100, 800), random.randint(100, 800))

                    # Пытаемся кликнуть "Показать еще" если есть
                    try:
                        more_btn = page.query_selector("button:has-text('Показать ещё')") or page.query_selector(
                            "div.reviews-view__more"
                        )
                        if more_btn and more_btn.is_visible():
                            more_btn.click()
                            time.sleep(2)
                    except Exception:
                        pass
            else:
                print("ℹ️ Вкладка Отзывы не найдена (селектор)")
        except Exception as e:
            print(f"⚠️ Ошибка при обработке отзывов: {e}")

        # 3. Кликаем и скроллим Фото (Photos)
        try:
            photos_tab = page.query_selector("div.tabs-select-view__title._name_gallery")
            if photos_tab:
                print("📷 Переходим во вкладку Фото...")

                # Пытаемся получить количество фото
                try:
                    photos_text = photos_tab.inner_text()
                    print(f"ℹ️ Текст вкладки фото: {photos_text}")
                    match = re.search(r"(\\d+)", photos_text)
                    if match:
                        extra_photos_count = int(match.group(1))
                except Exception:
                    pass

                photos_tab.click(force=True)
                time.sleep(2)
                print("📜 Скроллим фото...")
                scroll_page(10)
            else:
                print("ℹ️ Вкладка Фото не найдена")
        except Exception as e:
            print(f"⚠️ Ошибка при обработке фото: {e}")

        # 4. Кликаем и скроллим Новости (News/Posts)
        try:
            news_tab = page.query_selector("div.tabs-select-view__title._name_posts")
            if news_tab:
                print("📰 Переходим во вкладку Новости...")
                news_tab.click(force=True)
                time.sleep(2)
                print("📜 Скроллим новости...")
                scroll_page(10)
            else:
                print("ℹ️ Вкладка Новости не найдена")
        except Exception as e:
            print(f"⚠️ Ошибка при обработке новостей: {e}")

        # 5. Кликаем и скроллим Товары/Услуги (Prices/Goods)
        try:
            # Пробуем разные селекторы для таба товаров
            services_tab = page.query_selector("div.tabs-select-view__title._name_price")
            if not services_tab:
                services_tab = page.query_selector("div.tabs-select-view__title._name_goods")
            if not services_tab:
                # User provided selector (simplified) - 2nd tab in carousel
                services_tab = page.query_selector("div.carousel__content > div:nth-child(2) > div")

            # Fallback на поиск по тексту
            if not services_tab:
                for text in ["Цены", "Товары и услуги", "Услуги", "Товары", "Меню", "Прайс"]:
                    try:
                        found = page.get_by_text(text, exact=False)
                        if found.count() > 0:
                            # Check visibility to avoid hidden elements
                            if found.first.is_visible():
                                services_tab = found.first
                                print(f"✅ Нашли таб услуг по тексту: {text}")
                                break
                    except Exception:
                        pass

            if services_tab:
                print("💰 Переходим во вкладку Цены/Услуги...")
                services_tab.click(force=True)
                time.sleep(3)  # Чуть больше времени на загрузку
                print("📜 Скроллим услуги...")
                scroll_page(20)  # Больше скролла
            else:
                print("ℹ️ Вкладка Цены/Услуги не найдена")
        except Exception as e:
            print(f"⚠️ Ошибка при обработке услуг: {e}")

        # Проверка верификации через HTML (так как в JSON это может быть спрятано)
        is_verified = False
        try:
            verified_selectors = [
                ".business-verified-badge-view",
                "div._name_verified",
                ".business-card-view__verified-badge",
                "span[aria-label='Информация подтверждена владельцем']",
                "span.business-verified-badge",
                "div.business-verified-badge",
            ]
            for sel in verified_selectors:
                # Используем короткий таймаут для проверки
                try:
                    if page.query_selector(sel):
                        is_verified = True
                        print("✅ Найдена галочка верификации (HTML)")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"Ошибка проверки верификации: {e}")

        print(f"📦 Перехвачено {len(self.api_responses)} API запросов")

        # Извлекаем данные из перехваченных ответов
        data = self._extract_data_from_responses()
        data["is_verified"] = is_verified
        if extra_photos_count > 0:
            data["photos_count"] = extra_photos_count

        # Если не удалось извлечь данные через API, fallback на HTML парсинг
        # ПЕРЕД ЭТИМ: Hybrid Mode для отдельных секций

        # 1. Услуги/Товары (часто скрыты в API)
        if not data.get("products"):
            print("⚠️ Услуги не найдены через API, пробуем HTML парсинг (Hybrid Mode)...")
            try:
                # Импорт здесь, чтобы избежать циклических зависимостей
                from yandex_maps_scraper import parse_products

                # Убедимся, что мы на вкладке товаров (мы туда кликали ранее)
                # Но на всякий случай проверим
                html_products = parse_products(page)
                if html_products:
                    print(f"✅ Услуги найдены через HTML: {len(html_products)}")
                    data["products"] = html_products
                    data["fallback_used"] = True  # MARKER for worker.py warning

                    # Пересобираем overview grouped products
                    grouped_products = {}
                    for prod in html_products:
                        cat = prod.get("category", "Другое") or "Другое"
                        if cat not in grouped_products:
                            grouped_products[cat] = []
                        grouped_products[cat].append(prod)

                    final_products = []
                    for cat, items in grouped_products.items():
                        final_products.append({"category": cat, "items": items})
                    data["products"] = final_products
                else:
                    print("⚠️ HTML парсинг услуг тоже не вернул результатов")
            except Exception as e:
                print(f"⚠️ Ошибка Hybrid Mode для услуг: {e}")

        if not data.get("title") and not data.get("overview", {}).get("title"):
            print("⚠️ Не удалось извлечь данные через API, используем HTML парсинг как fallback")

            try:
                # 0. Попытка извлечь из мета-тегов (самый надежный способ для заголовка)
                meta_title = None
                try:
                    # og:title
                    og_title = page.locator("meta[property='og:title']").get_attribute("content")
                    if og_title:
                        meta_title = og_title.split("|")[0].strip()  # "Name | City" -> "Name"
                        print(f"✅ Нашли заголовок в og:title: {meta_title}")

                    # title tag
                    if not meta_title:
                        page_title = page.title()
                        if page_title:
                            meta_title = page_title.split("-")[0].strip()  # "Name - Yandex Maps" -> "Name"
                            print(f"✅ Нашли заголовок в page title: {meta_title}")
                except Exception as e:
                    print(f"⚠️ Ошибка извлечения мета-заголовка: {e}")

                # 0.1 Попытка извлечь заголовок через user selector (если мета не сработала или для надежности)
                if not meta_title:
                    try:
                        h1_el = page.query_selector("div.orgpage-header-view__header-wrapper > h1")
                        if h1_el:
                            meta_title = h1_el.inner_text().strip()
                            print(f"✅ Нашли заголовок через CSS селектор: {meta_title}")
                    except Exception as e:
                        print(f"⚠️ Ошибка CSS селектора заголовка: {e}")

                if meta_title:
                    if "overview" not in data:
                        data["overview"] = {}
                    data["title"] = meta_title
                    data["overview"]["title"] = meta_title

                # Проверка верификации через user selector (если еще не найдено)
                if not is_verified:
                    try:
                        # body > ... > h1 > span
                        verified_el = page.query_selector(
                            "div.orgpage-header-view__header-wrapper > h1 > span.business-verified-badge"
                        )
                        if not verified_el:
                            verified_el = page.query_selector(
                                "div.orgpage-header-view__header-wrapper > h1 > span"
                            )

                        if verified_el:
                            data["is_verified"] = True
                            print("✅ Найдена галочка верификации (User CSS)")
                    except Exception:
                        pass

                # Извлечение адреса (если нет в API)
                if not data.get("address") and not data.get("overview", {}).get("address"):
                    try:
                        # 1. Meta tag
                        meta_address = page.locator(
                            "meta[property='business:contact_data:street_address']"
                        ).get_attribute("content")
                        if meta_address:
                            print(f"✅ Нашли адрес в meta: {meta_address}")
                            data["address"] = meta_address
                        else:
                            # 2. CSS Selector
                            address_el = (
                                page.query_selector("div.orgpage-header-view__address")
                                or page.query_selector("a.orgpage-header-view__address")
                                or page.query_selector("div.business-contacts-view__address-link")
                            )
                            if address_el:
                                addr_text = address_el.inner_text()
                                print(f"✅ Нашли адрес через CSS: {addr_text}")
                                data["address"] = addr_text
                    except Exception as e:
                        print(f"⚠️ Ошибка извлечения адреса HTML: {e}")

            except Exception as e:
                print(f"⚠️ Error extracting title from meta/css: {e}")

            # Передаем селектор пользователя в парсер
            try:
                # Поскольку YandexMapsScraper класса нет, парсим руками

                # Only try to parse products if we don't have them yet
                if not data.get("products"):
                    print("🛠 Parsing services via HTML with USER Selectors...")

                    products_html: List[Dict[str, Any]] = []

                    # 0. Сначала кликаем по табу "Цены" или "Услуги" если еще не там
                    # (В parse_yandex_card мы уже пробовали, но может не вышло)
                    # ...

                    # 1. Используем логику пользователя (селекторы)
                    # Selector: body > ... > div.business-full-items-grouped-view__content

                    groups = page.query_selector_all("div.business-full-items-grouped-view__content > div")
                    for group in groups:
                        # Category title?
                        cat_title_el = group.query_selector("div.business-full-items-grouped-view__title")
                        cat_title = cat_title_el.inner_text() if cat_title_el else "Другое"

                        items = group.query_selector_all(
                            "div.business-full-items-grouped-view__item, div.related-product-view"
                        )
                        if not items:
                            # Try user selector
                            items = group.query_selector_all(
                                "div.business-full-items-grouped-view__items._grid > div"
                            )

                        for item in items:
                            try:
                                name_el = item.query_selector("div.related-product-view__title")
                                price_el = item.query_selector("div.related-product-view__price")
                                if name_el:
                                    products_html.append(
                                        {
                                            "name": name_el.inner_text(),
                                            "price": price_el.inner_text() if price_el else "",
                                            "category": cat_title,
                                            "description": "",
                                            "photo": "",
                                        }
                                    )
                            except Exception:
                                pass

                    # 2. Если не вышло - пробуем функцию из старого парсера
                    if not products_html:
                        print("🔄 Пробуем функцию parse_products из yandex_maps_scraper...")
                        try:
                            from yandex_maps_scraper import parse_products

                            products_html = parse_products(page)
                        except ImportError:
                            print("⚠️ Не удалось импортировать parse_products")

                    if products_html:
                        print(f"✅ HTML Fallback нашел {len(products_html)} услуг")
                        current = data.get("products", [])
                        current.extend(products_html)
                        data["products"] = current

            except Exception as e:
                print(f"⚠️ Ошибка user-selector HTML parsing: {e}")

            # Пробуем еще раз получить title если нет
            if not data.get("title"):
                try:
                    title_el = page.query_selector("h1.orgpage-header-view__header")
                    if title_el:
                        data["title"] = title_el.inner_text()
                except Exception:
                    pass

        # DEBUG BUNDLE (dev): сохранить сводку по странице и перехваченным данным (только при наличии bundle)
        if self.debug_bundle_dir:
            try:
                debug_dir = self.debug_bundle_dir
                os.makedirs(debug_dir, exist_ok=True)

                final_url = page.url
                page_title = ""
                try:
                    page_title = page.title()
                except Exception:
                    pass

                html_content = ""
                try:
                    html_content = page.content()
                except Exception:
                    pass
                html_length = len(html_content or "")

                intercepted_json_count = len(self.api_responses)
                all_urls = list(self.api_responses.keys())
                last_10_urls = all_urls[-10:]

                # Топ-3 самых крупных JSON-ответа по длине body
                sized = []
                for u, info in self.api_responses.items():
                    try:
                        body = info.get("data")
                        body_str = json.dumps(body, ensure_ascii=False)
                        sized.append((u, len(body_str)))
                    except Exception:
                        continue
                sized.sort(key=lambda x: x[1], reverse=True)
                top_3_urls = [u for (u, _) in sized[:3]]

                # Информация о cookies и доменах
                cookie_domains = set()
                final_host = ""
                try:
                    parsed = urlparse(final_url)
                    final_host = parsed.hostname or ""
                except Exception:
                    final_host = ""

                try:
                    cookies = context.cookies()
                    for c in cookies:
                        dom = c.get("domain")
                        if dom:
                            cookie_domains.add(dom)
                except Exception:
                    pass

                # Признаки блокировки / капчи
                blocked_flags = {
                    "has_captcha_text": any(
                        kw in (page_title or "")
                        for kw in ["Ой!", "Captcha", "Robot", "Вы не робот"]
                    ),
                    "html_contains_captcha": ("smart-captcha" in (html_content or "")),
                }

                timestamp = int(time.time() * 1000)
                safe_org = (self.org_id or "unknown")[:32]
                summary_name = f"debug_{timestamp}_{safe_org}.json"
                html_name = f"debug_{timestamp}_{safe_org}.html"
                screenshot_name = f"debug_{timestamp}_{safe_org}.png"

                summary_path = os.path.join(debug_dir, summary_name)
                html_path = os.path.join(debug_dir, html_name)
                screenshot_path = os.path.join(debug_dir, screenshot_name)

                debug_summary = {
                    "final_url": final_url,
                    "page_title": page_title,
                    "html_length": html_length,
                    "intercepted_json_count": intercepted_json_count,
                    "last_10_json_urls": last_10_urls,
                    "top_3_largest_json_urls": top_3_urls,
                    "cookie_domains": sorted(cookie_domains),
                    "final_host": final_host,
                    "blocked_flags": blocked_flags,
                    "org_id": self.org_id,
                }

                # Поиск ключевых путей в крупнейших JSON-ответах
                target_keys = [
                    "address",
                    "address_name",
                    "fullAddress",
                    "rating",
                    "score",
                    "ratingData",
                    "rubrics",
                    "categories",
                    "rubric",
                ]
                found_key_paths: Dict[str, List[Dict[str, str]]] = {}
                for u in top_3_urls:
                    info = self.api_responses.get(u)
                    if not info:
                        continue
                    data = info.get("data")
                    try:
                        paths = _find_paths(data, target_keys)
                        for key, items in paths.items():
                            bucket = found_key_paths.setdefault(key, [])
                            # лимитируем общий размер по ключу
                            for item in items:
                                if len(bucket) >= 30:
                                    break
                                bucket.append({"url": u, **item})
                    except Exception:
                        continue

                if found_key_paths:
                    debug_summary["found_key_paths"] = found_key_paths

                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(debug_summary, f, ensure_ascii=False, indent=2)

                if html_content:
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)

                try:
                    page.screenshot(path=screenshot_path, full_page=True)
                except Exception:
                    pass

                print(f"💾 Debug bundle saved: {summary_name}, {html_name}, {screenshot_name}")
            except Exception as e:
                print(f"⚠️ Failed to save debug bundle: {e}")

        # DEV-лог по итоговым полям
        try:
            cats = data.get("categories") or []
            if isinstance(cats, list):
                categories_count = len(cats)
            elif cats:
                categories_count = 1
            else:
                categories_count = 0

            quality_score = None
            meta = data.get("_meta")
            if isinstance(meta, dict):
                quality_score = meta.get("quality_score")

            print(
                f"DEV summary: title='{str(data.get('title', ''))[:80]}', "
                f"address_present={bool(data.get('address'))}, "
                f"rating='{data.get('rating', '')}', "
                f"reviews_count={data.get('reviews_count')}, "
                f"categories_count={categories_count}, "
                f"quality_score={quality_score}"
            )
        except Exception:
            pass

        # Канонический debug bundle для расследований:
        # request_url.txt, final_url.txt, http_status.txt, page.html, payload.json
        if self.debug_bundle_dir:
            try:
                bundle_dir = self.debug_bundle_dir
                os.makedirs(bundle_dir, exist_ok=True)

                # HTML последней страницы — всегда сохраняем
                try:
                    page_html = page.content()
                except Exception:
                    page_html = html_content or ""
                with open(os.path.join(bundle_dir, "page.html"), "w", encoding="utf-8") as f:
                    f.write(page_html or "")

                # Исходный URL
                try:
                    with open(os.path.join(bundle_dir, "request_url.txt"), "w", encoding="utf-8") as f:
                        f.write(initial_url or "")
                except Exception:
                    pass

                # Финальный URL
                try:
                    with open(os.path.join(bundle_dir, "final_url.txt"), "w", encoding="utf-8") as f:
                        f.write(final_url or "")
                except Exception:
                    pass

                # HTTP статус основного запроса
                try:
                    with open(os.path.join(bundle_dir, "http_status.txt"), "w", encoding="utf-8") as f:
                        f.write("" if main_http_status is None else str(main_http_status))
                except Exception:
                    pass

                # Сырой payload (итоговый card_data)
                try:
                    with open(os.path.join(bundle_dir, "payload.json"), "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"⚠️ Failed to write payload.json: {e}")
            except Exception as e:
                print(f"⚠️ Failed to write canonical debug bundle files: {e}")

        print(
            f"✅ Парсинг завершен. Найдено: название='{data.get('title', '')}', адрес='{data.get('address', '')}'"
        )
        return data
    
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
            'products': [],
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
                if org_data:
                    print(f"✅ Извлечены данные организации из location-info API")
                    data.update(org_data)
            
            # Специальная обработка для fetchGoods/Prices API
            elif 'fetchGoods' in url or 'prices' in url.lower() or 'goods' in url.lower() or 'product' in url.lower() or 'search' in url.lower() or 'catalog' in url.lower():
                products = self._extract_products_from_api(json_data)
                if products:
                    print(f"✅ Извлечено {len(products)} услуг/товаров из API запроса")
                    current_products = data.get('products', [])
                    current_products.extend(products)
                    data['products'] = current_products
            
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
        
        # 2. Если продукты не найдены по URL, ищем во ВСЕХ ответах (Brute Force)
        if not data.get('products'):
            print("⚠️ Товары не найдены по URL фильтру, ищем во всех ответах...")
            for url, response_info in self.api_responses.items():
                # Пропускаем уже обработанные (хотя extract_products идемпотентна, лучше не дублировать логику)
                # Но проще просто пройтись
                try:
                    json_data = response_info['data']
                    products = self._extract_products_from_api(json_data)
                    if products:
                        print(f"✅ Извлечено {len(products)} услуг из API (Brute Force): {url[-50:]}")
                        current_products = data.get('products', [])
                        current_products.extend(products)
                        data['products'] = current_products
                        break # Нашли - выходим, чтобы не дублировать если несколько чанков
                except:
                    pass
        
        # Deduplicate products by name and price
        if data.get('products'):
            unique_products = {}
            for p in data['products']:
                # Key: Name + Price (to distinguish "Haircut" 500 vs "Haircut" 1000)
                # Normalize name to lower case to catch case sensitivity issues
                key = (p.get('name', '').strip(), p.get('price', '').strip())
                if key not in unique_products:
                    unique_products[key] = p
            data['products'] = list(unique_products.values())
            print(f"✅ Уникальных услуг после дедупликации: {len(data['products'])}")
        
        # Группируем товары по категориям (для совместимости с отчетом)
        if data.get('products'):
            raw_products = data['products']
            grouped_products = {}
            for prod in raw_products:
                cat = prod.get('category', 'Другое')
                if not cat:
                    cat = 'Другое'
                if cat not in grouped_products:
                    grouped_products[cat] = []
                grouped_products[cat].append(prod)
            
            final_products = []
            for cat, items in grouped_products.items():
                final_products.append({
                    'category': cat,
                    'items': items
                })
            data['products'] = final_products
        
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
                title_cand = ''
                if 'name' in data:
                    title_cand = data['name']
                elif 'title' in data:
                    title_cand = data['title']
                
                # Filter out generic toponyms
                if title_cand and title_cand not in ['Санкт-Петербург', 'Россия', 'Яндекс Карты', 'Москва']:
                    result['title'] = title_cand
                
                # Ищем адрес (стандартный ключ + альтернативы для разных эндпоинтов)
                addr_val = None
                if 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        addr_val = addr.get('formatted', '') or addr.get('full', '') or addr.get('text', '') or str(addr)
                    else:
                        addr_val = str(addr)
                if not addr_val:
                    addr_val = data.get('address_name') or data.get('fullAddress') or data.get('full_address') or ''
                if addr_val and isinstance(addr_val, str) and len(addr_val.strip()) > 2:
                    _set_if_empty(result, "address", addr_val.strip())
                
                # Ищем рейтинг
                if 'rating' in data:
                    rating = data['rating']
                    if isinstance(rating, (int, float)):
                        _set_if_empty(result, "rating", str(rating))
                    elif isinstance(rating, dict):
                        _set_if_empty(
                            result,
                            "rating",
                            str(rating.get('value', rating.get('score', rating.get('val', '')))),
                        )
                elif 'score' in data:
                    _set_if_empty(result, "rating", str(data['score']))
                
                # Ищем количество отзывов
                if 'reviewsCount' in data:
                    try:
                        _set_if_empty(result, "reviews_count", int(data['reviewsCount']))
                    except (TypeError, ValueError):
                        pass
                elif 'reviews_count' in data:
                    try:
                        _set_if_empty(result, "reviews_count", int(data['reviews_count']))
                    except (TypeError, ValueError):
                        pass
                
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
                title_cand = ''
                if 'name' in data:
                    title_cand = data['name']
                elif 'title' in data:
                    title_cand = data['title']
                
                # Filter out generic toponyms
                if title_cand:
                    if title_cand in ['Санкт-Петербург', 'Россия', 'Яндекс Карты', 'Москва']:
                        # print(f"⚠️ [Parser] Ignored title '{title_cand}' (in blacklist)") 
                        pass # Don't spam, but we skip it
                    else:
                        # print(f"✅ [Parser] Found title: {title_cand}")
                        result['title'] = title_cand
                
                # Ищем адрес (стандартный ключ + альтернативы для разных эндпоинтов)
                addr_val = None
                if 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        addr_val = addr.get('formatted', '') or addr.get('full', '') or addr.get('text', '') or str(addr)
                    else:
                        addr_val = str(addr)
                if not addr_val:
                    addr_val = data.get('address_name') or data.get('fullAddress') or data.get('full_address') or ''
                if addr_val and isinstance(addr_val, str) and len(addr_val.strip()) > 2:
                    result['address'] = addr_val.strip()
                
                # Ищем рейтинг
                if 'rating' in data:
                    rating = data['rating']
                    if isinstance(rating, (int, float)):
                        result['rating'] = str(rating)
                    elif isinstance(rating, dict):
                        result['rating'] = str(rating.get('value', rating.get('score', '')))
                
                # Fallback rating
                elif 'score' in data:
                     result['rating'] = str(data['score'])

                # Ищем рейтинг внутри ratingData (часто бывает в location-info)
                elif 'ratingData' in data:
                    rd = data['ratingData']
                    if isinstance(rd, dict):
                         val = rd.get('rating') or rd.get('value') or rd.get('score')
                         if val: result['rating'] = str(val)
                         
                         count = rd.get('count') or rd.get('reviewCount')
                         if count: result['reviews_count'] = int(count)
                
                # Ищем количество отзывов
                if 'reviewsCount' in data:
                    result['reviews_count'] = int(data['reviewsCount'])
                elif 'reviews_count' in data:
                    result['reviews_count'] = int(data['reviews_count'])
                
                # Ищем категории / рубрики
                if 'rubrics' in data and isinstance(data['rubrics'], list):
                    names = []
                    for r in data['rubrics']:
                        if isinstance(r, dict):
                            n = r.get('name') or r.get('label')
                            if n:
                                names.append(str(n))
                    if names:
                        result['categories'] = names
                elif 'categories' in data:
                    cats = data['categories']
                    if isinstance(cats, list) and cats:
                        # Уже список строк или объектов
                        result['categories'] = cats
                    elif isinstance(cats, dict) and cats:
                        result['categories'] = [cats]
                elif 'rubric' in data:
                    rub = data['rubric']
                    if isinstance(rub, str) and rub.strip():
                        result['categories'] = [rub.strip()]
                    elif isinstance(rub, dict):
                        n = rub.get('name') or rub.get('label')
                        if n:
                            result['categories'] = [str(n)]
                
                # Ищем категории / рубрики
                if 'rubrics' in data and isinstance(data['rubrics'], list):
                    names = []
                    for r in data['rubrics']:
                        if isinstance(r, dict):
                            n = r.get('name') or r.get('label')
                            if n:
                                names.append(str(n))
                    if names:
                        _extend_unique(result, 'categories', names)
                elif 'categories' in data:
                    cats = data['categories']
                    if isinstance(cats, list) and cats:
                        _extend_unique(result, 'categories', cats)
                    elif isinstance(cats, dict) and cats:
                        _extend_unique(result, 'categories', [cats])
                elif 'rubric' in data:
                    rub = data['rubric']
                    if isinstance(rub, str) and rub.strip():
                        _extend_unique(result, 'categories', [rub.strip()])
                    elif isinstance(rub, dict):
                        n = rub.get('name') or rub.get('label')
                        if n:
                            _extend_unique(result, 'categories', [str(n)])
                
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

        # Fallback по наиболее частым путям (payload.company.*)
        try:
            addr_nested = (
                _get_nested(json_data, "payload.company.address.formatted")
                or _get_nested(json_data, "payload.company.address_name")
                or _get_nested(json_data, "payload.company.fullAddress")
            )
            _set_if_empty(result, "address", addr_nested)
        except Exception:
            pass

        try:
            rating_nested = (
                _get_nested(json_data, "payload.company.ratingData.rating")
                or _get_nested(json_data, "payload.company.ratingData.score")
            )
            _set_if_empty(result, "rating", rating_nested)
        except Exception:
            pass

        try:
            cnt = _get_nested(json_data, "payload.company.ratingData.count")
            if isinstance(cnt, (int, float, str)):
                try:
                    cnt_int = int(cnt)
                    _set_if_empty(result, "reviews_count", cnt_int)
                except ValueError:
                    pass
        except Exception:
            pass

        try:
            rubrics = _get_nested(json_data, "payload.company.rubrics") or []
            names = []
            if isinstance(rubrics, list):
                for r in rubrics:
                    if isinstance(r, dict):
                        n = r.get("name") or r.get("label")
                        if n:
                            names.append(str(n))
            if names:
                _extend_unique(result, "categories", names)
        except Exception:
            pass

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
                
                # Адрес: стандартный ключ + альтернативы (разные эндпоинты Яндекса)
                addr_val = None
                if 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        addr_val = addr.get('formatted', '') or addr.get('full', '') or addr.get('text', '') or str(addr)
                    else:
                        addr_val = str(addr)
                if not addr_val and 'address_name' in data:
                    addr_val = data.get('address_name') or ''
                if not addr_val and 'fullAddress' in data:
                    addr_val = data.get('fullAddress') or ''
                if not addr_val and 'full_address' in data:
                    addr_val = data.get('full_address') or ''
                if addr_val and isinstance(addr_val, str) and len(addr_val.strip()) > 2:
                    _set_if_empty(result, "address", addr_val.strip())
                
                if 'rating' in data:
                    rating = data['rating']
                    if isinstance(rating, (int, float)):
                        _set_if_empty(result, "rating", str(rating))
                    elif isinstance(rating, dict):
                         _set_if_empty(
                             result,
                             "rating",
                             str(rating.get('value', rating.get('score', rating.get('val', '')))),
                         )
                elif 'score' in data:
                    _set_if_empty(result, "rating", str(data['score']))
                
                # Support modularPin rating (Yandex Update)
                if 'modularPin' in data and isinstance(data['modularPin'], dict):
                    hints = data['modularPin'].get('subtitleHints', [])
                    for hint in hints:
                        if hint.get('type') == 'RATING':
                             result['rating'] = str(hint.get('text', ''))
                             break
                
                if 'reviewsCount' in data or 'reviews_count' in data:
                    try:
                        _set_if_empty(
                            result,
                            "reviews_count",
                            int(data.get('reviewsCount') or data.get('reviews_count', 0)),
                        )
                    except (TypeError, ValueError):
                        pass
                
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
                
                # Категории / рубрики
                if 'rubrics' in data and isinstance(data['rubrics'], list):
                    names = []
                    for r in data['rubrics']:
                        if isinstance(r, dict):
                            n = r.get('name') or r.get('label')
                            if n:
                                names.append(str(n))
                    if names:
                        _extend_unique(result, 'categories', names)
                elif 'categories' in data:
                    cats = data['categories']
                    if isinstance(cats, list) and cats:
                        _extend_unique(result, 'categories', cats)
                    elif isinstance(cats, dict) and cats:
                        _extend_unique(result, 'categories', [cats])
                elif 'rubric' in data:
                    rub = data['rubric']
                    if isinstance(rub, str) and rub.strip():
                        _extend_unique(result, 'categories', [rub.strip()])
                    elif isinstance(rub, dict):
                        n = rub.get('name') or rub.get('label')
                        if n:
                            _extend_unique(result, 'categories', [str(n)])
                
                # Рекурсивно обходим вложенные объекты
                for key, value in data.items():
                    extract_nested(value, f"{path}.{key}")
            
            elif isinstance(data, list):
                for item in data:
                    extract_nested(item, path)
        
        extract_nested(json_data)

        # Fallback по наиболее частым путям (payload.company.*)
        try:
            addr_nested = (
                _get_nested(json_data, "payload.company.address.formatted")
                or _get_nested(json_data, "payload.company.address_name")
                or _get_nested(json_data, "payload.company.fullAddress")
            )
            _set_if_empty(result, "address", addr_nested)
        except Exception:
            pass

        try:
            rating_nested = (
                _get_nested(json_data, "payload.company.ratingData.rating")
                or _get_nested(json_data, "payload.company.ratingData.score")
            )
            _set_if_empty(result, "rating", rating_nested)
        except Exception:
            pass

        try:
            cnt = _get_nested(json_data, "payload.company.ratingData.count")
            if isinstance(cnt, (int, float, str)):
                try:
                    cnt_int = int(cnt)
                    _set_if_empty(result, "reviews_count", cnt_int)
                except ValueError:
                    pass
        except Exception:
            pass

        try:
            rubrics = _get_nested(json_data, "payload.company.rubrics") or []
            names = []
            if isinstance(rubrics, list):
                for r in rubrics:
                    if isinstance(r, dict):
                        n = r.get("name") or r.get("label")
                        if n:
                            names.append(str(n))
            if names:
                _extend_unique(result, "categories", names)
        except Exception:
            pass

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
            
            # Извлекаем дату (может быть в разных форматах)
            date_fields = [
                'date', 'publishedAt', 'published_at', 'createdAt', 'created_at',
                'time', 'timestamp', 'created', 'published',
                'dateCreated', 'datePublished', 'reviewDate', 'review_date',
                'updatedTime'
            ]
            date_raw = next((item.get(field) for field in date_fields if item.get(field)), None)

            date = ''
            if date_raw:
                # Если это timestamp (число)
                if isinstance(date_raw, (int, float)):
                    try:
                        from datetime import datetime
                        # Проверяем, в миллисекундах или секундах
                        if date_raw > 1e10:  # Вероятно миллисекунды
                            date = datetime.fromtimestamp(date_raw / 1000.0).isoformat()
                        else:  # Секунды
                            date = datetime.fromtimestamp(date_raw).isoformat()
                    except Exception as e:
                        print(f"⚠️ Ошибка парсинга timestamp {date_raw}: {e}")
                        date = str(date_raw)
                # Если это строка ISO формата
                elif isinstance(date_raw, str):
                    # Пробуем распарсить как ISO
                    try:
                        from datetime import datetime
                        # Убираем Z и заменяем на +00:00
                        date_clean = date_raw.replace('Z', '+00:00')
                        datetime.fromisoformat(date_clean)  # Проверяем валидность
                        date = date_clean
                    except:
                        # Если не ISO, оставляем как есть (будет парситься в worker.py)
                        date = date_raw
                else:
                    date = str(date_raw)
            
            # Логируем дату отзыва (только для первых 5 отзывов)
            if date and len(reviews) < 5:
                print(f"📅 Дата отзыва извлечена: {date}")
            elif not date and len(reviews) < 5:
                print(f"⚠️ Дата отзыва не найдена. Доступные поля: {list(item.keys())}")
            
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
                    if response_text:
                        print(f"✅ Извлечен ответ организации: {response_text[:100]}...")
                else:
                    response_text = str(owner_comment)
                    if response_text:
                        print(f"✅ Извлечен ответ организации (строка): {response_text[:100]}...")
            
            # Логируем дату отзыва
            if date:
                print(f"📅 Дата отзыва: {date}")
            
            if text:
                review_data = {
                    'author': author_name or 'Анонимный пользователь',
                    'rating': rating,
                    'text': text,
                    'date': date,
                    'org_reply': response_text,  # Маппинг на org_reply для совместимости с worker.py
                    'response_text': response_text,  # Оставляем для обратной совместимости
                    'response_date': response_date,
                    'has_response': bool(response_text)
                }
                if response_text:
                    print(f"✅ Отзыв с ответом: автор={author_name}, рейтинг={rating}, ответ={response_text[:50]}...")
                return review_data
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
                        # LOGGING STRUCTURE
                        if len(data[key]) > 0:
                            item0 = data[key][0]
                            if isinstance(item0, dict):
                                print(f"🔍 DEBUG POSTS: Found list in '{key}', Item keys: {list(item0.keys())}")

                        for item in data[key]:
                            if isinstance(item, dict):
                                # Извлекаем дату (может быть в разных форматах)
                                date_fields = [
                                    'date', 'publishedAt', 'published_at', 'createdAt', 'created_at',
                                    'time', 'timestamp', 'created', 'published',
                                    'dateCreated', 'datePublished', 'updatedTime'
                                ]
                                
                                date_raw = None
                                for field in date_fields:
                                    val = item.get(field)
                                    if val:
                                        date_raw = val
                                        break
                                
                                # Fallback: check for nested date object (e.g. date: { value: ... })
                                if not date_raw and isinstance(item.get('date'), dict):
                                    date_raw = item.get('date').get('value')

                                date = ''
                                if date_raw:
                                    # Если это timestamp (число)
                                    if isinstance(date_raw, (int, float)):
                                        try:
                                            from datetime import datetime
                                            # Проверяем, в миллисекундах или секундах
                                            if date_raw > 1e10:  # Вероятно миллисекунды
                                                date = datetime.fromtimestamp(date_raw / 1000.0).isoformat()
                                            else:  # Секунды
                                                date = datetime.fromtimestamp(date_raw).isoformat()
                                        except Exception as e:
                                            print(f"⚠️ Error parsing timestamp {date_raw}: {e}")
                                    # Если это строка ISO формата
                                    elif isinstance(date_raw, str):
                                        try:
                                            # Убираем Z и заменяем на +00:00
                                            date_clean = date_raw.replace('Z', '+00:00')
                                            date = date_clean
                                        except:
                                            date = date_raw
                                
                                if not date:
                                    print(f"⚠️ DEBUG POSTS: No date found for item. Keys: {list(item.keys())}")
                                    if 'date' in item:
                                        print(f"   Date field content: {item['date']}")

                                post = {
                                    'title': item.get('title', ''),
                                    'text': item.get('text', item.get('content', item.get('message', ''))),
                                    'date': date,
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
        if posts:
            print(f"✅ Извлечено {len(posts)} новостей/постов")
            # Логируем первую новость для отладки
            print(f"📰 Пример новости: {posts[0].get('title', '')[:50]}... ({posts[0].get('date', 'нет даты')})")
        return posts
    
    def _extract_products_from_api(self, json_data: Any) -> List[Dict[str, Any]]:
        """Извлекает товары/услуги из API"""
        products = []
        
        def find_products(data):
            if isinstance(data, dict):
                # LOGGING: Print all keys if we suspect this dictates products but we missed it
                if any(k in data for k in ['data', 'result', 'search', 'goods', 'items']):
                    # Too verbose to print everything, just keys
                    pass 

                # Ищем список товаров
                # Ищем список товаров
                # Убрали 'features' (это свойства карты) и 'items' (слишком общее, часто это организации)
                # 'items' оставим, но с жесткой проверкой
                target_keys = ['goods', 'products', 'prices', 'searchResult', 'results', 'catalog', 'menu', 'services', 'items', 'categoryItems']
                
                for key in target_keys:
                    if key in data and isinstance(data[key], list):
                         if len(data[key]) > 0:
                            item0 = data[key][0]
                            if isinstance(item0, dict):
                                 # Debug log
                                 if any(k in item0 for k in ['name', 'title', 'price', 'text']):
                                     pass # print(f"🔍 DEBUG PRODUCTS: Found list in '{key}'...")
                        
                         for item in data[key]:
                            if isinstance(item, dict):
                                # 1. ПРОВЕРКА: Это товар или организация/фича?
                                # Организации обычно имеют ratingData, workingTime, geoId
                                if any(k in item for k in ['ratingData', 'workingTime', 'geoId', 'rubricId', 'stops']):
                                    continue
                                
                                # Фичи карты (features) часто имеют 'id', 'value', 'type', но не имеют price
                                if 'type' in item and 'value' in item and 'price' not in item:
                                    continue
                                
                                # Check if it's a product
                                name = item.get('name', item.get('title', ''))
                                
                                # Deep search for name if not found at top level
                                if not name and 'name' in item.get('data', {}):
                                    name = item.get('data', {}).get('name')

                                if not name:
                                    text_val = item.get('text', '')
                                    if text_val and len(text_val) < 100: 
                                         name = text_val
                                
                                if not name:
                                    continue
                                
                                # --- SEMI-STRICT PRICE CHECK ---
                                # Relaxed Rule (2026-01-30): Allow items without price IF they are not obvious map features.
                                # Previously we required price for 'items', 'searchResult', etc. to avoid "Toilets", "Entrances".
                                # Now we use a blacklist and name length check.
                                
                                has_price = False
                                price_val = ''
                                
                                price_obj = item.get('minPrice', {}) or item.get('price', {})
                                if isinstance(price_obj, dict):
                                     val = price_obj.get('value')
                                     text = price_obj.get('text')
                                     if val or text:
                                         has_price = True
                                         price_val = text or str(val)
                                elif 'price' in item:
                                     val = item['price']
                                     if val:
                                         has_price = True
                                         price_val = str(val)
                                
                                if key in ['items', 'searchResult', 'results', 'categoryItems'] and not has_price:
                                    # Check blacklist for common map features
                                    junk_terms = ['вход', 'туалет', 'парковка', 'банкомат', 'оплата', 'entrance', 'toilet', 'parking', 'atm', 'wc', 'этаж']
                                    name_lower = name.lower()
                                    
                                    # If name matches junk or is very short (likely not a service), skip
                                    is_junk = any(term in name_lower for term in junk_terms)
                                    if is_junk or len(name) < 3:
                                         continue
                                    
                                    # Otherwise, allow it (Oliver has services without prices)
                                    pass
                                
                                # Категория
                                category = ''
                                if isinstance(item.get('category'), dict):
                                    category = item.get('category').get('name', '')
                                else:
                                    category = str(item.get('category', ''))
                                
                                # Описание
                                description = item.get('description', '')
                                
                                # Фото
                                photo = ''
                                if isinstance(item.get('image'), dict):
                                    photo = item.get('image').get('url', '')
                                elif isinstance(item.get('photos'), list) and len(item['photos']) > 0:
                                     photo = item['photos'][0].get('urlTemplate', '')

                                products.append({
                                    'name': name,
                                    'price': price_val,
                                    'description': description,
                                    'category': category,
                                    'photo': photo
                                })
                
                # Рекурсивный поиск
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        find_products(value)
            
            elif isinstance(data, list):
                for item in data:
                    find_products(item)
                    
        find_products(json_data)
        if len(products) > 0:
            print(f"📦 DEBUG PRODUCTS: Extracted {len(products)} total items")
        return products
    
    def _fallback_html_parsing(self, page, url: str) -> Dict[str, Any]:
        """Fallback на HTML парсинг, если API не сработал"""
        print("🔄 Используем fallback HTML парсинг...")
        
        # Импортируем функции из оригинального парсера
        try:
            from yandex_maps_scraper import parse_overview_data, parse_reviews, parse_news, parse_photos, get_photos_count, parse_features, parse_competitors, parse_products
            
            data = parse_overview_data(page)
            data['url'] = url
            
            reviews_data = parse_reviews(page)
            data['reviews'] = reviews_data.get('items', [])
            data['news'] = parse_news(page)
            data['photos_count'] = get_photos_count(page)
            data['photos'] = parse_photos(page)
            data['features_full'] = parse_features(page)
            data['competitors'] = parse_competitors(page)
            data['products'] = parse_products(page)
            
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


def parse_yandex_card(
    url: str,
    keep_open_on_captcha: bool = False,
    session_registry: Optional[Dict[str, BrowserSession]] = None,
    session_id: Optional[str] = None,
    debug_bundle_id: Optional[str] = None,
    **session_kwargs: Any,
) -> Dict[str, Any]:
    """
    Оркестратор для парсинга Яндекс.Карт c поддержкой human-in-the-loop.

    - управляет жизненным циклом BrowserSession через BrowserSessionManager
    - сам парсер работает только с готовой сессией (session.page/session.context)
    """
    manager = BrowserSessionManager()
    session: Optional[BrowserSession] = None

    # Валидация разрешённых kwargs для сессии
    unknown = set(session_kwargs.keys()) - ALLOWED_SESSION_KWARGS
    if unknown:
        msg = f"Unknown session kwargs in parse_yandex_card: {unknown}"
        env = os.getenv("FLASK_ENV", "").lower()
        is_debug_env = env in ("development", "dev", "debug", "test", "testing")
        if is_debug_env:
            raise ValueError(msg)
        else:
            print(f"⚠️ {msg}")
            # В production — просто отбрасываем неизвестные ключи
            for k in list(unknown):
                session_kwargs.pop(k, None)

    # 1. Режим resume: берём сессию из registry по session_id
    if session_id and session_registry is not None:
        session = manager.get(session_registry, session_id)
        if session is None:
            return {
                "error": "captcha_session_lost",
                "captcha_session_id": session_id,
            }
    else:
        # 2. Первый заход: открываем новую сессию
        session = manager.open_session(
            headless=session_kwargs.get("headless", True),
            cookies=session_kwargs.get("cookies"),
            user_agent=session_kwargs.get("user_agent"),
            viewport=session_kwargs.get("viewport"),
            locale=session_kwargs.get("locale", "ru-RU"),
            timezone_id=session_kwargs.get("timezone_id", "Europe/Moscow"),
            proxy=session_kwargs.get("proxy"),
            launch_args=session_kwargs.get("launch_args"),
            init_scripts=session_kwargs.get("init_scripts"),
            keep_open=keep_open_on_captcha,
            geolocation=session_kwargs.get("geolocation"),
        )

    parser = YandexMapsInterceptionParser(debug_bundle_id=debug_bundle_id)

    result: Dict[str, Any]
    try:
        result = parser.parse_yandex_card(url, session=session)
    except Exception:
        # При любой ошибке — всегда закрываем сессию (она больше не пригодна)
        if session:
            manager.close_session(session)
            if session_registry is not None and session_id:
                session_registry.pop(session_id, None)
        raise

    # Капча + human-in-the-loop
    if isinstance(result, dict) and result.get("error") == "captcha_detected":
        # Если можно держать сессию открытой и есть registry — паркуем
        if keep_open_on_captcha and session_registry is not None and session:
            parked_id = manager.park(session_registry, session)
            result["captcha_session_id"] = parked_id
            result["captcha_needs_human"] = True
            return result

        # Иначе: некуда парковать — закрываем сессию, но помечаем, что нужен человек
        if session:
            manager.close_session(session)
            if session_registry is not None and session_id:
                session_registry.pop(session_id, None)
        result["captcha_needs_human"] = True
        return result

    # Обычный кейс: сессию всегда закрываем
    if session:
        manager.close_session(session)
        # Если это resume — чистим registry
        if session_registry is not None and session_id:
            session_registry.pop(session_id, None)

    return result


if __name__ == "__main__":
    # Тестирование
    test_url = "https://yandex.ru/maps/org/gagarin/180566191872/"
    result = parse_yandex_card(test_url)
    print("\n📊 Результат парсинга:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

