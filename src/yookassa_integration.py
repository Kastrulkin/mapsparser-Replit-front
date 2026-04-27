#!/usr/bin/env python3
"""YooKassa billing integration: checkout, webhook, renewals/retries."""

import json
import os
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import requests
from flask import Blueprint, jsonify, request

from auth_system import verify_session
from billing_constants import TARIFFS, TARIFF_ALIASES
from database_manager import DatabaseManager
from services.checkout_session_service import (
    complete_checkout,
    create_checkout_session,
    get_checkout_session_by_provider_invoice,
    get_checkout_status,
    load_checkout_session,
    mark_checkout_created,
    mark_checkout_failed,
    mark_checkout_paid,
)


billing_bp = Blueprint("billing", __name__)

RETRY_DELAYS_DAYS = (1, 2)  # D1, D3 relative to initial D0


class YooKassaClient:
    def __init__(self) -> None:
        self.shop_id = (os.getenv("YOOKASSA_SHOP_ID") or "").strip()
        self.secret_key = (os.getenv("YOOKASSA_SECRET_KEY") or "").strip()
        self.base_url = (os.getenv("YOOKASSA_API_BASE") or "https://api.yookassa.ru/v3/").strip()
        if not self.base_url.endswith("/"):
            self.base_url += "/"

    def configured(self) -> bool:
        return bool(self.shop_id and self.secret_key)

    def _request(self, method: str, path: str, *, idempotency_key: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.configured():
            raise RuntimeError("YooKassa is not configured")
        url = f"{self.base_url}{path.lstrip('/')}"
        headers = {"Content-Type": "application/json"}
        if idempotency_key:
            headers["Idempotence-Key"] = idempotency_key

        response = requests.request(
            method,
            url,
            headers=headers,
            json=payload,
            auth=(self.shop_id, self.secret_key),
            timeout=30,
        )
        if response.status_code >= 400:
            try:
                err_data = response.json()
            except Exception:
                err_data = {"raw": response.text}
            raise RuntimeError(f"YooKassa API {response.status_code}: {err_data}")
        return response.json()

    def create_payment(self, *, payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        return self._request("POST", "payments", idempotency_key=idempotency_key, payload=payload)

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        return self._request("GET", f"payments/{payment_id}")


def _short_idempotency_key(kind: str, subscription_id: str, extra: str = "") -> str:
    """
    YooKassa enforces max length for Idempotence-Key.
    Build stable, compact keys <= 64 chars.
    """
    digest = hashlib.sha1(f"{kind}|{subscription_id}|{extra}".encode("utf-8")).hexdigest()[:12]
    sid = (subscription_id or "").replace("-", "")[:12]
    stamp = _utcnow().strftime("%y%m%d%H%M%S")
    parts = [kind[:2], sid, stamp, digest]
    if extra:
        parts.append(hashlib.sha1(extra.encode("utf-8")).hexdigest()[:6])
    key = ":".join(parts)
    return key[:64]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_str_dt(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _normalize_tariff_id(tariff_id: str) -> Optional[str]:
    raw = str(tariff_id or "").strip().lower()
    if not raw:
        return None
    if raw in TARIFFS:
        return raw
    return TARIFF_ALIASES.get(raw)


def _normalize_checkout_provider(provider: str) -> str:
    raw = str(provider or "").strip().lower()
    if raw in {"russia", "ru", "yookassa"}:
        return "yookassa"
    if raw == "stripe":
        return "stripe"
    raise RuntimeError(f"Unsupported checkout provider: {provider}")


def _resolve_checkout_amount_and_currency(provider: str, tariff_id: str) -> Tuple[Decimal, str]:
    normalized_provider = _normalize_checkout_provider(provider)
    normalized_tariff = _normalize_tariff_id(tariff_id or "")
    if not normalized_tariff or normalized_tariff not in TARIFFS:
        raise RuntimeError(f"Неверный тариф: {tariff_id}")

    if normalized_provider == "stripe":
        from stripe_integration import TIERS, _normalize_checkout_tariff_for_stripe

        stripe_tier = _normalize_checkout_tariff_for_stripe(normalized_tariff)
        stripe_info = TIERS.get(stripe_tier) or {}
        cents = int(stripe_info.get("amount") or 0)
        return (Decimal(cents) / Decimal("100"), "USD")

    tariff = TARIFFS[normalized_tariff]
    return (Decimal(str(tariff["amount"])), str(tariff["currency"]))


def _require_auth() -> Optional[Dict[str, Any]]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    return verify_session(token)


def _row_to_dict(cursor, row) -> Dict[str, Any]:
    if not row:
        return {}
    if isinstance(row, dict):
        return row
    cols = [d[0] for d in (cursor.description or [])]
    return dict(zip(cols, row))


def _load_business_checkout_context(cursor, business_id: str) -> Dict[str, Any]:
    cursor.execute(
        """
        SELECT id, owner_id, name, yandex_url, city, address
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _ensure_subscription_row(cursor, *, user_id: str, business_id: Optional[str], tariff_id: str) -> Dict[str, Any]:
    if business_id:
        cursor.execute("SELECT * FROM subscriptions WHERE business_id = %s LIMIT 1", (business_id,))
        row = _row_to_dict(cursor, cursor.fetchone())
        if row:
            return row

    cursor.execute(
        """
        SELECT *
        FROM subscriptions
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone())
    if row and (not business_id or not row.get("business_id")):
        if business_id and not row.get("business_id"):
            cursor.execute(
                """
                UPDATE subscriptions
                SET business_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (business_id, row["id"]),
            )
            row["business_id"] = business_id
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


def _mark_business_subscription(cursor, business_id: Optional[str], *, tariff_id: str, status: str, next_billing_date: Optional[datetime]) -> None:
    if not business_id:
        return
    tier = TARIFFS.get(tariff_id, {}).get("business_tier", "starter")
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'businesses'
          AND column_name IN ('subscription_tier', 'subscription_status', 'subscription_ends_at', 'updated_at')
        """,
    )
    existing = {r[0] if not isinstance(r, dict) else r.get("column_name") for r in (cursor.fetchall() or [])}

    set_parts = []
    values = []
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


def _set_user_credits(cursor, *, user_id: str, subscription_id: str, tariff_id: str, payment_id: Optional[str], period_start: Optional[datetime], period_end: Optional[datetime]) -> None:
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
            payment_id,
        ),
    )


def _next_month_anniversary(dt: datetime) -> datetime:
    # Без внешних зависимостей: +31 day затем выравнивание на число месяца старта.
    # Для MVP достаточно стабильного "раз в месяц".
    base = dt + timedelta(days=31)
    return base.replace(day=min(dt.day, 28), hour=dt.hour, minute=dt.minute, second=dt.second, microsecond=0)


def _build_payment_payload(*, amount: Decimal, currency: str, return_url: str, description: str, metadata: Dict[str, Any], payment_method_id: Optional[str], save_payment_method: bool, recurring: bool) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "amount": {"value": f"{amount:.2f}", "currency": currency},
        "capture": True,
        "description": description,
        "metadata": {k: str(v) for k, v in (metadata or {}).items() if v is not None},
    }

    if payment_method_id:
        payload["payment_method_id"] = payment_method_id
    else:
        payload["confirmation"] = {
            "type": "redirect",
            "return_url": return_url,
        }

    if save_payment_method:
        payload["save_payment_method"] = True

    if recurring:
        payload["description"] = f"{description} (recurring)"

    return payload


