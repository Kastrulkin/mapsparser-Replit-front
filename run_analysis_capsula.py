#!/usr/bin/env python3
"""
Запуск анализатора на данных Capsula Hair
"""
import sys
import os
import traceback
import sqlite3
import uuid
from datetime import datetime

# Добавляем путь к src в sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def find_capsula_data():
    """Находим данные Capsula Hair в базе данных"""
    conn = sqlite3.connect("reports.db")
    cursor = conn.cursor()
    
    print("=== Поиск данных Capsula Hair ===")
    
    # Ищем карточки с Capsula в названии или URL
    cursor.execute("""
        SELECT id, title, url, seo_score, ai_analysis, recommendations, report_path, created_at
        FROM Cards 
        WHERE title LIKE '%capsula%' OR title LIKE '%Capsula%' OR url LIKE '%capsula%'
        ORDER BY created_at DESC
    """)
    
    cards = cursor.fetchall()
    
    if not cards:
        print("❌ Данные Capsula Hair не найдены в базе данных")
        conn.close()
        return None
    
    print(f"✅ Найдено {len(cards)} карточек Capsula Hair:")
    
    for i, card in enumerate(cards, 1):
        print(f"\n--- Карточка {i} ---")
        print(f"ID: {card[0]}")
        print(f"Название: {card[1]}")
        print(f"URL: {card[2]}")
        print(f"SEO-оценка: {card[3]}")
        print(f"ИИ-анализ: {'Есть' if card[4] else 'Нет'}")
        print(f"Рекомендации: {'Есть' if card[5] else 'Нет'}")
        print(f"Отчёт: {card[6] if card[6] else 'Не создан'}")
        print(f"Создан: {card[7]}")
    
    conn.close()
    return cards[0] if cards else None

def run_analysis_on_capsula():
    """Запускаем анализ на данных Capsula Hair"""
    print("\n=== Запуск анализатора на Capsula Hair ===")
    
    try:
        from gigachat_analyzer import analyze_business_data
        
        # Данные Capsula Hair из успешного парсинга
        capsula_data = {
            'title': 'Capsulahair',
            'address': '7-я линия Васильевского острова, 34, Санкт-Петербург',
            'phone': '+7 (812) 407-25-34',
            'rating': '5.0',
            'reviews_count': 1244,
            'categories': ['Салон красоты', 'Барбершоп', 'Парикмахерская'],
            'hours': 'Пн-Вс: 10:00–22:00',
            'description': 'Парикмахерская с высоким рейтингом и большим количеством отзывов',
            'photos': [],
            'reviews': [],
            'news': [],
            'products': [],
            'overview': {},
            'features_full': {'bool': [], 'valued': [], 'prices': [], 'categories': []}
        }
        
        print("Запускаем ИИ-анализ на данных Capsula Hair...")
        print(f"Название: {capsula_data['title']}")
        print(f"Адрес: {capsula_data['address']}")
        print(f"Телефон: {capsula_data['phone']}")
        print(f"Рейтинг: {capsula_data['rating']}")
        print(f"Отзывы: {capsula_data['reviews_count']}")
        
        result = analyze_business_data(capsula_data)
        
        print(f"\n✅ ИИ-анализ завершён")
        print(f"Результат содержит ключи: {list(result.keys())}")
        
        if 'analysis' in result:
            print(f"\n📊 Анализ:")
            analysis = result['analysis']
            if isinstance(analysis, dict):
                for key, value in analysis.items():
                    print(f"  {key}: {value}")
            else:
                print(f"  {analysis}")
        
        if 'score' in result:
            print(f"\n⭐ SEO-оценка: {result['score']}/100")
        
        if 'recommendations' in result:
            print(f"\n💡 Рекомендации:")
            for i, rec in enumerate(result['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        return result
        
    except Exception as e:
        print(f"❌ Ошибка ИИ-анализа: {e}")
        traceback.print_exc()
        return None

def generate_report_for_capsula():
    """Генерируем отчёт для Capsula Hair"""
    print("\n=== Генерация отчёта для Capsula Hair ===")
    
    try:
        from report import generate_html_report
        
        # Данные Capsula Hair
        capsula_data = {
            'title': 'Capsulahair',
            'address': '7-я линия Васильевского острова, 34, Санкт-Петербург',
            'phone': '+7 (812) 407-25-34',
            'rating': '5.0',
            'reviews_count': 1244,
            'categories': ['Салон красоты', 'Барбершоп', 'Парикмахерская'],
            'hours': 'Пн-Вс: 10:00–22:00',
            'photos': [],
            'reviews': [],
            'news': [],
            'products': [],
            'overview': {},
            'features_full': {'bool': [], 'valued': [], 'prices': [], 'categories': []}
        }
        
        # Результат анализа
        analysis_data = {
            'score': 100,
            'recommendations': [
                'Создайте официальный сайт для повышения видимости',
                'Добавьте качественные фотографии ваших услуг'
            ],
            'ai_analysis': {
                'generated_text': 'Отличный рейтинг показывает высокое качество услуг. Большое количество отзывов повышает доверие. Отсутствие сайта снижает видимость в поиске.',
                'strengths': ['Высокий рейтинг', 'Много отзывов', 'Есть телефон', 'Есть адрес'],
                'weaknesses': ['Нет сайта', 'Нет фото']
            }
        }
        
        print("Генерируем HTML отчёт...")
        report_path = generate_html_report(capsula_data, analysis_data)
        
        print(f"✅ Отчёт сгенерирован: {report_path}")
        
        # Проверяем файл
        if os.path.exists(report_path):
            file_size = os.path.getsize(report_path)
            print(f"📄 Размер файла: {file_size} байт")
            
            # Открываем в браузере
            print("🌐 Открываем отчёт в браузере...")
            os.system(f"open '{report_path}'")
            
            return report_path
        else:
            print("❌ Файл отчёта не создан")
            return None
        
    except Exception as e:
        print(f"❌ Ошибка генерации отчёта: {e}")
        traceback.print_exc()
        return None

def main():
    """Основная функция"""
    print("🔍 Анализ данных Capsula Hair")
    print("=" * 50)
    
    # Шаг 1: Ищем данные в базе
    capsula_card = find_capsula_data()
    
    # Шаг 2: Запускаем анализ
    analysis_result = run_analysis_on_capsula()
    
    # Шаг 3: Генерируем отчёт
    if analysis_result:
        report_path = generate_report_for_capsula()
        
        if report_path:
            print(f"\n🎉 Отчёт успешно создан: {report_path}")
        else:
            print("\n❌ Не удалось создать отчёт")
    else:
        print("\n❌ Анализ не выполнен")

if __name__ == "__main__":
    main()
