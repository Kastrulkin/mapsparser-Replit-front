from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from auth_system import CONSENT_VERSION, normalize_email
from database_manager import get_db_connection


material_downloads_bp = Blueprint("material_downloads_api", __name__)

MATERIAL_DOWNLOAD_MAX_AGE_SECONDS = 15 * 60
MATERIAL_DOWNLOADS = {
    "checklist-audita-kartochki-kompanii": {
        "path": Path(__file__).resolve().parents[2] / "output" / "pdf" / "localos-checklist-audita-kartochki.pdf",
        "download_name": "localos-checklist-audita-kartochki.pdf",
    },
}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _download_serializer() -> URLSafeTimedSerializer:
    secret = str(
        os.getenv("MATERIAL_DOWNLOAD_TOKEN_SECRET")
        or os.getenv("EXTERNAL_AUTH_SECRET_KEY")
        or "localos-development-material-download-secret"
    ).strip()
    return URLSafeTimedSerializer(secret, salt="localos-material-download-v1")


def _client_ip() -> str:
    forwarded = str(request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    return forwarded or str(request.remote_addr or "").strip()


@material_downloads_bp.route("/api/public/material-downloads", methods=["POST"])
def request_material_download():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "invalid_json", "message": "Некорректный запрос"}), 400

    if str(payload.get("company_site") or "").strip():
        return jsonify({"success": False, "error": "invalid_request", "message": "Некорректный запрос"}), 400

    email = normalize_email(str(payload.get("email") or ""))
    material_slug = str(payload.get("material_slug") or "").strip()
    consent_given = payload.get("personal_data_consent") is True
    consent_version = CONSENT_VERSION
    source_language_raw = str(payload.get("source_language") or "ru").strip().lower()
    source_language = source_language_raw if source_language_raw in {"ru", "en", "el"} else "ru"
    material = MATERIAL_DOWNLOADS.get(material_slug)

    if not email or len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return jsonify({"success": False, "error": "invalid_email", "message": "Укажите корректный email"}), 400
    if not consent_given:
        return jsonify({"success": False, "error": "consent_required", "message": "Подтвердите согласие на обработку персональных данных"}), 400
    if not material:
        return jsonify({"success": False, "error": "material_not_found", "message": "Материал не найден"}), 404
    if not material["path"].is_file():
        return jsonify({"success": False, "error": "material_unavailable", "message": "Материал временно недоступен"}), 503

    request_id = str(uuid.uuid4())
    consent_ip = _client_ip()
    consent_user_agent = str(request.headers.get("User-Agent") or "").strip()[:1000]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS request_count
            FROM materialdownloadrequests
            WHERE consent_ip = %s
              AND created_at >= NOW() - INTERVAL '1 hour'
            """,
            (consent_ip,),
        )
        rate_row = cursor.fetchone()
        request_count = int((rate_row.get("request_count") if hasattr(rate_row, "get") else rate_row[0]) or 0)
        if request_count >= 20:
            return jsonify({"success": False, "error": "rate_limited", "message": "Слишком много запросов. Повторите позже"}), 429

        cursor.execute(
            """
            INSERT INTO materialdownloadrequests (
                id, email, material_slug, source_language, personal_data_consent,
                personal_data_consent_version, personal_data_consent_at,
                consent_ip, consent_user_agent, created_at
            ) VALUES (%s, %s, %s, %s, TRUE, %s, NOW(), %s, %s, NOW())
            """,
            (
                request_id,
                email,
                material_slug,
                source_language,
                consent_version,
                consent_ip,
                consent_user_agent,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    token = _download_serializer().dumps({"request_id": request_id, "material_slug": material_slug})
    return jsonify(
        {
            "success": True,
            "download_url": f"/api/public/material-downloads/{token}",
            "expires_in": MATERIAL_DOWNLOAD_MAX_AGE_SECONDS,
        }
    )


@material_downloads_bp.route("/api/public/material-downloads/<token>", methods=["GET"])
def download_material(token: str):
    try:
        token_payload = _download_serializer().loads(token, max_age=MATERIAL_DOWNLOAD_MAX_AGE_SECONDS)
    except SignatureExpired:
        return jsonify({"success": False, "error": "download_expired", "message": "Ссылка на скачивание устарела"}), 410
    except BadSignature:
        return jsonify({"success": False, "error": "invalid_download", "message": "Недействительная ссылка"}), 404

    request_id = str(token_payload.get("request_id") or "").strip() if isinstance(token_payload, dict) else ""
    material_slug = str(token_payload.get("material_slug") or "").strip() if isinstance(token_payload, dict) else ""
    material = MATERIAL_DOWNLOADS.get(material_slug)
    if not request_id or not material or not material["path"].is_file():
        return jsonify({"success": False, "error": "material_not_found", "message": "Материал не найден"}), 404

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM materialdownloadrequests
            WHERE id = %s
              AND material_slug = %s
              AND personal_data_consent = TRUE
            LIMIT 1
            """,
            (request_id, material_slug),
        )
        consent_row = cursor.fetchone()
        if not consent_row:
            return jsonify({"success": False, "error": "download_not_authorized", "message": "Скачивание не подтверждено"}), 403
        cursor.execute(
            "UPDATE materialdownloadrequests SET downloaded_at = COALESCE(downloaded_at, NOW()) WHERE id = %s",
            (request_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return send_file(
        material["path"],
        mimetype="application/pdf",
        as_attachment=True,
        download_name=material["download_name"],
        max_age=0,
    )
