"""
analyzer.py — Модуль для анализа данных карточки и формирования рекомендаций по SEO
"""

import time
from playwright.sync_api import sync_playwright

def parse_overview(page):
    data = {}
    # Название
    try:
        data['title'] = page.query_selector("h1").inner_text()
    except Exception:
        data['title'] = ''
    # Адрес
    try:
        addr = page.query_selector("[class*='business-contacts-view__address'] span")
        data['address'] = addr.inner_text() if addr else ''
    except Exception:
        data['address'] = ''
    # Клик по кнопке "Показать телефон"
    try:
        show_phone_btn = page.query_selector("button:has-text('Показать телефон')")
        if show_phone_btn:
            show_phone_btn.click()
            page.wait_for_timeout(1000)
    except Exception:
        pass
    # Телефон
    try:
        phone = page.query_selector("a[href^='tel:']")
        data['phone'] = phone.inner_text() if phone else ''
    except Exception:
        data['phone'] = ''
    # Сайт
    try:
        site = page.query_selector("a.business-urls-view__text")
        data['site'] = site.get_attribute('href') if site else ''
    except Exception:
        data['site'] = ''
    # Описание
    try:
        desc = page.query_selector("[class*='card-about-view__description-text']")
        data['description'] = desc.inner_text() if desc else ''
    except Exception:
        data['description'] = ''
    # Категории
    try:
        cats = page.query_selector_all("[class*='business-card-title-view__categories'] span")
        data['categories'] = [c.inner_text() for c in cats if c.inner_text()]
    except Exception:
        data['categories'] = []
    # Часы работы
    try:
        hours = page.query_selector("[class*='business-working-status-view__text']")
        data['hours'] = hours.inner_text() if hours else ''
    except Exception:
        data['hours'] = ''
    return data

def analyze_card(card_data: dict) -> dict:
    """
    Анализирует данные карточки и возвращает оценку и рекомендации.
    """
    score = 0
    max_score = 10  # Количество параметров
    recommendations = []

    # Название
    if card_data.get('title'):
        score += 1
    else:
        recommendations.append('Добавьте название компании.')
    # Адрес
    if card_data.get('address'):
        score += 1
    else:
        recommendations.append('Укажите полный адрес компании.')
    # Телефон
    if card_data.get('phone'):
        score += 1
    else:
        recommendations.append('Добавьте номер телефона.')
    # Сайт
    if card_data.get('site'):
        score += 1
    else:
        recommendations.append('Добавьте сайт компании.')
    # Часы работы
    if card_data.get('hours'):
        score += 1
    else:
        recommendations.append('Укажите часы работы.')
    # Категории
    if card_data.get('categories'):
        score += 1
    else:
        recommendations.append('Добавьте категории деятельности.')
    # Рейтинг
    if card_data.get('rating'):
        score += 1
    else:
        recommendations.append('Получите первые отзывы для появления рейтинга.')
    # Количество отзывов
    if card_data.get('reviews_count') and card_data['reviews_count'] != '0':
        score += 1
    else:
        recommendations.append('Попросите клиентов оставить отзывы.')
    # Описание
    if card_data.get('description') and len(card_data['description']) >= 100:
        score += 1
    else:
        recommendations.append('Заполните подробное описание компании (не менее 100 символов).')
    # Фото
    photos_count = card_data.get('photos_count', 0)
    try:
        photos_count = int(photos_count) if photos_count else 0
    except (ValueError, TypeError):
        photos_count = 0
    
    if photos_count >= 5:
        score += 1
    else:
        recommendations.append('Добавьте не менее 5 фотографий (интерьер, услуги, сотрудники).')
    # Соцсети
    if card_data.get('social_links'):
        score += 0.5
    else:
        recommendations.append('Добавьте ссылки на соцсети (VK, Instagram, Facebook).')
    # Новости/лента
    if card_data.get('news_count', 0) > 0:
        score += 0.5
    else:
        recommendations.append('Публикуйте новости и акции в ленте компании.')

    # Итоговая оценка в процентах
    final_score = int((score / (max_score + 1)) * 100)
    return {
        'score': final_score,
        'recommendations': recommendations
    }

def parse_services(page):
    services = []
    # Клик по вкладке "Товары и услуги"
    try:
        services_tab = page.query_selector("div[role='tab']:has-text('Товары и услуги'), button:has-text('Товары и услуги')")
        if services_tab:
            services_tab.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass

    # Парсим услуги
    try:
        # Каждый блок услуги
        service_blocks = page.query_selector_all("[class*='services-list-item-view']")
        for block in service_blocks:
            try:
                category = ""
                # Иногда категория указана отдельным заголовком
                cat_elem = block.query_selector("[class*='services-list-item-view__category']")
                if cat_elem:
                    category = cat_elem.inner_text()
                name = block.query_selector("[class*='services-list-item-view__title']").inner_text()
                description = ""
                desc_elem = block.query_selector("[class*='services-list-item-view__description']")
                if desc_elem:
                    description = desc_elem.inner_text()
                price = ""
                price_elem = block.query_selector("[class*='services-list-item-view__price']")
                if price_elem:
                    price = price_elem.inner_text()
                photo = ""
                photo_elem = block.query_selector("img")
                if photo_elem:
                    photo = photo_elem.get_attribute('src')
                services.append({
                    "category": category,
                    "name": name,
                    "description": description,
                    "price": price,
                    "photo": photo
                })
            except Exception:
                continue
    except Exception:
        pass
    return services

