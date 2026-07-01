"""Sales-room audit-offer helpers."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from typing import Any
from urllib.parse import quote

from flask import request
from psycopg2.extras import Json

from auth_system import create_user, normalize_email
from core.email_delivery import send_email
from pg_db_utils import get_db_connection
from services.sales_room_helpers import make_sales_room_url
from services.sales_room_review_service import _to_json_compatible

AUDIT_OFFER_DEFAULT_TITLE = "Проверьте, как ваша компания выглядит на Яндекс Картах"
AUDIT_OFFER_DEFAULT_TEXT = (
    "LocalOS может создать короткий аудит вашей карточки: фото, отзывы, описание, "
    "услуги и видимость рядом с конкурентами."
)
AUDIT_OFFER_DEFAULT_BUTTON = "Создать аудит карточки"
AUDIT_OFFER_VISIBLE_STATUSES = {"prepared", "offered", "requested", "processing", "ready", "opened"}
AUDIT_OFFER_REQUESTABLE_STATUSES = {"prepared", "offered"}
AUDIT_OFFER_TERMINAL_STATUSES = {"ready", "opened"}
AUDIT_OFFER_PLATFORMS = {"yandex", "google", "2gis"}


def audit_offer_processing_delay_seconds() -> int:
    raw_value = os.environ.get("AUDIT_OFFER_PROCESSING_DELAY_SECONDS", "120")
    try:
        return max(0, int(raw_value))
    except (TypeError, ValueError):
        return 120


def sales_room_participant_token_secret() -> str:
    return str(os.environ.get("EXTERNAL_AUTH_SECRET_KEY") or os.environ.get("AUDIT_OFFER_TOKEN_SECRET") or "localos-dev-sales-room-token").strip()


def build_sales_room_participant_access_token(participant_id: str) -> str:
    nonce = secrets.token_urlsafe(18)
    payload = f"{participant_id}.{nonce}"
    signature = hmac.new(
        sales_room_participant_token_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def serialize_sales_room_participant(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {"verified": False}
    return _to_json_compatible(
        {
            "id": row.get("id"),
            "email": row.get("email"),
            "name": row.get("name") or "",
            "company": row.get("company") or "",
            "verified": bool(row.get("is_verified")),
            "verified_at": row.get("verified_at"),
        }
    )


def participant_token_from_request() -> str:
    header_token = str(request.headers.get("X-Sales-Room-Participant-Token") or "").strip()
    if header_token:
        return header_token
    query_token = str(request.args.get("participant_token") or "").strip()
    if query_token:
        return query_token
    data = request.get_json(silent=True) or {}
    return str(data.get("participant_token") or "").strip()


def load_sales_room_participant_by_token(cur, room_id: str, token: str) -> dict[str, Any]:
    clean_token = str(token or "").strip()
    if not clean_token:
        return {}
    cur.execute(
        """
        SELECT *
        FROM sales_room_participants
        WHERE room_id = %s
          AND access_token = %s
        LIMIT 1
        """,
        (room_id, clean_token),
    )
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else {}


def public_audit_offer_allowed_for_participant(offer: dict[str, Any], participant: dict[str, Any]) -> bool:
    if not offer or not participant:
        return False
    if not bool(offer.get("enabled")):
        return False
    if not bool(participant.get("is_verified")):
        return False
    if str(offer.get("status") or "").strip().lower() not in AUDIT_OFFER_VISIBLE_STATUSES:
        return False
    lead_email = normalize_email(str(offer.get("lead_email") or ""))
    participant_email = normalize_email(str(participant.get("email") or ""))
    if lead_email and participant_email != lead_email:
        return False
    return True


def serialize_public_audit_offer(
    offer: dict[str, Any],
    participant: dict[str, Any],
    *,
    expose_teaser: bool = False,
) -> dict[str, Any] | None:
    if not public_audit_offer_allowed_for_participant(offer, participant):
        if not expose_teaser:
            return None
        if not offer or not bool(offer.get("enabled")):
            return None
        if str(offer.get("status") or "").strip().lower() not in AUDIT_OFFER_VISIBLE_STATUSES:
            return None
        lead_email = normalize_email(str(offer.get("lead_email") or ""))
        participant_email = normalize_email(str((participant or {}).get("email") or ""))
        if lead_email and participant_email and participant_email != lead_email:
            return None
        status = str(offer.get("status") or "offered").strip().lower()
        return _to_json_compatible(
            {
                "id": offer.get("id"),
                "status": status,
                "platform": offer.get("platform") or "yandex",
                "company_name": offer.get("company_name") or "",
                "company_address": offer.get("company_address") or "",
                "offer_title": offer.get("offer_title") or AUDIT_OFFER_DEFAULT_TITLE,
                "offer_text": offer.get("offer_text") or AUDIT_OFFER_DEFAULT_TEXT,
                "button_text": offer.get("button_text") or AUDIT_OFFER_DEFAULT_BUTTON,
                "requested_at": offer.get("requested_at"),
                "processing_started_at": offer.get("processing_started_at"),
                "ready_at": offer.get("ready_at"),
                "opened_at": offer.get("opened_at"),
                "audit_url": None,
                "prepared_audit_slug": offer.get("prepared_audit_slug") or None,
                "requires_registration": True,
                "requires_verification": not bool((participant or {}).get("is_verified")),
                "processing_delay_seconds": audit_offer_processing_delay_seconds(),
            }
        )
    status = str(offer.get("status") or "offered").strip().lower()
    audit_url = str(offer.get("prepared_audit_url") or "").strip() if status in AUDIT_OFFER_TERMINAL_STATUSES else ""
    return _to_json_compatible(
        {
            "id": offer.get("id"),
            "status": status,
            "platform": offer.get("platform") or "yandex",
            "company_name": offer.get("company_name") or "",
            "company_address": offer.get("company_address") or "",
            "offer_title": offer.get("offer_title") or AUDIT_OFFER_DEFAULT_TITLE,
            "offer_text": offer.get("offer_text") or AUDIT_OFFER_DEFAULT_TEXT,
            "button_text": offer.get("button_text") or AUDIT_OFFER_DEFAULT_BUTTON,
            "requested_at": offer.get("requested_at"),
            "processing_started_at": offer.get("processing_started_at"),
            "ready_at": offer.get("ready_at"),
            "opened_at": offer.get("opened_at"),
            "audit_url": audit_url or None,
            "prepared_audit_slug": offer.get("prepared_audit_slug") or None,
            "requires_registration": False,
            "requires_verification": False,
            "processing_delay_seconds": audit_offer_processing_delay_seconds(),
        }
    )


def record_sales_room_event_by_id(cur, *, room_id: str, event_type: str, metadata: dict[str, Any] | None = None) -> None:
    cur.execute(
        """
        INSERT INTO sales_room_events (id, room_id, event_type, metadata_json, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (str(uuid.uuid4()), room_id, event_type, Json(metadata or {})),
    )


