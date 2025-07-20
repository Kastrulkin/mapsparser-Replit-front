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

    # Клик по кнопке "Показать телефон" перед парсингом
    try:
        show_phone_btn = page.query_selector("button:has-text('Показать телефон'), button[class*='phone']")
        if show_phone_btn:
            show_phone_btn.click()
            page.wait_for_timeout(1000)
    except Exception:
        pass

    # Телефон
    try:
        phone_elem = page.query_selector("div.business-contacts-view__phone-number span, span[class*='phone'], a[href^='tel:']")
        if phone_elem:
            phone_text = phone_elem.inner_text().strip()
            # Очищаем от лишних символов
            data['phone'] = re.sub(r'[^\d+\-\(\)\s]', '', phone_text)
        else:
            data['phone'] = ''
    except Exception:
        data['phone'] = ''

    # Ближайшее метро
    try:
        metro_block = page.query_selector("div.masstransit-stops-view._type_metro, div[class*='metro']")
        if metro_block:
            metro_name_el = metro_block.query_selector("div.masstransit-stops-view__stop-name, span, div")
            metro_dist_el = metro_block.query_selector("div.masstransit-stops-view__stop-distance-text, span[class*='distance']")
            data['nearest_metro'] = {
                'name': metro_name_el.inner_text().strip() if metro_name_el else '',
                'distance': metro_dist_el.inner_text().strip() if metro_dist_el else ''
            }
        else:
            data['nearest_metro'] = {'name': '', 'distance': ''}
    except Exception:
        data['nearest_metro'] = {'name': '', 'distance': ''}

    # Ближайшая остановка
    try:
        stop_block = page.query_selector("div.masstransit-stops-view._type_masstransit, div[class*='transport-stop']")
        if stop_block:
            stop_name_el = stop_block.query_selector("div.masstransit-stops-view__stop-name, span, div")
            stop_dist_el = stop_block.query_selector("div.masstransit-stops-view__stop-distance-text, span[class*='distance']")
            data['nearest_stop'] = {
                'name': stop_name_el.inner_text().strip() if stop_name_el else '',
                'distance': stop_dist_el.inner_text().strip() if stop_dist_el else ''
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

    # Категории
    try:
        cats = page.query_selector_all("div.business-card-title-view__categories span, span[class*='category']")
        data['categories'] = [c.inner_text().strip() for c in cats if c.inner_text().strip()]
    except Exception:
        data['categories'] = []

    # Рейтинг
    try:
        rating_el = page.query_selector("span.business-rating-badge-view__rating-text, span[class*='rating']")
        data['rating'] = rating_el.inner_text().replace(',', '.').strip() if rating_el else ''
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

    # Количество отзывов
    try:
        reviews_count_el = page.query_selector("span:has-text('отзыв'), span:has-text('отзывов')")
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
        hours_el = page.query_selector("div.business-working-hours-view span, span[class*='hours'], div[class*='working-hours']")
        data['hours'] = hours_el.inner_text().strip() if hours_el else ''
    except Exception:
        data['hours'] = ''

    # Полное расписание
    try:
        full_schedule = []
        schedule_items = page.query_selector_all("div.business-hours-view__day, div[class*='schedule-day']")
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
        data['hours_full'] = full_schedule
    except Exception:
        data['hours_full'] = []

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

    # Парсим товары и услуги
    try:
        # Переходим на вкладку "Услуги" или "Меню"
        services_tab = page.query_selector("div.tabs-select-view__title._name_services, div[role='tab']:has-text('Услуги'), button:has-text('Услуги'), div[role='tab']:has-text('Меню'), button:has-text('Меню')")
        if services_tab:
            services_tab.click()
            print("Клик по вкладке 'Услуги/Меню'")
            page.wait_for_timeout(2000)
            
            # Скроллим для загрузки услуг
            for i in range(10):
                page.mouse.wheel(0, 1000)
                time.sleep(1)
            
            products = []
            product_categories = []
            
            # Ищем категории услуг
            category_blocks = page.query_selector_all("div.services-list-category-view, div[class*='service-category'], div[class*='menu-category']")
            
            for cat_block in category_blocks:
                try:
                    # Название категории
                    cat_name_elem = cat_block.query_selector("h3, h4, div.services-list-category-view__title, span[class*='category-title']")
                    cat_name = cat_name_elem.inner_text().strip() if cat_name_elem else "Без категории"
                    
                    if cat_name not in product_categories:
                        product_categories.append(cat_name)
                    
                    # Товары/услуги в категории
                    items = []
                    service_items = cat_block.query_selector_all("div.services-list-item-view, div[class*='service-item'], div[class*='menu-item']")
                    
                    for item in service_items:
                        try:
                            name_elem = item.query_selector("div.services-list-item-view__title, span[class*='item-title'], h5")
                            name = name_elem.inner_text().strip() if name_elem else ""
                            
                            desc_elem = item.query_selector("div.services-list-item-view__description, span[class*='description']")
                            description = desc_elem.inner_text().strip() if desc_elem else ""
                            
                            price_elem = item.query_selector("div.services-list-item-view__price, span[class*='price']")
                            price = price_elem.inner_text().strip() if price_elem else ""
                            
                            duration_elem = item.query_selector("div.services-list-item-view__duration, span[class*='duration']")
                            duration = duration_elem.inner_text().strip() if duration_elem else ""
                            
                            photo_elem = item.query_selector("img")
                            photo = photo_elem.get_attribute('src') if photo_elem else ""
                            
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
                            "category": cat_name,
                            "items": items
                        })
                except Exception:
                    continue
            
            data['products'] = products
            data['product_categories'] = product_categories
        else:
            data['products'] = []
            data['product_categories'] = []
    except Exception:
        data['products'] = []
        data['product_categories'] = []

    return data

