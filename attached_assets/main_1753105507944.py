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
    print("Введите ссылку на карточку Яндекс.Карт:")
    url = input().strip()
    print("Парсинг страницы...")
    card_data = parse_yandex_card(url)
    print('DEBUG overview:', card_data.get('overview'))
    save_card_to_supabase(card_data)
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