
"""
parser.py — Модуль для парсинга публичной страницы Яндекс.Карт с помощью Selenium
"""
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager
import time
import re
import random

def parse_yandex_card(url: str) -> dict:
    """
    Парсит публичную страницу Яндекс.Карт и возвращает данные в виде словаря.
    """
    print(f"Начинаем парсинг: {url}")
    
    if not url or not url.startswith(('http://', 'https://')):
        raise ValueError(f"Некорректная ссылка: {url}")
    
    print("Используем парсинг через Selenium с Firefox...")
    
    # Настройка Firefox в headless режиме для Replit
    firefox_options = Options()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--no-sandbox")
    firefox_options.add_argument("--disable-dev-shm-usage")
    firefox_options.add_argument("--disable-gpu")
    firefox_options.add_argument("--window-size=1920,1080")
    firefox_options.set_preference("general.useragent.override", "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/91.0")
    firefox_options.set_preference("intl.accept_languages", "ru-RU,ru,en")
    
    try:
        # Сначала пробуем использовать предустановленный geckodriver
        try:
            driver = webdriver.Firefox(options=firefox_options)
            print("Используем системный Firefox/geckodriver")
        except Exception:
            # Если не получилось, используем WebDriverManager
            service = Service(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=firefox_options)
            print("Используем geckodriver через WebDriverManager")
    except Exception as e:
        print(f"Ошибка при инициализации Firefox: {e}")
        raise Exception(f"Не удалось запустить Firefox: {e}")
    
    try:
        driver.get(url)
        time.sleep(4)  # Дать странице прогрузиться
        
        # Переход на вкладку 'Обзор'
        try:
            overview_tab = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'tabs-select-view__title') and contains(@class, '_name_overview')] | //div[@role='tab' and contains(text(), 'Обзор')] | //button[contains(text(), 'Обзор')]"))
            )
            overview_tab.click()
            print("Клик по вкладке 'Обзор'")
            time.sleep(1.5)
        except TimeoutException:
            print("Вкладка 'Обзор' не найдена, продолжаем без клика")
        
        # Скроллим для подгрузки контента
        driver.execute_script("window.scrollTo(0, 2000);")
        time.sleep(2)
        
        data = parse_overview_data(driver)
        data['url'] = url
        
        # Дополнительные данные
        data['photos_count'] = get_photos_count(driver)
        data['news'] = parse_news(driver)
        data['reviews'] = parse_reviews(driver)
        data['features_full'] = parse_features(driver)
        data['competitors'] = parse_competitors(driver)
        
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
        
        driver.quit()
        print(f"Парсинг завершен. Найдено: название='{data['title']}', адрес='{data['address']}'")
        return data
        
    except Exception as e:
        driver.quit()
        raise Exception(f"Ошибка при парсинге: {e}")