def parse_news(page):
    news = []
    # Клик по вкладке "Новости" или "Лента"
    try:
        news_tab = page.query_selector("div[role='tab']:has-text('Новости'), button:has-text('Новости'), div[role='tab']:has-text('Лента'), button:has-text('Лента')")
        if news_tab:
            news_tab.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass

    # Парсим посты
    try:
        post_blocks = page.query_selector_all("[class*='feed-post-view']")
        for block in post_blocks:
            try:
                title = ""
                title_elem = block.query_selector("[class*='feed-post-view__title']")
                if title_elem:
                    title = title_elem.inner_text()
                text = ""
                text_elem = block.query_selector("[class*='feed-post-view__text']")
                if text_elem:
                    text = text_elem.inner_text()
                date = ""
                date_elem = block.query_selector("[class*='feed-post-view__date']")
                if date_elem:
                    date = date_elem.inner_text()
                photo = ""
                photo_elem = block.query_selector("img")
                if photo_elem:
                    photo = photo_elem.get_attribute('src')
                news.append({
                    "title": title,
                    "text": text,
                    "date": date,
                    "photo": photo
                })
            except Exception:
                continue
    except Exception:
        pass
    return news

def get_photos_count_from_tab(page):
    try:
        # Ищем элемент с классом tabs-select-view__title и _name_gallery
        tab = page.query_selector("div.tabs-select-view__title._name_gallery")
        if tab:
            counter = tab.query_selector("div.tabs-select-view__counter")
            if counter:
                count_text = counter.inner_text()
                return int(count_text)
    except Exception:
        pass
    return 0


def parse_photos(page):
    photos = []
    # Клик по вкладке "Фото"
    try:
        photos_tab = page.query_selector("div[role='tab']:has-text('Фото'), button:has-text('Фото')")
        if photos_tab:
            photos_tab.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass

    # Парсим все фото
    try:
        img_elems = page.query_selector_all("img[src*='avatars.mds.yandex.net']")
        for img in img_elems:
            src = img.get_attribute('src')
            if src and src not in photos:
                photos.append(src)
    except Exception:
        pass
    photos_count = get_photos_count_from_tab(page)
    return {
        "photos": photos,
        "photos_count": photos_count
    }

def parse_reviews(page):
    reviews = []
    # Клик по вкладке "Отзывы"
    try:
        reviews_tab = page.query_selector("div[role='tab']:has-text('Отзывы'), button:has-text('Отзывы')")
        if reviews_tab:
            reviews_tab.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass

    # Средняя оценка и количество отзывов
    try:
        rating_elem = page.query_selector("[class*='business-rating-badge-view__rating']")
        if rating_elem:
            reviews["rating"] = rating_elem.inner_text()
        count_elem = page.query_selector("[class*='business-rating-badge-view__reviews-count']")
        if count_elem:
            count_text = count_elem.inner_text()
            try:
                reviews["reviews_count"] = int(''.join(filter(str.isdigit, count_text)))
            except Exception:
                reviews["reviews_count"] = 0
    except Exception:
        pass

    # Парсим отзывы
    try:
        review_blocks = page.query_selector_all("[class*='business-review-view']")
        for block in review_blocks:
            try:
                author = ""
                author_elem = block.query_selector("[class*='business-review-view__author']")
                if author_elem:
                    author = author_elem.inner_text()
                date = ""
                date_elem = block.query_selector("[class*='business-review-view__date']")
                if date_elem:
                    date = date_elem.inner_text()
                score = ""
                score_elem = block.query_selector("[class*='business-review-view__rating']")
                if score_elem:
                    score = int(score_elem.inner_text()[0])  # Обычно "5 из 5"
                text = ""
                text_elem = block.query_selector("[class*='business-review-view__body-text']")
                if text_elem:
                    text = text_elem.inner_text()
                # Клик по "Посмотреть ответ организации"
                org_reply = ""
                try:
                    reply_btn = block.query_selector("button:has-text('Посмотреть ответ организации')")
                    if reply_btn:
                        reply_btn.click()
                        page.wait_for_timeout(500)
                except Exception:
                    pass
                reply_elem = block.query_selector("[class*='business-review-view__answer-text']")
                if reply_elem:
                    org_reply = reply_elem.inner_text()
                reviews.append({
                    "author": author,
                    "date": date,
                    "score": score,
                    "text": text,
                    "org_reply": org_reply
                })
            except Exception:
                continue
    except Exception:
        pass
    return reviews

def parse_features(page):
    features = []
    # Клик по вкладке "Особенности"
    try:
        features_tab = page.query_selector("div[role='tab']:has-text('Особенности'), button:has-text('Особенности')")
        if features_tab:
            features_tab.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass

    # Парсим особенности
    try:
        feature_blocks = page.query_selector_all("[class*='features-view__item']")
        for block in feature_blocks:
            try:
                name = ""
                value = ""
                name_elem = block.query_selector("[class*='features-view__item-title']")
                if name_elem:
                    name = name_elem.inner_text()
                value_elem = block.query_selector("[class*='features-view__item-value']")
                if value_elem:
                    value = value_elem.inner_text()
                if name or value:
                    features.append({"name": name, "value": value})
            except Exception:
                continue
    except Exception:
        pass
    return features

def parse_yandex_card(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_timeout(4000)
        page.mouse.wheel(0, 2000)
        time.sleep(2)

        data = {
            "overview": parse_overview(page),
            "services": parse_services(page),
            "news": parse_news(page),
            "photos": parse_photos(page),
            "reviews": parse_reviews(page),
            "features": parse_features(page)
        }

        browser.close()
        return data 