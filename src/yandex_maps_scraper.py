"""
parser.py — Модуль для парсинга публичной страницы Яндекс.Карт с помощью Playwright
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import re
import random
import os
from random import randint, uniform

def _launch_browser(p):
    """Пробует запустить браузер, возвращает (browser, name) или None"""
    browsers = [
        (
            p.chromium,
            "Chromium",
            {
                'headless': True,
                'args': [
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
                'ignore_default_args': ['--enable-automation'],
                'chromium_sandbox': False
            }
        ),
        (
            p.firefox,
            "Firefox",
            {
                'headless': True,
                'args': ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
                'firefox_user_prefs': {
                    'dom.webdriver.enabled': False,
                    'useAutomationExtension': False
                }
            }
        ),
        (
            p.webkit,
            "WebKit",
            {
                'headless': True,
                'args': ['--no-sandbox']
            }
        )
    ]
    
    for browser_type, name, options in browsers:
        try:
            browser = browser_type.launch(**options)
            print(f"Используем {name}")
            return browser, name
        except Exception as e:
            print(f"{name} недоступен: {e}")
            continue
    
    raise Exception("Не удалось запустить ни один браузер")

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
    """
    Парсит публичную страницу Яндекс.Карт и возвращает данные в виде словаря.
    """
    print(f"Начинаем парсинг: {url}")

    if not url or not url.startswith(('http://', 'https://')):
        raise ValueError(f"Некорректная ссылка: {url}")

    print("Используем парсинг через Playwright...")

    from parser_config_cookies import get_yandex_cookies
    cookies = get_yandex_cookies()
    with sync_playwright() as p:
        try:
            browser, browser_name = _launch_browser(p)

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
            reviews_data = parse_reviews(page)
            data['reviews'] = reviews_data.get('items', [])  # Возвращаем только список отзывов
            data['news'] = parse_news(page)
            data['photos_count'] = get_photos_count(page)
            data['photos'] = parse_photos(page)
            # data['photos'] = []
            data['features_full'] = parse_features(page)
            data['competitors'] = parse_competitors(page)

            # Создаем overview для отчета
            overview_keys = [
                'title', 'address', 'phone', 'site', 'description',
                'rubric', 'categories', 'hours', 'hours_full', 'rating', 'ratings_count', 'reviews_count', 'social_links'
            ]
            data['overview'] = {k: data.get(k, '') for k in overview_keys}
            data['overview']['reviews_count'] = data.get('reviews_count', '')

            browser.close()
            print(f"Парсинг завершен ({browser_name}). Найдено: название='{data['title']}', адрес='{data['address']}'")
            return data

        except PlaywrightTimeoutError as e:
            browser.close()
            raise Exception(f"Тайм-аут при загрузке страницы: {e}")
        except Exception as e:
            browser.close()
            raise Exception(f"Ошибка при парсинге: {e}")

def parse_overview_data(page):
    """Парсит основные данные с вкладки Обзор"""
    data = {}

    # Название
    try:
        title_el = page.query_selector("h1.card-title-view__title, h1")
        data['title'] = title_el.inner_text().strip() if title_el else ''
        
        # Проверка на галочку верификации (синяя галочка)
        verified_el = page.query_selector("span.business-verified-badge")
        data['is_verified'] = True if verified_el else False
        if data['is_verified']:
            print("✅ Организация верифицирована (синяя галочка)")
            
    except Exception:
        data['title'] = ''
        data['is_verified'] = False

    # Полный адрес
    try:
        address_selectors = [
            # User provided selector (High Priority)
            "div.orgpage-header-view__contacts > a",
            # Standard selectors
            "div.business-contacts-view__address",
            "a.business-contacts-view__address-link",
            "div.business-contacts-view__address-link",
            "[class*='business-contacts-view'] [class*='address']",
            "div[class*='orgpage-header-view__address']",
            "div.orgpage-header-view__address",
            "a[href*='/maps/'][aria-label*='Россия']" # Often address is a link to map
        ]
        
        data['address'] = ''
        for selector in address_selectors:
            addr_elem = page.query_selector(selector)
            if addr_elem:
                addr_text = addr_elem.inner_text().strip()
                if addr_text:
                    data['address'] = addr_text
                    print(f"✅ Найден адрес: {addr_text} (селектор: {selector})")
                    break
                    
        if not data['address']:
             print("❌ Адрес не найден ни по одному селектору")
    except Exception as e:
        print(f"Ошибка при парсинге адреса: {e}")
        data['address'] = ''

    # Клик по кнопке "Показать телефон" перед парсингом - улучшенная версия
    try:
        # Ждем появления кнопки телефона
        page.wait_for_timeout(2000)

        phone_btn_selectors = [
            # User provided selectors
            "div.orgpage-header-view__contacts > div.orgpage-header-view__contact", 
            "div.orgpage-header-view__contacts > div.orgpage-header-view__contact > div > div",
            # Standard
            "button:has-text('Показать телефон')",
            "div.business-contacts-view__phone button",
            "span:has-text('Показать телефон')",
            "button[class*='phone']",
            "[aria-label*='телефон'] button",
            "div.business-phones-view button",
            "div.card-phones-view__more-wrapper button",
            "button[class*='card-phones-view__more']",
            # Альтернативный селектор по примеру пользователя
            "div.card-feature-view__content > div > div > div > div > div > div"
        ]

        phone_clicked = False
        for selector in phone_btn_selectors:
            try:
                show_phone_btn = page.query_selector(selector)
                if show_phone_btn and show_phone_btn.is_visible():
                    print(f"Кликаем по кнопке телефона: {selector}")
                    show_phone_btn.click()
                    page.wait_for_timeout(2500)
                    phone_clicked = True
                    break
                else:
                    print(f"Кнопка не найдена или не видна: {selector}")
            except Exception as e:
                print(f"Ошибка при поиске/клике по селектору {selector}: {e}")
                continue

        if not phone_clicked:
            print("Кнопка 'Показать телефон' не найдена ни по одному селектору")
    except Exception as e:
        print(f"Ошибка при попытке кликнуть по кнопке телефона: {e}")
        pass

    # Телефон - улучшенный парсинг
    try:
        phone_selectors = [
            # Новые точные селекторы от пользователя
            "div.orgpage-header-view__contacts > div.orgpage-header-view__contact > div > div > div",
            "div.orgpage-header-view__contacts > div.orgpage-header-view__contact > div > div",
            "div.card-phones-view__phone-number",
            "div[class*='card-phones-view']",
            # Стандартные селекторы
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
            "div:has-text('Показать телефон')",
            # Альтернативный селектор по примеру пользователя
            "div.card-feature-view__content > div > div > div",
            # Новые селекторы для извлечения телефона из текста
            "div.card-feature-view__content",
            "div.business-contacts-view__phone",
            "div.orgpage-phones-view__phone-number",
            "div.card-phones-view__number"
        ]

        data['phone'] = ''
        for selector in phone_selectors:
            phone_elems = page.query_selector_all(selector)
            print(f"Пробуем селектор телефона: {selector}, найдено элементов: {len(phone_elems)}")
            for phone_elem in phone_elems:
                phone_text = phone_elem.inner_text().strip()
                print(f"  Кандидат на телефон: '{phone_text}' (селектор: {selector})")
                
                # Проверяем на наличие цифр и символов телефона
                import re
                if re.search(r'[\d+\-\(\)\s]{7,}', phone_text):
                    # Очищаем от лишних символов, оставляя только цифры, +, -, (, ), пробелы
                    phone_cleaned = re.sub(r'[^\d+\-\(\)\s]', '', phone_text).strip()
                    if len(phone_cleaned) >= 7:  # Минимальная длина телефона
                        data['phone'] = phone_cleaned
                        print(f"  Найден телефон: {data['phone']} (селектор: {selector})")
                        break

                # Также проверяем атрибут title
                title_attr = phone_elem.get_attribute('title')
                if title_attr and re.search(r'[\d+\-\(\)\s]{7,}', title_attr):
                    phone_cleaned = re.sub(r'[^\d+\-\(\)\s]', '', title_attr).strip()
                    if len(phone_cleaned) >= 7:
                        data['phone'] = phone_cleaned
                        print(f"  Найден телефон в title: {data['phone']} (селектор: {selector})")
                        break

            if data['phone']:
                break
                
        # Если телефон не найден, пробуем извлечь из всех элементов на странице
        if not data['phone']:
            import re
            all_elements = page.query_selector_all("*")
            for elem in all_elements:
                try:
                    text = elem.inner_text().strip()
                    if text and re.search(r'\+7\s*\(\d{3}\)\s*\d{3}-\d{2}-\d{2}', text):
                        phone_match = re.search(r'\+7\s*\(\d{3}\)\s*\d{3}-\d{2}-\d{2}', text)
                        if phone_match:
                            data['phone'] = phone_match.group(0)
                            print(f"  Найден телефон в общем поиске: {data['phone']}")
                            break
                except:
                    continue
                    
        print(f"Итоговый телефон: {data['phone']}")
    except Exception as e:
        print(f"Ошибка при парсинге телефона: {e}")
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
        site_el = page.query_selector("a.business-urls-view__link")
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
            # User provided selectors
            "div.business-header-rating-view__text._clickable",
            "div.business-rating-badge-view__rating",
            "span.business-rating-badge-view__rating-text",
            "div.business-rating-badge-view__stars", 
            # Standard
            "div.business-header-rating-view__rating span",
            "span[class*='rating-text']",
            "span.business-summary-rating-badge-view__rating-text",
            # New broad selectors
            "div.business-header-rating-view__rating",
            "div[class*='rating-badge']",
            "span.business-rating-amount-view__processed"
        ]

        data['rating'] = ''
        import re
        for selector in rating_selectors:
            rating_el = page.query_selector(selector)
            if rating_el:
                raw_text = rating_el.inner_text().strip()
                 # Ищем число (например 4.9 или 4,9)
                match = re.search(r'(\d+[.,]\d+)', raw_text)
                if match:
                    rating_text = match.group(1).replace(',', '.')
                    data['rating'] = rating_text
                    print(f"✅ Найден рейтинг: {rating_text} (из '{raw_text}', селектор: {selector})")
                    break
                elif raw_text and raw_text[0].isdigit():
                     # Fallback for single digit like '5' without decimal
                     rating_text = raw_text.split()[0].replace(',', '.')
                     data['rating'] = rating_text
                     print(f"✅ Найден рейтинг (fallback): {rating_text} (из '{raw_text}')")
                     break
        if not data['rating']:
            print("❌ Рейтинг не найден ни по одному селектору")
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

    # --- КОЛИЧЕСТВО ОТЗЫВОВ ---
    try:
        reviews_count = ''
        # 1. С вкладки "Отзывы"
        counter_el = page.query_selector("div.tabs-select-view__title._name_reviews div.tabs-select-view__counter")
        if counter_el:
            reviews_count = counter_el.inner_text().strip()
        # 2. Из заголовка секции отзывов
        if not reviews_count:
            h2_el = page.query_selector("h2.card-section-header__title._wide")
            if h2_el:
                import re
                match = re.search(r"(\d+)", h2_el.inner_text())
                if match:
                    reviews_count = match.group(1)
        data['reviews_count'] = reviews_count
    except Exception:
        data['reviews_count'] = ''

    # Краткое время работы (на главной) - улучшенный парсинг
    try:
        hours_selectors = [
            # User provided
            "div.business-working-status-view",
            # Standard
            "div.card-feature-view__wrapper",
            "div.business-working-status-view__text",
            "div[class*='working-status']",
            "div[class*='hours']",
            "div.card-feature-view__content",
            "div.business-contacts-view__hours",
            "span[class*='working']",
            "div:has-text('Открыто')",
            "div:has-text('Закрыто')"
        ]
        
        data['hours_short'] = ''
        for selector in hours_selectors:
            hours_el = page.query_selector(selector)
            if hours_el:
                hours_text = hours_el.inner_text().strip()
                print(f"Кандидат на часы работы: '{hours_text}' (селектор: {selector})")
                if hours_text and ('Открыто' in hours_text or 'Закрыто' in hours_text or 'до' in hours_text):
                    data['hours_short'] = hours_text
                    print(f"Найдены часы работы: {data['hours_short']}")
                    break
                    
        # Если не найдено, пробуем общий поиск
        if not data['hours_short']:
            all_elements = page.query_selector_all("*")
            for elem in all_elements:
                try:
                    text = elem.inner_text().strip()
                    if text and ('Открыто до' in text or 'Закрыто' in text) and len(text) < 50:
                        data['hours_short'] = text
                        print(f"Найдены часы работы в общем поиске: {data['hours_short']}")
                        break
                except:
                    continue
                    
    except Exception as e:
        print(f"Ошибка при парсинге краткого времени работы: {e}")
        data['hours_short'] = ''

    # Клик по кнопке "График" для полного расписания
    try:
        schedule_btn = page.query_selector("div.business-working-status-view, div.card-feature-view__additional, div.card-feature-view__value")
        if schedule_btn and schedule_btn.is_visible():
            print("Кликаем по кнопке 'График' для полного расписания")
            schedule_btn.click()
            page.wait_for_timeout(1500)
        else:
            print("Кнопка 'График' не найдена или не видна")
    except Exception as e:
        print(f"Ошибка при попытке кликнуть по кнопке 'График': {e}")

    # После клика ищем полное расписание (улучшенный парсинг)
    try:
        schedule_selectors = [
            "div.business-working-intervals-view._wide._card",
            "div.business-working-intervals-view",
            "div[class*='working-intervals']",
            "div[class*='schedule']",
            "table[class*='schedule']",
            "div:has-text('Понедельник')",
            "div:has-text('Вторник')"
        ]
        
        intervals_table = None
        for selector in schedule_selectors:
            intervals_table = page.query_selector(selector)
            if intervals_table:
                print(f"Найдена таблица расписания: {selector}")
                break
                
        hours_full = []
        if intervals_table:
            rows = intervals_table.query_selector_all("div.business-working-intervals-view__item, tr, div[class*='interval']")
            print(f"Найдено строк расписания: {len(rows)}")
            for row in rows:
                day_el = row.query_selector("div.business-working-intervals-view__day, td:first-child, div[class*='day']")
                interval_el = row.query_selector("div.business-working-intervals-view__interval, td:last-child, div[class*='time']")
                day = day_el.inner_text().strip() if day_el else ''
                interval = interval_el.inner_text().strip() if interval_el else ''
                print(f"  День: '{day}', часы: '{interval}'")
                if day and interval:
                    hours_full.append(f"{day}: {interval}")
        else:
            print("Таблица полного расписания не найдена!")
            
        data['hours_full'] = hours_full
        
        # Если полное расписание не найдено, используем краткое
        if not hours_full and data.get('hours_short'):
            data['hours'] = data['hours_short']
        elif hours_full:
            # Краткая форма: если все дни одинаковые, выводим "Пн-Вс: 10:00–00:00"
            try:
                if len(set([h.split(': ')[1] for h in hours_full])) == 1:
                    interval = hours_full[0].split(': ')[1]
                    data['hours'] = f"Пн-Вс: {interval}"
                    print(f"Все дни одинаковые, краткая форма: {data['hours']}")
                else:
                    data['hours'] = '; '.join(hours_full)
                    print(f"Часы работы по дням: {data['hours']}")
            except:
                data['hours'] = '; '.join(hours_full)
        else:
            data['hours'] = ''
            
    except Exception as e:
        print(f"Ошибка при парсинге полного расписания: {e}")
        data['hours'] = data.get('hours_short', '')
        data['hours_full'] = []

    # Социальные сети
    try:
        social_links = []
        # General search + WhatsApp
        social_els = page.query_selector_all("a[href*='vk.com'], a[href*='instagram.com'], a[href*='facebook.com'], a[href*='twitter.com'], a[href*='ok.ru'], a[href*='t.me'], a[href*='whatsapp.com'], a[href*='wa.me']")
        for el in social_els:
            href = el.get_attribute('href')
            if href and href not in social_links:
                social_links.append(href)
        
        # Specific search in "Messengers" block (User provided)
        try:
            messenger_block = page.query_selector("div.business-contacts-view__social-links")
            if messenger_block:
                messenger_links = messenger_block.query_selector_all("a")
                for link in messenger_links:
                    href = link.get_attribute('href')
                    if href and href not in social_links:
                        print(f"Ссылка из блока мессенджеров: {href}")
                        social_links.append(href)
        except Exception as e:
            print(f"Ошибка при парсинге блока мессенджеров: {e}")

        data['social_links'] = social_links
    except Exception:
        data['social_links'] = []

    # --- ПЕРЕХОД НА ВКЛАДКУ "Товары и услуги" ---
    # --- ПЕРЕХОД НА ВКЛАДКУ "Товары и услуги" ---
    products_tab = page.query_selector("div.carousel__content > div:nth-child(2) > div, div[role='tab']:has-text('Товары и услуги'), div[role='tab']:has-text('Услуги'), div[role='tab']:has-text('Цены'), button:has-text('Товары и услуги'), button:has-text('Услуги'), div.tabs-select-view__title._name_prices")
    if products_tab:
        products_tab.click()
        print("Клик по вкладке 'Товары и услуги'")
        page.wait_for_timeout(1500)
    # --- ПАРСИНГ ТОВАРОВ И УСЛУГ ПО КАТЕГОРИЯМ ---
    try:
        products = []
        product_categories = []  # Новый список для названий категорий
        category_blocks = page.query_selector_all('div.business-full-items-grouped-view__category')
        for cat_block in category_blocks:
            # Название категории
            cat_title_el = cat_block.query_selector('div.business-full-items-grouped-view__title')
            category = cat_title_el.inner_text().strip() if cat_title_el else ''
            if category:
                product_categories.append(category)
            # Все услуги/товары в категории
            items = []
            item_blocks = cat_block.query_selector_all('div.business-full-items-grouped-view__item')
            for item in item_blocks:
                # Пробуем сначала фото-товары
                name_el = item.query_selector('div.related-item-photo-view__title')
                desc_el = item.query_selector('div.related-item-photo-view__description')
                price_el = item.query_selector('span.related-product-view__price')
                duration_el = item.query_selector('span.related-product-view__volume')
                photo_el = item.query_selector('img.image__img')

                # Если не найдено, пробуем текстовые услуги (related-item-list-view)
                if not name_el:
                    name_el = item.query_selector('div.related-item-list-view__title')
                if not price_el:
                    price_el = item.query_selector('div.related-item-list-view__price')
                if not desc_el:
                    desc_el = item.query_selector('div.related-item-list-view__subtitle')
                # Фото для таких услуг обычно нет

                name = name_el.inner_text().strip() if name_el else ''
                description = desc_el.inner_text().strip() if desc_el else ''
                price = price_el.inner_text().strip() if price_el else ''
                duration = duration_el.inner_text().strip() if duration_el else ''
                photo = photo_el.get_attribute('src') if photo_el else ''

                items.append({
                    'name': name,
                    'description': description,
                    'price': price,
                    'duration': duration,
                    'photo': photo
                })
            products.append({
                'category': category,
                'items': items
            })
        data['products'] = products
        data['product_categories'] = product_categories  # Сохраняем список категорий

        # Дополнительный парсинг для структуры related-product-view (Novamed)
        if not products:
            try:
                print("Пробуем альтернативный парсинг услуг (related-product-view)...")
                # Ищем контейнеры категорий или просто списки
                related_items = page.query_selector_all("div.related-product-view")
                if related_items:
                    items = []
                    for item in related_items:
                        name_el = item.query_selector("div.related-product-view__title, a.related-product-view__title")
                        price_el = item.query_selector("span.related-product-view__price")
                        
                        name = name_el.inner_text().strip() if name_el else ""
                        price = price_el.inner_text().strip() if price_el else ""
                        
                        if name:
                            items.append({
                                'name': name,
                                'description': '',
                                'price': price,
                                'duration': '',
                                'photo': ''
                            })
                    
                    if items:
                        products.append({
                            'category': 'Услуги',
                            'items': items
                        })
                        print(f"Найдено {len(items)} услуг через related-product-view")
                        data['products'] = products
            except Exception as e:
                print(f"Ошибка при альтернативном парсинге услуг: {e}")
    except Exception:
        data['products'] = []
        data['product_categories'] = []

    return data

def parse_reviews(page):
    """Парсит отзывы с правильным подсчетом"""
    import time
    start_time = time.time()
    max_processing_time = 300  # Максимум 5 минут на обработку отзывов
    
    try:
        reviews_tab = page.query_selector("div.carousel__content > div:nth-child(5) > div, div.tabs-select-view__title._name_reviews, div[role='tab']:has-text('Отзывы'), button:has-text('Отзывы')")
        if reviews_tab:
            reviews_tab.click()
            print("Клик по вкладке 'Отзывы'")
            page.wait_for_timeout(2000)
        else:
            print("Вкладка 'Отзывы' не найдена!")
        
        reviews_data = {"items": [], "rating": "", "reviews_count": ""}

        # Рейтинг и количество отзывов - ПРАВИЛЬНЫЙ подсчет
        try:
            rating_el = page.query_selector("span.business-rating-badge-view__rating-text")
            reviews_data['rating'] = rating_el.inner_text().replace(',', '.').strip() if rating_el else ''

            # Правильный подсчет количества отзывов из заголовка секции
            count_selectors = [
                "h2.card-section-header__title._wide",
                "div.business-reviews-card-view__header h2",
                "h2:has-text('отзыв')",
                "span.business-rating-badge-view__reviews-count",
                "div.business-header-rating-view__text._clickable",
                "div[class*='reviews-count']",
                "span:has-text('отзыв')",
                "[class*='rating-badge'] [class*='count']"
            ]

            reviews_data['reviews_count'] = ''
            for selector in count_selectors:
                count_el = page.query_selector(selector)
                if count_el:
                    text = count_el.inner_text().strip()
                    # Извлекаем числа из текста типа "125 отзывов" или "1 отзыв"  
                    import re
                    match = re.search(r"(\d+(?:\s*\d+)*)", text.replace('\xa0', ' ').replace(' ', ''))
                    if match:
                        # Очищаем от пробелов и берем только цифры
                        number_str = re.sub(r'\D', '', match.group(1))
                        if number_str:
                            reviews_data['reviews_count'] = number_str
                            print(f"Найдено количество отзывов: {reviews_data['reviews_count']}")
                            break
        except Exception as e:
            print(f"Ошибка при подсчете отзывов: {e}")
            pass

        # Скролл для загрузки отзывов - ВОЗВРАЩАЕМ ОРИГИНАЛЬНЫЕ ПАРАМЕТРЫ
        max_loops = 100  # Возвращаем оригинальное значение
        patience = 30    # Возвращаем оригинальное значение
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
            time.sleep(random.uniform(1.5, 2.5))  # Возвращаем оригинальное время ожидания

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
            
            # Дополнительная проверка - если уже много отзывов, можно остановиться
            if current_count >= 50:  # Если уже 50+ отзывов, этого достаточно
                print(f"Достаточно отзывов собрано: {current_count}")
                break

        # Парсим отзывы с ИМЕНАМИ авторов - ОБРАБАТЫВАЕМ ВСЕ
        try:
            review_blocks = page.query_selector_all("div.business-review-view, div[class*='business-review-view']")
            print(f"Найдено блоков отзывов: {len(review_blocks)}")

            for i, block in enumerate(review_blocks):
                # Проверяем время обработки
                if time.time() - start_time > max_processing_time:
                    print(f"Превышено время обработки отзывов ({max_processing_time} сек), завершаем...")
                    break
                
                # Добавляем прогресс для больших объёмов
                if i > 0 and i % 20 == 0:
                    print(f"Обработано {i} отзывов...")
                
                # Ограничиваем время обработки отзывов (максимум 2 минуты)
                if i > 0 and i % 50 == 0:
                    print(f"Обработано {i} отзывов, продолжаем...")
                    # Небольшая пауза для предотвращения зависания
                    time.sleep(0.1)
                try:
                    # Имя автора - УЛУЧШЕННЫЙ парсинг
                    author = ""
                    author_selectors = [
                        "span.business-review-view__author-name",
                        "div.business-review-view__author span",
                        "div.business-review-view__author",
                        "[class*='author-name']",
                        "[data-bem*='author'] span"
                    ]

                    for selector in author_selectors:
                        author_elem = block.query_selector(selector)
                        if author_elem:
                            author_text = author_elem.inner_text().strip()
                            if author_text and not author_text.isspace():
                                author = author_text
                                break

                    # Дата - расширенный парсинг
                    date = ""
                    date_selectors = [
                        "div.Review-RatingDate",  # Селектор из кабинета Яндекс.Бизнес
                        "div.Review-InfoWrapper > div > div.Review-RatingDate",  # Полный путь
                        "div.business-review-view__date",
                        "span.business-review-view__date",
                        "span[class*='date']",
                        "time[datetime]",
                        "time",
                        "[data-date]",
                        "div[class*='review-date']",
                        "span[class*='review-date']"
                    ]
                    for selector in date_selectors:
                        date_el = block.query_selector(selector)
                        if not date_el:
                            continue
                        
                        # Пробуем атрибут datetime (если есть)
                        date_attr = date_el.get_attribute('datetime')
                        if date_attr:
                            date = date_attr.strip()
                            break
                        
                        # Пробуем атрибут data-date
                        data_date_attr = date_el.get_attribute('data-date')
                        if data_date_attr:
                            date = data_date_attr.strip()
                            break
                        
                        # Пробуем атрибут title (может содержать дату)
                        title_attr = date_el.get_attribute('title')
                        if title_attr and any(year in title_attr for year in ['202', '2023', '2024', '2025']):
                            date = title_attr.strip()
                            break
                        
                        # Иначе берем текст
                        date_text = date_el.inner_text().strip()
                        if date_text:
                            date = date_text
                            break
                    
                    # Если не нашли, логируем
                    if not date:
                        print(f"ℹ️ Дата не найдена для отзыва: {text[:50] if 'text' in locals() else 'N/A'}...")

                    # Рейтинг (звёзды) - улучшенный парсинг
                    rating = 0

                    # Расширенные селекторы для звёзд
                    star_selectors = [
                        "span.business-rating-view__star._fill",
                        "span[class*='star-fill']", 
                        "span[class*='rating-star'][class*='fill']",
                        "div.business-rating-view__stars span._fill",
                        "span.business-review-view__rating-star._fill",
                        "div[class*='stars'] span[class*='fill']",
                        "span[class*='star'][class*='active']"
                    ]

                    for selector in star_selectors:
                        rating_els = block.query_selector_all(selector)
                        if rating_els and len(rating_els) > 0:
                            rating = len(rating_els)
                            break

                    # Если не нашли звёзды, ищем атрибут с рейтингом
                    if rating == 0:
                        rating_meta = block.query_selector("meta[itemprop='ratingValue']")
                        if rating_meta:
                            try:
                                rating = int(float(rating_meta.get_attribute('content')))
                            except:
                                pass

                    # Если всё ещё не нашли, ищем текстовый рейтинг
                    if rating == 0:
                        rating_text_selectors = [
                            "span[class*='rating-text']",
                            "div[class*='score']",
                            "div.business-review-view__rating",
                            "span[class*='review-rating']"
                        ]

                        for selector in rating_text_selectors:
                            rating_text_elem = block.query_selector(selector)
                            if rating_text_elem:
                                rating_text = rating_text_elem.inner_text().strip()
                                # Ищем число в тексте (например "5 из 5", "4.5")
                                import re
                                match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
                                if match:
                                    try:
                                        rating = int(float(match.group(1)))
                                        break
                                    except:
                                        continue

                    # Текст отзыва
                    text_el = block.query_selector("span.business-review-view__body-text, div.business-review-view__body, div[class*='review-text']")
                    text = text_el.inner_text().strip() if text_el else ""

                    # Ответ организации - улучшенный парсинг
                    reply = ""
                    try:
                        # Ищем кнопку для раскрытия ответа
                        reply_btn_selectors = [
                            "div.business-review-view__comment-expand[aria-label='Посмотреть ответ организации']",
                            "div.business-review-view__comment-expand",
                            "button[aria-label*='ответ']",
                            "div[class*='comment-expand']",
                            "div[class*='reply']",
                            "button:has-text('ответ')",
                            "div:has-text('ответ организации')"
                        ]
                        
                        reply_clicked = False
                        for selector in reply_btn_selectors:
                            reply_btn = block.query_selector(selector)
                            if not reply_btn or not reply_btn.is_visible():
                                continue
                            
                            try:
                                reply_btn.click()
                                page.wait_for_timeout(500)
                                reply_clicked = True
                                print(f"Клик по кнопке ответа: {selector}")
                                break
                            except Exception as e:
                                print(f"Ошибка при клике по кнопке ответа {selector}: {e}")
                                continue
                        
                        # Ищем текст ответа
                        reply_selectors = [
                            "div.business-review-comment-content__bubble",
                            "div.business-review-view__comment",
                            "div[class*='comment-content']",
                            "div[class*='reply-content']",
                            "div[class*='business-reply']",
                            "div:has-text('ответ')"
                        ]
                        
                        for selector in reply_selectors:
                            reply_el = block.query_selector(selector)
                            if not reply_el:
                                continue
                            
                            reply_text = reply_el.inner_text().strip()
                            if not reply_text or len(reply_text) <= 10:
                                continue
                            
                            reply = reply_text
                            print(f"✅ Найден ответ организации (HTML парсинг): {reply[:50]}...")
                            break
                                    
                    except Exception as e:
                        print(f"⚠️ Ошибка при парсинге ответа организации: {e}")
                        pass
                    
                    # Логируем, если ответ не найден
                    if not reply:
                        print(f"ℹ️ Ответ организации не найден для отзыва: {text[:50]}...")

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
        # Переход на вкладку "Новости"
        news_tab = page.query_selector("div.carousel__content > div:nth-child(3), div.tabs-select-view__title._name_posts, div[role='tab']:has-text('Новости'), button:has-text('Новости')")
        if news_tab:
            news_tab.click()
            print("Клик по вкладке 'Новости'")
            page.wait_for_timeout(1500)
            # Скролл для новостей
            for i in range(20):
                page.mouse.wheel(0, 1000)
                time.sleep(1.5)
        else:
            print("Вкладка 'Новости' не найдена")
            return []

        # Парсинг новостей - как в рабочем коде
        news = []
        news_blocks = page.query_selector_all('div.business-posts-list-post-view')
        for block in news_blocks:
            try:
                date_el = block.query_selector('div.business-posts-list-post-view__date')
                date = date_el.inner_text().strip() if date_el else ''

                text_el = block.query_selector('div.business-posts-list-post-view__text')
                text = text_el.inner_text().strip() if text_el else ''

                photo_els = block.query_selector_all('img.image__img')
                photos = [el.get_attribute('src') for el in photo_els if el.get_attribute('src')]

                news.append({
                    'date': date,
                    'text': text,
                    'photos': photos
                })
            except Exception:
                continue

        print(f"Спарсено новостей: {len(news)}")
        return news
    except Exception as e:
        print(f"Ошибка при парсинге новостей: {e}")
        return []

def get_photos_count(page):
    """Получает количество фотографий"""
    try:
        # Пробуем разные селекторы для вкладки "Фото"
        photo_tab_selectors = [
            "div.tabs-select-view__title._name_gallery",
            "div[role='tab']:has-text('Фото')",
            "button:has-text('Фото')",
            "div.tabs-select-view__title:has-text('Фото')"
        ]
        
        photos_tab = None
        for selector in photo_tab_selectors:
            try:
                photos_tab = page.query_selector(selector)
                if photos_tab:
                    break
            except:
                continue
                
        if photos_tab:
            try:
                counter = photos_tab.query_selector("div.tabs-select-view__counter")
                if counter:
                    return counter.inner_text().strip()
            except Exception:
                pass
        return "0"
    except Exception:
        return "0"

def parse_photos(page):
    """Парсинг фотографий"""
    try:
        photos_tab = page.query_selector("div.carousel__content > div:nth-child(4), div.tabs-select-view__title._name_gallery, div[role='tab']:has-text('Фото'), button:has-text('Фото')")
        if photos_tab:
            photos_tab.click()
            print("Клик по вкладке 'Фото'")
            page.wait_for_timeout(1500)

            # Скролл для загрузки фото
            for i in range(20):
                page.mouse.wheel(0, 1000)
                time.sleep(1.5)

        photos = []
        img_elems = page.query_selector_all("img.image__img, img[src*='avatars.mds.yandex.net']")
        for img in img_elems:
            src = img.get_attribute('src')
            if src and src not in photos:
                photos.append(src)
        return photos
    except Exception:
        return []

def parse_features(page):
    """Парсинг особенностей"""
    try:
        # Переход на вкладку "Особенности"
        features_tab = page.query_selector("div.carousel__content > div:nth-child(6) > div, div.tabs-select-view__title._name_features, div[role='tab']:has-text('Особенности'), button:has-text('Особенности')")
        if features_tab:
            features_tab.click()
            print("Клик по вкладке 'Особенности'")
            page.wait_for_timeout(1500)
        else:
            print("Вкладка 'Особенности' не найдена!")
            
        # USER_PROVIDED_SELECTOR: div.business-card-view__overview > div:nth-child(17) > div
        # Пробуем спарсить блок особенностей по указанию пользователя
        try:
             user_features_block = page.query_selector("div.business-card-view__overview > div:nth-child(17) > div")
             if user_features_block:
                 print("Found user-specified features block")
                 # Extract text content as raw features if traditional parsing returns nothing
                 items = user_features_block.query_selector_all("div, span, li")
                 # This logic is tentative; extraction depends on internal structure
                 # But sticking to standard parsing first is safer if the tab click worked.
        except:
             pass

        # Парсинг особенностей - как в рабочем коде
        features = []
        feature_blocks = page.query_selector_all("[class*='features-view__item']")
        for block in feature_blocks:
            name_el = block.query_selector("[class*='features-view__item-title']")
            value_el = block.query_selector("[class*='features-view__item-value']")
            name = name_el.inner_text().strip() if name_el else ''
            value = value_el.inner_text().strip() if value_el else ''
            if name or value:
                features.append({"name": name, "value": value})

        # Парсинг булевых особенностей (галочки с типом)
        features_bool = []
        bool_items = page.query_selector_all("div.business-features-view__bool-item")
        for item in bool_items:
            text_el = item.query_selector("div.business-features-view__bool-text")
            icon_el = item.query_selector("div.business-features-view__bool-icon")
            text = text_el.inner_text().strip() if text_el else ''
            is_defined = False
            if icon_el and '_defined' in (icon_el.get_attribute('class') or ''):
                is_defined = True
            if text:
                features_bool.append({"text": text, "defined": is_defined})

        # Дополнительно: отдельные business-features-view__bool-text без обёртки
        all_bool_texts = page.query_selector_all("div.business-features-view__bool-text")
        for text_el in all_bool_texts:
            text = text_el.inner_text().strip()
            if text and not any(fb['text'] == text for fb in features_bool):
                features_bool.append({"text": text, "defined": False})

        # Парсинг ценностных особенностей (категории услуг)
        features_valued = []
        valued_blocks = page.query_selector_all("div.business-features-view__valued")
        for block in valued_blocks:
            title_el = block.query_selector("span.business-features-view__valued-title")
            value_el = block.query_selector("span.business-features-view__valued-value")
            title = title_el.inner_text().strip(':').strip() if title_el else ''
            value = value_el.inner_text().strip() if value_el else ''
            if title or value:
                features_valued.append({"title": title, "value": value})

        # Выделение цен из features_valued
        features_prices = []
        for item in features_valued:
            if 'цена' in item['title'].lower() or '₽' in item['value']:
                features_prices.append(item)

        # Парсинг категорий из блока orgpage-categories-info-view
        categories_full = []
        cat_block = page.query_selector("div.orgpage-categories-info-view")
        if cat_block:
            cat_spans = cat_block.query_selector_all("span.button__text")
            categories_full = [span.inner_text().strip() for span in cat_spans if span.inner_text()]

        # Собираем все особенности в features_full
        features_full = {
            "bool": features_bool,
            "valued": features_valued,
            "prices": features_prices,
            "categories": categories_full
        }

        print(f"Найдено особенностей: bool={len(features_bool)}, valued={len(features_valued)}, prices={len(features_prices)}, categories={len(categories_full)}")
        return features_full
    except Exception as e:
        print(f"Ошибка при парсинге особенностей: {e}")
        return {
            "bool": [],
            "valued": [],
            "prices": [],
            "categories": []
        }

def parse_competitors(page):
    """Парсинг конкурентов из секции 'Похожие места рядом'"""
    try:
        competitors = []

        # Ищем секцию с похожими местами - добавляю актуальный селектор
        similar_selectors = [
            "div.card-similar-carousel",
            "div.card-similar-carousel-wide",
            "div[class*='carousel']",
            "div[role='presentation'][class*='carousel']"
        ]

        similar_section = None
        for selector in similar_selectors:
            similar_section = page.query_selector(selector)
            if similar_section:
                break

        if not similar_section:
            print("Секция конкурентов не найдена!")
            return []

        # Ищем ссылки на конкурентов
        competitor_links = similar_section.query_selector_all("a.link-wrapper")
        for link in competitor_links:
            try:
                url = link.get_attribute('href')
                if url and not url.startswith('http'):
                    url = 'https://yandex.ru' + url

                # Название конкурента
                title_el = link.query_selector("div.orgpage-similar-item__title")
                title = title_el.inner_text().strip() if title_el else ''

                # Категория
                category_el = link.query_selector("div.orgpage-similar-item__rubrics")
                category = category_el.inner_text().strip() if category_el else ''

                # Рейтинг
                rating_el = link.query_selector("span.business-rating-badge-view__rating-text, div.business-rating-badge-view__rating-text")
                rating = rating_el.inner_text().strip() if rating_el else ''

                if title and url:
                    competitors.append({
                        'title': title,
                        'url': url,
                        'category': category,
                        'rating': rating
                    })
                    print(f"Найден конкурент: {title} - {rating}")
            except Exception as e:
                print(f"Ошибка при парсинге конкурента: {e}")
                continue

        print(f"Всего найдено конкурентов: {len(competitors)}")
        return competitors[:5]  # Ограничиваем 5 конкурентами
    except Exception as e:
        print(f"Ошибка при поиске конкурентов: {e}")
        return []

# This code parses Yandex Maps public pages to extract information like title, address, phone, etc.