def parse_overview_data(driver):
    """Парсит основные данные с вкладки Обзор"""
    data = {}
    
    # Название
    try:
        title_el = driver.find_element(By.TAG_NAME, "h1")
        data['title'] = title_el.text.strip() if title_el else ''
    except NoSuchElementException:
        data['title'] = ''
    
    # Адрес (на русском языке)
    try:
        addr_el = driver.find_element(By.CSS_SELECTOR, "[class*='business-contacts-view__address'] span")
        data['address'] = addr_el.text.strip() if addr_el else ''
    except NoSuchElementException:
        data['address'] = ''
    
    # Клик по кнопке "Показать телефон"
    try:
        show_phone_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Показать телефон')]")
        show_phone_btn.click()
        time.sleep(1)
    except NoSuchElementException:
        pass
    
    # Телефон
    try:
        phone_el = driver.find_element(By.CSS_SELECTOR, "a[href^='tel:']")
        data['phone'] = phone_el.text.strip() if phone_el else ''
    except NoSuchElementException:
        data['phone'] = ''
    
    # Сайт
    try:
        site_el = driver.find_element(By.CSS_SELECTOR, "a.business-urls-view__text")
        data['site'] = site_el.get_attribute('href') if site_el else ''
    except NoSuchElementException:
        data['site'] = ''
    
    # Описание
    try:
        desc_el = driver.find_element(By.CSS_SELECTOR, "[class*='card-about-view__description-text']")
        data['description'] = desc_el.text.strip() if desc_el else ''
    except NoSuchElementException:
        data['description'] = ''
    
    # Категории
    try:
        cats = driver.find_elements(By.CSS_SELECTOR, "[class*='business-card-title-view__categories'] span")
        data['categories'] = [c.text.strip() for c in cats if c.text.strip()]
    except NoSuchElementException:
        data['categories'] = []
    
    # Рейтинг
    try:
        rating_el = driver.find_element(By.CSS_SELECTOR, "span.business-rating-badge-view__rating-text")
        data['rating'] = rating_el.text.replace(',', '.').strip() if rating_el else ''
    except NoSuchElementException:
        data['rating'] = ''
    
    # Количество оценок
    try:
        ratings_count_el = driver.find_element(By.CSS_SELECTOR, "div.business-header-rating-view__text._clickable")
        if ratings_count_el:
            text = ratings_count_el.text
            match = re.search(r"(\d+)", text.replace('\xa0', ' '))
            data['ratings_count'] = match.group(1) if match else ''
        else:
            data['ratings_count'] = ''
    except NoSuchElementException:
        data['ratings_count'] = ''
    
    # Количество отзывов
    try:
        reviews_count_el = driver.find_element(By.XPATH, "//span[contains(text(), 'отзыв')]")
        if reviews_count_el:
            text = reviews_count_el.text
            match = re.search(r"(\d+)", text)
            data['reviews_count'] = match.group(1) if match else ''
        else:
            data['reviews_count'] = ''
    except NoSuchElementException:
        data['reviews_count'] = ''
    
    # Часы работы (краткие)
    try:
        hours_el = driver.find_element(By.CSS_SELECTOR, "[class*='business-hours-text']")
        data['hours'] = hours_el.text.strip() if hours_el else ''
    except NoSuchElementException:
        data['hours'] = ''
    
    # Полное расписание
    try:
        full_schedule = []
        schedule_items = driver.find_elements(By.CSS_SELECTOR, "[class*='business-hours-view__day']")
        for item in schedule_items:
            try:
                day_el = item.find_element(By.CSS_SELECTOR, "[class*='business-hours-view__day-name']")
                time_el = item.find_element(By.CSS_SELECTOR, "[class*='business-hours-view__hours']")
                day = day_el.text.strip() if day_el else ''
                work_time = time_el.text.strip() if time_el else ''
                if day and work_time:
                    full_schedule.append(f"{day}: {work_time}")
            except NoSuchElementException:
                continue
        data['hours_full'] = full_schedule
    except NoSuchElementException:
        data['hours_full'] = []
    
    # Ближайшее метро
    try:
        metro_el = driver.find_element(By.CSS_SELECTOR, "[class*='metro-station']")
        if metro_el:
            metro_name = metro_el.text.strip()
            try:
                distance_el = metro_el.find_element(By.CSS_SELECTOR, "[class*='distance']")
                distance = distance_el.text.strip() if distance_el else ''
            except NoSuchElementException:
                distance = ''
            data['nearest_metro'] = {'name': metro_name, 'distance': distance}
        else:
            data['nearest_metro'] = {'name': '', 'distance': ''}
    except NoSuchElementException:
        data['nearest_metro'] = {'name': '', 'distance': ''}
    
    # Ближайшая остановка
    try:
        stop_el = driver.find_element(By.CSS_SELECTOR, "[class*='transport-stop']")
        if stop_el:
            stop_name = stop_el.text.strip()
            try:
                distance_el = stop_el.find_element(By.CSS_SELECTOR, "[class*='distance']")
                distance = distance_el.text.strip() if distance_el else ''
            except NoSuchElementException:
                distance = ''
            data['nearest_stop'] = {'name': stop_name, 'distance': distance}
        else:
            data['nearest_stop'] = {'name': '', 'distance': ''}
    except NoSuchElementException:
        data['nearest_stop'] = {'name': '', 'distance': ''}
    
    # Социальные сети
    try:
        social_links = []
        social_els = driver.find_elements(By.CSS_SELECTOR, "a[href*='vk.com'], a[href*='instagram.com'], a[href*='facebook.com'], a[href*='twitter.com'], a[href*='ok.ru']")
        for el in social_els:
            href = el.get_attribute('href')
            if href:
                social_links.append(href)
        data['social_links'] = social_links
    except NoSuchElementException:
        data['social_links'] = []
    
    # Товары и услуги
    data['products'] = []
    data['product_categories'] = []
    
    return data

def get_photos_count(driver):
    """Получает количество фотографий"""
    try:
        photos_tab = driver.find_element(By.CSS_SELECTOR, "div.tabs-select-view__title._name_gallery")
        if photos_tab:
            try:
                counter = photos_tab.find_element(By.CSS_SELECTOR, "div.tabs-select-view__counter")
                return int(counter.text.strip())
            except NoSuchElementException:
                pass
    except NoSuchElementException:
        pass
    return 0

def parse_news(driver):
    """Парсит новости"""
    try:
        news_tab = driver.find_element(By.XPATH, "//div[@role='tab' and contains(text(), 'Лента')] | //button[contains(text(), 'Лента')]")
        news_tab.click()
        time.sleep(1.5)
        
        news = []
        news_blocks = driver.find_elements(By.CSS_SELECTOR, "[class*='feed-post-view']")
        for block in news_blocks:
            try:
                title_elem = block.find_element(By.CSS_SELECTOR, "[class*='feed-post-view__title']")
                title = title_elem.text if title_elem else ""
                
                text_elem = block.find_element(By.CSS_SELECTOR, "[class*='feed-post-view__text']")
                text = text_elem.text if text_elem else ""
                
                date_elem = block.find_element(By.CSS_SELECTOR, "[class*='feed-post-view__date']")
                date = date_elem.text if date_elem else ""
                
                photo_elem = block.find_element(By.TAG_NAME, "img")
                photo = photo_elem.get_attribute('src') if photo_elem else ""
                
                news.append({
                    "title": title,
                    "text": text,
                    "date": date,
                    "photo": photo
                })
            except NoSuchElementException:
                continue
        return news
    except NoSuchElementException:
        return []

