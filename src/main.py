"""
main.py — Точка входа для SEO-анализатора Яндекс.Карт
"""
import sys
from parser import parse_yandex_card
from analyzer import analyze_card
from report import generate_html_report
from bs4 import BeautifulSoup
import re
from save_to_supabase import save_card_to_supabase

def main():
    try:
        print("Введите ссылку на карточку Яндекс.Карт:")
        url = input().strip()

        if not url:
            print("Ошибка: Пустая ссылка")
            return

        print("Парсинг основной страницы...")
        card_data = parse_yandex_card(url)
        
        # Проверяем результат парсинга
        if not card_data:
            print("❌ Ошибка: Парсинг вернул пустой результат")
            return
            
        # Проверяем на ошибку captcha
        if card_data.get('error') == 'captcha_detected':
            print("❌ Парсинг остановлен из-за captcha")
            print("Попробуйте использовать другую ссылку или повторить позже")
            return
            
        print('DEBUG overview:', card_data.get('overview'))

        # Сохраняем основную карточку
        from save_to_supabase import save_card_to_supabase, get_next_available_competitor, save_competitor_to_supabase
        main_card_id = save_card_to_supabase(card_data)

        # Парсим конкурента, если найдены конкуренты
        competitor_data = None
        competitors = card_data.get('competitors', [])

        if competitors:
            print(f"Найдено {len(competitors)} конкурентов: {[c.get('title') for c in competitors]}")

            # Парсим первого конкурента
            if len(competitors) > 0:
                competitor_url = competitors[0].get('url')
                competitor_title = competitors[0].get('title')

                print(f"Парсинг конкурента: {competitor_title} - {competitor_url}")
                try:
                    competitor_data = parse_yandex_card(competitor_url)
                    
                    # Проверяем на captcha у конкурента
                    if competitor_data.get('error') == 'captcha_detected':
                        print(f"❌ Captcha при парсинге конкурента {competitor_title}, пропускаем")
                        competitor_data = None
                    else:
                        competitor_data['is_competitor'] = True
                        competitor_data['competitor_info'] = competitors[0]

                        # Сохраняем конкурента с привязкой к основной карточке
                        save_competitor_to_supabase(competitor_data, main_card_id, url)

                        print(f"Конкурент '{competitor_title}' успешно спарсен")

                except Exception as e:
                    print(f"Ошибка при парсинге конкурента: {e}")
                    competitor_data = None
        else:
            print("Конкуренты не найдены в разделе 'Похожие места рядом'")

        print("Результат парсинга основной карточки:")
        import pprint
        pprint.pprint({k: v for k, v in card_data.items() if k != 'reviews'})  # Не выводим отзывы для краткости

        if competitor_data:
            print("Результат парсинга конкурента:")
            pprint.pprint({k: v for k, v in competitor_data.items() if k != 'reviews'})

        print("Анализ данных...")
        analysis = analyze_card(card_data)

        # Обновляем количество отзывов из секции отзывов  
        if card_data and isinstance(card_data, dict) and card_data.get('reviews') and isinstance(card_data.get('reviews'), dict) and card_data.get('reviews', {}).get('reviews_count'):
            card_data['reviews_count'] = card_data['reviews']['reviews_count']

        # Создаем overview для отчета
        card_data['overview'] = {
            'title': card_data.get('title', ''),
            'address': card_data.get('address', ''),
            'phone': card_data.get('phone', ''),
            'site': card_data.get('site', ''),
            'description': card_data.get('description', ''),
            'rubric': card_data.get('rubric', []),
            'categories': card_data.get('categories', []),
            'hours': card_data.get('hours', ''),
            'hours_full': card_data.get('hours_full', []),
            'rating': card_data.get('rating', ''),
            'ratings_count': card_data.get('ratings_count', ''),
            'reviews_count': card_data.get('reviews_count', '') or (card_data.get('reviews') or {}).get('reviews_count', ''),
            'social_links': card_data.get('social_links', [])
        }

        print("Генерация отчёта...")
        # Передаём данные конкурента в отчёт
        report_path = generate_html_report(card_data, analysis, competitor_data)
        print(f"Готово! Отчёт сохранён: {report_path}")

    except KeyboardInterrupt:
        print("\nОперация прервана пользователем")
    except Exception as e:
        print(f"Произошла ошибка: {type(e).__name__}: {str(e)}")
        import traceback
        print("Детальная информация об ошибке:")
        traceback.print_exc()
        print("\nЕсли ошибка повторяется, попробуйте:")
        print("1. Проверить правильность ссылки на Яндекс.Карты")
        print("2. Убедиться, что страница загружается в браузере")
        print("3. Попробовать другую карточку")

if __name__ == "__main__":
    main()