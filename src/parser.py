"""
parser.py — Модуль для парсинга публичной страницы Яндекс.Карт с помощью Playwright
"""
from playwright.sync_api import sync_playwright
import time

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
        data = {}
        # Название
        try:
            data['title'] = page.query_selector("h1").inner_text()
        except Exception:
            data['title'] = ''
        # Адрес (ищем сразу, он обычно виден)
        try:
            addr = page.query_selector("[class*='business-contacts-view__address'] span")
            data['address'] = addr.inner_text() if addr else ''
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
        # Телефон (ищем после клика)
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
            data['rating'] = rating.inner_text() if rating else ''
        except Exception:
            data['rating'] = ''
        # Количество отзывов
        try:
            reviews = page.query_selector("[class*='business-rating-badge-view__reviews-count']")
            data['reviews_count'] = reviews.inner_text() if reviews else ''
        except Exception:
            data['reviews_count'] = ''
        # Описание
        try:
            desc = page.query_selector("[class*='card-about-view__description-text']")
            data['description'] = desc.inner_text() if desc else ''
        except Exception:
            data['description'] = ''
        # Фото
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
        # Клик по вкладке 'Лента' или 'Новости' (если есть)
        try:
            news_tab = page.query_selector("button:has-text('Лента'), button:has-text('Новости'), div[role='tab']:has-text('Лента'), div[role='tab']:has-text('Новости')")
            if news_tab:
                news_tab.click()
                page.wait_for_timeout(1500)
        except Exception:
            pass
        # Лента/новости (ищем после клика)
        try:
            posts = page.query_selector_all("[class*='feed-post-view__title']")
            data['news_count'] = len(posts)
        except Exception:
            data['news_count'] = 0
        data['url'] = url
        browser.close()
        return data 