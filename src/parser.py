"""
parser.py — Модуль для парсинга публичной страницы Яндекс.Карт с помощью Playwright
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import re
import random
import os

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

            # Попытка запуска Chromium (используем системный из Nix)
            try:
                browser = p.chromium.launch(
                    executable_path='/nix/store/.../bin/chromium',  # Путь к системному Chromium
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

            # Дополнительные данные
            data['photos_count'] = get_photos_count(page)
            data['news'] = parse_news(page)
            data['reviews'] = parse_reviews(page)
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
        title_el = page.query_selector("h1")
        data['title'] = title_el.inner_text().strip() if title_el else ''
    except Exception:
        data['title'] = ''

    # Адрес
    try:
        addr_elem = page.query_selector("div.business-contacts-view__address span")
        data['address'] = addr_elem.inner_text().strip() if addr_elem else ''
    except Exception:
        data['address'] = ''

    # Ближайшее метро
    try:
        metro_block = page.query_selector("div.masstransit-stops-view._type_metro")
        if metro_block:
            metro_name = metro_block.query_selector("div.masstransit-stops-view__stop-name")
            metro_dist = metro_block.query_selector("div.masstransit-stops-view__stop-distance-text")
            data['nearest_metro'] = {
                'name': metro_name.inner_text() if metro_name else '',
                'distance': metro_dist.inner_text() if metro_dist else ''
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
                'name': stop_name.inner_text() if stop_name else '',
                'distance': stop_dist.inner_text() if stop_dist else ''
            }
        else:
            data['nearest_stop'] = {'name': '', 'distance': ''}
    except Exception:
        data['nearest_stop'] = {'name': '', 'distance': ''}

    # Телефон
    try:
        phone_elem = page.query_selector("div.business-contacts-view__phone-number span[class*='phone-number']")
        data['phone'] = phone_elem.inner_text().strip() if phone_elem else ''
    except Exception:
        data['phone'] = ''

    # Часы работы
    try:
        hours_elem = page.query_selector("div.business-working-hours-view span[class*='working-hours']")
        data['working_hours'] = hours_elem.inner_text().strip() if hours_elem else ''
    except Exception:
        data['working_hours'] = ''

    # Клик по кнопке "Показать телефон"
    try:
        show_phone_btn = page.query_selector("button:has-text('Показать телефон')")
        if show_phone_btn:
            show_phone_btn.click()
            page.wait_for_timeout(1000)
    except Exception:
        pass

    # Сайт
    try:
        site_el = page.query_selector("a.business-urls-view__text")
        data['site'] = site_el.get_attribute('href') if site_el else ''
    except Exception:
        data['site'] = ''

    # Описание
    try:
        desc_el = page.query_selector("[class*='card-about-view__description-text']")
        data['description'] = desc_el.inner_text().strip() if desc_el else ''
    except Exception:
        data['description'] = ''

    # Категории
    try:
        cats = page.query_selector_all("[class*='business-card-title-view__categories'] span")
        data['categories'] = [c.inner_text().strip() for c in cats if c.inner_text().strip()]
    except Exception:
        data['categories'] = []

    # Рейтинг
    try:
        rating_el = page.query_selector("span.business-rating-badge-view__rating-text")
        data['rating'] = rating_el.inner_text().replace(',', '.').strip() if rating_el else ''
    except Exception:
        data['rating'] = ''

    # Количество оценок
    try:
        ratings_count_el = page.query_selector("div.business-header-rating-view__text._clickable")
        if ratings_count_el:
            text = ratings_count_el.inner_text()
            match = re.search(r"(\d+)", text.replace('\xa0', ' '))
            data['ratings_count'] = match.group(1) if match else ''
        else:
            data['ratings_count'] = ''
    except Exception:
        data['ratings_count'] = ''

    # Количество отзывов
    try:
        reviews_count_el = page.query_selector("span:has-text('отзыв')")
        if reviews_count_el:
            text = reviews_count_el.inner_text()
            match = re.search(r"(\d+)", text)
            data['reviews_count'] = match.group(1) if match else ''
        else:
            data['reviews_count'] = ''
    except Exception:
        data['reviews_count'] = ''

    # Часы работы
    try:
        hours_el = page.query_selector("[class*='business-hours-text']")
        data['hours'] = hours_el.inner_text().strip() if hours_el else ''
    except Exception:
        data['hours'] = ''

    # Полное расписание
    try:
        full_schedule = []
        schedule_items = page.query_selector_all("[class*='business-hours-view__day']")
        for item in schedule_items:
            try:
                day_el = item.query_selector("[class*='business-hours-view__day-name']")
                time_el = item.query_selector("[class*='business-hours-view__hours']")
                day = day_el.inner_text().strip() if day_el else ''
                work_time = time_el.inner_text().strip() if time_el else ''
                if day and work_time:
                    full_schedule.append(f"{day}: {work_time}")
            except Exception:
                continue
        data['hours_full'] = full_schedule
    except Exception:
        data['hours_full'] = []

    # Ближайшее метро
    try:
        metro_el = page.query_selector("[class*='metro-station']")
        if metro_el:
            metro_name = metro_el.inner_text().strip()
            try:
                distance_el = metro_el.query_selector("[class*='distance']")
                distance = distance_el.inner_text().strip() if distance_el else ''
            except Exception:
                distance = ''
            data['nearest_metro'] = {'name': metro_name, 'distance': distance}
        else:
            data['nearest_metro'] = {'name': '', 'distance': ''}
    except Exception:
        data['nearest_metro'] = {'name': '', 'distance': ''}

    # Ближайшая остановка
    try:
        stop_el = page.query_selector("[class*='transport-stop']")
        if stop_el:
            stop_name = stop_el.inner_text().strip()
            try:
                distance_el = stop_el.query_selector("[class*='distance']")
                distance = distance_el.inner_text().strip() if distance_el else ''
            except Exception:
                distance = ''
            data['nearest_stop'] = {'name': stop_name, 'distance': distance}
        else:
            data['nearest_stop'] = {'name': '', 'distance': ''}
    except Exception:
        data['nearest_stop'] = {'name': '', 'distance': ''}

    # Социальные сети
    try:
        social_links = []
        social_els = page.query_selector_all("a[href*='vk.com'], a[href*='instagram.com'], a[href*='facebook.com'], a[href*='twitter.com'], a[href*='ok.ru']")
        for el in social_els:
            href = el.get_attribute('href')
            if href:
                social_links.append(href)
        data['social_links'] = social_links

    except Exception:
        data['social_links'] = []

    data['products'] = []
    data['product_categories'] = []

    return data

def get_photos_count(page):
    """Получает количество фотографий"""
    try:
        photos_tab = page.query_selector("div.tabs-select-view__title._name_gallery")
        if photos_tab:
            try:
                counter = photos_tab.query_selector("div.tabs-select-view__counter")
                return int(counter.inner_text().strip())
            except Exception:
                pass
    except Exception:
        pass
    return 0

def parse_news(page):
    """Парсит новости"""
    try:
        news_tab = page.query_selector("div[role='tab']:has-text('Лента'), button:has-text('Лента')")
        if news_tab:
            news_tab.click()
            page.wait_for_timeout(1500)

        news = []
        news_blocks = page.query_selector_all("[class*='feed-post-view']")
        for block in news_blocks:
            try:
                title_elem = block.query_selector("[class*='feed-post-view__title']")
                title = title_elem.inner_text() if title_elem else ""

                text_elem = block.query_selector("[class*='feed-post-view__text']")
                text = text_elem.inner_text() if text_elem else ""

                date_elem = block.query_selector("[class*='feed-post-view__date']")
                date = date_elem.inner_text() if date_elem else ""

                photo_elem = block.query_selector("img")
                photo = photo_elem.get_attribute('src') if photo_elem else ""

                news.append({
                    "title": title,
                    "text": text,
                    "date": date,
                    "photo": photo
                })
            except Exception:
                continue
        return news
    except Exception:
        return []

def parse_reviews(page):
    """Парсит отзывы"""
    try:
        reviews_tab = page.query_selector("div[role='tab']:has-text('Отзывы'), button:has-text('Отзывы')")
        if reviews_tab:
            reviews_tab.click()
            page.wait_for_timeout(2000)

        reviews_data = {"items": [], "rating": "", "reviews_count": ""}

        # Рейтинг и количество отзывов
        try:
            rating_el = page.query_selector("span.business-rating-badge-view__rating-text")
            reviews_data['rating'] = rating_el.inner_text().replace(',', '.').strip() if rating_el else ''

            count_el = page.query_selector("span:has-text('отзыв')")
            if count_el:
                text = count_el.inner_text()
                match = re.search(r"(\d+)", text)
                reviews_data['reviews_count'] = match.group(1) if match else ''
        except Exception:
            pass

        # Парсим отзывы
        try:
            review_blocks = page.query_selector_all("[class*='business-review-view']")
            for block in review_blocks:
                try:
                    author = ""
                    author_elem = block.query_selector("[class*='business-review-view__author'] span")
                    if author_elem:
                        author = author_elem.inner_text()

                    date_el = block.query_selector("[class*='business-review-view__date']")
                    date = date_el.inner_text().strip() if date_el else ""

                    rating_els = block.query_selector_all("[class*='star-fill']")
                    rating = len(rating_els)

                    text_el = block.query_selector("[class*='business-review-view__body']")
                    text = text_el.inner_text().strip() if text_el else ""

                    reply_el = block.query_selector("[class*='business-review-view__reply']")
                    reply = reply_el.inner_text().strip() if reply_el else ""

                    reviews_data['items'].append({
                        "author": author,
                        "date": date,
                        "rating": rating,
                        "text": text,
                        "reply": reply
                    })
                except Exception:
                    continue
        except Exception:
            pass

        return reviews_data
    except Exception:
        return {"items": [], "rating": "", "reviews_count": ""}

def parse_features(page):
    """Парсит особенности"""
    try:
        features_tab = page.query_selector("div[role='tab']:has-text('Особенности'), button:has-text('Особенности')")
        if features_tab:
            features_tab.click()
            page.wait_for_timeout(1500)

        features_data = {"bool": [], "valued": [], "prices": [], "categories": []}

        feature_blocks = page.query_selector_all("[class*='features-view__item']")
        for block in feature_blocks:
            try:
                name_el = block.query_selector("[class*='features-view__name']")
                name = name_el.inner_text().strip() if name_el else ""

                value_el = block.query_selector("[class*='features-view__value']")
                value = value_el.inner_text().strip() if value_el else ""

                if name:
                    if value:
                        features_data['valued'].append(f"{name}: {value}")
                    else:
                        features_data['bool'].append(name)
            except Exception:
                continue

        return features_data
    except Exception:
        return {"bool": [], "valued": [], "prices": [], "categories": []}

def parse_competitors(page):
    """Парсит конкурентов из раздела 'Похожие места рядом'"""
    try:
        similar_section = page.query_selector("[class*='card-similar'], [class*='similar-places']")
        if not similar_section:
            return []

        competitors = []
        competitor_blocks = similar_section.query_selector_all("a[href*='/org/']")

        for block in competitor_blocks[:5]:
            try:
                href = block.get_attribute('href')
                if href and not href.startswith('http'):
                    href = f"https://yandex.ru{href}"

                title_el = block.query_selector("[class*='title'], h3, h4")
                title = title_el.inner_text().strip() if title_el else ""

                if title and href:
                    competitors.append({
                        "title": title,
                        "url": href
                    })
            except Exception:
                continue

        return competitors
    except Exception:
        return []
# Удаляем дублирующую функцию

    except Exception:
        data['social_links'] = []

    data['products'] = []
    data['product_categories'] = []

    return data

def get_photos_count(page):
    """Получает количество фотографий"""
    try:
        photos_tab = page.query_selector("div.tabs-select-view__title._name_gallery")
        if photos_tab:
            try:
                counter = photos_tab.query_selector("div.tabs-select-view__counter")
                return int(counter.inner_text().strip())
            except Exception:
                pass
    except Exception:
        pass
    return 0

def parse_news(page):
    """Парсит новости"""
    try:
        news_tab = page.query_selector("div[role='tab']:has-text('Лента'), button:has-text('Лента')")
        if news_tab:
            news_tab.click()
            page.wait_for_timeout(1500)

        news = []
        news_blocks = page.query_selector_all("[class*='feed-post-view']")
        for block in news_blocks:
            try:
                title_elem = block.query_selector("[class*='feed-post-view__title']")
                title = title_elem.inner_text() if title_elem else ""

                text_elem = block.query_selector("[class*='feed-post-view__text']")
                text = text_elem.inner_text() if text_elem else ""

                date_elem = block.query_selector("[class*='feed-post-view__date']")
                date = date_elem.inner_text() if date_elem else ""

                photo_elem = block.query_selector("img")
                photo = photo_elem.get_attribute('src') if photo_elem else ""

                news.append({
                    "title": title,
                    "text": text,
                    "date": date,
                    "photo": photo
                })
            except Exception:
                continue
        return news
    except Exception:
        return []

def parse_reviews(page):
    """Парсит отзывы"""
    try:
        reviews_tab = page.query_selector("div[role='tab']:has-text('Отзывы'), button:has-text('Отзывы')")
        if reviews_tab:
            reviews_tab.click()
            page.wait_for_timeout(2000)

        reviews_data = {"items": [], "rating": "", "reviews_count": ""}

        # Рейтинг и количество отзывов
        try:
            rating_el = page.query_selector("span.business-rating-badge-view__rating-text")
            reviews_data['rating'] = rating_el.inner_text().replace(',', '.').strip() if rating_el else ''

            count_el = page.query_selector("span:has-text('отзыв')")
            if count_el:
                text = count_el.inner_text()
                match = re.search(r"(\d+)", text)
                reviews_data['reviews_count'] = match.group(1) if match else ''
        except Exception:
            pass

        # Парсим отзывы
        try:
            review_blocks = page.query_selector_all("[class*='business-review-view']")
            for block in review_blocks:
                try:
                    author = ""
                    author_elem = block.query_selector("[class*='business-review-view__author'] span")
                    if author_elem:
                        author = author_elem.inner_text()

                    date_el = block.query_selector("[class*='business-review-view__date']")
                    date = date_el.inner_text().strip() if date_el else ""

                    rating_els = block.query_selector_all("[class*='star-fill']")
                    rating = len(rating_els)

                    text_el = block.query_selector("[class*='business-review-view__body']")
                    text = text_el.inner_text().strip() if text_el else ""

                    reply_el = block.query_selector("[class*='business-review-view__reply']")
                    reply = reply_el.inner_text().strip() if reply_el else ""

                    reviews_data['items'].append({
                        "author": author,
                        "date": date,
                        "rating": rating,
                        "text": text,
                        "reply": reply
                    })
                except Exception:
                    continue
        except Exception:
            pass

        return reviews_data
    except Exception:
        return {"items": [], "rating": "", "reviews_count": ""}

def parse_features(page):
    """Парсит особенности"""
    try:
        features_tab = page.query_selector("div[role='tab']:has-text('Особенности'), button:has-text('Особенности')")
        if features_tab:
            features_tab.click()
            page.wait_for_timeout(1500)

        features_data = {"bool": [], "valued": [], "prices": [], "categories": []}

        feature_blocks = page.query_selector_all("[class*='features-view__item']")
        for block in feature_blocks:
            try:
                name_el = block.query_selector("[class*='features-view__name']")
                name = name_el.inner_text().strip() if name_el else ""

                value_el = block.query_selector("[class*='features-view__value']")
                value = value_el.inner_text().strip() if value_el else ""

                if name:
                    if value:
                        features_data['valued'].append(f"{name}: {value}")
                    else:
                        features_data['bool'].append(name)
            except Exception:
                continue

        return features_data
    except Exception:
        return {"bool": [], "valued": [], "prices": [], "categories": []}

def parse_competitors(page):
    """Парсит конкурентов из раздела 'Похожие места рядом'"""
    try:
        similar_section = page.query_selector("[class*='card-similar'], [class*='similar-places']")
        if not similar_section:
            return []

        competitors = []
        competitor_blocks = similar_section.query_selector_all("a[href*='/org/']")

        for block in competitor_blocks[:5]:
            try:
                href = block.get_attribute('href')
                if href and not href.startswith('http'):
                    href = f"https://yandex.ru{href}"

                title_el = block.query_selector("[class*='title'], h3, h4")
                title = title_el.inner_text().strip() if title_el else ""

                if title and href:
                    competitors.append({
                        "title": title,
                        "url": href
                    })
            except Exception:
                continue

        return competitors
    except Exception:
        return []

    # --- ПЕРЕХОД НА ВКЛАДКУ "Товары и услуги" ---
    try:
        products_tab = page.query_selector("div[role='tab']:has-text('Товары и услуги'), button:has-text('Товары и услуги'), div.tabs-select-view__title._name_prices")
        if products_tab:
            products_tab.click()
            print("Клик по вкладке 'Товары и услуги'")
            page.wait_for_timeout(1500)

            # Парсим категории товаров и услуг
            try:
                category_blocks = page.query_selector_all("div.business-prices-view__category")
                data['product_categories'] = []
                for cat_block in category_blocks:
                    cat_name_elem = cat_block.query_selector("div.business-prices-view__category-name")
                    if cat_name_elem:
                        data['product_categories'].append(cat_name_elem.inner_text().strip())
            except Exception:
                data['product_categories'] = []

            # Парсим товары и услуги
            try:
                product_blocks = page.query_selector_all("div.business-prices-view__item")
                data['products'] = []
                for prod_block in product_blocks:
                    try:
                        name_elem = prod_block.query_selector("div.business-prices-view__item-name")
                        price_elem = prod_block.query_selector("div.business-prices-view__item-price")
                        if name_elem:
                            product = {
                                'name': name_elem.inner_text().strip(),
                                'price': price_elem.inner_text().strip() if price_elem else ''
                            }
                            data['products'].append(product)
                    except Exception:
                        continue
            except Exception:
                data['products'] = []
    except Exception:
        data['product_categories'] = []
        data['products'] = []

    # --- ПЕРЕХОД НА ВКЛАДКУ "Новости" ---
    try:
        news_tab = page.query_selector("div[role='tab']:has-text('Новости'), button:has-text('Новости')")
        if news_tab:
            news_tab.click()
            print("Клик по вкладке 'Новости'")
            page.wait_for_timeout(1500)

            # Парсим новости
            try:
                news_blocks = page.query_selector_all("div.business-news-view__item")
                data['news'] = []
                for news_block in news_blocks:
                    try:
                        title_elem = news_block.query_selector("div.business-news-view__title")
                        date_elem = news_block.query_selector("div.business-news-view__date")
                        if title_elem:
                            news_item = {
                                'title': title_elem.inner_text().strip(),
                                'date': date_elem.inner_text().strip() if date_elem else ''
                            }
                            data['news'].append(news_item)
                    except Exception:
                        continue
            except Exception:
                data['news'] = []
    except Exception:
        data['news'] = []

    # --- ПЕРЕХОД НА ВКЛАДКУ "Фото" ---
    try:
        photos_tab = page.query_selector("div[role='tab']:has-text('Фото'), button:has-text('Фото')")
        if photos_tab:
            photos_tab.click()
            print("Клик по вкладке 'Фото'")
            page.wait_for_timeout(1500)

            # Парсим фото
            try:
                photo_blocks = page.query_selector_all("div.business-photos-view__photo")
                data['photos'] = []
                for photo_block in photo_blocks:
                    try:
                        img_elem = photo_block.query_selector("img")
                        if img_elem:
                            src = img_elem.get_attribute("src")
                            if src:
                                data['photos'].append(src)
                    except Exception:
                        continue
            except Exception:
                data['photos'] = []
    except Exception:
        data['photos'] = []

    # Парсим особенности
    try:
        features_blocks = page.query_selector_all("div.business-features-view__item")
        data['features'] = []
        for feature_block in features_blocks:
            try:
                feature_elem = feature_block.query_selector("span")
                if feature_elem:
                    data['features'].append(feature_elem.inner_text().strip())
            except Exception:
                continue
    except Exception:
        data['features'] = []

    return data