def parse_reviews(page):
    """Парсит отзывы"""
    try:
        reviews_tab = page.query_selector("div.tabs-select-view__title._name_reviews, div[role='tab']:has-text('Отзывы'), button:has-text('Отзывы')")
        if reviews_tab:
            reviews_tab.click()
            print("Клик по вкладке 'Отзывы'")
            page.wait_for_timeout(2000)
        else:
            print("Вкладка 'Отзывы' не найдена!")

        reviews_data = {"items": [], "rating": "", "reviews_count": ""}

        # Рейтинг и количество отзывов
        try:
            rating_el = page.query_selector("span.business-rating-badge-view__rating-text")
            reviews_data['rating'] = rating_el.inner_text().replace(',', '.').strip() if rating_el else ''

            count_el = page.query_selector("h2.card-section-header__title._wide")
            if count_el:
                text = count_el.inner_text()
                match = re.search(r"(\d+)", text.replace('\xa0', ' '))
                reviews_data['reviews_count'] = match.group(1) if match else ''
        except Exception:
            pass

        # Скролл для загрузки отзывов
        max_loops = 100
        patience = 30
        last_count = 0
        same_count = 0

        for i in range(max_loops):
            # Иногда двигаем мышь
            if i % 7 == 0:
                page.mouse.move(random.randint(200, 600), random.randint(400, 800))

            # Иногда кликаем по вкладке 'Отзывы'
            if i % 25 == 0 and reviews_tab:
                reviews_tab.click()
                time.sleep(0.5)

            # Прокручиваем вниз
            page.mouse.wheel(0, 1000)
            time.sleep(random.uniform(1.5, 2.5))

            # Проверяем количество загруженных отзывов
            current_reviews = page.query_selector_all("div.business-review-view, div[class*='review-item']")
            current_count = len(current_reviews)

            if current_count == last_count:
                same_count += 1
                if same_count >= patience:
                    print(f"Отзывы перестали загружаться после {i} итераций. Найдено {current_count} отзывов")
                    break
            else:
                same_count = 0
                last_count = current_count
                print(f"Загружено отзывов: {current_count}")

        # Парсим отзывы
        try:
            review_blocks = page.query_selector_all("div.business-review-view, div[class*='review-item']")
            for block in review_blocks:
                try:
                    # Имя автора
                    author = ""
                    author_elem = block.query_selector("div.business-review-view__author span, span.business-review-view__author-name, div.business-review-view__author")
                    if author_elem:
                        author = author_elem.inner_text().strip()
                    
                    if not author:
                        # Альтернативный селектор для имени
                        author_elem = block.query_selector("span[class*='author'], div[class*='username'], [data-bem*='author']")
                        if author_elem:
                            author = author_elem.inner_text().strip()

                    # Дата
                    date_el = block.query_selector("div.business-review-view__date, span.business-review-view__date, span[class*='date']")
                    date = date_el.inner_text().strip() if date_el else ""

                    # Рейтинг (звёзды)
                    rating = 0
                    rating_els = block.query_selector_all("span.business-rating-view__star._fill, span[class*='star-fill'], span[class*='rating-star'][class*='fill']")
                    rating = len(rating_els)
                    
                    # Если не нашли звёзды, ищем текстовый рейтинг
                    if rating == 0:
                        rating_text_elem = block.query_selector("span[class*='rating-text'], div[class*='score']")
                        if rating_text_elem:
                            rating_text = rating_text_elem.inner_text().strip()
                            try:
                                rating = int(float(rating_text.replace(',', '.')))
                            except:
                                rating = 0

                    # Текст отзыва
                    text_el = block.query_selector("div.business-review-view__body, div[class*='review-text']")
                    text = text_el.inner_text().strip() if text_el else ""

                    # Ответ организации
                    reply_el = block.query_selector("div.business-review-view__reply, div[class*='reply']")
                    reply = reply_el.inner_text().strip() if reply_el else ""

                    reviews_data['items'].append({
                        "author": author,
                        "date": date,
                        "score": rating,
                        "text": text,
                        "org_reply": reply
                    })
                except Exception:
                    continue
        except Exception:
            pass

        return reviews_data
    except Exception:
        return {"items": [], "rating": "", "reviews_count": ""}

