"""
parser.py — Модуль для парсинга публичной страницы Яндекс.Карт с помощью Playwright
"""
from playwright.sync_api import sync_playwright
import time
import re
import random

def parse_yandex_card(url: str) -> dict:
    """
    Парсит публичную страницу Яндекс.Карт и возвращает данные в виде словаря.
    """
    try:
        print(f"Начинаем парсинг: {url}")
        
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError(f"Некорректная ссылка: {url}")
            
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # headless=True для скрытого режима
            page = browser.new_page()
            
            # Устанавливаем User-Agent
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
        page.goto(url, timeout=60000)
        page.wait_for_timeout(4000)  # Дать странице прогрузиться
        # --- ПЕРЕХОД НА ВКЛАДКУ 'Обзор' ---
        overview_tab = page.query_selector("div.tabs-select-view__title._name_overview, div[role='tab']:has-text('Обзор'), button:has-text('Обзор')")
        if overview_tab:
            overview_tab.click()
            print("Клик по вкладке 'Обзор'")
            page.wait_for_timeout(1500)
        else:
            print("Вкладка 'Обзор' не найдена!")
        # Скроллим вниз для подгрузки фото и отзывов (если нужно)
        page.mouse.wheel(0, 2000)
        time.sleep(2)
        # Дополнительная пауза для полной загрузки страницы
        time.sleep(2)
        data = {}
        # --- СБОР ДАННЫХ С "ОБЗОРА" ---
        # Название
        try:
            data['title'] = page.query_selector("h1").inner_text()
        except Exception:
            data['title'] = ''
        # Адрес
        try:
            addr_block = page.query_selector("a.orgpage-header-view__address")
            if addr_block:
                spans = addr_block.query_selector_all("span")
                address_parts = [s.inner_text() for s in spans if s.inner_text()]
                data['address'] = ', '.join(address_parts)
            else:
                data['address'] = ''
        except Exception:
            data['address'] = ''
        # Клик по кнопке 'Показать телефон' (если есть)
        try:
            show_phone_btn = page.query_selector("button:has-text('Показать телефон')")
            if show_phone_btn:
                show_phone_btn.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass
        # Телефон
        try:
            # Клик по кнопке "Показать телефон", если есть
            show_phone_btn = page.query_selector("button:has-text('Показать телефон'), div.card-phones-view__more, div.orgpage-phones-view__more")
            if show_phone_btn:
                show_phone_btn.click()
                page.wait_for_timeout(1000)
            # Пробуем разные варианты селекторов
            phone = None
            for selector in [
                "a[href^='tel:']",
                "span[itemprop='telephone']",
                "div.orgpage-phones-view__phone-number",
                "div.card-phones-view__number"
            ]:
                el = page.query_selector(selector)
                if el:
                    phone = el.inner_text()
                    break
            data['phone'] = phone if phone else ''
        except Exception:
            data['phone'] = ''
        # Сайт
        try:
            site_a = page.query_selector("a.business-urls-view__text")
            if site_a:
                data['site'] = site_a.get_attribute('href')
            else:
                site_span = page.query_selector("span.business-urls-view__text")
                data['site'] = site_span.inner_text().strip() if site_span else ''
        except Exception:
            data['site'] = ''
        # Часы работы
        try:
            hours = None
            # Пробуем несколько селекторов для часов работы
            selectors = [
                "[class*='business-working-status-view__text']",
                "div.business-working-status-view__text",
                "span.business-working-status-view__text",
                "[class*='working-status-view']",
                "[class*='business-hours']"
            ]
            
            for selector in selectors:
                hours = page.query_selector(selector)
                if hours:
                    break
            
            data['hours'] = hours.inner_text().strip() if hours else ''
        except Exception as e:
            print(f"Ошибка при парсинге часов работы: {e}")
            data['hours'] = ''
        # Полный график работы
        try:
            intervals = page.query_selector_all("div.business-working-intervals-view__item")
            full_schedule = []
            for interval in intervals:
                day_el = interval.query_selector("div.business-working-intervals-view__day")
                time_el = interval.query_selector("div.business-working-intervals-view__interval")
                day = day_el.inner_text().strip() if day_el else ''
                work_time = time_el.inner_text().strip() if time_el else ''
                if day and work_time:
                    full_schedule.append(f"{day}: {work_time}")
            data['hours_full'] = full_schedule
        except Exception:
            data['hours_full'] = []
        # Категории
        try:
            cats = page.query_selector_all("[class*='business-card-title-view__categories'] span")
            data['categories'] = [c.inner_text() for c in cats if c.inner_text()]
        except Exception:
            data['categories'] = []
        # Рейтинг
        try:
            rating_el = page.query_selector("span.business-rating-badge-view__rating-text")
            data['rating'] = rating_el.inner_text().replace(',', '.').strip() if rating_el else ''
        except Exception:
            data['rating'] = ''
        # Количество оценок (всех)
        try:
            ratings_count_el = None
            # Пробуем несколько селекторов для количества оценок
            selectors = [
                "div.business-header-rating-view__text._clickable",
                "span.business-rating-badge-view__reviews-count",
                "div.business-rating-badge-view__text",
                "[class*='rating-badge-view__reviews-count']",
                "[class*='header-rating-view__text']"
            ]
            
            for selector in selectors:
                ratings_count_el = page.query_selector(selector)
                if ratings_count_el:
                    break
            
            if ratings_count_el:
                import re
                text = ratings_count_el.inner_text()
                # Ищем числа в тексте, убираем неразрывные пробелы
                match = re.search(r"(\d+)", text.replace('\xa0', ' ').replace(' ', ''))
                data['ratings_count'] = match.group(1) if match else ''
            else:
                data['ratings_count'] = ''
        except Exception as e:
            print(f"Ошибка при парсинге количества оценок: {e}")
            data['ratings_count'] = ''
        # Описание
        try:
            desc = page.query_selector("[class*='card-about-view__description-text']")
            data['description'] = desc.inner_text() if desc else ''
        except Exception:
            data['description'] = ''
        # Фото (превью)
        try:
            imgs = page.query_selector_all("img[src*='avatars.mds.yandex.net']")
            data['photos_count'] = len(imgs)
        except Exception:
            data['photos_count'] = 0
        # Соцсети (иконки)
        try:
            social_icons = page.query_selector_all("span.business-contacts-view__social-icon")
            social_links = []
            for icon in social_icons:
                parent_a = icon.evaluate_handle('el => el.closest("a")')
                if parent_a:
                    href = parent_a.get_attribute('href')
                    if href:
                        social_links.append(href)
            data['social_links'] = social_links
        except Exception:
            data['social_links'] = []
        # Ближайшая станция метро
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
        # --- ПЕРЕХОД НА ВКЛАДКУ "Товары и услуги" ---
        products_tab = page.query_selector("div[role='tab']:has-text('Товары и услуги'), button:has-text('Товары и услуги'), div.tabs-select-view__title._name_prices")
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
        except Exception:
            data['products'] = []
            data['product_categories'] = []
        # --- ПЕРЕХОД НА ВКЛАДКУ "Новости" ---
        news_tab = page.query_selector("div.tabs-select-view__title._name_posts, div[role='tab']:has-text('Новости'), button:has-text('Новости')")
        if news_tab:
            news_tab.click()
            print("Клик по вкладке 'Новости'")
            page.wait_for_timeout(1500)
            # --- СКРОЛЛ ДЛЯ НОВОСТЕЙ ---
            for i in range(20):
                page.mouse.wheel(0, 1000)
                time.sleep(1.5)
        # --- ПАРСИНГ НОВОСТЕЙ ---
        try:
            news = []
            news_blocks = page.query_selector_all('div.business-posts-list-post-view')
            for block in news_blocks:
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
            data['news'] = news
        except Exception:
            data['news'] = []
        # --- ПЕРЕХОД НА ВКЛАДКУ "Фото" ---
        photos_tab = page.query_selector("div.tabs-select-view__title._name_gallery, div[role='tab']:has-text('Фото'), button:has-text('Фото')")
        if photos_tab:
            photos_tab.click()
            print("Клик по вкладке 'Фото'")
            page.wait_for_timeout(1500)
            # --- СКРОЛЛ ДЛЯ ФОТО ---
            for i in range(20):
                page.mouse.wheel(0, 1000)
                time.sleep(1.5)
        # --- ПАРСИНГ ФОТО ---
        try:
            photos = []
            img_elems = page.query_selector_all("img.image__img, img[src*='avatars.mds.yandex.net']")
            for img in img_elems:
                src = img.get_attribute('src')
                if src and src not in photos:
                    photos.append(src)
            data['photos'] = photos
            data['photos_count'] = len(photos)
        except Exception:
            data['photos'] = []
            data['photos_count'] = 0
        # --- ПЕРЕХОД НА ВКЛАДКУ "Отзывы" ---
        reviews_tab = page.query_selector("div.tabs-select-view__title._name_reviews, div[role='tab']:has-text('Отзывы'), button:has-text('Отзывы')")
        if reviews_tab:
            reviews_tab.click()
            print("Клик по вкладке 'Отзывы'")
            page.wait_for_timeout(2000)
        else:
            print("Вкладка 'Отзывы' не найдена!")
        # Парсим количество отзывов с вкладки
        try:
            reviews_count_elem = None
            # Пробуем несколько селекторов для количества отзывов
            selectors = [
                "h2.card-section-header__title._wide",
                "h2[class*='card-section-header__title']",
                "[class*='reviews-count']",
                "div.business-reviews-view__header",
                "[class*='section-header__title']"
            ]
            
            for selector in selectors:
                reviews_count_elem = page.query_selector(selector)
                if reviews_count_elem:
                    break
            
            if reviews_count_elem:
                import re
                text = reviews_count_elem.inner_text()
                # Ищем числа в тексте
                match = re.search(r"(\d+)", text.replace('\xa0', ' ').replace(' ', ''))
                reviews_count_from_tab = match.group(1) if match else ''
                # Используем количество отзывов с вкладки, если оно найдено
                if reviews_count_from_tab:
                    data['reviews_count'] = reviews_count_from_tab
            
            # Если не нашли на вкладке, оставляем то что было найдено ранее
            if not data.get('reviews_count'):
                data['reviews_count'] = str(len(review_blocks)) if review_blocks else ''
                
        except Exception as e:
            print(f"Ошибка при парсинге количества отзывов: {e}")
            # Fallback - считаем реально спарсенные отзывы
            data['reviews_count'] = str(len(review_blocks)) if 'review_blocks' in locals() else ''
        # Человекообразный скролл отзывов: wheel, mousemove, случайные паузы, иногда вверх, иногда клик по вкладке
        max_loops = 500
        patience = 100  # Было 30, стало 100
        last_count = 0
        same_count = 0
        for i in range(max_loops):
            # Иногда двигаем мышь по области отзывов
            if i % 7 == 0:
                page.mouse.move(random.randint(200, 600), random.randint(400, 800))
            # Иногда кликаем по вкладке 'Отзывы'
            if i % 25 == 0 and reviews_tab:
                reviews_tab.click()
                time.sleep(0.5)
            # Иногда прокручиваем немного вверх
            if i % 30 == 0 and i > 0:
                page.mouse.wheel(0, -500)
                time.sleep(0.7)
            # Wheel-скролл вниз
            page.mouse.wheel(0, random.randint(800, 1200))
            time.sleep(random.uniform(1.0, 1.7))
            review_blocks = page.query_selector_all("div.business-reviews-card-view__review")
            current_count = len(review_blocks)
            if current_count == last_count:
                same_count += 1
            else:
                same_count = 0
            if same_count >= patience:
                break
            last_count = current_count
        time.sleep(2)  # Финальная пауза
        review_blocks = page.query_selector_all("div.business-reviews-card-view__review")
        print("ФИНАЛЬНО wheel-скроллом отзывов найдено:", len(review_blocks))
        reviews = []
        for i, block in enumerate(review_blocks):
            print(f"Парсим отзыв №{i+1}")
            # Автор
            author_el = block.query_selector("div.business-review-view__author-name span[itemprop='name']")
            author = author_el.inner_text().strip() if author_el else ''
            # Дата
            date_el = block.query_selector("span.business-review-view__date span")
            date = date_el.inner_text().strip() if date_el else ''
            # Оценка
            score_el = block.query_selector("div.business-review-view__rating meta[itemprop='ratingValue']")
            score = score_el.get_attribute('content').strip() if score_el else ''
            # Текст отзыва
            text_el = block.query_selector("div.business-review-view__body .spoiler-view__text-container")
            if not text_el:
                text_el = block.query_selector("div.business-review-view__body")
            text = text_el.inner_text().strip() if text_el else ''
            # Ответ организации (если есть)
            org_reply = ''
            try:
                reply_btn = block.query_selector("div.business-review-view__comment-expand[aria-label='Посмотреть ответ организации']")
                if reply_btn and reply_btn.is_visible():
                    reply_btn.click()
                    for _ in range(10):
                        reply_el = block.query_selector("div.business-review-comment-content__bubble")
                        if reply_el:
                            org_reply = reply_el.inner_text().strip()
                            break
                        page.wait_for_timeout(200)
            except Exception:
                pass
            reviews.append({
                'author': author,
                'date': date,
                'score': score,
                'text': text,
                'org_reply': org_reply
            })

        data['reviews'] = {
            'items': reviews,
            'rating': data.get('rating', ''),
            'reviews_count': data.get('reviews_count', len(reviews))
        }
        # --- ПЕРЕХОД НА ВКЛАДКУ "Особенности" ---
        features_tab = page.query_selector("div.tabs-select-view__title._name_features, div[role='tab']:has-text('Особенности'), button:has-text('Особенности')")
        if features_tab:
            features_tab.click()
            print("Клик по вкладке 'Особенности'")
            page.wait_for_timeout(1500)
        else:
            print("Вкладка 'Особенности' не найдена!")
        # --- ПАРСИНГ ОСОБЕННОСТЕЙ ---
        features = []
        feature_blocks = page.query_selector_all("[class*='features-view__item']")
        for block in feature_blocks:
            name_el = block.query_selector("[class*='features-view__item-title']")
            value_el = block.query_selector("[class*='features-view__item-value']")
            name = name_el.inner_text().strip() if name_el else ''
            value = value_el.inner_text().strip() if value_el else ''
            if name or value:
                features.append({"name": name, "value": value})
        data['features'] = features

        # --- ПАРСИНГ БУЛЕВЫХ ОСОБЕННОСТЕЙ (галочки с типом) ---
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
        # --- ДОПОЛНИТЕЛЬНО: отдельные business-features-view__bool-text без обёртки ---
        all_bool_texts = page.query_selector_all("div.business-features-view__bool-text")
        for text_el in all_bool_texts:
            text = text_el.inner_text().strip()
            if text and not any(fb['text'] == text for fb in features_bool):
                features_bool.append({"text": text, "defined": False})

        # --- ПАРСИНГ ЦЕННОСТНЫХ ОСОБЕННОСТЕЙ (категории услуг) ---
        features_valued = []
        valued_blocks = page.query_selector_all("div.business-features-view__valued")
        for block in valued_blocks:
            title_el = block.query_selector("span.business-features-view__valued-title")
            value_el = block.query_selector("span.business-features-view__valued-value")
            title = title_el.inner_text().strip(':').strip() if title_el else ''
            value = value_el.inner_text().strip() if value_el else ''
            if title or value:
                features_valued.append({"title": title, "value": value})
        data['features_valued'] = features_valued

        # --- ВЫДЕЛЕНИЕ ЦЕН ИЗ features_valued ---
        features_prices = []
        for item in features_valued:
            if 'цена' in item['title'].lower() or '₽' in item['value']:
                features_prices.append(item)
        data['features_prices'] = features_prices

        # --- ПАРСИНГ КАТЕГОРИЙ ИЗ БЛОКА orgpage-categories-info-view ---
        categories_full = []
        cat_block = page.query_selector("div.orgpage-categories-info-view")
        if cat_block:
            cat_spans = cat_block.query_selector_all("span.button__text")
            categories_full = [span.inner_text().strip() for span in cat_spans if span.inner_text()]
        data['categories_full'] = categories_full

        # --- СОБИРАЕМ ВСЕ ОСОБЕННОСТИ В features_full ---
        data['features_full'] = {
            "bool": features_bool,
            "valued": features_valued,
            "prices": features_prices,
            "categories": categories_full
        }

        # --- ПАРСИНГ КОНКУРЕНТОВ ИЗ РАЗДЕЛА "ПОХОЖИЕ МЕСТА РЯДОМ" ---
        # Возвращаемся на вкладку Обзор для поиска конкурентов
        overview_tab = page.query_selector("div.tabs-select-view__title._name_overview, div[role='tab']:has-text('Обзор'), button:has-text('Обзор')")
        if overview_tab:
            overview_tab.click()
            page.wait_for_timeout(1500)

        competitors = []
        try:
            # Ищем блок "Похожие места рядом"
            similar_carousel = page.query_selector("div.card-similar-carousel")
            if similar_carousel:
                # Получаем все ссылки на конкурентов
                competitor_links = similar_carousel.query_selector_all("a.link-wrapper")
                print(f"Найдено конкурентов в карусели: {len(competitor_links)}")
                
                for i, link in enumerate(competitor_links[:3]):  # Берём только первых 3-х конкурентов
                    try:
                        competitor_url = link.get_attribute('href')
                        if competitor_url and not competitor_url.startswith('http'):
                            competitor_url = 'https://yandex.ru' + competitor_url
                        
                        # Получаем базовую информацию о конкуренте из карусели
                        competitor_title_el = link.query_selector("div.orgpage-similar-item__title")
                        competitor_title = competitor_title_el.inner_text().strip() if competitor_title_el else ''
                        
                        competitor_rubric_el = link.query_selector("div.orgpage-similar-item__rubrics")
                        competitor_rubric = competitor_rubric_el.inner_text().strip() if competitor_rubric_el else ''
                        
                        competitor_rating_el = link.query_selector("div.business-rating-badge-view__stars")
                        competitor_rating = ''
                        if competitor_rating_el:
                            # Подсчитываем количество заполненных звёзд
                            filled_stars = len(competitor_rating_el.query_selector_all("span._full"))
                            competitor_rating = str(filled_stars) if filled_stars > 0 else ''
                        
                        competitors.append({
                            'title': competitor_title,
                            'url': competitor_url,
                            'rubric': competitor_rubric,
                            'rating': competitor_rating,
                            'source': 'similar_places'
                        })
                        
                        print(f"Конкурент {i+1}: {competitor_title} - {competitor_url}")
                        
                    except Exception as e:
                        print(f"Ошибка при обработке конкурента {i+1}: {e}")
                        continue
            else:
                print("Блок 'Похожие места рядом' не найден")
                
        except Exception as e:
            print(f"Ошибка при парсинге конкурентов: {e}")

        data['competitors'] = competitors
        data['url'] = url
        browser.close()
        
        # Отладочная информация
        print(f"DEBUG: ratings_count = '{data.get('ratings_count', '')}'")
        print(f"DEBUG: reviews_count = '{data.get('reviews_count', '')}'") 
        print(f"DEBUG: hours = '{data.get('hours', '')}'")
        print(f"DEBUG: competitors found = {len(competitors)}")
        
        # Формируем overview для отчёта
        overview_keys = [
            'title', 'address', 'phone', 'site', 'description',
            'categories', 'hours', 'hours_full', 'rating', 'ratings_count', 'reviews_count', 'social_links'
        ]
        data['overview'] = {k: data.get(k, '') for k in overview_keys}
        
        print("Парсинг завершён успешно")
        return data
        
    except Exception as e:
        print(f"Ошибка при парсинге: {type(e).__name__}: {str(e)}")
        raise 