"""
parser.py — Модуль для парсинга публичной страницы Яндекс.Карт с помощью Playwright
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import re
import random
import os

def parse_reviews_from_main_page(page):
    """Парсинг отзывов с главной страницы, если вкладка не найдена"""
    reviews = {
        "rating": "",
        "reviews_count": 0,
        "items": []
    }

    # Средняя оценка и количество отзывов
    try:
        rating_elem = page.query_selector("[class*='business-rating-badge-view__rating'], .business-summary-rating-badge-view__rating")
        if rating_elem:
            reviews["rating"] = rating_elem.inner_text().strip()

        count_elem = page.query_selector("[class*='business-rating-badge-view__reviews-count'], .business-summary-rating-badge-view__reviews-count")
        if count_elem:
            count_text = count_elem.inner_text()
            try:
                reviews["reviews_count"] = int(''.join(filter(str.isdigit, count_text)))
            except:
                reviews["reviews_count"] = 0
    except Exception as e:
        print(f"Ошибка при парсинге рейтинга с главной: {e}")

    return reviews

def parse_yandex_card(url: str) -> dict:
    """Основная функция парсинга карточки Яндекс.Карт"""
    with sync_playwright() as p:
        # Используем Firefox вместо Chromium
        print("Используем Firefox")
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            print("Переходим на страницу...")
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)

            # Проверяем на captcha
            if page.query_selector("form[action*='captcha']") or "captcha" in page.url.lower() or "Подтвердите, что запросы отправляли вы" in page.title():
                browser.close()
                print("⚠️  Обнаружена captcha! Попробуйте:")
                print("1. Открыть ссылку в браузере и пройти captcha")
                print("2. Попробовать позже")
                print("3. Использовать другую ссылку")
                return {"error": "captcha_detected", "url": url}

        except Exception as e:
            print(f"Ошибка при парсинге: {e}")
            return {"error": str(e), "url": url}
        finally:
            if browser:
                browser.close()

def parse_reviews(page):
    """Парсинг отзывов"""
    reviews = {
        "rating": "",
        "reviews_count": 0,
        "items": []
    }

    # Проверяем, не попали ли мы на страницу captcha
    if page.query_selector("form[action*='captcha']") or "captcha" in page.url.lower():
        print("Обнаружена captcha! Пропускаем парсинг отзывов.")
        return reviews

    # Клик по вкладке "Отзывы" - улучшенный поиск
    try:
        # Множественные селекторы для поиска вкладки отзывы
        reviews_tab_selectors = [
            "div[role='tab']:has-text('Отзывы')",
            "button:has-text('Отзывы')", 
            "[data-tab='reviews']",
            "div.tabs-select-view__tab:has-text('Отзывы')",
            "a:has-text('Отзывы')",
            ".tabs-menu-view__tab:has-text('Отзывы')",
            "span:has-text('Отзывы')"
        ]

        reviews_tab = None
        for selector in reviews_tab_selectors:
            try:
                reviews_tab = page.query_selector(selector)
                if reviews_tab:
                    print(f"Найдена вкладка 'Отзывы' с селектором: {selector}")
                    break
            except:
                continue

        if reviews_tab:
            reviews_tab.click()
            page.wait_for_timeout(2000)
        else:
            print("Вкладка 'Отзывы' не найдена ни одним селектором!")
            # Пробуем найти отзывы на главной странице
            return parse_reviews_from_main_page(page)

    except Exception as e:
        print(f"Ошибка при клике на вкладку 'Отзывы': {e}")
        return parse_reviews_from_main_page(page)

def parse_yandex_card(url: str) -> dict:
    """
    Парсит публичную страницу Яндекс.Карт и возвращает данные в виде словаря.
    """
    print(f"Начинаем парсинг: {url}")

    if not url or not url.startswith(('http://', 'https://')):
        raise ValueError(f"Некорректная ссылка: {url}")

    print("Используем парсинг через Playwright...")

    with sync_playwright() as p:
        try:
            # Правильные переменные окружения для Replit
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/home/runner/.cache/ms-playwright'
            os.environ['PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD'] = '0'

            browser = None
            browser_name = ""

            # Попытка запуска Chromium
            try:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox', 
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding',
                        '--disable-extensions',
                        '--disable-plugins',
                        '--disable-sync',
                        '--disable-translate',
                        '--disable-notifications',
                        '--disable-permissions-api',
                        '--disable-default-apps',
                        '--no-first-run',
                        '--no-default-browser-check',
                        '--disable-background-networking',
                        '--single-process',
                        '--disable-zygote'
                    ],
                    ignore_default_args=['--enable-automation'],
                    chromium_sandbox=False
                )
                browser_name = "Chromium"
                print("Используем Chromium")
            except Exception as e:
                print(f"Chromium недоступен: {e}")

                # Если Chromium не работает, пробуем Firefox
                try:
                    browser = p.firefox.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu'
                        ],
                        firefox_user_prefs={
                            'dom.webdriver.enabled': False,
                            'useAutomationExtension': False
                        }
                    )
                    browser_name = "Firefox"
                    print("Используем Firefox")
                except Exception as e2:
                    print(f"Firefox недоступен: {e2}")

                    # В крайнем случае пробуем WebKit
                    try:
                        browser = p.webkit.launch(
                            headless=True,
                            args=['--no-sandbox']
                        )
                        browser_name = "WebKit"
                        print("Используем WebKit")
                    except Exception as e3:
                        raise Exception(f"Все браузеры недоступны: Chromium={e}, Firefox={e2}, WebKit={e3}")

            if not browser:
                raise Exception("Не удалось запустить ни один браузер")

            # Создаем контекст с антидетектом
            context = browser.new_context(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='ru-RU',
                timezone_id='Europe/Moscow',
                viewport={'width': 1920, 'height': 1080},
                screen={'width': 1920, 'height': 1080},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                color_scheme='light',
                reduced_motion='no-preference',
                forced_colors='none',
                extra_http_headers={
                    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-User': '?1',
                    'Sec-Fetch-Dest': 'document'
                }
            )

            # Добавляем JavaScript для скрытия автоматизации
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });

                delete navigator.__proto__.webdriver;

                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });

                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en'],
                });

                window.chrome = {
                    runtime: {}
                };

                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' }),
                    }),
                });
            """)

            page = context.new_page()

            # Устанавливаем дополнительные заголовки
            page.set_extra_http_headers({
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            })

            # Переходим на страницу с увеличенным таймаутом
            print("Переходим на страницу...")
            page.goto(url, wait_until='domcontentloaded', timeout=60000)

            # Ждем загрузки контента
            time.sleep(random.uniform(3, 5))

            # Проверяем на captcha сразу после загрузки
            if page.query_selector("form[action*='captcha']") or "captcha" in page.url.lower() or "Подтвердите, что запросы отправляли вы" in page.title():
                browser.close()
                print("⚠️  Обнаружена captcha! Попробуйте:")
                print("1. Открыть ссылку в браузере и пройти captcha")
                print("2. Попробовать позже")
                print("3. Использовать другую ссылку")
                return {"error": "captcha_detected", "url": url}

            # Переход на вкладку 'Обзор'
            try:
                page.wait_for_selector("body", timeout=10000)
                overview_tab = page.query_selector("div.tabs-select-view__title._name_overview, div[role='tab']:has-text('Обзор'), button:has-text('Обзор')")
                if overview_tab:
                    overview_tab.click()
                    print("Клик по вкладке 'Обзор'")
                    page.wait_for_timeout(2000)
            except Exception as e:
                print(f"Вкладка 'Обзор' не найдена: {e}")

            # Скроллим для подгрузки контента
            page.mouse.wheel(0, 1000)
            time.sleep(2)
            page.mouse.wheel(0, 1000)
            time.sleep(2)

            data = parse_overview_data(page)
            data['url'] = url

            # Парсим остальные вкладки
            data['reviews'] = parse_reviews(page)
            data['news'] = parse_news(page)
            data['photos_count'] = get_photos_count(page)
            data['photos'] = parse_photos(page)
            data['features_full'] = parse_features(page)
            data['competitors'] = parse_competitors(page)

            # Создаем overview для отчета
            data['overview'] = {
                'title': data.get('title', ''),
                'address': data.get('address', ''),
                'phone': data.get('phone', ''),
                'site': data.get('site', ''),
                'description': data.get('description', ''),
                'categories': data.get('categories', []),
                'hours': data.get('hours', ''),
                'hours_full': data.get('hours_full', []),
                'rating': data.get('rating', ''),
                'ratings_count': data.get('ratings_count', ''),
                'reviews_count': data.get('reviews_count', ''),
                'social_links': data.get('social_links', [])
            }

            browser.close()
            print(f"Парсинг завершен ({browser_name}). Найдено: название='{data['title']}', адрес='{data['address']}'")
            return data

        except PlaywrightTimeoutError as e:
            if browser:
                browser.close()
            raise Exception(f"Тайм-аут при загрузке страницы: {e}")
        except Exception as e:
            if browser:
                browser.close()
            raise Exception(f"Ошибка при парсинге: {e}")

