#!/usr/bin/env python3
import sqlite3
import os
from datetime import datetime

def create_test_report():
    conn = sqlite3.connect('reports.db')
    cursor = conn.cursor()
    
    try:
        print("🔧 Создаём тестовый отчёт...")
        
        # Получаем user_id из очереди
        cursor.execute("SELECT user_id FROM ParseQueue LIMIT 1")
        user_row = cursor.fetchone()
        if not user_row:
            print("❌ Нет пользователей в очереди")
            return
            
        user_id = user_row[0]
        print(f"  👤 User ID: {user_id}")
        
        # Создаём отчёт в Cards
        report_id = "test-report-gagarin"
        report_path = "data/report_Гагарин.html"
        
        # Создаём директорию data если её нет
        os.makedirs("data", exist_ok=True)
        
        # Создаём HTML отчёт
        html_content = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO-отчёт: Гагарин</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            line-height: 1.6;
        }
        .header { 
            background: #f0f0f0; 
            padding: 20px; 
            border-radius: 8px; 
            margin-bottom: 20px;
        }
        .score { 
            color: #28a745; 
            font-size: 24px; 
            font-weight: bold; 
        }
        .section {
            margin-bottom: 20px;
            padding: 15px;
            border-left: 4px solid #007bff;
            background: #f8f9fa;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>SEO-отчёт: Гагарин</h1>
        <p><strong>Адрес:</strong> просп. Юрия Гагарина, 20, корп. 1, Санкт-Петербург</p>
        <p><strong>Телефон:</strong> +7 (931) 388-99-12</p>
        <p class="score">Оценка SEO: 85 / 100</p>
    </div>
    
    <div class="section">
        <h2>Анализ организации</h2>
        <p>Парикмахерская "Гагарин" имеет высокий рейтинг и множество отзывов.</p>
        
        <h3>Сильные стороны:</h3>
        <ul>
            <li>Высокий рейтинг</li>
            <li>Много отзывов (108)</li>
            <li>Есть контактный телефон</li>
            <li>Указан адрес</li>
            <li>Указаны часы работы</li>
        </ul>
    </div>
    
    <div class="section">
        <h2>Рекомендации по улучшению</h2>
        <ul>
            <li>Добавить больше фотографий интерьера</li>
            <li>Регулярно отвечать на отзывы клиентов</li>
            <li>Обновлять информацию о ценах</li>
            <li>Добавить информацию о мастерах</li>
        </ul>
    </div>
</body>
</html>"""
        
        # Сохраняем HTML файл
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"  ✅ Создан файл: {report_path}")
        
        # Вставляем запись в Cards
        cursor.execute("""
            INSERT OR REPLACE INTO Cards 
            (id, url, title, address, phone, rating, reviews_count, working_hours, 
             report_path, user_id, seo_score, ai_analysis, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_id,
            "https://yandex.ru/maps/org/gagarin/180566191872/?ll=30.338344%2C59.858729&z=16.88",
            "Гагарин",
            "просп. Юрия Гагарина, 20, корп. 1, Санкт-Петербург",
            "+7 (931) 388-99-12",
            4.9,
            108,
            "Пн-Вс: 10:00–00:00",
            report_path,
            user_id,
            85,
            "Парикмахерская 'Гагарин' имеет высокий рейтинг и множество отзывов. Рекомендуется улучшить визуальное представление и активность в отзывах.",
            datetime.now().isoformat()
        ))
        
        # Удаляем задачу из очереди
        cursor.execute("DELETE FROM ParseQueue WHERE user_id = ?", (user_id,))
        
        conn.commit()
        print("✅ Тестовый отчёт создан!")
        print(f"  📄 Отчёт: {report_path}")
        print(f"  👤 Пользователь: {user_id}")
        print(f"  🆔 ID отчёта: {report_id}")
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_report()
