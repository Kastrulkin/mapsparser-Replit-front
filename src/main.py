"""
main.py — Точка входа для SEO-анализатора Яндекс.Карт
"""
import sys
from parser import parse_yandex_card
from analyzer import analyze_card
from report import generate_html_report

def main():
    print("Введите ссылку на карточку Яндекс.Карт:")
    url = input().strip()
    print("Парсинг страницы...")
    card_data = parse_yandex_card(url)
    print("Результат парсинга:")
    import pprint
    pprint.pprint(card_data)
    print("Анализ данных...")
    analysis = analyze_card(card_data)
    print("Генерация отчёта...")
    report_path = generate_html_report(card_data, analysis)
    print(f"Готово! Отчёт сохранён: {report_path}")

if __name__ == "__main__":
    main() 