"""
download_report.py — API endpoint для скачивания HTML отчётов (SQLite)
"""
import os
import sqlite3
from flask import Flask, send_file, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


def _get_connection():
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/download-report/<card_id>', methods=['GET'])
def download_report(card_id):
    """
    Скачивание HTML отчёта по ID карточки
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT report_path, user_id, title FROM Cards WHERE id = ?", (card_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return jsonify({"error": "Отчёт не найден"}), 404

        report_path = row["report_path"]
        if not report_path or not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404

        title = row.get('title') if isinstance(row, dict) else row['title']
        title = title or 'report'
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
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT report_path, user_id, title, seo_score FROM Cards WHERE id = ?", (card_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return jsonify({"error": "Отчёт не найден"}), 404

        report_path = row['report_path']
        if not report_path:
            return jsonify({"error": "Отчёт ещё не сгенерирован"}), 404
        if not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404

        return jsonify({
            "success": True,
            "card_id": card_id,
            "title": row['title'],
            "seo_score": row['seo_score'],
            "report_path": report_path,
            "download_url": f"/download-report/{card_id}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)