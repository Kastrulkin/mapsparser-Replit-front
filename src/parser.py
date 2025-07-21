import asyncio
import json
from playwright.async_api import async_playwright
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import re


@dataclass
class YandexCard:
    url: str
    overview: Dict[str, Any]
    categories_full: List[str]
    product_categories: List[str]
    features_bool: Dict[str, bool]
    features_valued: Dict[str, str]
    features_prices: Dict[str, str]
    features_full: Dict[str, Any]
    products: List[Dict]
    news: List[Dict]
    photos: List[str]
    reviews: List[Dict]
    competitors: List[Dict]


class YandexMapsParser:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None

    async def init_browser(self):
        """Инициализация браузера"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        self.page = await self.context.new_page()

    async def close_browser(self):
        """Закрытие браузера"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def parse_card(self, url: str) -> YandexCard:
        """Парсинг карточки организации"""
        await self.page.goto(url)
        await asyncio.sleep(3)

        # Парсим основную информацию
        overview = await self.parse_overview_data()
        categories_full = await self.parse_categories()
        product_categories = await self.parse_product_categories()
        features = await self.parse_features()
        products = await self.parse_products()
        news = await self.parse_news()
        photos = await self.parse_photos()
        reviews = await self.parse_reviews()
        competitors = await self.parse_competitors()

        return YandexCard(
            url=url,
            overview=overview,
            categories_full=categories_full,
            product_categories=product_categories,
            features_bool=features.get('bool', {}),
            features_valued=features.get('valued', {}),
            features_prices=features.get('prices', {}),
            features_full=features,
            products=products,
            news=news,
            photos=photos,
            reviews=reviews,
            competitors=competitors
        )

    async def parse_overview_data(self) -> Dict[str, Any]:
        """Парсинг основной информации об организации"""
        overview = {}

        # Название
        title_selector = '.orgpage-header-view__header .orgpage-header-view__title'
        try:
            overview['title'] = await self.page.locator(title_selector).text_content()
        except:
            overview['title'] = None

        # Рейтинг
        rating_selector = '.business-summary-rating-badge-view__rating-text'
        try:
            rating_text = await self.page.locator(rating_selector).text_content()
            overview['rating'] = rating_text.strip() if rating_text else None
        except:
            overview['rating'] = None

        # Количество оценок
        ratings_count_selector = '.business-summary-rating-badge-view__count'
        try:
            ratings_text = await self.page.locator(ratings_count_selector).text_content()
            # Извлекаем число из строки вида "511 оценок"
            if ratings_text:
                match = re.search(r'(\d+)', ratings_text.replace(' ', ''))
                overview['ratings_count'] = int(match.group(1)) if match else None
            else:
                overview['ratings_count'] = None
        except:
            overview['ratings_count'] = None

        # Количество отзывов
        try:
            # Находим все элементы с отзывами
            reviews_elements = await self.page.locator('.business-reviews-card-view__review').all()
            overview['reviews_count'] = len(reviews_elements)
        except:
            overview['reviews_count'] = None

        # Адрес
        address_selector = '.business-contacts-view__address'
        try:
            overview['address'] = await self.page.locator(address_selector).text_content()
        except:
            overview['address'] = None

        # Телефон
        phone_selector = '.business-contacts-view__phone'
        try:
            overview['phone'] = await self.page.locator(phone_selector).text_content()
        except:
            overview['phone'] = None

        # Сайт
        website_selector = '.business-contacts-view__website'
        try:
            overview['site'] = await self.page.locator(website_selector).get_attribute('href')
        except:
            overview['site'] = None

        # Часы работы
        try:
            # Пытаемся найти кнопку часов работы
            hours_button_selector = '.business-summary-schedule-view__text'
            hours_text = await self.page.locator(hours_button_selector).text_content()
            overview['hours'] = hours_text if hours_text else None

            # Пытаемся получить полную информацию о часах работы
            overview['hours_full'] = await self.parse_full_hours()
        except:
            overview['hours'] = None
            overview['hours_full'] = None

        # Ближайшее метро
        metro_selector = '.business-contacts-view__item .business-contacts-view__meta'
        try:
            metro_elements = await self.page.locator(metro_selector).all()
            for element in metro_elements:
                text = await element.text_content()
                if text and ('метро' in text.lower() or 'м.' in text.lower()):
                    overview['nearest_metro'] = text
                    break
            else:
                overview['nearest_metro'] = None
        except:
            overview['nearest_metro'] = None

        # Ближайшая остановка
        stop_selector = '.business-contacts-view__item .business-contacts-view__meta'
        try:
            stop_elements = await self.page.locator(stop_selector).all()
            for element in stop_elements:
                text = await element.text_content()
                if text and ('остановка' in text.lower() or 'ост.' in text.lower()):
                    overview['nearest_stop'] = text
                    break
            else:
                overview['nearest_stop'] = None
        except:
            overview['nearest_stop'] = None

        return overview

    async def parse_full_hours(self) -> Optional[Dict]:
        """Парсинг полной информации о часах работы"""
        try:
            # Пытаемся кликнуть по кнопке часов работы для раскрытия полной информации
            hours_button = '.business-summary-schedule-view__text'
            await self.page.locator(hours_button).click()
            await asyncio.sleep(1)

            # Парсим расширенную информацию о часах работы
            hours_info = {}
            schedule_items = await self.page.locator('.business-schedule-view__day').all()

            for item in schedule_items:
                try:
                    day = await item.locator('.business-schedule-view__day-name').text_content()
                    time = await item.locator('.business-schedule-view__day-time').text_content()
                    if day and time:
                        hours_info[day.strip()] = time.strip()
                except:
                    continue

            return hours_info if hours_info else None
        except:
            return None

    async def parse_categories(self) -> List[str]:
        """Парсинг категорий организации"""
        categories = []
        try:
            # Основная категория
            main_category_selector = '.business-card-title-view__category'
            main_category = await self.page.locator(main_category_selector).text_content()
            if main_category:
                categories.append(main_category.strip())

            # Дополнительные категории
            additional_categories_selector = '.business-card-title-view__categories .business-card-title-view__category'
            additional_elements = await self.page.locator(additional_categories_selector).all()
            for element in additional_elements:
                category = await element.text_content()
                if category and category.strip() not in categories:
                    categories.append(category.strip())
        except Exception as e:
            print(f"Ошибка при парсинге категорий: {e}")

        return categories

    async def parse_product_categories(self) -> List[str]:
        """Парсинг категорий товаров/услуг"""
        categories = []
        try:
            # Ищем блок с категориями товаров/услуг
            categories_selector = '.business-related-items-rubricator-categories .business-related-items-rubricator-categories__item'
            category_elements = await self.page.locator(categories_selector).all()

            for element in category_elements:
                category_text = await element.text_content()
                if category_text:
                    categories.append(category_text.strip())
        except Exception as e:
            print(f"Ошибка при парсинге категорий товаров: {e}")

        return categories

    async def parse_features(self) -> Dict[str, Any]:
        """Парсинг особенностей организации"""
        features = {
            'bool': {},
            'valued': {},
            'prices': {}
        }

        try:
            # Парсим особенности в виде да/нет
            bool_features_selector = '.business-features-view .business-features-view__item'
            bool_elements = await self.page.locator(bool_features_selector).all()

            for element in bool_elements:
                try:
                    feature_name = await element.locator('.business-features-view__name').text_content()
                    feature_value = await element.locator('.business-features-view__value').text_content()

                    if feature_name and feature_value:
                        if feature_value.lower() in ['да', 'нет', 'yes', 'no']:
                            features['bool'][feature_name.strip()] = feature_value.lower() in ['да', 'yes']
                        else:
                            features['valued'][feature_name.strip()] = feature_value.strip()
                except:
                    continue

            # Парсим ценовые особенности
            price_features_selector = '.business-prices-view .business-prices-view__item'
            price_elements = await self.page.locator(price_features_selector).all()

            for element in price_elements:
                try:
                    service_name = await element.locator('.business-prices-view__service').text_content()
                    price = await element.locator('.business-prices-view__price').text_content()

                    if service_name and price:
                        features['prices'][service_name.strip()] = price.strip()
                except:
                    continue

        except Exception as e:
            print(f"Ошибка при парсинге особенностей: {e}")

        return features

    async def parse_products(self) -> List[Dict]:
        """Парсинг товаров/услуг"""
        products = []
        try:
            products_selector = '.business-products-view .business-products-view__item'
            product_elements = await self.page.locator(products_selector).all()

            for element in product_elements:
                try:
                    name = await element.locator('.business-products-view__name').text_content()
                    price = await element.locator('.business-products-view__price').text_content()
                    description = await element.locator('.business-products-view__description').text_content()

                    product = {}
                    if name:
                        product['name'] = name.strip()
                    if price:
                        product['price'] = price.strip()
                    if description:
                        product['description'] = description.strip()

                    if product:
                        products.append(product)
                except:
                    continue
        except Exception as e:
            print(f"Ошибка при парсинге товаров: {e}")

        return products

    async def parse_news(self) -> List[Dict]:
        """Парсинг новостей/постов"""
        news = []
        try:
            news_selector = '.business-posts-view .business-posts-view__item'
            news_elements = await self.page.locator(news_selector).all()

            for element in news_elements:
                try:
                    title = await element.locator('.business-posts-view__title').text_content()
                    text = await element.locator('.business-posts-view__text').text_content()
                    date = await element.locator('.business-posts-view__date').text_content()

                    news_item = {}
                    if title:
                        news_item['title'] = title.strip()
                    if text:
                        news_item['text'] = text.strip()
                    if date:
                        news_item['date'] = date.strip()

                    if news_item:
                        news.append(news_item)
                except:
                    continue
        except Exception as e:
            print(f"Ошибка при парсинге новостей: {e}")

        return news

    async def parse_photos(self) -> List[str]:
        """Парсинг фотографий"""
        photos = []
        try:
            photos_selector = '.business-photos-view img'
            photo_elements = await self.page.locator(photos_selector).all()

            for element in photo_elements:
                try:
                    src = await element.get_attribute('src')
                    if src and src not in photos:
                        photos.append(src)
                except:
                    continue
        except Exception as e:
            print(f"Ошибка при парсинге фотографий: {e}")

        return photos

    async def parse_reviews(self) -> List[Dict]:
        """Парсинг отзывов"""
        reviews = []
        try:
            # Пытаемся перейти на вкладку отзывов
            reviews_tab_selector = '[data-tab-name="reviews"]'
            try:
                await self.page.locator(reviews_tab_selector).click()
                await asyncio.sleep(2)
            except:
                pass

            # Парсим отзывы
            reviews_selector = '.business-reviews-card-view__review'
            review_elements = await self.page.locator(reviews_selector).all()

            for i, element in enumerate(review_elements):
                try:
                    # Имя автора
                    author_selector = '.business-review-view__author'
                    author = await element.locator(author_selector).text_content()

                    # Дата отзыва
                    date_selector = '.business-review-view__date'
                    date = await element.locator(date_selector).text_content()

                    # Рейтинг
                    rating_selector = '.business-rating-badge-view__rating'
                    rating = await element.locator(rating_selector).text_content()

                    # Текст отзыва
                    text_selector = '.business-review-view__body-text'
                    text = await element.locator(text_selector).text_content()

                    # Ответ организации
                    response_selector = '.business-review-view__response .business-review-view__response-text'
                    try:
                        response = await element.locator(response_selector).text_content()
                    except:
                        response = None

                    review = {
                        'id': i + 1,
                        'author': author.strip() if author else None,
                        'date': date.strip() if date else None,
                        'rating': rating.strip() if rating else None,
                        'text': text.strip() if text else None,
                        'response': response.strip() if response else None
                    }

                    reviews.append(review)
                except Exception as e:
                    print(f"Ошибка при парсинге отзыва {i}: {e}")
                    continue
        except Exception as e:
            print(f"Ошибка при парсинге отзывов: {e}")

        return reviews

    async def parse_competitors(self) -> List[Dict]:
        """Парсинг конкурентов"""
        competitors = []
        try:
            # Ищем блок с похожими организациями
            competitors_selector = '.card-similar-carousel-wide .card-similar-card-view'
            competitor_elements = await self.page.locator(competitors_selector).all()

            for element in competitor_elements:
                try:
                    name = await element.locator('.card-similar-card-view__title').text_content()
                    rating = await element.locator('.business-rating-badge-view__rating').text_content()
                    address = await element.locator('.card-similar-card-view__address').text_content()

                    competitor = {}
                    if name:
                        competitor['name'] = name.strip()
                    if rating:
                        competitor['rating'] = rating.strip()
                    if address:
                        competitor['address'] = address.strip()

                    if competitor:
                        competitors.append(competitor)
                except:
                    continue
        except Exception as e:
            print(f"Ошибка при парсинге конкурентов: {e}")

        return competitors


async def parse_yandex_card(url: str) -> Dict:
    """Главная функция для парсинга карточки"""
    parser = YandexMapsParser()
    try:
        await parser.init_browser()
        card = await parser.parse_card(url)

        # Преобразуем в словарь для сохранения
        return {
            'url': card.url,
            'overview': card.overview,
            'categories_full': card.categories_full,
            'product_categories': card.product_categories,
            'features_bool': card.features_bool,
            'features_valued': card.features_valued,
            'features_prices': card.features_prices,
            'features_full': card.features_full,
            'products': card.products,
            'news': card.news,
            'photos': card.photos,
            'reviews': card.reviews,
            'competitors': card.competitors
        }
    finally:
        await parser.close_browser()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        result = asyncio.run(parse_yandex_card(url))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Использование: python parser.py <URL>")