def _build_checkout_return_url(session: Dict[str, Any]) -> str:
    frontend_base = (os.getenv("FRONTEND_BASE_URL") or "http://localhost:8000").rstrip("/")
    if str(session.get("entry_point") or "").strip() == "registered_paywall" and str(session.get("business_id") or "").strip():
        return f"{frontend_base}/dashboard/profile?yookassa_return=1&checkout_session={session.get('id')}"
    return f"{frontend_base}/checkout/return?session_id={session.get('id')}"


def create_yookassa_payment_for_checkout_session(session_id: str) -> Dict[str, Any]:
    session = load_checkout_session(session_id)
    tariff_id = _normalize_tariff_id(str(session.get("tariff_id") or ""))
    if not tariff_id or tariff_id not in TARIFFS:
        raise RuntimeError(f"Неверный тариф: {session.get('tariff_id')}")
    client = YooKassaClient()
    if not client.configured():
        raise RuntimeError("YooKassa is not configured")

    amount = TARIFFS[tariff_id]["amount"]
    currency = TARIFFS[tariff_id]["currency"]
    payment = client.create_payment(
        payload=_build_payment_payload(
            amount=amount,
            currency=currency,
            return_url=_build_checkout_return_url(session),
            description=f"LocalOS {tariff_id} checkout",
            metadata={
                "checkout_session_id": str(session.get("id") or ""),
                "tariff_id": tariff_id,
                "entry_point": str(session.get("entry_point") or ""),
                "kind": "checkout_session_payment",
                "env": os.getenv("YOOKASSA_ENV", "prod"),
            },
            payment_method_id=None,
            save_payment_method=True,
            recurring=False,
        ),
        idempotency_key=_short_idempotency_key("cs", str(session.get("id") or ""), uuid.uuid4().hex[:10]),
    )
    updated = mark_checkout_created(
        str(session.get("id") or ""),
        provider_invoice_id=str(payment.get("id") or "").strip() or None,
        provider_status=str(payment.get("status") or "").strip() or None,
    )
    return {
        "session": updated,
        "payment_id": payment.get("id"),
        "confirmation_url": ((payment.get("confirmation") or {}).get("confirmation_url")),
        "payment_status": payment.get("status"),
    }


