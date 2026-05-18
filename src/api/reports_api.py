import os
import sys

from flask import Blueprint, Response, jsonify

from safe_db_utils import get_db_connection


reports_bp = Blueprint("reports_api", __name__)


_TRANSLIT_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "YO", "Ж": "ZH", "З": "Z",
    "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N", "О": "O", "П": "P", "Р": "R",
    "С": "S", "Т": "T", "У": "U", "Ф": "F", "Х": "H", "Ц": "TS", "Ч": "CH", "Ш": "SH", "Щ": "SCH",
    "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "YU", "Я": "YA",
}


def _get_card(card_id):
    normalized_id = card_id.replace("_", "-")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM Cards WHERE id = ?", (normalized_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def _safe_report_title(title):
    safe_title = ""
    for char in title:
        if char in _TRANSLIT_MAP:
            safe_title += _TRANSLIT_MAP[char]
        elif char.isalnum() or char in (" ", "-", "_"):
            safe_title += char
        else:
            safe_title += "_"
    return safe_title.strip().replace(" ", "_")


@reports_bp.route("/api/download-report/<card_id>", methods=["GET"])
def download_report(card_id):
    """Скачивание HTML отчёта по ID карточки."""
    try:
        card_data = _get_card(card_id)
        if not card_data:
            return jsonify({"error": "Отчёт не найден"}), 404

        report_path = card_data["report_path"]
        if not report_path:
            return jsonify({"error": "Отчёт ещё не сгенерирован"}), 404
        if not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404

        title = card_data["title"] if card_data["title"] else "report"
        filename = f"seo_report_{_safe_report_title(title)}_{card_id}.html"

        with open(report_path, "r", encoding="utf-8") as report_file:
            content = report_file.read()

        response = Response(content, mimetype="text/html; charset=utf-8")
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response
    except Exception:
        error = sys.exc_info()[1]
        return jsonify({"error": str(error)}), 500


@reports_bp.route("/api/view-report/<card_id>", methods=["GET"])
def view_report(card_id):
    """Просмотр HTML отчёта в браузере."""
    try:
        card_data = _get_card(card_id)
        if not card_data:
            return jsonify({"error": "Отчёт не найден"}), 404

        report_path = card_data["report_path"]
        if not report_path:
            return jsonify({"error": "Отчёт ещё не сгенерирован"}), 404
        if not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404

        with open(report_path, "r", encoding="utf-8") as report_file:
            content = report_file.read()

        response = Response(content, mimetype="text/html; charset=utf-8")
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        response.headers["X-Frame-Options"] = "ALLOWALL"
        return response
    except Exception:
        error = sys.exc_info()[1]
        return jsonify({"error": str(error)}), 500


@reports_bp.route("/api/reports/<card_id>/status", methods=["GET"])
def report_status(card_id):
    """Проверка статуса отчёта."""
    try:
        card_data = _get_card(card_id)
        if not card_data:
            return jsonify({"error": "Отчёт не найден"}), 404

        return jsonify({
            "success": True,
            "card_id": card_id,
            "title": card_data["title"],
            "seo_score": card_data["seo_score"],
            "has_report": bool(card_data["report_path"]),
            "has_ai_analysis": bool(card_data["ai_analysis"]),
            "report_path": card_data["report_path"],
        })
    except Exception:
        error = sys.exc_info()[1]
        return jsonify({"error": str(error)}), 500
