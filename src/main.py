"""
main.py — Точка входа для SEO-анализатора Яндекс.Карт
"""
from src.parser import parse_yandex_card
from src.analyzer import analyze_card
from src.report import generate_html_report
from src.save_to_supabase import save_card_to_supabase, check_competitor_exists

# Автоматическая загрузка переменных окружения из .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print('Внимание: для автоматической загрузки .env установите пакет python-dotenv')

def main():
    print("Введите ссылку на карточку Яндекс.Карт:")
    url = input().strip()
    print("Парсинг страницы...")
    card_data = parse_yandex_card(url)
    print('DEBUG overview:', card_data.get('overview'))

    # --- Проверка на капчу ---
    if card_data.get('error') == 'captcha_detected':
        print('Данные не спарсились: страница закрыта капчой. Сохраню отчёт с этой информацией.')
        # Генерируем минимальный отчёт с сообщением о капче
        minimal_data = {
            'overview': {
                'title': 'Ошибка: капча',
                'description': 'Данные не спарсились, страница закрыта капчой. Попробуйте позже или вручную пройдите капчу.',
                'rubric': [],
                'rating': '',
                'address': '',
                'phone': '',
                'site': '',
                'hours': '',
                'reviews_count': '',
            },
            'products': [],
            'product_categories': [],
            'reviews': {'items': [], 'rating': '', 'reviews_count': ''},
            'competitors': [],
            'url': url
        }
        analysis = {'score': 0, 'recommendations': ['Данные не спарсились из-за капчи.']}
        report_path = generate_html_report(minimal_data, analysis, None)
        print(f"Готово! Отчёт сохранён: {report_path}")
        return

    # --- Логика выбора и парсинга конкурента ---
    competitor_data = None
    competitor_url = None
    competitors = card_data.get('competitors', [])
    competitor_status = ''
    if competitors:
        # Берём первого конкурента, которого нет в базе
        for comp in competitors:
            comp_url = comp.get('url')
            if comp_url and not check_competitor_exists(comp_url):
                competitor_url = comp_url
                break
        if competitor_url:
            print(f"Парсим конкурента: {competitor_url}")
            try:
                competitor_data = parse_yandex_card(competitor_url)
                competitor_data['competitors'] = []
                save_card_to_supabase(competitor_data)
            except Exception as e:
                print(f"Ошибка при парсинге конкурента: {e}")
                competitor_status = f"Ошибка при парсинге конкурента: {e}"
        else:
            print("Все конкуренты уже были спарсены ранее.")
            competitor_status = "Все конкуренты уже были спарсены ранее."
    else:
        print("Конкуренты не найдены на карточке.")
        competitor_status = "Конкуренты не найдены на карточке."

    # --- Сохраняем основную карточку, добавляем ссылку на конкурента ---
    competitors_urls = []
    if competitor_url:
        competitors_urls.append(competitor_url)
    card_data['competitors'] = competitors_urls
    save_card_to_supabase(card_data)

    print("Результат парсинга:")
    import pprint
    pprint.pprint(card_data)
    print("Анализ данных...")
    analysis = analyze_card(card_data)
    print("Генерация отчёта...")
    report_path = generate_html_report(card_data, analysis, competitor_data if competitor_data else {'status': competitor_status})
    print(f"Готово! Отчёт сохранён: {report_path}")

if __name__ == "__main__":
    main()