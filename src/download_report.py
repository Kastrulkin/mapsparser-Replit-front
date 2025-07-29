"""
download_report.py — API endpoint для скачивания HTML отчётов
"""
import os
from flask import Flask, send_file, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Инициализация Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

@app.route('/download-report/<card_id>', methods=['GET'])
def download_report(card_id):
    """
    Скачивание HTML отчёта по ID карточки
    """
    try:
        # Получаем данные карточки
        response = supabase.table("Cards").select("report_path, user_id, title").eq("id", card_id).execute()
        
        if not response.data:
            return jsonify({"error": "Отчёт не найден"}), 404
        
        card_data = response.data[0]
        report_path = card_data.get('report_path')
        
        if not report_path or not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404
        
        # Проверяем права доступа (опционально)
        # user_id = request.headers.get('X-User-ID')
        # if user_id and card_data['user_id'] != user_id:
        #     return jsonify({"error": "Доступ запрещён"}), 403
        
        # Формируем имя файла для скачивания
        title = card_data.get('title', 'report')
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"seo_report_{safe_title}_{card_id}.html"
        
        return send_file(
            report_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/html'
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reports/<card_id>/download', methods=['GET'])
def api_download_report(card_id):
    """
    API endpoint для скачивания отчёта (JSON ответ)
    """
    try:
        # Получаем данные карточки
        response = supabase.table("Cards").select("report_path, user_id, title, seo_score").eq("id", card_id).execute()
        
        if not response.data:
            return jsonify({"error": "Отчёт не найден"}), 404
        
        card_data = response.data[0]
        report_path = card_data.get('report_path')
        
        if not report_path:
            return jsonify({"error": "Отчёт ещё не сгенерирован"}), 404
        
        if not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404
        
        # Возвращаем информацию об отчёте
        return jsonify({
            "success": True,
            "card_id": card_id,
            "title": card_data.get('title'),
            "seo_score": card_data.get('seo_score'),
            "report_path": report_path,
            "download_url": f"/download-report/{card_id}"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True) 