def _create_billing_attempt(cursor, *, subscription_id: str, attempt_type: str, attempt_no: int, status: str, scheduled_at: Optional[datetime], amount: Decimal, currency: str, idempotency_key: str, payment_id: Optional[str], error_message: Optional[str], metadata: Optional[Dict[str, Any]] = None) -> None:
    cursor.execute(
        """
        INSERT INTO billing_attempts (
            id, subscription_id, attempt_type, attempt_no, scheduled_at,
            status, payment_id, idempotency_key, amount_value, currency,
            error_message, metadata, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (idempotency_key)
        DO UPDATE SET
            status = EXCLUDED.status,
            payment_id = COALESCE(EXCLUDED.payment_id, billing_attempts.payment_id),
            error_message = COALESCE(EXCLUDED.error_message, billing_attempts.error_message),
            metadata = COALESCE(EXCLUDED.metadata, billing_attempts.metadata),
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            str(uuid.uuid4()),
            subscription_id,
            attempt_type,
            int(attempt_no),
            _as_str_dt(scheduled_at),
            status,
            payment_id,
            idempotency_key,
            f"{amount:.2f}",
            currency,
            error_message,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )


def _subscription_public_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "tariff_id": row.get("tariff_id"),
        "pending_tariff_id": row.get("pending_tariff_id"),
        "status": row.get("status"),
        "period_start": _as_str_dt(_parse_dt(row.get("period_start"))),
        "next_billing_date": _as_str_dt(_parse_dt(row.get("next_billing_date"))),
        "retry_count": int(row.get("retry_count") or 0),
        "next_retry_at": _as_str_dt(_parse_dt(row.get("next_retry_at"))),
        "last_payment_id": row.get("last_payment_id"),
        "business_id": row.get("business_id"),
    }


def _apply_payment_succeeded(cursor, *, payment: Dict[str, Any], source_event: str) -> Dict[str, Any]:
    metadata = dict(payment.get("metadata") or {})
    subscription_id = str(metadata.get("subscription_id") or "").strip()
    if not subscription_id:
        raise RuntimeError("YooKassa payment metadata.subscription_id is missing")

    cursor.execute("SELECT * FROM subscriptions WHERE id = %s", (subscription_id,))
    sub = _row_to_dict(cursor, cursor.fetchone())
    if not sub:
        raise RuntimeError(f"Subscription not found: {subscription_id}")

    payment_id = str(payment.get("id") or "")
    paid_at = _parse_dt(payment.get("captured_at") or payment.get("paid_at") or payment.get("created_at")) or _utcnow()

    effective_tariff = sub.get("pending_tariff_id") or sub.get("tariff_id")
    if effective_tariff not in TARIFFS:
        effective_tariff = _normalize_tariff_id(str(effective_tariff)) or "starter_monthly"

    next_billing = _next_month_anniversary(paid_at)
    payment_method = (payment.get("payment_method") or {}).get("id") or sub.get("payment_method_id")

    cursor.execute(
        """
        UPDATE subscriptions
        SET tariff_id = %s,
            pending_tariff_id = NULL,
            status = 'active',
            period_start = %s,
            next_billing_date = %s,
            payment_method_id = %s,
            last_payment_id = %s,
            retry_count = 0,
            next_retry_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
        """,
        (
            effective_tariff,
            _as_str_dt(paid_at),
            _as_str_dt(next_billing),
            payment_method,
            payment_id,
            subscription_id,
        ),
    )
    updated = _row_to_dict(cursor, cursor.fetchone())

    _set_user_credits(
        cursor,
        user_id=str(updated.get("user_id")),
        subscription_id=subscription_id,
        tariff_id=effective_tariff,
        payment_id=payment_id,
        period_start=paid_at,
        period_end=next_billing,
    )

    _mark_business_subscription(
        cursor,
        updated.get("business_id"),
        tariff_id=effective_tariff,
        status="active",
        next_billing_date=next_billing,
    )

    return {
        "subscription_id": subscription_id,
        "payment_id": payment_id,
        "status": "active",
        "event": source_event,
    }


def _apply_payment_canceled(cursor, *, payment: Dict[str, Any], source_event: str) -> Dict[str, Any]:
    metadata = dict(payment.get("metadata") or {})
    subscription_id = str(metadata.get("subscription_id") or "").strip()
    if not subscription_id:
        return {"status": "ignored", "reason": "missing_subscription_id", "event": source_event}

    cursor.execute("SELECT * FROM subscriptions WHERE id = %s", (subscription_id,))
    sub = _row_to_dict(cursor, cursor.fetchone())
    if not sub:
        return {"status": "ignored", "reason": "subscription_not_found", "event": source_event}

    retry_count = int(sub.get("retry_count") or 0)
    next_retry_at = None
    if retry_count < len(RETRY_DELAYS_DAYS):
        next_retry_at = _utcnow() + timedelta(days=RETRY_DELAYS_DAYS[retry_count])

    new_retry_count = retry_count + 1
    cursor.execute(
        """
        UPDATE subscriptions
        SET status = 'blocked',
            retry_count = %s,
            next_retry_at = %s,
            last_payment_id = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
        """,
        (new_retry_count, _as_str_dt(next_retry_at), str(payment.get("id") or ""), subscription_id),
    )
    updated = _row_to_dict(cursor, cursor.fetchone())

    _mark_business_subscription(
        cursor,
        updated.get("business_id"),
        tariff_id=str(updated.get("tariff_id") or "starter_monthly"),
        status="blocked",
        next_billing_date=_parse_dt(updated.get("next_billing_date")),
    )

    return {
        "subscription_id": subscription_id,
        "status": "blocked",
        "retry_count": new_retry_count,
        "next_retry_at": _as_str_dt(next_retry_at),
        "event": source_event,
    }


def run_due_renewals(batch_size: int = 25) -> Dict[str, Any]:
    client = YooKassaClient()
    if not client.configured():
        return {"success": False, "error": "YooKassa is not configured", "processed": 0}

    now = _utcnow()
    summary = {"success": True, "processed": 0, "scheduled": 0, "errors": 0, "details": []}

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM subscriptions
            WHERE
              (
                status = 'active'
                AND next_billing_date IS NOT NULL
                AND next_billing_date <= %s
              )
              OR (
                status = 'blocked'
                AND retry_count < 3
                AND next_retry_at IS NOT NULL
                AND next_retry_at <= %s
              )
            ORDER BY COALESCE(next_retry_at, next_billing_date) ASC
            LIMIT %s
            """,
            (_as_str_dt(now), _as_str_dt(now), max(1, min(int(batch_size), 200))),
        )
        rows = cursor.fetchall() or []

        for raw in rows:
            sub = _row_to_dict(cursor, raw)
            tariff_id = _normalize_tariff_id(str(sub.get("tariff_id") or ""))
            if not tariff_id or tariff_id not in TARIFFS:
                summary["errors"] += 1
                summary["details"].append({"subscription_id": sub.get("id"), "error": "invalid tariff_id"})
                continue

            if not sub.get("payment_method_id"):
                summary["errors"] += 1
                summary["details"].append({"subscription_id": sub.get("id"), "error": "missing payment_method_id"})
                continue

            attempt_type = "renewal" if sub.get("status") == "active" else "retry"
            attempt_no = int(sub.get("retry_count") or 0)
            date_key = now.strftime("%Y-%m-%d")
            if attempt_type == "renewal":
                idem_key = _short_idempotency_key("rn", str(sub["id"]), date_key)
            else:
                idem_key = _short_idempotency_key("rt", str(sub["id"]), str(attempt_no))

            amount = TARIFFS[tariff_id]["amount"]
            currency = TARIFFS[tariff_id]["currency"]
            payload = _build_payment_payload(
                amount=amount,
                currency=currency,
                return_url=(os.getenv("YOOKASSA_RETURN_URL") or "").strip() or ((os.getenv("FRONTEND_BASE_URL") or "http://localhost:8000").rstrip("/") + "/dashboard/profile?yookassa_return=1"),
                description=f"LocalOS {tariff_id} subscription {attempt_type}",
                metadata={
                    "subscription_id": sub.get("id"),
                    "user_id": sub.get("user_id"),
                    "business_id": sub.get("business_id") or "",
                    "tariff_id": tariff_id,
                    "kind": f"subscription_{attempt_type}",
                },
                payment_method_id=str(sub.get("payment_method_id")),
                save_payment_method=False,
                recurring=True,
            )

            try:
                payment = client.create_payment(payload=payload, idempotency_key=idem_key)
                status = str(payment.get("status") or "pending")
                _create_billing_attempt(
                    cursor,
                    subscription_id=str(sub["id"]),
                    attempt_type=attempt_type,
                    attempt_no=attempt_no,
                    status=status,
                    scheduled_at=now,
                    amount=amount,
                    currency=currency,
                    idempotency_key=idem_key,
                    payment_id=str(payment.get("id") or ""),
                    error_message=None,
                    metadata={"source": "run_due_renewals"},
                )
                summary["scheduled"] += 1
                summary["details"].append(
                    {
                        "subscription_id": sub.get("id"),
                        "attempt_type": attempt_type,
                        "payment_id": payment.get("id"),
                        "status": status,
                    }
                )
            except Exception as e:
                _create_billing_attempt(
                    cursor,
                    subscription_id=str(sub["id"]),
                    attempt_type=attempt_type,
                    attempt_no=attempt_no,
                    status="failed",
                    scheduled_at=now,
                    amount=amount,
                    currency=currency,
                    idempotency_key=idem_key,
                    payment_id=None,
                    error_message=str(e),
                    metadata={"source": "run_due_renewals"},
                )
                summary["errors"] += 1
                summary["details"].append({"subscription_id": sub.get("id"), "error": str(e)})
            summary["processed"] += 1

        db.conn.commit()
    except Exception as e:
        db.conn.rollback()
        return {"success": False, "error": str(e), **summary}
    finally:
        db.close()

    return summary


