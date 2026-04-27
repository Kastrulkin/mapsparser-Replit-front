from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from billing_constants import TARIFFS, TARIFF_ALIASES
from database_manager import get_db_connection

CHECKOUT_PROVIDERS = {"telegram_crypto", "yookassa", "stripe"}
CHECKOUT_CHANNELS = {"telegram", "web"}
CHECKOUT_ENTRY_POINTS = {"public_audit", "registered_paywall", "pricing_page", "telegram_guest"}
CHECKOUT_STATUSES = {
    "created",
    "checkout_created",
    "paid",
    "account_linked",
    "business_linked",
    "completed",
    "failed",
    "expired",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_str_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _row_to_dict(cursor, row) -> dict[str, Any]:
    if not row:
        return {}
    if isinstance(row, dict):
        return dict(row)
    cols = [d[0] for d in (cursor.description or [])]
    return dict(zip(cols, row))


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _json_loads(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return dict(parsed)
    return {}


def _normalize_tariff_id(tariff_id: str) -> str | None:
    raw = str(tariff_id or "").strip().lower()
    if not raw:
        return None
    if raw in TARIFFS:
        return raw
    return TARIFF_ALIASES.get(raw)


def _normalize_provider(provider: str) -> str:
    raw = str(provider or "").strip().lower()
    if raw in CHECKOUT_PROVIDERS:
        return raw
    raise RuntimeError(f"Unsupported checkout provider: {provider}")


def _normalize_channel(channel: str) -> str:
    raw = str(channel or "").strip().lower()
    if raw in CHECKOUT_CHANNELS:
        return raw
    raise RuntimeError(f"Unsupported checkout channel: {channel}")


def _normalize_entry_point(entry_point: str) -> str:
    raw = str(entry_point or "").strip().lower()
    if raw in CHECKOUT_ENTRY_POINTS:
        return raw
    raise RuntimeError(f"Unsupported checkout entry_point: {entry_point}")


def _pseudo_email_for_telegram(telegram_id: str) -> str:
    safe = "".join(ch for ch in str(telegram_id or "").strip() if ch.isdigit()) or uuid.uuid4().hex[:12]
    return f"telegram-{safe}@localos.bot"


def _next_month_anniversary(base_dt: datetime) -> datetime:
    safe_base = base_dt.astimezone(timezone.utc) if base_dt.tzinfo else base_dt.replace(tzinfo=timezone.utc)
    next_month = safe_base.month + 1
    next_year = safe_base.year
    if next_month == 13:
        next_month = 1
        next_year += 1
    day = min(safe_base.day, 28)
    return safe_base.replace(year=next_year, month=next_month, day=day)


def _ensure_subscription_row(cursor, *, user_id: str, business_id: str | None, tariff_id: str) -> dict[str, Any]:
    if business_id:
        cursor.execute("SELECT * FROM subscriptions WHERE business_id = %s LIMIT 1", (business_id,))
        existing = _row_to_dict(cursor, cursor.fetchone())
        if existing:
            return existing

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
    existing = _row_to_dict(cursor, cursor.fetchone())
    if existing:
        if business_id and not existing.get("business_id"):
            cursor.execute(
                """
                UPDATE subscriptions
                SET business_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
                """,
                (business_id, existing["id"]),
            )
            return _row_to_dict(cursor, cursor.fetchone())
        return existing

    subscription_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO subscriptions (
            id, user_id, business_id, tariff_id, pending_tariff_id, status,
            retry_count, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, NULL, 'blocked', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING *
        """,
        (subscription_id, user_id, business_id, tariff_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _mark_business_subscription(
    cursor,
    business_id: str | None,
    *,
    tariff_id: str,
    status: str,
    next_billing_date: datetime | None,
) -> None:
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


def _set_user_credits(
    cursor,
    *,
    user_id: str,
    subscription_id: str,
    tariff_id: str,
    external_id: str,
    period_start: datetime,
    period_end: datetime,
) -> None:
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


def _checkout_payload(session: dict[str, Any]) -> dict[str, Any]:
    payload = _json_loads(session.get("payload_json"))
    return payload


def _load_session_for_update(cursor, session_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM checkout_sessions WHERE id = %s LIMIT 1", (session_id,))
    session = _row_to_dict(cursor, cursor.fetchone())
    if not session:
        raise RuntimeError(f"Checkout session not found: {session_id}")
    return session


def create_checkout_session(
    *,
    provider: str,
    channel: str,
    entry_point: str,
    tariff_id: str,
    amount: Decimal | None = None,
    currency: str | None = None,
    user_id: str | None = None,
    business_id: str | None = None,
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
    source: str | None = None,
    payload_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    normalized_channel = _normalize_channel(channel)
    normalized_entry_point = _normalize_entry_point(entry_point)
    normalized_tariff = _normalize_tariff_id(tariff_id or "")
    if not normalized_tariff or normalized_tariff not in TARIFFS:
        raise RuntimeError(f"Unsupported tariff_id: {tariff_id}")
    tariff = TARIFFS[normalized_tariff]
    session_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO checkout_sessions (
                id, provider, channel, entry_point, status, tariff_id, amount, currency,
                user_id, business_id, telegram_id, telegram_username, telegram_name, email, phone,
                maps_url, normalized_maps_url, audit_slug, audit_public_url,
                competitor_maps_url, competitor_audit_url, source, payload_json,
                created_at, updated_at
            )
            VALUES (
                %s, %s, %s, %s, 'created', %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s::jsonb,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING *
            """,
            (
                session_id,
                normalized_provider,
                normalized_channel,
                normalized_entry_point,
                normalized_tariff,
                f"{(amount if amount is not None else tariff['amount']):.2f}",
                str(currency or tariff["currency"]),
                str(user_id or "").strip() or None,
                str(business_id or "").strip() or None,
                str(telegram_id or "").strip() or None,
                str(telegram_username or "").strip() or None,
                str(telegram_name or "").strip() or None,
                str(email or "").strip() or None,
                str(phone or "").strip() or None,
                str(maps_url or "").strip() or None,
                str(normalized_maps_url or maps_url or "").strip() or None,
                str(audit_slug or "").strip() or None,
                str(audit_public_url or "").strip() or None,
                str(competitor_maps_url or "").strip() or None,
                str(competitor_audit_url or "").strip() or None,
                str(source or "").strip() or None,
                json.dumps(payload_json or {}, ensure_ascii=False),
            ),
        )
        row = _row_to_dict(cursor, cursor.fetchone())
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_checkout_session(session_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        return _load_session_for_update(cursor, session_id)
    finally:
        conn.close()


def get_checkout_session_by_provider_invoice(provider: str, provider_invoice_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM checkout_sessions
            WHERE provider = %s AND provider_invoice_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (_normalize_provider(provider), str(provider_invoice_id or "").strip()),
        )
        return _row_to_dict(cursor, cursor.fetchone())
    finally:
        conn.close()


def mark_checkout_created(
    session_id: str,
    *,
    provider_invoice_id: str | None,
    provider_status: str | None,
    payload_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        session = _load_session_for_update(cursor, session_id)
        payload = _checkout_payload(session)
        if payload_patch:
            payload.update(payload_patch)
        cursor.execute(
            """
            UPDATE checkout_sessions
            SET status = 'checkout_created',
                provider_invoice_id = COALESCE(%s, provider_invoice_id),
                provider_status = COALESCE(%s, provider_status),
                payload_json = %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (
                str(provider_invoice_id or "").strip() or None,
                str(provider_status or "").strip() or None,
                json.dumps(payload, ensure_ascii=False),
                session_id,
            ),
        )
        updated = _row_to_dict(cursor, cursor.fetchone())
        conn.commit()
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_checkout_paid(
    session_id: str,
    *,
    provider_payment_id: str | None,
    provider_status: str | None,
) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE checkout_sessions
            SET status = CASE
                    WHEN status = 'completed' THEN status
                    ELSE 'paid'
                END,
                provider_payment_id = COALESCE(%s, provider_payment_id),
                provider_status = COALESCE(%s, provider_status),
                paid_at = COALESCE(paid_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (
                str(provider_payment_id or "").strip() or None,
                str(provider_status or "").strip() or None,
                session_id,
            ),
        )
        row = _row_to_dict(cursor, cursor.fetchone())
        if not row:
            raise RuntimeError(f"Checkout session not found: {session_id}")
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_checkout_failed(session_id: str, *, provider_status: str | None, error_message: str | None = None) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        session = _load_session_for_update(cursor, session_id)
        payload = _checkout_payload(session)
        if error_message:
            payload["last_error"] = str(error_message)
        cursor.execute(
            """
            UPDATE checkout_sessions
            SET status = 'failed',
                provider_status = COALESCE(%s, provider_status),
                payload_json = %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (
                str(provider_status or "").strip() or None,
                json.dumps(payload, ensure_ascii=False),
                session_id,
            ),
        )
        updated = _row_to_dict(cursor, cursor.fetchone())
        conn.commit()
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def find_or_create_user_for_checkout(session: dict[str, Any], cursor) -> dict[str, Any]:
    existing_user_id = str(session.get("user_id") or "").strip()
    if existing_user_id:
        cursor.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (existing_user_id,))
        existing = _row_to_dict(cursor, cursor.fetchone())
        if existing:
            return existing

    telegram_id = str(session.get("telegram_id") or "").strip()
    email = str(session.get("email") or "").strip()
    phone = str(session.get("phone") or "").strip()

    if telegram_id:
        cursor.execute("SELECT * FROM users WHERE telegram_id = %s LIMIT 1", (telegram_id,))
        existing = _row_to_dict(cursor, cursor.fetchone())
        if existing:
            return existing

    if email:
        cursor.execute("SELECT * FROM users WHERE email = %s LIMIT 1", (email,))
        existing = _row_to_dict(cursor, cursor.fetchone())
        if existing:
            if telegram_id and not str(existing.get("telegram_id") or "").strip():
                cursor.execute(
                    """
                    UPDATE users
                    SET telegram_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING *
                    """,
                    (telegram_id, existing["id"]),
                )
                return _row_to_dict(cursor, cursor.fetchone())
            return existing

    if phone:
        cursor.execute("SELECT * FROM users WHERE phone = %s LIMIT 1", (phone,))
        existing = _row_to_dict(cursor, cursor.fetchone())
        if existing:
            if telegram_id and not str(existing.get("telegram_id") or "").strip():
                cursor.execute(
                    """
                    UPDATE users
                    SET telegram_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING *
                    """,
                    (telegram_id, existing["id"]),
                )
                return _row_to_dict(cursor, cursor.fetchone())
            return existing

    user_id = str(uuid.uuid4())
    effective_email = email or _pseudo_email_for_telegram(telegram_id)
    user_name = str(session.get("telegram_name") or "").strip() or "LocalOS customer"
    cursor.execute(
        """
        INSERT INTO users (id, email, password_hash, name, phone, telegram_id, created_at)
        VALUES (%s, %s, NULL, %s, %s, %s, CURRENT_TIMESTAMP)
        RETURNING *
        """,
        (
            user_id,
            effective_email,
            user_name,
            phone or None,
            telegram_id or None,
        ),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _business_name_from_session(session: dict[str, Any]) -> str:
    payload = _checkout_payload(session)
    candidates = [
        payload.get("business_name"),
        payload.get("name"),
        payload.get("company_name"),
    ]
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text
    audit_slug = str(session.get("audit_slug") or "").strip()
    if audit_slug:
        return audit_slug.replace("-", " ").strip().title()
    return "Новый бизнес"


def _insert_business_row(cursor, values_map: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'businesses'
        """
    )
    existing_columns = {
        r[0] if not isinstance(r, dict) else r.get("column_name")
        for r in (cursor.fetchall() or [])
    }
    fields: list[str] = []
    values: list[Any] = []
    for field, value in values_map.items():
        if field in existing_columns:
            fields.append(field)
            values.append(value)
    placeholders = ", ".join(["%s"] * len(fields))
    cursor.execute(
        f"""
        INSERT INTO businesses ({", ".join(fields)})
        VALUES ({placeholders})
        RETURNING *
        """,
        tuple(values),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def find_or_create_business_for_checkout(session: dict[str, Any], user_id: str, cursor) -> dict[str, Any] | None:
    existing_business_id = str(session.get("business_id") or "").strip()
    if existing_business_id:
        cursor.execute("SELECT * FROM businesses WHERE id = %s LIMIT 1", (existing_business_id,))
        existing = _row_to_dict(cursor, cursor.fetchone())
        if existing:
            return existing

    normalized_maps_url = str(session.get("normalized_maps_url") or session.get("maps_url") or "").strip()
    if not normalized_maps_url:
        return None

    cursor.execute(
        """
        SELECT *
        FROM businesses
        WHERE owner_id = %s
          AND (
            COALESCE(yandex_url, '') = %s
            OR COALESCE(website, '') = %s
          )
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
        """,
        (user_id, normalized_maps_url, normalized_maps_url),
    )
    existing = _row_to_dict(cursor, cursor.fetchone())
    if existing:
        return existing

    business_id = str(uuid.uuid4())
    business = _insert_business_row(
        cursor,
        {
            "id": business_id,
            "name": _business_name_from_session(session),
            "description": "Created automatically from checkout session",
            "address": str(_checkout_payload(session).get("address") or "").strip() or None,
            "city": str(_checkout_payload(session).get("city") or "").strip() or None,
            "country": str(_checkout_payload(session).get("country") or "Россия").strip(),
            "owner_id": user_id,
            "yandex_url": normalized_maps_url,
            "website": None,
            "moderation_status": "pending",
            "created_at": _as_str_dt(_utcnow()),
            "updated_at": _as_str_dt(_utcnow()),
        },
    )
    return business


def attach_checkout_context(session: dict[str, Any], user_id: str, business_id: str | None, cursor) -> None:
    if not business_id:
        return
    payload = _checkout_payload(session)
    maps_url = str(session.get("normalized_maps_url") or session.get("maps_url") or "").strip()
    address = str(payload.get("address") or "").strip()
    city = str(payload.get("city") or "").strip()
    set_parts: list[str] = []
    values: list[Any] = []
    if maps_url:
        set_parts.append("yandex_url = COALESCE(NULLIF(yandex_url, ''), %s)")
        values.append(maps_url)
    if address:
        set_parts.append("address = COALESCE(NULLIF(address, ''), %s)")
        values.append(address)
    if city:
        set_parts.append("city = COALESCE(NULLIF(city, ''), %s)")
        values.append(city)
    if not set_parts:
        return
    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    values.append(business_id)
    cursor.execute(f"UPDATE businesses SET {', '.join(set_parts)} WHERE id = %s", tuple(values))


def activate_subscription_from_checkout(
    session: dict[str, Any],
    user_id: str,
    business_id: str | None,
    cursor,
) -> dict[str, Any]:
    tariff_id = _normalize_tariff_id(str(session.get("tariff_id") or ""))
    if not tariff_id or tariff_id not in TARIFFS:
        raise RuntimeError(f"Unsupported tariff_id: {session.get('tariff_id')}")
    provider_payment_id = str(session.get("provider_payment_id") or session.get("provider_invoice_id") or session.get("id") or "")
    subscription = _ensure_subscription_row(cursor, user_id=user_id, business_id=business_id, tariff_id=tariff_id)
    period_start = _parse_dt(session.get("paid_at")) or _utcnow()
    next_billing = _next_month_anniversary(period_start)
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
            _as_str_dt(period_start),
            _as_str_dt(next_billing),
            provider_payment_id or None,
            subscription["id"],
        ),
    )
    updated = _row_to_dict(cursor, cursor.fetchone())
    _set_user_credits(
        cursor,
        user_id=user_id,
        subscription_id=str(updated.get("id")),
        tariff_id=tariff_id,
        external_id=provider_payment_id,
        period_start=period_start,
        period_end=next_billing,
    )
    _mark_business_subscription(
        cursor,
        business_id,
        tariff_id=tariff_id,
        status="active",
        next_billing_date=next_billing,
    )
    return updated


def complete_checkout(session_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        session = _load_session_for_update(cursor, session_id)
        if str(session.get("status") or "").strip() == "completed":
            return build_checkout_status_payload(session, cursor)
        if not session.get("paid_at") and not session.get("provider_payment_id"):
            raise RuntimeError("Checkout session is not marked as paid")

        user = find_or_create_user_for_checkout(session, cursor)
        cursor.execute(
            """
            UPDATE checkout_sessions
            SET user_id = %s,
                status = 'account_linked',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (user["id"], session_id),
        )
        session = _row_to_dict(cursor, cursor.fetchone())

        business = find_or_create_business_for_checkout(session, str(user["id"]), cursor)
        if business:
            cursor.execute(
                """
                UPDATE checkout_sessions
                SET business_id = %s,
                    status = 'business_linked',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
                """,
                (business["id"], session_id),
            )
            session = _row_to_dict(cursor, cursor.fetchone())
            attach_checkout_context(session, str(user["id"]), str(business["id"]), cursor)

        subscription = activate_subscription_from_checkout(
            session,
            str(user["id"]),
            str((business or {}).get("id") or "").strip() or None,
            cursor,
        )

        cursor.execute(
            """
            UPDATE checkout_sessions
            SET status = 'completed',
                completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (session_id,),
        )
        completed = _row_to_dict(cursor, cursor.fetchone())
        conn.commit()
        status_payload = build_checkout_status_payload(completed, cursor)
        status_payload["subscription_id"] = subscription.get("id")
        return status_payload
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_checkout_status_payload(session: dict[str, Any], cursor=None) -> dict[str, Any]:
    needs_close = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        needs_close = True
    try:
        user = {}
        if session.get("user_id"):
            cursor.execute("SELECT id, email, password_hash, telegram_id FROM users WHERE id = %s", (str(session.get("user_id")),))
            user = _row_to_dict(cursor, cursor.fetchone())
        business = {}
        if session.get("business_id"):
            cursor.execute("SELECT id, name, yandex_url FROM businesses WHERE id = %s", (str(session.get("business_id")),))
            business = _row_to_dict(cursor, cursor.fetchone())
        return {
            "session_id": str(session.get("id") or ""),
            "provider": str(session.get("provider") or ""),
            "entry_point": str(session.get("entry_point") or ""),
            "status": str(session.get("status") or ""),
            "tariff_id": str(session.get("tariff_id") or ""),
            "email": str(user.get("email") or session.get("email") or ""),
            "telegram_id": str(user.get("telegram_id") or session.get("telegram_id") or ""),
            "user_id": str(user.get("id") or session.get("user_id") or ""),
            "business_id": str(business.get("id") or session.get("business_id") or ""),
            "business_name": str(business.get("name") or ""),
            "audit_public_url": str(session.get("audit_public_url") or ""),
            "maps_url": str(session.get("normalized_maps_url") or session.get("maps_url") or ""),
            "account_created": bool(user),
            "business_created": bool(business),
            "requires_password_setup": bool(user) and not bool(str(user.get("password_hash") or "").strip()) and bool(str(user.get("email") or "").strip()) and not bool(str(user.get("telegram_id") or "").strip()),
            "paid_at": _as_str_dt(_parse_dt(session.get("paid_at"))),
            "completed_at": _as_str_dt(_parse_dt(session.get("completed_at"))),
            "provider_status": str(session.get("provider_status") or ""),
        }
    finally:
        if needs_close:
            cursor.connection.close()


def get_checkout_status(session_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        session = _load_session_for_update(cursor, session_id)
        return build_checkout_status_payload(session, cursor)
    finally:
        conn.close()
