"""
parser.py — Модуль для парсинга публичной страницы Яндекс.Карт с помощью Playwright
"""
from playwright.sync_api import sync_playwright
import time
import re

def parse_yandex_card(url: str) -> dict:
    """
    Парсит публичную страницу Яндекс.Карт и возвращает данные в виде словаря.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=True для скрытого режима
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_timeout(4000)  # Дать странице прогрузиться
        # Скроллим вниз для подгрузки фото и отзывов
        page.mouse.wheel(0, 2000)
        time.sleep(2)
        # Дополнительная пауза для полной загрузки страницы
        time.sleep(2)
        data = {}
        # --- СБОР ДАННЫХ ТОЛЬКО С "ОБЗОРА" ---
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
            rating = page.query_selector("[class*='business-rating-badge-view__rating']")
            if rating:
                rating_text = rating.inner_text()
                match = re.search(r'([\d,.]+)', rating_text)
                data['rating'] = match.group(1).replace(',', '.') if match else ''
            else:
                data['rating'] = ''
        except Exception:
            data['rating'] = ''
        # Количество оценок
        try:
            reviews_count_elem = page.query_selector("div.business-header-rating-view__text._clickable")
            if reviews_count_elem:
                text = reviews_count_elem.inner_text()
                match = re.search(r'(\d+)', text.replace('\xa0', ' '))
                data['reviews_count'] = match.group(1) if match else ''
            else:
                data['reviews_count'] = ''
        except Exception:
            data['reviews_count'] = ''
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
        # --- ТОЛЬКО ПОСЛЕ ЭТОГО переходим на вкладку "Новости" ---
        try:
            news_tab = page.query_selector("button:has-text('Лента'), button:has-text('Новости'), div[role='tab']:has-text('Лента'), div[role='tab']:has-text('Новости')")
            if news_tab:
                news_tab.click()
                page.wait_for_timeout(1500)
                # Лента/новости (ищем после клика)
                posts = page.query_selector_all("[class*='feed-post-view__title']")
                data['news_count'] = len(posts)
            else:
                data['news_count'] = 0
        except Exception:
            data['news_count'] = 0
        data['url'] = url
        browser.close()
        # Формируем overview для отчёта
        overview_keys = [
            'title', 'address', 'phone', 'site', 'description',
            'categories', 'hours', 'rating', 'reviews_count'
        ]
        data['overview'] = {k: data.get(k, '') for k in overview_keys}
        return data 