@billing_bp.route("/api/billing/checkout/session/start", methods=["POST", "OPTIONS"])
def billing_checkout_session_start():
    if request.method == "OPTIONS":
        return ("", 204)

    client_payload = request.get_json(silent=True) or {}
    user_data = _require_auth()
    raw_provider = str(client_payload.get("provider") or client_payload.get("payment_provider") or "yookassa").strip()
    raw_entry_point = str(client_payload.get("entry_point") or "pricing_page").strip()
    raw_tariff = str(client_payload.get("tariff_id") or client_payload.get("tier") or "").strip()
    tariff_id = _normalize_tariff_id(raw_tariff)

    if not tariff_id or tariff_id not in TARIFFS:
        return jsonify({"error": f"Неверный тариф: {raw_tariff}"}), 400
    if raw_entry_point not in {"public_audit", "registered_paywall", "pricing_page"}:
        return jsonify({"error": f"Неверная точка входа: {raw_entry_point}"}), 400

    auth_user_id = str((user_data or {}).get("user_id") or (user_data or {}).get("id") or "").strip()
    business_id = str(client_payload.get("business_id") or "").strip()
    email = str(client_payload.get("email") or "").strip() or None
    phone = str(client_payload.get("phone") or "").strip() or None
    maps_url = str(client_payload.get("maps_url") or "").strip() or None
    normalized_maps_url = str(client_payload.get("normalized_maps_url") or maps_url or "").strip() or None
    audit_slug = str(client_payload.get("audit_slug") or "").strip() or None
    audit_public_url = str(client_payload.get("audit_public_url") or "").strip() or None
    competitor_maps_url = str(client_payload.get("competitor_maps_url") or "").strip() or None
    competitor_audit_url = str(client_payload.get("competitor_audit_url") or "").strip() or None
    source = str(client_payload.get("source") or raw_entry_point).strip() or raw_entry_point

    if raw_entry_point == "registered_paywall" and not auth_user_id:
        return jsonify({"error": "Требуется авторизация"}), 401
    if not auth_user_id and not email:
        return jsonify({"error": "Для оплаты без аккаунта нужен email"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        provider = _normalize_checkout_provider(raw_provider)
        checkout_amount, checkout_currency = _resolve_checkout_amount_and_currency(provider, tariff_id)
        resolved_user_id = auth_user_id or None
        resolved_business_id = business_id or None

        if business_id:
            business_row = _load_business_checkout_context(cursor, business_id)
            if not business_row:
                return jsonify({"error": "Бизнес не найден"}), 404
            owner_id = str(business_row.get("owner_id") or "").strip()
            if auth_user_id and owner_id and owner_id != auth_user_id and not (user_data or {}).get("is_superadmin"):
                return jsonify({"error": "Нет доступа к бизнесу"}), 403
            resolved_user_id = owner_id or resolved_user_id
            resolved_business_id = str(business_row.get("id") or "").strip() or resolved_business_id
            maps_url = maps_url or str(business_row.get("yandex_url") or "").strip() or None
            normalized_maps_url = normalized_maps_url or maps_url
            payload_json = {
                "business_name": str(business_row.get("name") or "").strip(),
                "city": str(business_row.get("city") or "").strip(),
                "address": str(business_row.get("address") or "").strip(),
            }
        else:
            payload_json = dict(client_payload.get("payload_json") or {})

        if resolved_user_id and not email:
            cursor.execute("SELECT email FROM users WHERE id = %s LIMIT 1", (resolved_user_id,))
            owner_row = _row_to_dict(cursor, cursor.fetchone())
            email = str(owner_row.get("email") or "").strip() or None

        session = create_checkout_session(
            provider=provider,
            channel="web",
            entry_point=raw_entry_point,
            tariff_id=tariff_id,
            amount=checkout_amount,
            currency=checkout_currency,
            user_id=resolved_user_id,
            business_id=resolved_business_id,
            email=email,
            phone=phone,
            maps_url=maps_url,
            normalized_maps_url=normalized_maps_url,
            audit_slug=audit_slug,
            audit_public_url=audit_public_url,
            competitor_maps_url=competitor_maps_url,
            competitor_audit_url=competitor_audit_url,
            source=source,
            payload_json=payload_json,
        )

        if provider == "yookassa":
            payment = create_yookassa_payment_for_checkout_session(str(session.get("id") or ""))
            response_payload = {
                "success": True,
                "provider": "yookassa",
                "checkout_session_id": session.get("id"),
                "payment_id": payment.get("payment_id"),
                "confirmation_url": payment.get("confirmation_url"),
                "payment_status": payment.get("payment_status"),
            }
        else:
            from stripe_integration import create_stripe_checkout_for_checkout_session

            checkout = create_stripe_checkout_for_checkout_session(str(session.get("id") or ""))
            response_payload = {
                "success": True,
                "provider": "stripe",
                "checkout_session_id": session.get("id"),
                "checkout_id": checkout.get("checkout_id"),
                "url": checkout.get("url"),
                "payment_status": checkout.get("payment_status"),
            }

        db.conn.commit()
        return jsonify(response_payload)
    except Exception as e:
        db.conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@billing_bp.route("/api/billing/checkout/session/status", methods=["GET", "OPTIONS"])
def billing_checkout_session_status():
    if request.method == "OPTIONS":
        return ("", 204)

    session_id = str(request.args.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"error": "session_id обязателен"}), 400

    try:
        status_payload = get_checkout_status(session_id)
        provider = str(status_payload.get("provider") or "").strip()
        current_status = str(status_payload.get("status") or "").strip()
        provider_invoice_id = str((load_checkout_session(session_id) or {}).get("provider_invoice_id") or "").strip()

        if current_status not in {"completed", "failed", "expired"} and provider_invoice_id:
            if provider == "yookassa":
                client = YooKassaClient()
                if client.configured():
                    payment = client.get_payment(provider_invoice_id)
                    payment_status = str(payment.get("status") or "").strip().lower()
                    if payment_status == "succeeded":
                        mark_checkout_paid(
                            session_id,
                            provider_payment_id=str(payment.get("id") or provider_invoice_id),
                            provider_status=payment_status,
                        )
                        status_payload = complete_checkout(session_id)
                    elif payment_status == "canceled":
                        mark_checkout_failed(session_id, provider_status=payment_status, error_message="payment canceled")
                        status_payload = get_checkout_status(session_id)
            elif provider == "stripe":
                from stripe_integration import get_stripe_checkout_session_status

                checkout = get_stripe_checkout_session_status(provider_invoice_id)
                checkout_status = str(checkout.get("status") or "").strip().lower()
                payment_status = str(checkout.get("payment_status") or "").strip().lower()
                if checkout_status == "complete" or payment_status == "paid":
                    mark_checkout_paid(
                        session_id,
                        provider_payment_id=str(checkout.get("payment_intent") or provider_invoice_id),
                        provider_status=payment_status or checkout_status,
                    )
                    status_payload = complete_checkout(session_id)
                elif checkout_status == "expired":
                    mark_checkout_failed(session_id, provider_status=checkout_status, error_message="checkout expired")
                    status_payload = get_checkout_status(session_id)

        return jsonify({"success": True, "checkout": status_payload})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/api/billing/checkout/start", methods=["POST", "OPTIONS"])
def billing_checkout_start():
    if request.method == "OPTIONS":
        return ("", 204)

    user_data = _require_auth()
    if not user_data:
        return jsonify({"error": "Требуется авторизация"}), 401

    client = YooKassaClient()
    if not client.configured():
        return jsonify({"error": "YOOKASSA is not configured"}), 500

    data = request.get_json(silent=True) or {}
    business_id = str(data.get("business_id") or "").strip()
    raw_tariff = str(data.get("tariff_id") or data.get("tier") or "").strip()
    tariff_id = _normalize_tariff_id(raw_tariff)

    if not business_id:
        return jsonify({"error": "business_id обязателен"}), 400
    if not tariff_id or tariff_id not in TARIFFS:
        return jsonify({"error": f"Неверный тариф: {raw_tariff}"}), 400

    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    if not user_id:
        return jsonify({"error": "user_id not found in session"}), 401

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (business_id,))
        biz = _row_to_dict(cursor, cursor.fetchone())
        if not biz:
            return jsonify({"error": "Бизнес не найден"}), 404
        business_owner_id = str(biz.get("owner_id") or "")
        if business_owner_id != user_id and not user_data.get("is_superadmin"):
            return jsonify({"error": "Нет доступа к бизнесу"}), 403

        effective_user_id = business_owner_id or user_id
        cursor.execute(
            "SELECT email FROM users WHERE id = %s LIMIT 1",
            (effective_user_id,),
        )
        owner_row = _row_to_dict(cursor, cursor.fetchone())
        cursor.execute(
            "SELECT yandex_url FROM businesses WHERE id = %s LIMIT 1",
            (business_id,),
        )
        business_row = _row_to_dict(cursor, cursor.fetchone())
        session = create_checkout_session(
            provider="yookassa",
            channel="web",
            entry_point="registered_paywall",
            tariff_id=tariff_id,
            user_id=effective_user_id,
            business_id=business_id,
            email=str(owner_row.get("email") or "").strip() or None,
            maps_url=str(business_row.get("yandex_url") or "").strip() or None,
            normalized_maps_url=str(business_row.get("yandex_url") or "").strip() or None,
            source=str(data.get("source") or "registered_paywall").strip(),
            payload_json={},
        )
        payment = create_yookassa_payment_for_checkout_session(str(session.get("id") or ""))
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "checkout_session_id": session.get("id"),
                "payment_id": payment.get("payment_id"),
                "confirmation_url": payment.get("confirmation_url"),
                "payment_status": payment.get("payment_status"),
            }
        )
    except Exception as e:
        db.conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@billing_bp.route("/api/billing/status", methods=["GET", "OPTIONS"])