def parse_overview_data(page):
    """Парсит основные данные с вкладки Обзор"""
    data = {}

    # Название
    try:
        title_el = page.query_selector("h1.card-title-view__title, h1")
        data['title'] = title_el.inner_text().strip() if title_el else ''
    except Exception:
        data['title'] = ''

    # Полный адрес
    try:
        addr_elem = page.query_selector("div.business-contacts-view__address")
        if addr_elem:
            data['address'] = addr_elem.inner_text().strip()
        else:
            # Альтернативный селектор
            addr_elem = page.query_selector("[class*='business-contacts-view'] [class*='address']")
            data['address'] = addr_elem.inner_text().strip() if addr_elem else ''
    except Exception:
        data['address'] = ''

    # Клик по кнопке "Показать телефон" перед парсингом - улучшенная версия
    try:
        # Ждем появления кнопки телефона
        page.wait_for_timeout(2000)

        phone_btn_selectors = [
            "button:has-text('Показать телефон')",
            "div.business-contacts-view__phone button",
            "span:has-text('Показать телефон')",
            "button[class*='phone']",
            "[aria-label*='телефон'] button",
            "div.business-phones-view button"
        ]

        phone_clicked = False
        for selector in phone_btn_selectors:
            try:
                show_phone_btn = page.query_selector(selector)
                if show_phone_btn and show_phone_btn.is_visible():
                    print(f"Кликаем по кнопке телефона: {selector}")
                    show_phone_btn.click()
                    page.wait_for_timeout(2000)
                    phone_clicked = True
                    break
            except Exception:
                continue

        if not phone_clicked:
            print("Кнопка 'Показать телефон' не найдена")
    except Exception:
        pass

    # Телефон - улучшенный парсинг
    try:
        phone_selectors = [
            "span.business-phones-view__text",
            "div.business-contacts-view__phone-number span",
            "div.business-contacts-view__phone span",
            "span[class*='phone-text']",
            "span[class*='phone']", 
            "a[href^='tel:']",
            "div[class*='phone'] span",
            "[data-bem*='phone'] span",
            "div.business-contacts-view span[title*='+7']",
            "span[title^='+7']",
            "div.business-phones-view span",
            "span:has-text('+7')",
            "div:has-text('Показать телефон')"
        ]

        data['phone'] = ''
        for selector in phone_selectors:
            phone_elems = page.query_selector_all(selector)
            for phone_elem in phone_elems:
                phone_text = phone_elem.inner_text().strip()
                # Проверяем на наличие цифр и символов телефона
                if re.search(r'[\d+\-\(\)\s]{7,}', phone_text):
                    # Очищаем от лишних символов, оставляя только цифры, +, -, (, ), пробелы
                    phone_cleaned = re.sub(r'[^\d+\-\(\)\s]', '', phone_text).strip()
                    if len(phone_cleaned) >= 7:  # Минимальная длина телефона
                        data['phone'] = phone_cleaned
                        print(f"Найден телефон: {data['phone']}")
                        break

                # Также проверяем атрибут title
                title_attr = phone_elem.get_attribute('title')
                if title_attr and re.search(r'[\d+\-\(\)\s]{7,}', title_attr):
                    phone_cleaned = re.sub(r'[^\d+\-\(\)\s]', '', title_attr).strip()
                    if len(phone_cleaned) >= 7:
                        data['phone'] = phone_cleaned
                        print(f"Найден телефон в title: {data['phone']}")
                        break

            if data['phone']:
                break
    except Exception:
        data['phone'] = ''

    # Ближайшее метро
    try:
        metro_block = page.query_selector("div.masstransit-stops-view._type_metro")
        if metro_block:
            metro_name = metro_block.query_selector("div.masstransit-stops-view__stop-name")
            metro_dist = metro_block.query_selector("div.masstransit-stops-view__stop-distance-text")
            data['nearest_metro'] = {
                'name': metro_name.inner_text().strip() if metro_name else '',
                'distance': metro_dist.inner_text().strip() if metro_dist else ''
            }
        else:
            data['nearest_metro'] = {'name': '', 'distance': ''}
    except Exception:
        data['nearest_metro'] = {'name': '', 'distance': ''}

    # Ближайшая остановка
    try:
        stop_block = page.query_selector("div.masstransit-stops-view._type_masstransit")
        if stop_block:
            stop_name = stop_block.query_selector("div.masstransit-stops-view__stop-name")
            stop_dist = stop_block.query_selector("div.masstransit-stops-view__stop-distance-text")
            data['nearest_stop'] = {
                'name': stop_name.inner_text().strip() if stop_name else '',
                'distance': stop_dist.inner_text().strip() if stop_dist else ''
            }
        else:
            data['nearest_stop'] = {'name': '', 'distance': ''}
    except Exception:
        data['nearest_stop'] = {'name': '', 'distance': ''}

    # Сайт
    try:
        site_el = page.query_selector("a.business-urls-view__text, a[class*='url'], a[href^='http']")
        data['site'] = site_el.get_attribute('href') if site_el else ''
    except Exception:
        data['site'] = ''

    # Описание
    try:
        desc_el = page.query_selector("div.card-about-view__description-text, div[class*='description']")
        data['description'] = desc_el.inner_text().strip() if desc_el else ''
    except Exception:
        data['description'] = ''

    # Категории бизнеса (основные)
    try:
        # Сначала ищем основные категории бизнеса
        business_category_selectors = [
            "div.business-card-title-view__categories span",
            "div.business-summary-view__categories span",
            "span.business-card-title-view__category",
            "div.card-title-view__categories span",
            "[class*='business-card'] [class*='categories'] span",
            "div[class*='category'] span"
        ]

        rubric = []
        for selector in business_category_selectors:
            cats = page.query_selector_all(selector)
            if cats:
                categories = [c.inner_text().strip() for c in cats if c.inner_text().strip()]
                if categories:
                    rubric = categories
                    print(f"Найдены основные категории бизнеса: {categories}")
                    break
        data['rubric'] = rubric

        # Если основные категории не найдены, пробуем категории товаров/услуг
        data['categories'] = []

    except Exception:
        data['categories'] = []

    # Рейтинг
    try:
        rating_selectors = [
            "span.business-rating-badge-view__rating-text",
            "div.business-header-rating-view__rating span",
            "span[class*='rating-text']",
            "span.business-summary-rating-badge-view__rating-text"
        ]

        data['rating'] = ''
        for selector in rating_selectors:
            rating_el = page.query_selector(selector)
            if rating_el:
                rating_text = rating_el.inner_text().replace(',', '.').strip()
                if rating_text and rating_text != '':
                    data['rating'] = rating_text
                    break
    except Exception:
        data['rating'] = ''

    # Количество оценок
    try:
        ratings_count_el = page.query_selector("div.business-header-rating-view__text._clickable, span:has-text('оценок'), span:has-text('оценка')")
        if ratings_count_el:
            text = ratings_count_el.inner_text()
            match = re.search(r"(\d+)", text.replace('\xa0', ' '))
            data['ratings_count'] = match.group(1) if match else ''
        else:
            data['ratings_count'] = ''
    except Exception:
        data['ratings_count'] = ''

    # Количество отзывов - берем из секции отзывов, а не из обзора
    try:
        data['reviews_count'] = ''  # Будет заполнено в parse_reviews
    except Exception:
        data['reviews_count'] = ''

    # Социальные сети
    try:
        social_links = []
        social_els = page.query_selector_all("a[href*='vk.com'], a[href*='instagram.com'], a[href*='facebook.com'], a[href*='twitter.com'], a[href*='ok.ru'], a[href*='t.me']")
        for el in social_els:
            href = el.get_attribute('href')
            if href:
                social_links.append(href)
        data['social_links'] = social_links
    except Exception:
        data['social_links'] = []

    # Часы работы - ВАЖНО: парсим ДО перехода на другие вкладки
    try:
        hours_selectors = [
            "div.business-working-hours-view span",
            "span.business-hours-view__current-status", 
            "div[class*='working-hours'] span",
            "[data-bem*='hours'] span"
        ]

        data['hours'] = ''
        for selector in hours_selectors:
            hours_el = page.query_selector(selector)
            if hours_el:
                hours_text = hours_el.inner_text().strip()
                if hours_text and ('круглосуточно' in hours_text.lower() or 'открыт' in hours_text.lower() or 'закрыт' in hours_text.lower() or ':' in hours_text):
                    data['hours'] = hours_text
                    break
    except Exception:
        data['hours'] = ''

    # Полное расписание - ВАЖНО: парсим ДО перехода на другие вкладки
    try:
        full_schedule = []

        # Клик по часам работы для раскрытия полного расписания - улучшенная версия
        hours_selectors_for_click = [
            "div.business-working-hours-view",
            "div[class*='working-hours']",
            "div.business-hours-view",
            "span.business-hours-view__current-status"
        ]

        for selector in hours_selectors_for_click:
            hours_click = page.query_selector(selector)
            if hours_click:
                try:
                    hours_click.click()
                    page.wait_for_timeout(800)
                    break
                except:
                    continue

        schedule_selectors = [
            "div.business-hours-view__day",
            "div[class*='schedule-day']", 
            "div[class*='hours-day']",
            "div.business-working-intervals-view__item"
        ]

        for selector in schedule_selectors:
            schedule_items = page.query_selector_all(selector)
            for item in schedule_items:
                try:
                    day_el = item.query_selector("div.business-hours-view__day-name, span[class*='day']")
                    time_el = item.query_selector("div.business-hours-view__hours, span[class*='time']")
                    day = day_el.inner_text().strip() if day_el else ''
                    work_time = time_el.inner_text().strip() if time_el else ''
                    if day and work_time:
                        full_schedule.append(f"{day}: {work_time}")
                except Exception:
                    continue

            if full_schedule:
                break

        data['hours_full'] = full_schedule
    except Exception:
        data['hours_full'] = []

    # Парсим товары и услуги - ИСПРАВЛЕННАЯ ВЕРСИЯ
    try:
        products_tab = page.query_selector("div[role='tab']:has-text('Товары и услуги'), button:has-text('Товары и услуги'), div.tabs-select-view__title._name_prices")
        if products_tab:
            products_tab.click()
            print("Клик по вкладке 'Товары и услуги'")
            page.wait_for_timeout(1500)

            # Сначала кликаем по категориям в рубрикаторе, если они есть
            try:
                category_tabs = page.query_selector_all("div.business-related-items-rubricator__category")
                print(f"Найдено категорий в рубрикаторе: {len(category_tabs)}")

                # Кликаем по каждой категории для загрузки товаров
                for i, cat_tab in enumerate(category_tabs[:10]):  # Ограничиваем 10 категориями
                    try:
                        cat_name = cat_tab.inner_text().strip()
                        print(f"Кликаем по категории: {cat_name}")
                        cat_tab.click()
                        page.wait_for_timeout(800)
                    except Exception:
                        continue
            except Exception:
                pass

            # Скроллим для загрузки всех услуг
            for i in range(15):
                page.mouse.wheel(0, 1000)
                time.sleep(0.8)

            # ВАЖНО: Ищем категории ПОСЛЕ всех кликов и скроллинга
            products = []
            product_categories = []
            processed_categories = set()

            # Повторный поиск категорий услуг после изменения DOM
            category_blocks = page.query_selector_all('div.business-full-items-grouped-view__category')

            for cat_block in category_blocks:
                try:
                    # Название категории - несколько вариантов селекторов
                    category_selectors = [
                        'div.business-full-items-grouped-view__category-title',
                        'h3.business-full-items-grouped-view__category-title',
                        'div.business-full-items-grouped-view__title'
                    ]

                    category = ""
                    for sel in category_selectors:
                        category_el = cat_block.query_selector(sel)
                        if category_el:
                            category = category_el.inner_text().strip()
                            break

                    if not category:
                        category = "Основные услуги"

                    # Избегаем дубликатов категорий
                    if category not in processed_categories:
                        processed_categories.add(category)
                        if category not in product_categories:
                            product_categories.append(category)

                        # Товары/услуги в категории
                        items = []
                        item_selectors = [
                            'div.business-full-items-grouped-view__item',
                            'div.related-item-photo-view',
                            'div.related-item-view'
                        ]

                        item_blocks = []
                        for sel in item_selectors:
                            items_found = cat_block.query_selector_all(sel)
                            item_blocks.extend(items_found)

                        for item in item_blocks:
                            try:
                                # Множественные селекторы для названия
                                name_selectors = [
                                    'div.related-item-photo-view__title',
                                    'div.related-item-view__title',
                                    'div.related-item-list-view__title',
                                    'span.related-product-view__title'
                                ]

                                name = ""
                                for sel in name_selectors:
                                    name_el = item.query_selector(sel)
                                    if name_el:
                                        name = name_el.inner_text().strip()
                                        break

                                # Множественные селекторы для описания
                                desc_selectors = [
                                    'div.related-item-photo-view__description',
                                    'div.related-item-view__description',
                                    'div.related-item-list-view__subtitle',
                                    'span.related-product-view__description'
                                ]

                                description = ""
                                for sel in desc_selectors:
                                    desc_el = item.query_selector(sel)
                                    if desc_el:
                                        description = desc_el.inner_text().strip()
                                        break

                                # Множественные селекторы для цены
                                price_selectors = [
                                    'span.related-product-view__price',
                                    'span.related-item-view__price',
                                    'div.related-item-list-view__price',
                                    'span[class*="price"]'
                                ]

                                price = ""
                                for sel in price_selectors:
                                    price_el = item.query_selector(sel)
                                    if price_el:
                                        price = price_el.inner_text().strip()
                                        break

                                # Продолжительность
                                duration_el = item.query_selector('span.related-product-view__volume')
                                duration = duration_el.inner_text().strip() if duration_el else ""

                                # Фото
                                photo_el = item.query_selector('img.image__img')
                                photo = photo_el.get_attribute('src') if photo_el else ""

                                if name:
                                    items.append({
                                        "name": name,
                                        "description": description,
                                        "price": price,
                                        "duration": duration,
                                        "photo": photo
                                    })
                            except Exception:
                                continue

                        if items:
                            products.append({
                                "category": category,
                                "items": items
                            })
                except Exception:
                    continue

            data['products'] = products
            data['product_categories'] = product_categories
            data['categories'] = product_categories  # Категории товаров/услуг для отчета как в рабочем коде

            print(f"Собрано категорий товаров: {len(product_categories)}")
            print(f"Собрано групп товаров: {len(products)}")
            print(f"Рубрика (основные категории бизнеса): {data.get('rubric', [])}")
            print(f"Категории товаров/услуг ({len(product_categories)}): {product_categories}")
        else:
            data['products'] = []
            data['product_categories'] = []
    except Exception:
        data['products'] = []
        data['product_categories'] = []

    # Возвращаемся на вкладку "Обзор" для парсинга часов работы
    try:
        overview_tab = page.query_selector("div.tabs-select-view__title._name_overview, div[role='tab']:has-text('Обзор'), button:has-text('Обзор')")
        if overview_tab:
            overview_tab.click()
            print("Возвращаемся на вкладку 'Обзор' для парсинга часов работы")