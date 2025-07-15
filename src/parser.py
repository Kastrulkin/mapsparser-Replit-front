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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=True для скрытого режима
        page = browser.new_page()
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
            site = page.query_selector("a.business-urls-view__text")
            data['site'] = site.get_attribute('href') if site else ''
        except Exception:
            data['site'] = ''
        # Часы работы
        try:
            hours = page.query_selector("[class*='business-working-status-view__text']")
            data['hours'] = hours.inner_text() if hours else ''
        except Exception:
            data['hours'] = ''
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
            ratings_count_el = page.query_selector("div.business-header-rating-view__text._clickable")
            if ratings_count_el:
                import re
                text = ratings_count_el.inner_text()
                match = re.search(r"(\d+)", text.replace('\xa0', ' '))
                data['ratings_count'] = match.group(1) if match else ''
            else:
                data['ratings_count'] = ''
        except Exception:
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
        # Соцсети
        try:
            socials = page.query_selector_all("a[href*='vk.com'], a[href*='instagram.com'], a[href*='facebook.com']")
            data['social_links'] = [s.get_attribute('href') for s in socials]
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
                    name_el = item.query_selector('div.related-item-photo-view__title')
                    name = name_el.inner_text().strip() if name_el else ''
                    desc_el = item.query_selector('div.related-item-photo-view__description')
                    description = desc_el.inner_text().strip() if desc_el else ''
                    price_el = item.query_selector('span.related-product-view__price')
                    price = price_el.inner_text().strip() if price_el else ''
                    duration_el = item.query_selector('span.related-product-view__volume')
                    duration = duration_el.inner_text().strip() if duration_el else ''
                    photo_el = item.query_selector('img.image__img')
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
            reviews_count_elem = page.query_selector("h2.card-section-header__title._wide")
            if reviews_count_elem:
                import re
                text = reviews_count_elem.inner_text()
                match = re.search(r"(\d+)", text.replace('\xa0', ' '))
                data['reviews_count'] = match.group(1) if match else ''
            else:
                data['reviews_count'] = ''
        except Exception:
            data['reviews_count'] = ''
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

        data['url'] = url
        browser.close()
        # Формируем overview для отчёта
        overview_keys = [
            'title', 'address', 'phone', 'site', 'description',
            'categories', 'hours', 'rating', 'reviews_count'
        ]
        data['overview'] = {k: data.get(k, '') for k in overview_keys}
        return data 