def billing_status():
    if request.method == "OPTIONS":
        return ("", 204)

    user_data = _require_auth()
    if not user_data:
        return jsonify({"error": "Требуется авторизация"}), 401

    user_id = str(user_data.get("user_id") or user_data.get("id") or "")
    business_id = str(request.args.get("business_id") or "").strip()
    subscription_id = str(request.args.get("subscription_id") or "").strip()

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        if subscription_id:
            cursor.execute("SELECT * FROM subscriptions WHERE id = %s LIMIT 1", (subscription_id,))
        elif business_id:
            cursor.execute("SELECT * FROM subscriptions WHERE business_id = %s LIMIT 1", (business_id,))
        else:
            cursor.execute(
                "SELECT * FROM subscriptions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            )
        sub = _row_to_dict(cursor, cursor.fetchone())
        if not sub:
            return jsonify({"success": True, "subscription": None})

        sub_user_id = str(sub.get("user_id") or "")
        access_allowed = (sub_user_id == user_id) or bool(user_data.get("is_superadmin"))
        if not access_allowed and sub.get("business_id"):
            cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (str(sub.get("business_id")),))
            biz_row = _row_to_dict(cursor, cursor.fetchone())
            access_allowed = str((biz_row or {}).get("owner_id") or "") == user_id
        if not access_allowed:
            return jsonify({"error": "Нет доступа"}), 403

        # Fallback reconciliation: if webhook is delayed/missed, poll YooKassa
        # for the latest pending attempt and apply terminal state.
        client = YooKassaClient()
        if client.configured() and str(sub.get("status") or "") != "active":
            cursor.execute(
                """
                SELECT id, payment_id, status
                FROM billing_attempts
                WHERE subscription_id = %s
                  AND payment_id IS NOT NULL
                  AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(sub.get("id")),),
            )
            pending_attempt = _row_to_dict(cursor, cursor.fetchone())
            if pending_attempt and pending_attempt.get("payment_id"):
                try:
                    payment = client.get_payment(str(pending_attempt.get("payment_id")))
                    payment_status = str(payment.get("status") or "").lower()
                    if payment_status == "succeeded":
                        _apply_payment_succeeded(cursor, payment=payment, source_event="status_poll")
                        cursor.execute(
                            """
                            UPDATE billing_attempts
                            SET status = 'succeeded',
                                updated_at = CURRENT_TIMESTAMP
                            WHERE payment_id = %s
                            """,
                            (str(pending_attempt.get("payment_id")),),
                        )
                        db.conn.commit()
                    elif payment_status == "canceled":
                        cancel_reason = ((payment.get("cancellation_details") or {}).get("reason") or "").strip() or None
                        _apply_payment_canceled(cursor, payment=payment, source_event="status_poll")
                        cursor.execute(
                            """
                            UPDATE billing_attempts
                            SET status = 'canceled',
                                error_message = COALESCE(%s, error_message),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE payment_id = %s
                            """,
                            (cancel_reason, str(pending_attempt.get("payment_id"))),
                        )
                        db.conn.commit()

                    if payment_status in {"succeeded", "canceled"}:
                        cursor.execute("SELECT * FROM subscriptions WHERE id = %s", (str(sub.get("id")),))
                        sub = _row_to_dict(cursor, cursor.fetchone()) or sub
                except Exception as rec_err:
                    print(f"[billing_status] reconciliation failed: {rec_err}", flush=True)
                    db.conn.rollback()

        cursor.execute("SELECT credits_balance FROM users WHERE id = %s", (str(sub.get("user_id")),))
        user_row = _row_to_dict(cursor, cursor.fetchone())

        cursor.execute(
            """
            SELECT id, attempt_type, attempt_no, status, payment_id, error_message, created_at
            FROM billing_attempts
            WHERE subscription_id = %s
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (str(sub.get("id")),),
        )
        recent_attempts = [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]

        return jsonify(
            {
                "success": True,
                "subscription": _subscription_public_payload(sub),
                "credits_balance": int(user_row.get("credits_balance") or 0),
                "recent_attempts": recent_attempts,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@billing_bp.route("/api/billing/tariff/change", methods=["POST", "OPTIONS"])
def billing_tariff_change():
    if request.method == "OPTIONS":
        return ("", 204)

    user_data = _require_auth()
    if not user_data:
        return jsonify({"error": "Требуется авторизация"}), 401

    data = request.get_json(silent=True) or {}
    business_id = str(data.get("business_id") or "").strip()
    subscription_id = str(data.get("subscription_id") or "").strip()
    raw_tariff = str(data.get("tariff_id") or data.get("tier") or "").strip()
    tariff_id = _normalize_tariff_id(raw_tariff)

    if not tariff_id or tariff_id not in TARIFFS:
        return jsonify({"error": f"Неверный тариф: {raw_tariff}"}), 400

    user_id = str(user_data.get("user_id") or user_data.get("id") or "")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        if subscription_id:
            cursor.execute("SELECT * FROM subscriptions WHERE id = %s LIMIT 1", (subscription_id,))
        elif business_id:
            cursor.execute("SELECT * FROM subscriptions WHERE business_id = %s LIMIT 1", (business_id,))
        else:
            cursor.execute("SELECT * FROM subscriptions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,))

        sub = _row_to_dict(cursor, cursor.fetchone())
        if not sub:
            return jsonify({"error": "Подписка не найдена"}), 404
        if str(sub.get("user_id")) != user_id and not user_data.get("is_superadmin"):
            return jsonify({"error": "Нет доступа"}), 403

        cursor.execute(
            """
            UPDATE subscriptions
            SET pending_tariff_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (tariff_id, sub["id"]),
        )
        updated = _row_to_dict(cursor, cursor.fetchone())
        db.conn.commit()

        return jsonify(
            {
                "success": True,
                "subscription": _subscription_public_payload(updated),
                "message": "Тариф будет применен со следующего биллинга",
            }
        )
    except Exception as e:
        db.conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@billing_bp.route("/api/yookassa/webhook", methods=["POST"])
def yookassa_webhook():
    client = YooKassaClient()
    if not client.configured():
        return jsonify({"error": "YOOKASSA is not configured"}), 500

    payload = request.get_json(silent=True) or {}
    event_name = str(payload.get("event") or "").strip()
    obj = dict(payload.get("object") or {})
    payment_id = str(obj.get("id") or "").strip()

    if not event_name or not payment_id:
        return jsonify({"error": "event/payment id required"}), 400

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        dedupe_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO yookassa_webhook_events (id, event_name, payment_id, payload, processed_at)
            VALUES (%s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT DO NOTHING
            """,
            (dedupe_id, event_name, payment_id, json.dumps(payload, ensure_ascii=False)),
        )
        inserted = cursor.rowcount > 0
        if not inserted:
            db.conn.commit()
            return jsonify({"ok": True, "deduplicated": True}), 200

        api_payment = client.get_payment(payment_id)
        api_status = str(api_payment.get("status") or "")
        metadata = dict(api_payment.get("metadata") or {})
        checkout_session_id = str(metadata.get("checkout_session_id") or "").strip()

        if checkout_session_id and event_name == "payment.succeeded":
            if api_status != "succeeded":
                raise RuntimeError(f"payment status mismatch: webhook={event_name} api={api_status}")
            mark_checkout_paid(
                checkout_session_id,
                provider_payment_id=payment_id,
                provider_status=api_status,
            )
            result = complete_checkout(checkout_session_id)
        elif checkout_session_id and event_name == "payment.canceled":
            if api_status != "canceled":
                raise RuntimeError(f"payment status mismatch: webhook={event_name} api={api_status}")
            result = mark_checkout_failed(
                checkout_session_id,
                provider_status=api_status,
                error_message=str(((api_payment.get("cancellation_details") or {}).get("reason") or "payment canceled")).strip(),
            )
        elif event_name == "payment.succeeded":
            if api_status != "succeeded":
                raise RuntimeError(f"payment status mismatch: webhook={event_name} api={api_status}")
            result = _apply_payment_succeeded(cursor, payment=api_payment, source_event=event_name)
        elif event_name == "payment.canceled":
            if api_status != "canceled":
                raise RuntimeError(f"payment status mismatch: webhook={event_name} api={api_status}")
            result = _apply_payment_canceled(cursor, payment=api_payment, source_event=event_name)
        else:
            result = {"status": "ignored", "event": event_name}

        db.conn.commit()
        return jsonify({"ok": True, "result": result}), 200
    except Exception as e:
        db.conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        db.close()


@billing_bp.route("/api/billing/renewals/run", methods=["POST", "OPTIONS"])
def billing_renewals_run():
    if request.method == "OPTIONS":
        return ("", 204)

    user_data = _require_auth()
    if not user_data:
        return jsonify({"error": "Требуется авторизация"}), 401
    if not user_data.get("is_superadmin"):
        return jsonify({"error": "Доступ запрещён"}), 403

    data = request.get_json(silent=True) or {}
    batch_size = int(data.get("batch_size") or 25)
    result = run_due_renewals(batch_size=batch_size)
    code = 200 if result.get("success") else 500
    return jsonify(result), code
