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
from parsers.parse_result import ParseResult


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
            print("DEBUG: BASE RESTORED VERSION (без A–G)")

            if not url or not url.startswith(("http://", "https://")):
                raise ValueError(f"Некорректная ссылка: {url}")

            self.org_id = self.extract_org_id(url)
            if not self.org_id:
                raise ValueError(f"Не удалось извлечь org_id из URL: {url}")

            print(f"📋 Извлечен org_id: {self.org_id}")

            # Cookies для имитации браузера
            from parser_config_cookies import get_yandex_cookies

            cookies = get_yandex_cookies()
            print(f"🍪 Используем {len(cookies)} cookies")

            browser = None
            with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--disable-images",  # Не загружаем картинки для скорости
                            "--disable-blink-features=AutomationControlled",
                            "--disable-web-security",
                            "--disable-features=IsolateOrigins,site-per-process",
                        ],
                    )

                    context = browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        viewport={"width": 1920, "height": 1080},
                        device_scale_factor=1,
                    )

                    context.add_cookies(cookies)

                    # Скрываем webdriver и усиливаем антидетект
                    context.add_init_script(
                        """
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined,
                        });
                        delete navigator.__proto__.webdriver;
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5],
                        });
                        window.chrome = { runtime: {} };
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['ru-RU', 'ru'],
                        });
                    """
                    )

                    page = context.new_page()

                    # Очищаем предыдущие ответы
                    self.api_responses = {}

                    # Перехватываем все запросы/ответы
                    def handle_request(request):
                        """Легкий перехват запросов (для отладки orgcard/net-трафика)"""
                        try:
                            url_req = request.url
                            if "yandex.ru" in url_req and ("/org/" in url_req or "orgcard" in url_req):
                                # Не спамим лог, только важные org/orgcard запросы
                                print(f"🔎 REQUEST org/orgcard: {url_req[:120]}...")
                        except Exception:
                            pass

                    def handle_response(response):
                        """Обработчик для перехвата сетевых запросов"""
                        try:
                            url_resp = response.url
                            # Лёгкое логирование всех ответов (в т.ч. location-info)
                            try:
                                print(f"📥 Response: {url_resp} status={response.status}")
                            except Exception:
                                pass

                            # Ищем API запросы Яндекс.Карт
                            if "yandex.ru" in url_resp or "yandex.net" in url_resp:
                                # Проверяем, это JSON ответ?
                                content_type = response.headers.get("content-type", "")
                                if (
                                    "application/json" in content_type
                                    or "json" in url_resp.lower()
                                    or "ajax=1" in url_resp
                                ):
                                    try:
                                        # Пытаемся получить JSON
                                        json_data = response.json()

                                        # Сохраняем ответ
                                        self.api_responses[url_resp] = {
                                            "data": json_data,
                                            "status": response.status,
                                            "headers": dict(response.headers),
                                        }

                                        # Показываем только важные запросы
                                        if any(
                                            kw in url_resp
                                            for kw in [
                                                "org",
                                                "organization",
                                                "business",
                                                "company",
                                                "reviews",
                                                "feedback",
                                                "location-info",
                                            ]
                                        ):
                                            print(
                                                f"✅ Перехвачен важный API запрос: {url_resp[:100]}..."
                                            )
                                    except Exception:
                                        # Не JSON, пропускаем
                                        pass
                        except Exception:
                            # print(f"⚠️ Ошибка при перехвате ответа: {e}")
                            pass

                    # ВАЖНО: листенеры вешаем ДО goto, чтобы не пропустить ранние org/orgcard запросы
                    page.on("request", handle_request)
                    page.on("response", handle_response)

                    # Загружаем страницу
                    print("🌐 Загружаем страницу и перехватываем API запросы...")
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)

                        # Проверяем на капчу, даём время на ручное решение
                        for _ in range(24):  # до 120 секунд
                            try:
                                title = page.title()
                                is_captcha = (
                                    "Ой!" in title
                                    or "Captcha" in title
                                    or "Robot" in title
                                    or page.get_by_text(
                                        "Подтвердите, что вы не робот"
                                    ).is_visible()
                                    or page.locator(".smart-captcha").count() > 0
                                    or page.locator("input[name='smart-token']").count() > 0
                                )
                                if is_captcha:
                                    print(
                                        "⚠️ Обнаружена капча! Ждем 15 секунд... (не трогаем страницу)"
                                    )
                                    page.wait_for_timeout(15000)
                                else:
                                    break
                            except Exception:
                                break
                    except Exception:
                        print("⚠️ Страница не загрузилась полностью, но продолжаем...")

                    # === B. Явное ожидание org/orgcard ответа с проверкой OID ===
                    expected_oid = self.org_id

                    def _orgcard_predicate(response) -> bool:
                        try:
                            url_resp = response.url
                            if "yandex.ru" not in url_resp:
                                return False
                            if response.status != 200:
                                return False

                            # Основной сигнал: location-info API с нужным oid
                            if "location-info" in url_resp:
                                try:
                                    json_data = response.json()
                                    if isinstance(json_data, dict):
                                        org_block = json_data.get("organization") or {}
                                        oid_value = (
                                            org_block.get("id")
                                            or org_block.get("oid")
                                            or json_data.get("oid")
                                            or json_data.get("id")
                                        )
                                        if expected_oid and oid_value and str(oid_value) == str(
                                            expected_oid
                                        ):
                                            return True
                                except Exception:
                                    return False
                                # Если это location-info, но oid не совпал — не считаем успехом
                                return False

                            # Дополнительный сигнал: любые org/orgcard JSON'ы
                            if "/org/" not in url_resp and "orgcard" not in url_resp:
                                return False

                            content_type = response.headers.get("content-type", "")
                            if (
                                "application/json" not in content_type
                                and "json" not in url_resp.lower()
                            ):
                                return False

                            # Пытаемся вытащить oid для валидации из общих org/orgcard ответов
                            json_data = response.json()
                            oid_value = None
                            if isinstance(json_data, dict):
                                org_block = (
                                    json_data.get("organization")
                                    or json_data.get("org")
                                    or {}
                                )
                                oid_value = (
                                    org_block.get("oid")
                                    or org_block.get("id")
                                    or json_data.get("oid")
                                    or json_data.get("id")
                                )

                            if expected_oid and oid_value and str(oid_value) != str(expected_oid):
                                # Это orgcard, но не наша — не считаем успехом
                                return False

                            return True
                        except Exception:
                            return False

                    # Сначала проверяем уже перехваченные ответы (location-info мог прийти ДО ожидания)
                    orgcard_found = False
                    for url_resp, response_info in self.api_responses.items():
                        if "location-info" in url_resp:
                            try:
                                json_data = response_info.get("data", {}) or {}
                                if isinstance(json_data, dict):
                                    org_block = json_data.get("organization") or {}
                                    oid_value = (
                                        org_block.get("id")
                                        or org_block.get("oid")
                                        or json_data.get("oid")
                                        or json_data.get("id")
                                    )
                                    if expected_oid and oid_value and str(oid_value) == str(
                                        expected_oid
                                    ):
                                        print("✅ Location-info уже перехвачен с нужным OID")
                                        orgcard_found = True
                                        break
                            except Exception:
                                pass

                    if not orgcard_found:
                        try:
                            print("⏳ Ждём org/orgcard API ответ...")
                            page.wait_for_event(
                                "response",
                                predicate=_orgcard_predicate,
                                timeout=10000,
                            )
                            print("✅ Orgcard API ответ получен через wait_for_event")
                        except Exception:
                            print("❌ Orgcard API ответ не получен за 10 секунд → orgcard_not_received")
                            # Собираем расширенный список endpoint'ов с метаданными
                            endpoints = []
                            for url_resp, response_info in self.api_responses.items():
                                try:
                                    headers = response_info.get("headers") or {}
                                    endpoints.append(
                                        {
                                            "url": url_resp,
                                            "status": response_info.get("status"),
                                            "content_type": headers.get("content-type"),
                                            "has_data": bool(response_info.get("data")),
                                        }
                                    )
                                except Exception:
                                    print(
                                        f"⚠️ Ошибка при сборе raw_endpoints (timeout case) для url={url_resp[:80]}"
                                    )

                            return {
                                "error": "orgcard_not_received",
                                "_raw_capture": {
                                    "endpoints": endpoints,
                                },
                            }

                    # Double-check капчи
                    title = page.title()
                    if (
                        "Ой!" in title
                        or "Captcha" in title
                        or "Robot" in title
                        or "Вы не робот" in title
                    ):
                        print(
                            f"❌ Капча не была решена за отведённое время. Заголовок: {title}"
                        )
                        if browser:
                            browser.close()
                        return {"error": "captcha_detected"}

                    # Ожидание загрузки карточки
                    try:
                        print("⏳ Ожидание загрузки карточки организации...")
                        page.wait_for_selector(
                            "h1, div.business-card-title-view, div.card-title-view__title, "
                            "div.orgpage-header-view__header, "
                            "div.orgpage-header-view__header-wrapper > h1",
                            timeout=15000,
                        )
                        print("✅ Карточка загружена")
                    except Exception:
                        print(
                            "⚠️ Не удалось дождаться загрузки карточки. Возможно, капча не решена или бан."
                        )

                    # Проверка редиректа
                    current_url = page.url
                    title = page.title()
                    print(f"📍 Текущий URL: {current_url}, Заголовок: {title}")

                    is_business_card = False
                    try:
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
                        is_business_card = False

                    if (not is_business_card) or (
                        "yandex.ru" in current_url and "/org/" not in current_url
                    ):
                        print(
                            "⚠️ Не похоже на карточку организации! (Редирект?). Пробуем перейти по ссылке снова..."
                        )
                        try:
                            with open(
                                "debug_data/redirect_page.html", "w", encoding="utf-8"
                            ) as f:
                                f.write(page.content())
                            print(
                                "💾 Сохранена HTML страница редиректа в debug_data/redirect_page.html"
                            )
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
                        except Exception:
                            print(
                                "❌ Не удалось загрузить карточку даже после повторного перехода. Возможно бан."
                            )
                            try:
                                with open(
                                    "debug_data/failed_page_final.html",
                                    "w",
                                    encoding="utf-8",
                                ) as f:
                                    f.write(page.content())
                            except Exception:
                                pass
                    else:
                        print("✅ Страница похожа на карточку организации.")

                    # Вспомогательная функция для скролла
                    def scroll_page(times: int = 5) -> None:
                        for _ in range(times):
                            page.mouse.wheel(0, 1000)
                            time.sleep(random.uniform(0.5, 1.0))

                    extra_photos_count = 0

                    # 1. Скроллим основную страницу
                    print("📜 Скроллим основную страницу...")
                    scroll_page(3)

                    # 2. Кликаем и скроллим Отзывы (Reviews)
                    reviews_tab = page.query_selector(
                        "div.tabs-select-view__title._name_reviews"
                    )
                    if reviews_tab:
                        print("💬 Переходим во вкладку Отзывы...")
                        reviews_tab.click(force=True)
                        time.sleep(2)

                        print(
                            "📜 Скроллим отзывы (глубокий скролл - загрузка всех)..."
                        )
                        last_height = 0
                        stuck_count = 0

                        for i in range(80):
                            delta = random.randint(2000, 4000)
                            page.mouse.wheel(0, delta)
                            page.evaluate(
                                f"window.scrollBy(0, {delta//2})"
                            )
                            time.sleep(random.uniform(0.5, 1.2))

                            if i % 5 == 0:
                                page.mouse.wheel(0, -500)
                                time.sleep(0.5)
                                page.mouse.wheel(0, 500)

                            page.mouse.move(
                                random.randint(100, 800), random.randint(100, 800)
                            )

                            try:
                                more_btn = page.query_selector(
                                    "button:has-text('Показать ещё')"
                                ) or page.query_selector("div.reviews-view__more")
                                if more_btn and more_btn.is_visible():
                                    more_btn.click()
                                    time.sleep(2)
                            except Exception:
                                pass
                    else:
                        print("ℹ️ Вкладка Отзывы не найдена (селектор)")

                    # 3. Кликаем и скроллим Фото (Photos)
                    photos_tab = page.query_selector(
                        "div.tabs-select-view__title._name_gallery"
                    )
                    if photos_tab:
                        print("📷 Переходим во вкладку Фото...")
                        try:
                            photos_text = photos_tab.inner_text()
                            print(f"ℹ️ Текст вкладки фото: {photos_text}")
                            m = re.search(r"(\\d+)", photos_text)
                            if m:
                                extra_photos_count = int(m.group(1))
                        except Exception:
                            pass

                        photos_tab.click(force=True)
                        time.sleep(2)
                        print("📜 Скроллим фото...")
                        scroll_page(10)
                    else:
                        print("ℹ️ Вкладка Фото не найдена")

                    # 4. Кликаем и скроллим Новости (News/Posts)
                    try:
                        news_tab = page.query_selector(
                            "div.tabs-select-view__title._name_posts"
                        )
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
                        services_tab = page.query_selector(
                            "div.tabs-select-view__title._name_price"
                        ) or page.query_selector(
                            "div.tabs-select-view__title._name_goods"
                        )
                        if services_tab:
                            print("💰 Переходим во вкладку Цены/Услуги...")
                            services_tab.click(force=True)
                            time.sleep(3)
                            print("📜 Скроллим услуги...")
                            scroll_page(20)
                        else:
                            print("ℹ️ Вкладка Цены/Услуги не найдена")
                    except Exception as e:
                        print(f"⚠️ Ошибка при обработке услуг: {e}")

                    # Проверка верификации через HTML
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

                    # SOURCE PRIORITY PIPELINE
                    results: List[ParseResult] = []

                    try:
                        api_data = self._extract_data_from_responses()
                        if api_data:
                            api_data["is_verified"] = is_verified
                            if extra_photos_count > 0:
                                api_data["photos_count"] = extra_photos_count
                            results.append(
                                ParseResult(api_data, "yandex_api_v2", 100)
                            )
                            print("✅ API данные извлечены (quality: 100)")
                    except Exception as e:
                        print(f"⚠️ API parsing failed: {e}")

                    api_has_data = results and results[0].data and (
                        results[0].data.get("title")
                        or results[0].data.get("overview", {}).get("title")
                        or results[0].data.get("products") is not None
                    )

                    if not api_has_data:
                        print(
                            "⚠️ API не вернул данных, пробуем HTML fallback (quality: 70)..."
                        )
                        try:
                            html_data = self._fallback_html_parsing(page, url)
                            if html_data and not html_data.get("error"):
                                results.append(
                                    ParseResult(html_data, "html_fallback", 70)
                                )
                                print("✅ HTML данные извлечены (quality: 70)")
                        except Exception as e:
                            print(f"⚠️ HTML parsing failed: {e}")

                    if not results:
                        print(
                            "⚠️ API и HTML не сработали, пробуем meta tags (quality: 40)..."
                        )
                        try:
                            meta_data = self._parse_meta_tags(page, url)
                            if meta_data:
                                results.append(
                                    ParseResult(meta_data, "meta_tags", 40)
                                )
                                print("✅ Meta данные извлечены (quality: 40)")
                        except Exception as e:
                            print(f"⚠️ Meta parsing failed: {e}")

                    if not results:
                        return {"error": "all_sources_failed", "url": url}

                    results.sort(key=lambda r: r.quality_score, reverse=True)

                    final = results[0]
                    for other in results[1:]:
                        final = final.merge(other)

                    data = final.to_dict()
                    data["_parse_metadata"]["sources_used"] = [
                        r.source for r in results
                    ]

                    api_products = None
                    if results and results[0].source == "yandex_api_v2":
                        api_products = results[0].data.get("products")

                    if api_products is None:
                        print(
                            "⚠️ API не вернул данные об услугах, пробуем HTML парсинг..."
                        )
                        try:
                            from yandex_maps_scraper import parse_products

                            html_products = parse_products(page)
                            if html_products:
                                grouped_products: Dict[
                                    str, List[Dict[str, Any]]
                                ] = {}
                                for prod in html_products:
                                    cat = prod.get("category", "Другое") or "Другое"
                                    grouped_products.setdefault(cat, []).append(
                                        prod
                                    )

                                final_products: List[Dict[str, Any]] = []
                                for cat, items in grouped_products.items():
                                    final_products.append(
                                        {"category": cat, "items": items}
                                    )
                                data["products"] = final_products
                                data["_parse_metadata"]["products_source"] = (
                                    "html_fallback"
                                )
                                data["_parse_metadata"][
                                    "products_quality_score"
                                ] = 70
                                print(
                                    f"✅ Услуги найдены через HTML: {len(html_products)}"
                                )
                        except Exception as e:
                            print(f"⚠️ HTML парсинг услуг не удался: {e}")
                            data["products"] = []
                            data["_parse_metadata"]["products_source"] = "none"
                            data["_parse_metadata"]["products_quality_score"] = 0
                    elif api_products == []:
                        print("✅ API вернул пустой список услуг - услуг нет")
                        data["products"] = []
                        data["_parse_metadata"]["products_source"] = "api"
                        data["_parse_metadata"]["products_quality_score"] = 100
                    else:
                        data["_parse_metadata"]["products_source"] = "api"
                        data["_parse_metadata"]["products_quality_score"] = 100

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
                    print("✅ Извлечены данные организации из location-info API")
                    data.update(org_data)

                # Прямое извлечение базовых полей из location-info
                try:
                    organization = json_data.get("organization") or {}
                    if organization:
                        name = organization.get("name") or organization.get("title")
                        if name:
                            data["title"] = name
                        address = organization.get("address") or {}
                        if isinstance(address, dict):
                            formatted = address.get("formatted") or address.get("text")
                            if formatted:
                                data["address"] = formatted
                        phones = organization.get("phones") or []
                        if isinstance(phones, list) and phones:
                            # Берём первый телефон как основной
                            phone_raw = phones[0]
                            if isinstance(phone_raw, dict):
                                value = (
                                    phone_raw.get("formatted")
                                    or phone_raw.get("number")
                                    or phone_raw.get("value")
                                )
                                if value:
                                    data["phone"] = value
                except Exception:
                    # Не ломаем весь парсинг, если структура неожиданная
                    pass
            
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

        # Структурированный raw_capture для воркера:
        # - список всех перехваченных endpoint'ов
        # - базовая телеметрия по ответам
        raw_endpoints = []
        for url, response_info in self.api_responses.items():
            try:
                headers = response_info.get('headers') or {}
                raw_endpoints.append({
                    'url': url,
                    'status': response_info.get('status'),
                    'content_type': headers.get('content-type'),
                    'has_data': bool(response_info.get('data')),
                })
            except Exception:
                # Логгер для отладки, но не ломаем парсинг
                print(f"⚠️ Ошибка при сборе raw_endpoints для url={url[:80]}")

        data['_raw_capture'] = {
            'endpoints': raw_endpoints,
        }
        
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
                        result['rating'] = str(rating.get('value', rating.get('score', rating.get('val', ''))))
                elif 'score' in data:
                    result['rating'] = str(data['score'])
                
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
                         result['rating'] = str(rating.get('value', rating.get('score', rating.get('val', ''))))
                elif 'score' in data:
                    result['rating'] = str(data['score'])
                
                # Support modularPin rating (Yandex Update)
                if 'modularPin' in data and isinstance(data['modularPin'], dict):
                    hints = data['modularPin'].get('subtitleHints', [])
                    for hint in hints:
                        if hint.get('type') == 'RATING':
                             result['rating'] = str(hint.get('text', ''))
                             break
                
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
    
    def _parse_meta_tags(self, page, url: str) -> Dict[str, Any]:
        """Парсинг из meta тегов (самый низкий приоритет)"""
        print("🔄 Парсинг из meta тегов...")
        
        try:
            data = {'url': url}
            
            # og:title
            try:
                og_title = page.locator("meta[property='og:title']").get_attribute("content")
                if og_title:
                    title = og_title.split('|')[0].strip()
                    data['title'] = title
                    data['overview'] = {'title': title}
            except Exception:
                pass
            
            # og:description
            try:
                og_desc = page.locator("meta[property='og:description']").get_attribute("content")
                if og_desc:
                    if 'overview' not in data:
                        data['overview'] = {}
                    data['overview']['description'] = og_desc
            except Exception:
                pass
            
            # og:image (для фото)
            try:
                og_image = page.locator("meta[property='og:image']").get_attribute("content")
                if og_image:
                    data['photos'] = [{'url': og_image}]
                    data['photos_count'] = 1
            except Exception:
                pass
            
            return data if data.get('title') or data.get('overview') else None
        except Exception as e:
            print(f"❌ Ошибка парсинга meta тегов: {e}")
            return None


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

