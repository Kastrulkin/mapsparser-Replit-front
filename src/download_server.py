"""
download_server.py — Простой веб-сервер для скачивания отчётов
"""
import os
import sqlite3
from flask import Flask, send_file, jsonify, Response
from urllib.parse import urlparse

app = Flask(__name__)

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/download-report/<card_id>', methods=['GET'])
def download_report(card_id):
    """
    Скачивание HTML отчёта по ID карточки
    """
    try:
        # Нормализуем ID
        normalized_id = card_id.replace('_', '-')
        
        # Получаем данные карточки из SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Cards WHERE id = ?", (normalized_id,))
        card_data = cursor.fetchone()
        conn.close()
        
        if not card_data:
            return jsonify({"error": "Отчёт не найден"}), 404
        
        report_path = card_data['report_path']
        
        if not report_path:
            return jsonify({"error": "Отчёт ещё не сгенерирован"}), 404
        
        if not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404
        
        # Формируем имя файла для скачивания (только латинские символы)
        title = card_data['title'] if card_data['title'] else 'report'
        # Транслитерация русских символов
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z',
            'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
            'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'YO', 'Ж': 'ZH', 'З': 'Z',
            'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R',
            'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'TS', 'Ч': 'CH', 'Ш': 'SH', 'Щ': 'SCH',
            'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'YU', 'Я': 'YA'
        }
        
        safe_title = ""
        for char in title:
            if char in translit_map:
                safe_title += translit_map[char]
            elif char.isalnum() or char in (' ', '-', '_'):
                safe_title += char
            else:
                safe_title += '_'
        
        safe_title = safe_title.strip().replace(' ', '_')
        filename = f"seo_report_{safe_title}_{card_id}.html"
        
        # Читаем содержимое файла
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Создаём ответ с правильными заголовками для скачивания
        response = Response(content, mimetype='text/html; charset=utf-8')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        # Убираем строгие заголовки безопасности для скачивания
        
        return response
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/view-report/<card_id>', methods=['GET'])
def view_report(card_id):
    """
    Просмотр HTML отчёта в браузере
    """
    try:
        # Нормализуем ID
        normalized_id = card_id.replace('_', '-')
        
        # Получаем данные карточки из SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Cards WHERE id = ?", (normalized_id,))
        card_data = cursor.fetchone()
        conn.close()
        
        if not card_data:
            return jsonify({"error": "Отчёт не найден"}), 404
        
        report_path = card_data['report_path']
        
        if not report_path:
            return jsonify({"error": "Отчёт ещё не сгенерирован"}), 404
        
        if not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404
        
        # Читаем содержимое файла
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Создаём ответ для просмотра в браузере
        response = Response(content, mimetype='text/html; charset=utf-8')
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        # Разрешаем отображение в iframe для просмотра
        response.headers['X-Frame-Options'] = 'ALLOWALL'
        
        return response
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reports/<card_id>/status', methods=['GET'])
def report_status(card_id):
    """
    Проверка статуса отчёта
    """
    try:
        # Нормализуем ID
        normalized_id = card_id.replace('_', '-')
        
        # Получаем данные карточки из SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Cards WHERE id = ?", (normalized_id,))
        card_data = cursor.fetchone()
        conn.close()
        
        if not card_data:
            return jsonify({"error": "Отчёт не найден"}), 404
        
        return jsonify({
            "success": True,
            "card_id": card_id,
            "title": card_data['title'],
            "seo_score": card_data['seo_score'],
            "has_report": bool(card_data['report_path']),
            "has_ai_analysis": bool(card_data['ai_analysis']),
            "report_path": card_data['report_path']
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("Сервер скачивания отчётов запущен на порту 8001")
    app.run(host='0.0.0.0', port=8001, debug=True) 