def parse_reviews(driver):
    """Парсит отзывы"""
    try:
        reviews_tab = driver.find_element(By.XPATH, "//div[@role='tab' and contains(text(), 'Отзывы')] | //button[contains(text(), 'Отзывы')]")
        reviews_tab.click()
        time.sleep(2)
        
        reviews_data = {"items": [], "rating": "", "reviews_count": ""}
        
        # Рейтинг и количество отзывов
        try:
            rating_el = driver.find_element(By.CSS_SELECTOR, "span.business-rating-badge-view__rating-text")
            reviews_data['rating'] = rating_el.text.replace(',', '.').strip() if rating_el else ''
            
            count_el = driver.find_element(By.XPATH, "//span[contains(text(), 'отзыв')]")
            if count_el:
                text = count_el.text
                match = re.search(r"(\d+)", text)
                reviews_data['reviews_count'] = match.group(1) if match else ''
        except NoSuchElementException:
            pass
        
        # Отзывы
        review_blocks = driver.find_elements(By.CSS_SELECTOR, "[class*='business-review-view']")
        for i, block in enumerate(review_blocks[:50]):  # Ограничиваем 50 отзывами
            try:
                author_el = block.find_element(By.CSS_SELECTOR, "[class*='business-review-view__author']")
                author = author_el.text.strip() if author_el else f"Автор {i+1}"
                
                date_el = block.find_element(By.CSS_SELECTOR, "[class*='business-review-view__date']")
                date = date_el.text.strip() if date_el else ""
                
                rating_els = block.find_elements(By.CSS_SELECTOR, "[class*='star-fill']")
                rating = len(rating_els)
                
                text_el = block.find_element(By.CSS_SELECTOR, "[class*='business-review-view__body']")
                text = text_el.text.strip() if text_el else ""
                
                reply_el = block.find_element(By.CSS_SELECTOR, "[class*='business-review-view__reply']")
                reply = reply_el.text.strip() if reply_el else ""
                
                reviews_data['items'].append({
                    "author": author,
                    "date": date,
                    "rating": rating,
                    "text": text,
                    "reply": reply
                })
            except NoSuchElementException:
                continue
        
        return reviews_data
    except NoSuchElementException:
        return {"items": [], "rating": "", "reviews_count": ""}

def parse_features(driver):
    """Парсит особенности"""
    try:
        features_tab = driver.find_element(By.XPATH, "//div[@role='tab' and contains(text(), 'Особенности')] | //button[contains(text(), 'Особенности')]")
        features_tab.click()
        time.sleep(1.5)
        
        features_data = {"bool": [], "valued": [], "prices": [], "categories": []}
        
        feature_blocks = driver.find_elements(By.CSS_SELECTOR, "[class*='features-view__item']")
        for block in feature_blocks:
            try:
                name_el = block.find_element(By.CSS_SELECTOR, "[class*='features-view__name']")
                name = name_el.text.strip() if name_el else ""
                
                value_el = block.find_element(By.CSS_SELECTOR, "[class*='features-view__value']")
                value = value_el.text.strip() if value_el else ""
                
                if name:
                    if value:
                        features_data['valued'].append(f"{name}: {value}")
                    else:
                        features_data['bool'].append(name)
            except NoSuchElementException:
                continue
        
        return features_data
    except NoSuchElementException:
        return {"bool": [], "valued": [], "prices": [], "categories": []}

def parse_competitors(driver):
    """Парсит конкурентов из раздела 'Похожие места рядом'"""
    try:
        # Ищем блок с похожими местами
        similar_section = driver.find_element(By.CSS_SELECTOR, "[class*='card-similar'], [class*='similar-places']")
        if not similar_section:
            return []
        
        competitors = []
        competitor_blocks = similar_section.find_elements(By.CSS_SELECTOR, "a[href*='/org/']")
        
        for block in competitor_blocks[:5]:  # Ограничиваем 5 конкурентами
            try:
                href = block.get_attribute('href')
                if href and not href.startswith('http'):
                    href = f"https://yandex.ru{href}"
                
                title_el = block.find_element(By.CSS_SELECTOR, "[class*='title'], h3, h4")
                title = title_el.text.strip() if title_el else ""
                
                if title and href:
                    competitors.append({
                        "title": title,
                        "url": href
                    })
            except NoSuchElementException:
                continue
        
        return competitors
    except NoSuchElementException:
        return []
