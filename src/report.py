"""
report.py — Модуль для генерации HTML-отчёта по результатам анализа
"""
from jinja2 import Environment, FileSystemLoader
import os

def generate_html_report(card_data: dict, analysis: dict) -> str:
    """
    Генерирует HTML-отчёт и возвращает путь к файлу.
    """
    env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')))
    template = env.get_template('report_template.html')
    html = template.render(card=card_data, analysis=analysis)
    output_path = os.path.join('data', f"report_{card_data.get('overview', {}).get('title', 'card')}.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path 