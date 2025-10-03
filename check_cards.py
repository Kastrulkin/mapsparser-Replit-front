#!/usr/bin/env python3
"""
Проверка созданных карточек в базе данных
"""
import sqlite3
from datetime import datetime

def check_cards():
    """Проверяем все созданные карточки"""
    conn = sqlite3.connect("reports.db")
    cursor = conn.cursor()
    
    print("=== Созданные карточки ===")
    cursor.execute("""
        SELECT id, title, url, seo_score, ai_analysis, recommendations, report_path, created_at
        FROM Cards 
        ORDER BY created_at DESC
    """)
    
    cards = cursor.fetchall()
    
    if not cards:
        print("❌ Карточки не найдены")
        return
    
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

if __name__ == "__main__":
    check_cards()
