"""
report.py — Модуль для генерации HTML-отчёта по результатам анализа
"""
from jinja2 import Environment, FileSystemLoader
import os

def generate_html_report(card_data: dict, analysis: dict = None, competitor_data: dict = None) -> str:
    """
    Генерирует HTML-отчёт и возвращает путь к файлу.
    """
    # Если анализ не передан, используем данные из card_data
    if analysis is None:
        analysis = {
            'score': card_data.get('seo_score', 50),
            'recommendations': card_data.get('recommendations', []),
            'ai_analysis': card_data.get('ai_analysis', {})
        }
    
    # Нормализуем структуру products перед рендерингом
    if 'products' in card_data and isinstance(card_data['products'], list):
        normalized_products = []
        for cat in card_data['products']:
            if isinstance(cat, dict):
                items = cat.get('items', [])
                # Убеждаемся, что items - это список, а не метод
                if not isinstance(items, list):
                    items = []
                normalized_products.append({
                    'category': cat.get('category', ''),
                    'items': items
                })
        card_data = dict(card_data)  # Создаём копию, чтобы не изменять оригинал
        card_data['products'] = normalized_products
    elif 'products' not in card_data:
        card_data = dict(card_data)
        card_data['products'] = []
    
    env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')))
    template = env.get_template('report_template.html')
    html = template.render(card=card_data, analysis=analysis, competitor=competitor_data)
    
    # Получаем название из title для имени файла
    title = card_data.get('title', 'card')
    
    # Создаём директорию data в корне проекта, если её нет
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    output_path = os.path.join(data_dir, f"report_{title}.html")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path