def parse_news(page):
    """Парсит новости"""
    try:
        news_tab = page.query_selector("div.tabs-select-view__title._name_feed, div[role='tab']:has-text('Лента'), button:has-text('Лента')")
        if news_tab:
            news_tab.click()
            print("Клик по вкладке 'Лента'")
            page.wait_for_timeout(1500)

        news = []
        news_blocks = page.query_selector_all("div.feed-post-view, div[class*='news-item']")
        for block in news_blocks:
            try:
                title_elem = block.query_selector("div.feed-post-view__title, h3, h4")
                title = title_elem.inner_text() if title_elem else ""

                text_elem = block.query_selector("div.feed-post-view__text, div[class*='text']")
                text = text_elem.inner_text() if text_elem else ""

                date_elem = block.query_selector("div.feed-post-view__date, span[class*='date']")
                date = date_elem.inner_text() if date_elem else ""

                # Парсим фото
                photos = []
                photo_elems = block.query_selector_all("img")
                for img in photo_elems:
                    src = img.get_attribute('src')
                    if src:
                        photos.append(src)

                news.append({
                    "title": title,
                    "text": text,
                    "date": date,
                    "photos": photos
                })
            except Exception:
                continue
        return news
    except Exception:
        return []

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

def parse_photos(page):
    """Парсит фотографии"""
    try:
        photos_tab = page.query_selector("div.tabs-select-view__title._name_gallery, div[role='tab']:has-text('Фото'), button:has-text('Фото')")
        if photos_tab:
            photos_tab.click()
            print("Клик по вкладке 'Фото'")
            page.wait_for_timeout(2000)

            # Скролл для загрузки фото
            for i in range(30):
                page.mouse.wheel(0, 1500)
                time.sleep(2)

        photos = []
        # Расширенный поиск изображений
        img_selectors = [
            "img.image__img",
            "img[src*='avatars.mds.yandex.net']",
            "img[src*='yandex.ru']",
            "img[src*='maps-photo']", 
            "div.photo-card img",
            "div.gallery-item img",
            "div[class*='photo'] img",
            "div[class*='image'] img"
        ]
        
        for selector in img_selectors:
            img_elems = page.query_selector_all(selector)
            for img in img_elems:
                src = img.get_attribute('src')
                if src and src not in photos and ('avatars.mds.yandex' in src or 'yandex.ru' in src):
                    # Увеличиваем размер изображения если возможно
                    if '/L/' in src:
                        src = src.replace('/L/', '/XL/')
                    elif '/M/' in src:
                        src = src.replace('/M/', '/XL/')
                    elif '/S/' in src:
                        src = src.replace('/S/', '/XL/')
                    photos.append(src)
        
        return photos
    except Exception:
        return []

def parse_features(page):
    """Парсит особенности"""
    try:
        features_tab = page.query_selector("div.tabs-select-view__title._name_features, div[role='tab']:has-text('Особенности'), button:has-text('Особенности')")
        if features_tab:
            features_tab.click()
            print("Клик по вкладке 'Особенности'")
            page.wait_for_timeout(1500)

        features_data = {"bool": [], "valued": [], "prices": [], "categories": []}

        # Булевые особенности
        try:
            bool_blocks = page.query_selector_all("div.business-features-view__item._feature, div[class*='feature-bool']")
            for block in bool_blocks:
                try:
                    text_el = block.query_selector("span, div")
                    if text_el:
                        text = text_el.inner_text().strip()
                        defined = "feature_defined" in block.get_attribute("class") or ""
                        features_data['bool'].append({
                            "text": text,
                            "defined": defined
                        })
                except Exception:
                    continue
        except Exception:
            pass

        # Ценностные особенности
        try:
            valued_blocks = page.query_selector_all("div.business-features-view__item._category, div[class*='feature-valued']")
            for block in valued_blocks:
                try:
                    title_el = block.query_selector("div.business-features-view__category-name, span[class*='title']")
                    value_el = block.query_selector("div.business-features-view__category-value, span[class*='value']")

                    if title_el and value_el:
                        features_data['valued'].append({
                            "title": title_el.inner_text().strip(),
                            "value": value_el.inner_text().strip()
                        })
                except Exception:
                    continue
        except Exception:
            pass

        return features_data
    except Exception:
        return {"bool": [], "valued": [], "prices": [], "categories": []}

def parse_competitors(page):
    """Парсит конкурентов из раздела 'Похожие места рядом'"""
    try:
        similar_section = page.query_selector("div.card-similar-carousel-wide, div[class*='similar'], section[class*='similar']")
        if not similar_section:
            return []

        competitors = []
        competitor_blocks = similar_section.query_selector_all("a[href*='/org/']")

        for block in competitor_blocks[:5]:
            try:
                href = block.get_attribute('href')
                if href and not href.startswith('http'):
                    href = f"https://yandex.ru{href}"

                title_el = block.query_selector("div.card-title-view__title, h3, h4, span")
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