def build_sales_room_verification_link(*, slug: str, participant_token: str, verification_token: str) -> str:
    base_url = make_sales_room_url(slug)
    return f"{base_url}?participant_token={quote(participant_token)}&verify_token={quote(verification_token)}"


def send_sales_room_participant_verification_email(*, email: str, name: str, slug: str, participant_token: str, verification_token: str) -> bool:
    display_name = str(name or "").strip() or "пользователь"
    link = build_sales_room_verification_link(
        slug=slug,
        participant_token=participant_token,
        verification_token=verification_token,
    )
    subject = "Подтвердите email для цифровой комнаты LocalOS"
    body = f"""
Здравствуйте, {display_name}!

Подтвердите email, чтобы получать уведомления и пользоваться доступными действиями в цифровой комнате:
{link}

Если вы не открывали цифровую комнату LocalOS, просто проигнорируйте это письмо.

---
LocalOS
    """
    return send_email(email, subject, body)


def send_sales_room_audit_ready_email(*, email: str, company_name: str, audit_url: str, user_id: str | None = None) -> bool:
    setup_hint = ""
    if user_id:
        setup_hint = "\n\nАккаунт LocalOS уже подготовлен. Если нужно задать пароль, используйте восстановление или ссылку доступа из LocalOS."
    subject = "Аудит вашей карточки готов"
    body = f"""
Мы подготовили аудит карточки вашей компании на Яндекс Картах.

Компания: {company_name}

Внутри — что видно клиентам, чего не хватает и какие быстрые улучшения можно сделать.

Открыть аудит:
{audit_url}{setup_hint}

---
LocalOS
    """
    return send_email(email, subject, body)


def ensure_audit_offer_user(email: str, name: str = "") -> str:
    normalized_email = normalize_email(email)
    if not normalized_email:
        return ""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE LOWER(email) = %s LIMIT 1", (normalized_email,))
        row = cur.fetchone()
        existing_id = row.get("id") if row and hasattr(row, "get") else (row[0] if row else "")
        if existing_id:
            return str(existing_id)
    finally:
        conn.close()
    result = create_user(
        normalized_email,
        None,
        str(name or "").strip() or normalized_email,
        None,
        personal_data_consent=False,
        is_verified=True,
    )
    if result.get("error"):
        return ""
    return str(result.get("id") or "")
