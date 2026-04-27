from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth_system import verify_session
from crypto_pay_client import (
    apply_crypto_invoice_paid,
    create_crypto_invoice_for_business,
    crypto_pay_webhook_secret,
    verify_crypto_pay_signature,
)
from database_manager import get_db_connection


crypto_pay_bp = Blueprint("crypto_pay", __name__)


def _require_auth():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    return verify_session(token)


@crypto_pay_bp.route("/api/billing/crypto/checkout/start", methods=["POST", "OPTIONS"])
def crypto_checkout_start():
    if request.method == "OPTIONS":
        return ("", 204)

    user_data = _require_auth()
    if not user_data:
        return jsonify({"error": "Требуется авторизация"}), 401

    data = request.get_json(silent=True) or {}
    business_id = str(data.get("business_id") or "").strip()
    raw_tariff = str(data.get("tariff_id") or data.get("tier") or "").strip()
    if not business_id:
        return jsonify({"error": "business_id обязателен"}), 400

    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    if not user_id:
        return jsonify({"error": "user_id not found in session"}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (business_id,))
        row = cursor.fetchone()
        owner_id = ""
        if row:
            owner_id = row.get("owner_id") if hasattr(row, "get") else (row[0] if row else "")
        if not owner_id:
            return jsonify({"error": "Бизнес не найден"}), 404
        if str(owner_id) != user_id and not user_data.get("is_superadmin"):
            return jsonify({"error": "Нет доступа к бизнесу"}), 403
    finally:
        conn.close()

    try:
        invoice = create_crypto_invoice_for_business(
            user_id=str(owner_id or user_id),
            business_id=business_id,
            tariff_id=raw_tariff,
            source="web_checkout",
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(
        {
            "success": True,
            "invoice_id": invoice.get("invoice_id") or invoice.get("id"),
            "invoice_url": invoice.get("bot_invoice_url") or invoice.get("mini_app_invoice_url") or invoice.get("web_app_invoice_url"),
            "status": invoice.get("status"),
        }
    )


@crypto_pay_bp.route("/api/crypto-pay/webhook/<secret_path>", methods=["POST"])
def crypto_pay_webhook(secret_path: str):
    expected_secret = crypto_pay_webhook_secret()
    if not expected_secret or secret_path != expected_secret:
        return jsonify({"error": "invalid webhook path"}), 403

    raw_body = request.get_data(cache=False)
    signature = request.headers.get("crypto-pay-api-signature") or request.headers.get("Crypto-Pay-Api-Signature") or ""
    if not verify_crypto_pay_signature(raw_body, signature):
        return jsonify({"error": "invalid signature"}), 403

    payload = request.get_json(silent=True) or {}
    update_type = str(payload.get("update_type") or "").strip().lower()
    invoice = dict(payload.get("payload") or {})
    if update_type != "invoice_paid":
        return jsonify({"success": True, "ignored": True, "update_type": update_type})
    try:
        result = apply_crypto_invoice_paid(invoice)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"success": True, "result": result})
