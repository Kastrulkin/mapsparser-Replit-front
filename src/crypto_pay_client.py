from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from billing_constants import TARIFFS, TARIFF_ALIASES
from database_manager import DatabaseManager
from services.checkout_session_service import (
    complete_checkout,
    create_checkout_session,
    get_checkout_session_by_provider_invoice,
    mark_checkout_created,
    mark_checkout_paid,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_str_dt(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _row_to_dict(cursor, row) -> dict[str, Any]:
    if not row:
        return {}
    if isinstance(row, dict):
        return row
    cols = [d[0] for d in (cursor.description or [])]
    return dict(zip(cols, row))


def _normalize_tariff_id(tariff_id: str) -> str | None:
    raw = str(tariff_id or "").strip().lower()
    if not raw:
        return None
    if raw in TARIFFS:
        return raw
    return TARIFF_ALIASES.get(raw)


def _next_month_anniversary(base_dt: datetime) -> datetime:
    safe_base = base_dt.astimezone(timezone.utc) if base_dt.tzinfo else base_dt.replace(tzinfo=timezone.utc)
    next_month = safe_base.month + 1
    next_year = safe_base.year
    if next_month == 13:
        next_month = 1
        next_year += 1
    day = min(safe_base.day, 28)
    return safe_base.replace(year=next_year, month=next_month, day=day)


def _ensure_subscription_row(cursor, *, user_id: str, business_id: str, tariff_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM subscriptions WHERE business_id = %s LIMIT 1", (business_id,))
    row = _row_to_dict(cursor, cursor.fetchone())
    if row:
        return row

    sub_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO subscriptions (
            id, user_id, business_id, tariff_id, pending_tariff_id, status,
            retry_count, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, NULL, 'blocked', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING *
        """,
        (sub_id, user_id, business_id, tariff_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _mark_business_subscription(cursor, business_id: str, *, tariff_id: str, status: str, next_billing_date: datetime | None) -> None:
    tier = TARIFFS.get(tariff_id, {}).get("business_tier", "starter")
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'businesses'
          AND column_name IN ('subscription_tier', 'subscription_status', 'subscription_ends_at', 'updated_at')
        """
    )
    existing = {r[0] if not isinstance(r, dict) else r.get("column_name") for r in (cursor.fetchall() or [])}

    set_parts: list[str] = []
    values: list[Any] = []
    if "subscription_tier" in existing:
        set_parts.append("subscription_tier = %s")
        values.append(tier)
    if "subscription_status" in existing:
        set_parts.append("subscription_status = %s")
        values.append(status)
    if "subscription_ends_at" in existing:
        set_parts.append("subscription_ends_at = %s")
        values.append(_as_str_dt(next_billing_date))
    if "updated_at" in existing:
        set_parts.append("updated_at = CURRENT_TIMESTAMP")
    if not set_parts:
        return
    values.append(business_id)
    cursor.execute(f"UPDATE businesses SET {', '.join(set_parts)} WHERE id = %s", tuple(values))


def _set_user_credits(cursor, *, user_id: str, subscription_id: str, tariff_id: str, external_id: str, period_start: datetime, period_end: datetime) -> None:
    credits = TARIFFS.get(tariff_id, {}).get("credits")
    if credits is None:
        return

    cursor.execute("SELECT credits_balance FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    old_balance = int((_row_to_dict(cursor, row).get("credits_balance") if row else 0) or 0)
    new_balance = int(credits)
    delta = new_balance - old_balance
    cursor.execute(
        "UPDATE users SET credits_balance = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (new_balance, user_id),
    )
    cursor.execute(
        """
        INSERT INTO credit_ledger (
            id, user_id, subscription_id, delta, reason, period_start, period_end, external_id, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (
            str(uuid.uuid4()),
            user_id,
            subscription_id,
            delta,
            "period_refresh",
            _as_str_dt(period_start),
            _as_str_dt(period_end),
            external_id,
        ),
    )


class CryptoPayClient:
    def __init__(self) -> None:
        self.token = (os.getenv("CRYPTO_PAY_API_TOKEN") or "").strip()
        self.base_url = (os.getenv("CRYPTO_PAY_API_BASE") or "https://pay.crypt.bot/api/").strip()
        if not self.base_url.endswith("/"):
            self.base_url += "/"

    def configured(self) -> bool:
        return bool(self.token)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.configured():
            raise RuntimeError("CRYPTO_PAY_API_TOKEN is not configured")
        response = requests.request(
            method,
            f"{self.base_url}{path.lstrip('/')}",
            headers={
                "Content-Type": "application/json",
                "Crypto-Pay-API-Token": self.token,
            },
            json=payload,
            timeout=30,
        )
        try:
            data = response.json()
        except Exception:
            data = {"ok": False, "error": response.text}
        if response.status_code >= 400 or not data.get("ok"):
            raise RuntimeError(str(data.get("error") or f"Crypto Pay API error {response.status_code}"))
        return dict(data.get("result") or {})

    def create_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "createInvoice", payload)

    def get_invoices(self, invoice_ids: list[str] | None = None, status: str | None = None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {}
        if invoice_ids:
            payload["invoice_ids"] = ",".join(str(item).strip() for item in invoice_ids if str(item).strip())
        if status:
            payload["status"] = str(status).strip()
        result = self._request("POST", "getInvoices", payload)
        invoices = result.get("items")
        if isinstance(invoices, list):
            return [dict(item or {}) for item in invoices]
        if isinstance(result, list):
            return [dict(item or {}) for item in result]
        return []


def crypto_pay_webhook_secret() -> str:
    explicit = (os.getenv("CRYPTO_PAY_WEBHOOK_SECRET") or "").strip()
    if explicit:
        return explicit
    token = (os.getenv("CRYPTO_PAY_API_TOKEN") or "").strip()
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def verify_crypto_pay_signature(raw_body: bytes, signature: str) -> bool:
    token = (os.getenv("CRYPTO_PAY_API_TOKEN") or "").strip()
    incoming = str(signature or "").strip()
    if not token or not incoming:
        return False
    secret = hashlib.sha256(token.encode("utf-8")).digest()
    computed = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, incoming)


def _build_return_url(tier_key: str) -> str:
    base = (os.getenv("FRONTEND_BASE_URL") or "https://localos.pro").rstrip("/")
    return f"{base}/dashboard/profile?crypto_pay_return=1&tier={tier_key}"


def create_crypto_invoice_for_business(*, user_id: str, business_id: str, tariff_id: str, source: str) -> dict[str, Any]:
    normalized_tariff = _normalize_tariff_id(tariff_id or "")
    if not normalized_tariff or normalized_tariff not in TARIFFS:
        raise RuntimeError(f"Неверный тариф: {tariff_id}")

    client = CryptoPayClient()
    if not client.configured():
        raise RuntimeError("Crypto Pay не настроен")

    tariff = TARIFFS[normalized_tariff]
    payload_data = {
        "kind": "subscription_crypto_payment",
        "user_id": str(user_id or "").strip(),
        "business_id": str(business_id or "").strip(),
        "tariff_id": normalized_tariff,
        "source": str(source or "").strip(),
        "nonce": uuid.uuid4().hex[:12],
        "issued_at": _utcnow().isoformat(),
    }
    invoice = client.create_invoice(
        {
            "currency_type": "fiat",
            "fiat": "RUB",
            "amount": str(int(tariff["amount"])),
            "description": f"LocalOS {normalized_tariff} subscription",
            "payload": json.dumps(payload_data, ensure_ascii=False),
            "expires_in": 3600,
            "allow_comments": False,
            "allow_anonymous": False,
            "paid_btn_name": "callback",
            "paid_btn_url": _build_return_url(normalized_tariff),
        }
    )
    invoice["payload_data"] = payload_data
    return invoice


def create_crypto_invoice_for_checkout_session(
    *,
    tariff_id: str,
    source: str,
    telegram_id: str | None = None,
    telegram_username: str | None = None,
    telegram_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    maps_url: str | None = None,
    normalized_maps_url: str | None = None,
    audit_slug: str | None = None,
    audit_public_url: str | None = None,
    competitor_maps_url: str | None = None,
    competitor_audit_url: str | None = None,
    payload_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_tariff = _normalize_tariff_id(tariff_id or "")
    if not normalized_tariff or normalized_tariff not in TARIFFS:
        raise RuntimeError(f"Неверный тариф: {tariff_id}")

    client = CryptoPayClient()
    if not client.configured():
        raise RuntimeError("Crypto Pay не настроен")

    session = create_checkout_session(
        provider="telegram_crypto",
        channel="telegram",
        entry_point="telegram_guest",
        tariff_id=normalized_tariff,
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        telegram_name=telegram_name,
        email=email,
        phone=phone,
        maps_url=maps_url,
        normalized_maps_url=normalized_maps_url,
        audit_slug=audit_slug,
        audit_public_url=audit_public_url,
        competitor_maps_url=competitor_maps_url,
        competitor_audit_url=competitor_audit_url,
        source=source,
        payload_json=payload_json or {},
    )
    tariff = TARIFFS[normalized_tariff]
    payload_data = {
        "kind": "checkout_session_crypto_payment",
        "checkout_session_id": str(session.get("id") or ""),
        "tariff_id": normalized_tariff,
        "source": str(source or "").strip(),
        "nonce": uuid.uuid4().hex[:12],
        "issued_at": _utcnow().isoformat(),
    }
    invoice = client.create_invoice(
        {
            "currency_type": "fiat",
            "fiat": "RUB",
            "amount": str(int(tariff["amount"])),
            "description": f"LocalOS {normalized_tariff} subscription",
            "payload": json.dumps(payload_data, ensure_ascii=False),
            "expires_in": 3600,
            "allow_comments": False,
            "allow_anonymous": False,
            "paid_btn_name": "callback",
            "paid_btn_url": _build_return_url(normalized_tariff),
        }
    )
    mark_checkout_created(
        str(session.get("id") or ""),
        provider_invoice_id=str(invoice.get("invoice_id") or invoice.get("id") or "").strip() or None,
        provider_status=str(invoice.get("status") or "").strip() or None,
        payload_patch={
            "telegram_username": str(telegram_username or "").strip() or None,
            "telegram_name": str(telegram_name or "").strip() or None,
        },
    )
    invoice["payload_data"] = payload_data
    invoice["checkout_session_id"] = str(session.get("id") or "")
    return invoice


def apply_crypto_invoice_paid(invoice: dict[str, Any]) -> dict[str, Any]:
    payload_raw = str(invoice.get("payload") or "").strip()
    if not payload_raw:
        raise RuntimeError("Crypto invoice payload is missing")
    try:
        payload = json.loads(payload_raw)
    except Exception as exc:
        raise RuntimeError(f"Crypto invoice payload is invalid: {exc}")

    invoice_id = str(invoice.get("invoice_id") or invoice.get("id") or "").strip()
    checkout_session_id = str(payload.get("checkout_session_id") or "").strip()
    if checkout_session_id:
        existing_session = get_checkout_session_by_provider_invoice("telegram_crypto", invoice_id)
        session_id = str(existing_session.get("id") or checkout_session_id).strip()
        session = mark_checkout_paid(
            session_id,
            provider_payment_id=invoice_id or None,
            provider_status=str(invoice.get("status") or "paid").strip() or "paid",
        )
        if str(session.get("status") or "").strip() == "completed":
            return complete_checkout(session_id)
        return complete_checkout(session_id)

    business_id = str(payload.get("business_id") or "").strip()
    user_id = str(payload.get("user_id") or "").strip()
    tariff_id = _normalize_tariff_id(str(payload.get("tariff_id") or ""))
    if not business_id or not user_id or not tariff_id:
        raise RuntimeError("Crypto invoice payload is incomplete")

    paid_at = _utcnow()
    period_end = _next_month_anniversary(paid_at)

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        sub = _ensure_subscription_row(cursor, user_id=user_id, business_id=business_id, tariff_id=tariff_id)
        if str(sub.get("last_payment_id") or "").strip() == invoice_id and invoice_id:
            db.conn.commit()
            return {
                "status": "ignored",
                "reason": "already_applied",
                "subscription_id": sub.get("id"),
                "invoice_id": invoice_id,
            }

        cursor.execute(
            """
            UPDATE subscriptions
            SET tariff_id = %s,
                pending_tariff_id = NULL,
                status = 'active',
                period_start = %s,
                next_billing_date = %s,
                last_payment_id = %s,
                retry_count = 0,
                next_retry_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (
                tariff_id,
                _as_str_dt(paid_at),
                _as_str_dt(period_end),
                invoice_id or f"crypto-{uuid.uuid4().hex[:12]}",
                sub["id"],
            ),
        )
        updated = _row_to_dict(cursor, cursor.fetchone())
        _set_user_credits(
            cursor,
            user_id=user_id,
            subscription_id=str(updated.get("id") or sub.get("id") or ""),
            tariff_id=tariff_id,
            external_id=invoice_id,
            period_start=paid_at,
            period_end=period_end,
        )
        _mark_business_subscription(
            cursor,
            business_id,
            tariff_id=tariff_id,
            status="active",
            next_billing_date=period_end,
        )
        db.conn.commit()
        return {
            "status": "active",
            "subscription_id": updated.get("id"),
            "invoice_id": invoice_id,
            "business_id": business_id,
            "tariff_id": tariff_id,
        }
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
