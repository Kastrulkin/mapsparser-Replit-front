#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

try:
    # Получаем данные отчёта "У Жени"
    result = supabase.table('Cards').select('*').eq('id', 'ac33c28e-f0b8-4d10-89da-b52bed600d14').execute()
    
    if result.data:
        card = result.data[0]
        
        # Создаём HTML отчёт
        html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Отчёт: {card.get('title', 'У Жени')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f9f9f9; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .score {{ font-size: 24px; font-weight: bold; color: #27ae60; }}
        .info {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        .recommendation {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0; }}
        .strength {{ color: #27ae60; }}
        .weakness {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>SEO Отчёт: {card.get('title', 'У Жени')}</h1>
        
        <div class="info">
            <strong>Адрес:</strong> {card.get('address', 'Не указан')}<br>
            <strong>Рейтинг:</strong> {card.get('rating', 'Не указан')}<br>
            <strong>Отзывов:</strong> {card.get('reviews_count', '0')}<br>
            <strong>SEO-оценка:</strong> <span class="score">{card.get('seo_score', '0')}/100</span>
        </div>
        
        <h2>AI-анализ</h2>
        <div class="info">
            <strong>Сгенерированный текст:</strong><br>
            {card.get('ai_analysis', {}).get('generated_text', 'Анализ недоступен')}
        </div>
        
        <h2>Сильные стороны</h2>
        <ul>
            {''.join([f'<li class="strength">{strength}</li>' for strength in card.get('ai_analysis', {}).get('strengths', [])])}
        </ul>
        
        <h2>Слабые стороны</h2>
        <ul>
            {''.join([f'<li class="weakness">{weakness}</li>' for weakness in card.get('ai_analysis', {}).get('weaknesses', [])])}
        </ul>
        
        <h2>Рекомендации</h2>
        {''.join([f'<div class="recommendation">{rec}</div>' for rec in card.get('recommendations', [])])}
        
        <div style="margin-top: 40px; text-align: center; color: #7f8c8d; font-size: 12px;">
            Отчёт сгенерирован автоматически
        </div>
    </div>
</body>
</html>
        """
        
        # Создаём файл отчёта
        report_path = "/root/mapsparser-Replit-front/data/report_У Жени.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Файл отчёта создан: {report_path}")
        
        # Обновляем путь в базе данных
        update_result = supabase.table('Cards').update({
            'report_path': report_path
        }).eq('id', 'ac33c28e-f0b8-4d10-89da-b52bed600d14').execute()
        
        print("Путь обновлён в базе данных")
        
    else:
        print("Отчёт не найден")
        
except Exception as e:
    print(f"Ошибка: {e}") 