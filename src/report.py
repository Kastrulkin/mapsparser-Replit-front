"""
report.py — Модуль для генерации HTML-отчёта по результатам анализа
"""
from jinja2 import Environment, FileSystemLoader
import os

def generate_html_report(card_data: dict, analysis: dict, competitor_data: dict = None) -> str:
    """
    Генерирует HTML-отчёт и возвращает путь к файлу.
    """
    env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')))
    template = env.get_template('report_template.html')
    html = template.render(card=card_data, analysis=analysis, competitor=competitor_data)
    
    # Получаем название из overview или title для имени файла
    title = card_data.get('overview', {}).get('title') or card_data.get('title', 'card')
    
    # Создаём директорию data в корне проекта, если её нет
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    output_path = os.path.join(data_dir, f"report_{title}.html")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path