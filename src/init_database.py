#!/usr/bin/env python3
"""
Скрипт для инициализации SQLite базы данных
"""
import sqlite3
import os
from datetime import datetime

def init_database():
    """Создать и инициализировать базу данных"""
    # Создаем базу данных
    conn = sqlite3.connect("reports.db")
    cursor = conn.cursor()
    
    # Создаем таблицу Cards
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Cards (
        id TEXT PRIMARY KEY,
        url TEXT,
        title TEXT,
        report_path TEXT,
        user_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        seo_score INTEGER,
        ai_analysis TEXT
    )
    """)
    
    # Добавляем тестовые данные
    cursor.execute("""
    INSERT OR REPLACE INTO Cards (id, url, title, report_path, user_id, seo_score, ai_analysis)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        "2a8b7279-ac0c-4218-9ec3-dfdbe410a0bd",
        "https://yandex.ru/maps/org/gagarin/180566191872/?ll=30.339235%2C59.859247&z=17.22",
        "Гагарин",
        "/root/mapsparser-Replit-front/data/report_Гагарин.html",
        "f2123626-71b1-4424-8b2a-0bc93ab8f2eb",
        100,
        "Отличный рейтинг показывает высокое качество услуг"
    ))
    
    conn.commit()
    conn.close()
    print("База данных инициализирована успешно!")

if __name__ == "__main__":
    init_database()
