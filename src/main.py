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