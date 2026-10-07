import os
import uuid

from flask import Blueprint, Response, current_app, g, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import get_db_connection


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


def _error_response(code, message, status_code):
    request_id = str(getattr(g, "request_id", "") or request.headers.get("X-Request-ID") or uuid.uuid4())
    return jsonify({"code": code, "message": message, "request_id": request_id}), status_code


def _require_report_user():
    user_data = require_auth_from_request()
    if not user_data:
        return None, _error_response("authentication_required", "Требуется авторизация", 401)
    return user_data, None


def _require_card_access(card_data, user_data):
    business_id = str(card_data.get("business_id") or "").strip()
    if not business_id:
        if user_data.get("is_superadmin", False):
            return None
        return _error_response("business_access_denied", "Нет доступа к отчёту", 403)

    conn = get_db_connection()
    try:
        allowed, _owner_id = verify_business_access(conn.cursor(), business_id, user_data)
    finally:
        conn.close()
    if not allowed:
        return _error_response("business_access_denied", "Нет доступа к отчёту", 403)
    return None


def _internal_error():
    request_id = str(getattr(g, "request_id", "") or request.headers.get("X-Request-ID") or uuid.uuid4())
    current_app.logger.exception("Report API request failed request_id=%s", request_id)
    return jsonify({
        "code": "internal_error",
        "message": "Не удалось обработать отчёт",
        "request_id": request_id,
    }), 500


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
        user_data, auth_error = _require_report_user()
        if auth_error:
            return auth_error
        card_data = _get_card(card_id)
        if not card_data:
            return _error_response("report_not_found", "Отчёт не найден", 404)
        access_error = _require_card_access(card_data, user_data)
        if access_error:
            return access_error

        report_path = card_data["report_path"]
        if not report_path:
            return _error_response("report_not_ready", "Отчёт ещё не сгенерирован", 404)
        if not os.path.exists(report_path):
            return _error_response("report_file_not_found", "Файл отчёта не найден", 404)

        title = card_data["title"] if card_data["title"] else "report"
        filename = f"seo_report_{_safe_report_title(title)}_{card_id}.html"

        with open(report_path, "r", encoding="utf-8") as report_file:
            content = report_file.read()

        response = Response(content, mimetype="text/html; charset=utf-8")
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response
    except Exception:
        return _internal_error()


@reports_bp.route("/api/view-report/<card_id>", methods=["GET"])
def view_report(card_id):
    """Просмотр HTML отчёта в браузере."""
    try:
        user_data, auth_error = _require_report_user()
        if auth_error:
            return auth_error
        card_data = _get_card(card_id)
        if not card_data:
            return _error_response("report_not_found", "Отчёт не найден", 404)
        access_error = _require_card_access(card_data, user_data)
        if access_error:
            return access_error

        report_path = card_data["report_path"]
        if not report_path:
            return _error_response("report_not_ready", "Отчёт ещё не сгенерирован", 404)
        if not os.path.exists(report_path):
            return _error_response("report_file_not_found", "Файл отчёта не найден", 404)

        with open(report_path, "r", encoding="utf-8") as report_file:
            content = report_file.read()

        response = Response(content, mimetype="text/html; charset=utf-8")
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        response.headers["X-Frame-Options"] = "ALLOWALL"
        return response
    except Exception:
        return _internal_error()


@reports_bp.route("/api/reports/<card_id>/status", methods=["GET"])
def report_status(card_id):
    """Проверка статуса отчёта."""
    try:
        user_data, auth_error = _require_report_user()
        if auth_error:
            return auth_error
        card_data = _get_card(card_id)
        if not card_data:
            return _error_response("report_not_found", "Отчёт не найден", 404)
        access_error = _require_card_access(card_data, user_data)
        if access_error:
            return access_error

        return jsonify({
            "success": True,
            "card_id": card_id,
            "title": card_data["title"],
            "seo_score": card_data["seo_score"],
            "has_report": bool(card_data["report_path"]),
            "has_ai_analysis": bool(card_data["ai_analysis"]),
        })
    except Exception:
        return _internal_error()
