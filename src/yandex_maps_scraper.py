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

def _close_dialogs(page):
    """
    Закрывает всплывающие модальные окна, баннеры и диалоги.
    """
    try:
        dialog_close_btns = [
            "div.dialog__close-button",
            "button[aria-label='Закрыть']",
            "button.search-form-view__close", # Close search
            "div.popover__close",
            "a.close",
            ".dialog button",
            "div[class*='close-button']",
            "div.banner-view__close",
            "div.dialog" # Sometimes clicking the dialog itself helps? No.
        ]
        for sel in dialog_close_btns:
            try:
                btns = page.query_selector_all(sel)
                for btn in btns:
                    if btn.is_visible():
                        print(f"Закрываем диалог/баннер: {sel}")
                        btn.click()
                        page.wait_for_timeout(300)
            except:
                continue
    except Exception:
        pass

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
                _close_dialogs(page)

                overview_tab = page.query_selector("div.tabs-select-view__title._name_overview, div[role='tab']:has-text('Обзор'), button:has-text('Обзор')")
                if overview_tab:
                    # Force click via JS if obscured
                    try:
                        overview_tab.click(timeout=2000)
                    except:
                        print("Обычный клик не прошел, пробуем force click")
                        overview_tab.dispatch_event('click')
                        
                    print("Клик по вкладке 'Обзор'")
                    page.wait_for_timeout(2000)
            except Exception as e:
                print(f"Вкладка 'Обзор' не найдена или ошибка клика: {e}")

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
            data['products'] = parse_products(page)
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
        # 1. Primary selectors
        title_el = page.query_selector("h1.card-title-view__title, h1.orgpage-header-view__header, h1")
        data['title'] = title_el.inner_text().strip() if title_el else ''
        
        # 2. Fallback: Meta tags
        if not data['title']:
            og_title = page.query_selector("meta[property='og:title']")
            if og_title:
                content = og_title.get_attribute("content")
                if content:
                    data['title'] = content.replace(' — Яндекс Карты', '').strip()
                    print(f"✅ Найдено название из meta tag: {data['title']}")

        # 3. Fallback: Page title
        if not data['title']:
            data['title'] = page.title().replace(' — Яндекс Карты', '').strip()
            print(f"✅ Найдено название из page title: {data['title']}")
    except Exception as e:
        print(f"Ошибка получения названия: {e}")
        data['title'] = ''

    # Проверка на галочку верификации (синяя галочка)
    try:
        # Селекторы галочки
        verified_selectors = [
            ".business-verified-badge-view",
            "div._name_verified",
            ".business-card-view__verified-badge",
            "span[aria-label='Информация подтверждена владельцем']",
            "span.business-verified-badge", 
            "div.business-verified-badge"
        ]
        is_verified = False
        for sel in verified_selectors:
            if page.query_selector(sel):
                is_verified = True
                break
        
        data['is_verified'] = is_verified
        if is_verified:
            print("✅ Бизнес подтвержден (Синяя галочка)")
    except Exception as e:
        print(f"Ошибка проверки верификации: {e}")
        data['is_verified'] = False

    # Полный адрес
    try:
        address_selectors = [
            # User provided selector (High Priority)
            "div.orgpage-header-view__contacts > a",
            # Standard selectors
            "div.business-contacts-view__address",

            "div.orgpage-header-view__address",
            "a[href*='/maps/'][aria-label*='Россия']",
            # New generic fallbacks
            "div[class*='address']",
            "span[class*='address']",
            "a.link-view[href*='/maps/']" 
        ]
        
        data['address'] = ''
        for selector in address_selectors:
            # Try specific exact check first
            addr_elem = page.query_selector(selector)
            if addr_elem:
                addr_text = addr_elem.inner_text().strip()
                # Simple validation: should contain some letters and be reasonably long but not too long
                if addr_text and len(addr_text) > 5 and len(addr_text) < 200:
                    data['address'] = addr_text
                    print(f"✅ Найден адрес: {addr_text} (селектор: {selector})")
                    break
        
        # Fallback: Meta description
        if not data['address']:
             og_desc = page.query_selector("meta[property='og:description']")
             if og_desc:
                 content = og_desc.get_attribute("content")
                 if content:
                     # Description often format: "Place name, address. Phone..."
                     # This is a heuristic attempt
                     parts = content.split('.')
                     if len(parts) > 1:
                         data['address'] = parts[1].strip() # Often the second part
                         print(f"⚠️ Адрес взят из мета-описания (может быть неточным): {data['address']}")

        if not data['address']:
             print("❌ Адрес не найден ни по одному селектору. Используем заглушку.")
             data['address'] = "Адрес не указан (автоматически)"
    except Exception as e:
        print(f"Ошибка при парсинге адреса: {e}")
        data['address'] = "Ошибка парсинга адреса"

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
            "div.card-feature-view__content > div > div > div > div > div > div",
            # New generic matchers
            "button:has-text('показать')",
            "div[class*='phone'] button"
        ]

        phone_clicked = False
        for selector in phone_btn_selectors:
            try:
                # Get all matches to handle multiple buttons
                btns = page.query_selector_all(selector)
                for btn in btns:
                    if btn and btn.is_visible():
                        # Double check text if generic
                        if 'показать' in selector and 'телефон' not in btn.inner_text().lower() and 'номер' not in btn.inner_text().lower():
                             continue
                             
                        print(f"Кликаем по кнопке телефона: {selector}")
                        try:
                            btn.click(timeout=1000)
                        except:
                            btn.dispatch_event('click')
                        
                        page.wait_for_timeout(1000)
                        phone_clicked = True
                        # Don't break immediately, might be multiple phones? usually just one expander
                        break
                if phone_clicked:
                    break
            except Exception as e:
                # print(f"Ошибка при поиске/клике по селектору {selector}: {e}")
                continue

        if not phone_clicked:
            print("Кнопка 'Показать телефон' не найдена ни по одному селектору")
    except Exception as e:
        print(f"Ошибка при попытке кликнуть по кнопке телефона: {e}")
        pass

    # Телефон - улучшенный парсинг
    try:
        data['phone'] = ''
        
        # 1. Поиск ссылок tel:
        tel_links = page.query_selector_all("a[href^='tel:']")
        for link in tel_links:
            href = link.get_attribute('href')
            if href:
                phone = href.replace('tel:', '').strip()
                if len(phone) > 7:
                    data['phone'] = phone
                    print(f"✅ Найден телефон (href): {data['phone']}")
                    break
        
        # 2. Если не найдено, поиск по селекторам
        if not data['phone']:
            phone_selectors = [
                "div.orgpage-header-view__contacts", 
                "div.card-phones-view__phone-number",
                "span.business-phones-view__text",
                "div.business-contacts-view__phone-number"
            ]
            
            for selector in phone_selectors:
                elems = page.query_selector_all(selector)
                for elem in elems:
                    text = elem.inner_text().strip()
                    import re
                    # Ищем +7 или 8 и цифры
                    match = re.search(r'(\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text)
                    if match:
                        data['phone'] = match.group(0)
                        print(f"✅ Найден телефон (текст): {data['phone']}")
                        break
                if data['phone']:
                    break
                    
        # 3. Если всё ещё нет, ищем во всём хедере
        if not data['phone']:
             header = page.query_selector("div.orgpage-header-view__header, div.business-card-title-view__info")
             if header:
                 text = header.inner_text()
                 match = re.search(r'(\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text)
                 if match:
                     data['phone'] = match.group(0)
                     print(f"✅ Найден телефон (хедер): {data['phone']}")

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
        site_selectors = [
            "a.business-urls-view__link",
            "span.business-urls-view__text",
            "a[href*='http']:not([href*='yandex'])" # Generic external link
        ]
        data['site'] = ''
        for selector in site_selectors:
            el = page.query_selector(selector)
            if el:
                href = el.get_attribute('href')
                if href and 'yandex' not in href:
                    data['site'] = href
                    break
                # Fallback to text if it looks like domain
                text = el.inner_text().strip()
                if '.' in text and ' ' not in text:
                    data['site'] = text
                    break
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
            "div.business-header-rating-view__text",
            "div.business-rating-badge-view__rating",
            "span[class*='rating-text']",
            "div[class*='rating'] span",
            "span[class*='rating']"
        ]

        data['rating'] = ''
        import re
        
        # 1. Поиск по селекторам
        for selector in rating_selectors:
            rating_el = page.query_selector(selector)
            if rating_el:
                try:
                    text = rating_el.inner_text().strip()
                    # Ищем число с точкой или запятой (4.9, 5,0)
                    match = re.search(r'([0-5][.,]\d)', text)
                    if match:
                        data['rating'] = match.group(1).replace(',', '.')
                        print(f"✅ Найден рейтинг: {data['rating']} (селектор: {selector})")
                        break
                except:
                    continue
                    
        # 2. Если не найдено, ищем в заголовке любое число от 0 до 5
        if not data['rating']:
             header_el = page.query_selector("div.orgpage-header-view__header")
             if header_el:
                 header_text = header_el.inner_text()
                 match = re.search(r'\b([0-5][.,]\d)\b', header_text)
                 if match:
                     data['rating'] = match.group(1).replace(',', '.')
                     print(f"✅ Найден рейтинг в заголовке: {data['rating']}")

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
        
        # Если не найдено, пробуем общий поиск
        if not data['hours_short']:
            # Search for text containing keywords in the header area
            try:
                header_area = page.query_selector("div.orgpage-header-view__header, div.business-card-title-view__info")
                if header_area:
                    all_text = header_area.inner_text()
                    # Look for time patterns like "Ежедневно с 10:00 до 22:00" or synonyms
                    match = re.search(r'(Ежедневно|Пн|Вт|Ср|Чт|Пт|Сб|Вс)[^0-9]*\d{1,2}:\d{2}', all_text)
                    if match:
                         data['hours_short'] = match.group(0).split('\n')[0]
                         print(f"Найдены часы работы (regex): {data['hours_short']}")
            except:
                pass

            if not data['hours_short']:
                all_elements = page.query_selector_all("div, span")
                for elem in all_elements:
                    try:
                        text = elem.inner_text().strip()
                        if text and ('Открыто до' in text or 'Закрыто до' in text or 'Круглосуточно' in text) and len(text) < 50:
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
        _close_dialogs(page) # Закрываем диалоги перед кликом
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
    # Try multiple selectors for the tab
    products_tab_selectors = [
        "div[role='tab']:has-text('Товары')", 
        "div[role='tab']:has-text('Услуги')", 
        "div[role='tab']:has-text('Цены')", 
        "div[role='tab']:has-text('Меню')",
        "button:has-text('Товары')",
        "button:has-text('Услуги')",
        "button:has-text('Цены')",
        "div.tabs-select-view__title:has-text('Товары')",
        "div.tabs-select-view__title:has-text('Услуги')",
        "div.tabs-select-view__title:has-text('Цены')"
    ]
    
    products_tab = None
    for selector in products_tab_selectors:
        products_tab = page.query_selector(selector)
        if products_tab:
            print(f"Найдена вкладка услуг: {selector}")
            break
            
    if products_tab:
        _close_dialogs(page) # Закрываем диалоги перед кликом
        products_tab.click()
        print("Клик по вкладке услуг")
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
            _close_dialogs(page) # Закрываем диалоги перед кликом
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
        # Скролл для загрузки отзывов - ОПТИМИЗИРОВАНО (БЕЗ ЛИМИТА 15)
        # Рассчитываем целевое количество отзывов
        review_goal = 1000 # Дефолт
        try:
             goal_str = reviews_data.get('reviews_count', '0')
             if goal_str and goal_str.isdigit():
                 review_goal = int(goal_str)
                 print(f"Цель скачивания: {review_goal} отзывов")
        except:
             pass

        max_loops = 100 # Увеличено до 100 (хватит на ~500 отзывов)
        patience = 8    # Увеличено patience
        last_count = 0
        same_count = 0
        
        print(f"Начинаем скролл отзывов (макс {max_loops} циклов)...")

        for i in range(max_loops):
            # Проверяем тайм-аут
            if time.time() - start_time > max_processing_time:
                print("⚠️ Превышено время обработки отзывов")
                break
                
            # Прокручиваем вниз
            page.mouse.wheel(0, 1500) # Чуть больше скролл
            time.sleep(random.uniform(1.0, 2.0)) # Чуть быстрее

            # Проверяем количество загруженных отзывов
            current_reviews = page.query_selector_all("div.business-review-view, div[class*='review-item']")
            current_count = len(current_reviews)
            
            # Если достигли цели - выходим
            if current_count >= review_goal and review_goal > 0:
                 print(f"✅ Достигнута цель: {current_count} из {review_goal}")
                 break

            if current_count == last_count:
                same_count += 1
                # Пробуем "подтолкнуть" scroll
                if same_count > 3:
                     page.mouse.wheel(0, 500)
                     time.sleep(0.5)
                
                if same_count >= patience:
                    print(f"Скролл остановился на {current_count} отзывах")
                    break
            else:
                same_count = 0
                if current_count > last_count:
                    # print(f"Загружено {current_count} отзывов...")
                    pass
                last_count = current_count
                
            # Иногда двигаем мышь для эмуляции
            if i % 10 == 0:
                page.mouse.move(random.randint(200, 600), random.randint(400, 800))

        # Парсим отзывы с ИМЕНАМИ авторов - ОБРАБАТЫВАЕМ ВСЕ
        try:
            review_blocks = page.query_selector_all("div.business-review-view") # Strict selector
            if not review_blocks:
                 review_blocks = page.query_selector_all("div[class^='business-review-view ']") # Fallback
            print(f"Найдено блоков отзывов: {len(review_blocks)}")
            seen_hashes = set()

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
                    # Проверяем видимость (Yandex может дублировать элементы для разных layout)
                    if not block.is_visible():
                         continue

                    # 1. Сначала извлекаем текст и автора для дедупликации
                    text_el = block.query_selector("span.business-review-view__body-text, div.business-review-view__body, div[class*='review-text']")
                    text = text_el.inner_text().strip() if text_el else ""

                    # Имя автора
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

                    # Дата
                    date = ""
                    date_selectors = [
                        "div.Review-RatingDate", 
                        "div.Review-InfoWrapper > div > div.Review-RatingDate",
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
                        
                        # Пробуем атрибуты
                        date_attr = date_el.get_attribute('datetime') or date_el.get_attribute('data-date') or date_el.get_attribute('title')
                        if date_attr:
                            date = date_attr.strip()
                            break
                        
                        date_text = date_el.inner_text().strip()
                        if date_text:
                            date = date_text
                            break
                    
                    # --- ДЕДУПЛИКАЦИЯ ---
                    # Создаем уникальный ключ отзыва (более строгий)
                    # Используем полный текст, чтобы избежать коллизий
                    review_hash = f"{author}|{date}|{text}"
                    if review_hash in seen_hashes:
                        # Skip duplicate
                        continue
                    seen_hashes.add(review_hash)

                    # Логируем если даты нет (теперь текст доступен)
                    if not date:
                         # Только если текст длинный, чтобы не спамить пустышками
                         if len(text) > 10:
                             print(f"ℹ️ Дата не найдена для отзыва: {text[:30]}...")

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

                    # Текст отзыва (уже извлечен выше для дедупликации)
                    # text_el = block.query_selector("span.business-review-view__body-text, div.business-review-view__body, div[class*='review-text']")
                    # text = text_el.inner_text().strip() if text_el else ""

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
            for i in range(5):
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
            for i in range(5):
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
        features_tab_selectors = [
            "div[role='tab']:has-text('Особенности')",
            "div[role='tab']:has-text('Реквизиты')", 
            "button:has-text('Особенности')",
            "div.tabs-select-view__title:has-text('Особенности')"
        ]
        
        features_tab = None
        for selector in features_tab_selectors:
            features_tab = page.query_selector(selector)
            if features_tab:
                break
                
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
            title = block.query_selector("div.features-view__name, div.card-feature-view__name")
            val = block.query_selector("div.features-view__value, div.card-feature-view__value")
            if title:
                t = title.inner_text().strip()
                v = val.inner_text().strip() if val else "Да"
                features.append({"name": t, "value": v})
                
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

def parse_products(page):
    """Парсинг товаров и услуг"""
    print("Начинаем парсинг услуг/товаров...")
    try:
        # 1. Поиск и клик по вкладке "Цены" или "Товары"
        products_tab_selectors = [
            "div[role='tab']:has-text('Цены')",
            "div[role='tab']:has-text('Товары')",
            "div[role='tab']:has-text('Услуги')",
            "button:has-text('Цены')",
            "div.tabs-select-view__title._name_prices",
            "div.tabs-select-view__title._name_products"
        ]
        
        products_tab = None
        for selector in products_tab_selectors:
            try:
                products_tab = page.query_selector(selector)
                if products_tab and products_tab.is_visible():
                    print(f"Найдена вкладка услуг: {selector}")
                    break
            except:
                continue
                
        if products_tab:
            try:
                products_tab.click()
                print("Клик по вкладке услуг")
                page.wait_for_timeout(2000)
                
                # Скролл для подгрузки
                for i in range(3):
                    page.mouse.wheel(0, 1000)
                    time.sleep(1)
            except Exception as e:
                print(f"Ошибка при клике/скролле услуг: {e}")
        else:
            print("Вкладка 'Цены/Товары' не найдена")

        products = []
        
        # 2. Парсинг категорий и товаров
        # Попробуем найти контейнеры категорий
        category_selectors = [
            "div.business-full-items-view__category",
            "div.related-items-view__category",
            "div.business-prices-view__category"
        ]
        
        found_categories = False
        
        for cat_selector in category_selectors:
            cat_blocks = page.query_selector_all(cat_selector)
            if cat_blocks:
                found_categories = True
                print(f"Найдено {len(cat_blocks)} категорий по селектору {cat_selector}")
                
                for block in cat_blocks:
                    try:
                        cat_title_el = block.query_selector("div.business-full-items-view__category-title, div.related-items-view__category-title, h2")
                        cat_name = cat_title_el.inner_text().strip() if cat_title_el else "Разное"
                        
                        items_in_cat = []
                        # Ищем товары внутри категории
                        item_selectors = [
                            "div.business-full-items-view__item",
                            "div.related-item-view",
                            "div.business-prices-view__item"
                        ]
                        
                        for item_sel in item_selectors:
                            item_els = block.query_selector_all(item_sel)
                            for item_el in item_els:
                                try:
                                    name_el = item_el.query_selector("div.related-item-view__title, div.business-full-items-view__title, div.business-prices-view__name")
                                    if not name_el: continue
                                    name = name_el.inner_text().strip()
                                    
                                    price_el = item_el.query_selector("div.related-item-view__price, div.business-full-items-view__price, div.business-prices-view__price")
                                    price = price_el.inner_text().strip() if price_el else ""
                                    
                                    desc_el = item_el.query_selector("div.related-item-view__description, div.business-full-items-view__description")
                                    desc = desc_el.inner_text().strip() if desc_el else ""
                                    
                                    items_in_cat.append({
                                        "name": name,
                                        "price": price,
                                        "description": desc
                                    })
                                except:
                                    continue
                            if items_in_cat: break 
                            
                        if items_in_cat:
                            products.append({
                                "category": cat_name,
                                "items": items_in_cat
                            })
                    except Exception as e:
                        print(f"Ошибка парсинга категории: {e}")
                        continue
                break 
        
        # Если категории не найдены, ищем плоский список
        if not products:
            print("Категории не найдены, ищем плоский список товаров...")
            flat_items = []
            item_selectors = [
                "div.business-full-items-view__item",
                "div.related-item-view",
                "div.business-prices-view__item",
                "div.business-card-price-view",
                "div[class*='related-item-view']",
                "div[class*='business-items-view__item']"
            ]
            
            for item_sel in item_selectors:
                item_els = page.query_selector_all(item_sel)
                if item_els:
                    print(f"Найдено {len(item_els)} товаров (flat) по селектору {item_sel}")
                    for item_el in item_els:
                        try:
                            name_el = item_el.query_selector("div.related-item-view__title, div.business-full-items-view__title, div.business-prices-view__name, div.business-card-price-view__name")
                            if not name_el: continue
                            name = name_el.inner_text().strip()
                            
                            price_el = item_el.query_selector("div.related-item-view__price, div.business-full-items-view__price, div.business-prices-view__price, div.business-card-price-view__value")
                            price = price_el.inner_text().strip() if price_el else ""
                            
                            desc_el = item_el.query_selector("div.related-item-view__description, div.business-full-items-view__description")
                            desc = desc_el.inner_text().strip() if desc_el else ""
                            
                            flat_items.append({
                                "name": name,
                                "price": price,
                                "description": desc
                            })
                        except:
                            continue
                    if flat_items: break
            
            if flat_items:
                products.append({
                    "category": "Основные услуги",
                    "items": flat_items
                })

        print(f"Спарсено категорий услуг: {len(products)}")
        return products

    except Exception as e:
        print(f"Ошибка при парсинге услуг: {e}")
        return []

def parse_competitors(page):
    """Парсит конкурентов из HTML секции 'Похожие места'."""
    try:
        selectors = [
            "div.card-similar-carousel",
            "div.card-similar-carousel-wide",
            "div[class*='similar']",
            "div[class*='related']",
            "section[class*='related']",
            "div.orgpage-similar-items-view",
        ]
        containers = []
        for selector in selectors:
            containers.extend(page.query_selector_all(selector))

        if not containers:
            return []

        competitors = []
        seen = set()
        for container in containers:
            cards = container.query_selector_all("a[href*='/org/'], a.link-wrapper, div.orgpage-similar-item")
            for card in cards:
                try:
                    href = card.get_attribute("href")
                    if href and href.startswith("/"):
                        href = f"https://yandex.ru{href}"

                    name_el = card.query_selector(
                        "[class*='name'], .title, .orgpage-similar-item__title, .search-business-snippet-view__title"
                    )
                    name = name_el.inner_text().strip() if name_el else None
                    if not name:
                        continue
                    if name in seen:
                        continue
                    seen.add(name)

                    rating_el = card.query_selector("[class*='rating'], .business-rating-badge-view__rating-text")
                    category_el = card.query_selector("[class*='rubric'], [class*='category']")
                    competitors.append({
                        "name": name,
                        "title": name,
                        "url": href,
                        "rating": rating_el.inner_text().strip() if rating_el else "",
                        "category": category_el.inner_text().strip() if category_el else "",
                        "source": "html_parsing",
                    })
                except Exception:
                    continue

        if competitors:
            print(f"[parse_competitors] Found {len(competitors)} competitors via HTML")
        return competitors[:10]
    except Exception as e:
        print(f"[parse_competitors] Error: {e}")
        return []

# This code parses Yandex Maps public pages to extract information like title, address, phone, etc.
