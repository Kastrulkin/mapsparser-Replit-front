from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

import requests
from psycopg2.extras import Json
from werkzeug.security import check_password_hash, generate_password_hash

from core.email_delivery import send_email
from services.creator_offer_distribution_service import activate_pending_offers, update_offer_preferences
from services.creator_promotion_service import add_metric_snapshot


RELATIONSHIP_STAGES = (
    "discovered", "contact_ready", "contacted", "replied", "interested",
    "needs_details", "declined", "paid_only", "invalid_contact", "paused",
)
TERMINAL_REPLY_STAGES = {"replied", "interested", "needs_details", "declined", "paid_only", "paused"}


def creator_portal_feature_state() -> dict[str, bool]:
    def enabled(name: str) -> bool:
        return str(os.getenv(name) or "false").strip().lower() in {"1", "true", "yes", "on"}
    return {
        "relationships": enabled("CREATOR_RELATIONSHIPS_ENABLED"),
        "portal": enabled("CREATOR_PORTAL_ENABLED"),
        "bot": enabled("CREATOR_BOT_ENABLED"),
    }


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_ready(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _base_url() -> str:
    return str(os.getenv("PUBLIC_BASE_URL") or os.getenv("FRONTEND_URL") or "https://localos.pro").rstrip("/")


def _publication_url(value: Any) -> str:
    url = str(value or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("Добавьте полную публичную ссылку на материал")
    return url


def _new_token(cursor: Any, *, profile_id: str, purpose: str, email: str | None,
               created_by: str | None, hours: int) -> str:
    token = secrets.token_urlsafe(32)
    cursor.execute(
        """
        INSERT INTO creator_invites
            (id, creator_profile_id, token_hash, purpose, email, expires_at, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, NULLIF(%s, ''))
        """,
        (str(uuid.uuid4()), profile_id, _hash(token), purpose, email,
         datetime.now(timezone.utc) + timedelta(hours=hours), created_by or ""),
    )
    return token


def ensure_relationship(cursor: Any, profile_id: str) -> None:
    cursor.execute(
        """
        INSERT INTO creator_relationships (creator_profile_id, stage)
        VALUES (%s, 'discovered') ON CONFLICT (creator_profile_id) DO NOTHING
        """,
        (profile_id,),
    )


def set_relationship_stage(cursor: Any, *, profile_id: str, stage: str,
                           reason: str | None = None) -> None:
    if stage not in RELATIONSHIP_STAGES:
        raise ValueError("Недопустимый статус отношений")
    ensure_relationship(cursor, profile_id)
    cursor.execute(
        """
        UPDATE creator_relationships SET stage = %s, status_reason = COALESCE(%s, status_reason),
            last_replied_at = CASE WHEN %s = ANY(%s) THEN NOW() ELSE last_replied_at END,
            last_contacted_at = CASE WHEN %s = 'contacted' THEN NOW() ELSE last_contacted_at END,
            updated_at = NOW()
        WHERE creator_profile_id = %s
        """,
        (stage, reason, stage, list(TERMINAL_REPLY_STAGES), stage, profile_id),
    )


def add_contact_event(cursor: Any, *, profile_id: str, event_type: str, channel: str,
                      body: str | None = None, contact: str | None = None,
                      classification: str | None = None, source: str = "localos",
                      actor_user_id: str | None = None, campaign_id: str | None = None,
                      collaboration_id: str | None = None,
                      provider_message_id: str | None = None,
                      occurred_at: datetime | None = None,
                      metadata: dict[str, Any] | None = None) -> str:
    event_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO creator_contact_events (
            id, creator_profile_id, campaign_id, collaboration_id, event_type, channel,
            contact_value, provider_message_id, occurred_at, classification, body_text,
            source, actor_user_id, metadata_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), %s, %s, %s,
                  NULLIF(%s, ''), %s)
        ON CONFLICT DO NOTHING
        """,
        (event_id, profile_id, campaign_id, collaboration_id, event_type, channel,
         contact, provider_message_id, occurred_at, classification, body, source,
         actor_user_id or "", Json(metadata or {})),
    )
    return event_id


def list_relationships(cursor: Any, *, business_id: str, is_superadmin: bool,
                       stage: str | None = None, stages: list[str] | None = None, limit: int = 100,
                       offset: int = 0) -> dict[str, Any]:
    if stage and stage not in RELATIONSHIP_STAGES:
        raise ValueError("Недопустимый статус")
    requested_stages = [item for item in (stages or []) if item]
    if any(item not in RELATIONSHIP_STAGES for item in requested_stages):
        raise ValueError("Недопустимый статус")
    scope_base = "" if is_superadmin else "AND EXISTS (SELECT 1 FROM creator_campaign_candidates cc JOIN creator_campaigns c ON c.id = cc.campaign_id WHERE cc.creator_profile_id = p.id AND c.business_id = %s)"
    scope = scope_base
    params: list[Any] = [business_id]
    if not is_superadmin:
        params.append(business_id)
    if stage:
        scope += " AND r.stage = %s"
        params.append(stage)
    elif requested_stages:
        scope += " AND r.stage = ANY(%s)"
        params.append(requested_stages)
    params.extend([limit, offset])
    cursor.execute(
        f"""
        SELECT p.id, p.display_name, p.profile_type, p.description, p.primary_city, p.primary_area,
               p.topics_json, p.verification_status, r.stage, r.primary_channel, r.contact_value,
               r.last_contacted_at, r.last_replied_at, r.status_reason, r.paused_until,
               commercial.formats_json, commercial.accepts_barter, commercial.price_min,
               commercial.price_max, commercial.currency, commercial.availability_text,
               taxonomy.home_city, taxonomy.home_district, taxonomy.metro_stations_json,
               taxonomy.content_geographies_json, taxonomy.audience_types_json,
               taxonomy.audience_size_band, taxonomy.content_styles_json,
               taxonomy.classification_status, taxonomy.evidence_json,
               account.status AS account_status,
               COALESCE(pending_offers.count, 0) AS pending_offers_count,
               COALESCE(channels.items, '[]'::jsonb) AS channels,
               evidence.summary_text AS evidence_summary, evidence.source_url AS evidence_url,
               evidence.observed_at AS evidence_observed_at
        FROM creator_profiles p
        JOIN creator_relationships r ON r.creator_profile_id = p.id
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = p.id
        LEFT JOIN creator_profile_taxonomy taxonomy ON taxonomy.creator_profile_id = p.id
        LEFT JOIN creator_accounts account ON account.creator_profile_id = p.id
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::INT AS count
            FROM creator_offer_recipients recipient
            WHERE recipient.creator_profile_id = p.id AND recipient.business_id = %s
              AND recipient.status = 'pending_account'
        ) pending_offers ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(jsonb_build_object(
                'platform', ch.platform, 'url', ch.canonical_url,
                'metrics', ch.public_metrics_json, 'contactability', ch.contactability,
                'verification_status', ch.verification_status
            ) ORDER BY ch.platform) AS items
            FROM creator_channels ch WHERE ch.creator_profile_id = p.id
        ) channels ON TRUE
        LEFT JOIN LATERAL (
            SELECT e.summary_text, e.source_url, e.observed_at
            FROM creator_evidence e WHERE e.creator_profile_id = p.id
            ORDER BY e.observed_at DESC NULLS LAST, e.created_at DESC LIMIT 1
        ) evidence ON TRUE
        WHERE TRUE {scope}
        ORDER BY COALESCE(r.last_replied_at, r.last_contacted_at, r.updated_at) DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )
    items = []
    for raw in cursor.fetchall():
        item = _dict(raw)
        for key in ("topics_json", "formats_json", "metro_stations_json", "content_geographies_json",
                    "audience_types_json", "content_styles_json", "evidence_json", "channels"):
            item[key.removesuffix("_json")] = _json(item.pop(key, None), [])
        if not is_superadmin:
            item.pop("primary_channel", None)
            item.pop("contact_value", None)
        items.append(_ready(item))
    cursor.execute(
        f"""
        SELECT r.stage, COUNT(*) AS count FROM creator_relationships r
        JOIN creator_profiles p ON p.id = r.creator_profile_id
        WHERE TRUE {scope_base}
        GROUP BY r.stage
        """,
        tuple([] if is_superadmin else [business_id]),
    )
    counts = {str(row["stage"]): int(row["count"]) for row in cursor.fetchall()}
    return {"items": items, "counts": counts, "total": sum(counts.values()), "limit": limit, "offset": offset}


def relationship_detail(cursor: Any, *, profile_id: str, business_id: str,
                        is_superadmin: bool) -> dict[str, Any]:
    result = list_relationships(cursor, business_id=business_id, is_superadmin=is_superadmin, limit=50000)
    item = next((row for row in result["items"] if row["id"] == profile_id), None)
    if not item:
        raise LookupError("Автор не найден")
    cursor.execute(
        """
        SELECT id, event_type, channel, contact_value, provider_message_id, occurred_at,
               classification, body_text, source, actor_user_id, metadata_json
        FROM creator_contact_events WHERE creator_profile_id = %s
        ORDER BY occurred_at DESC, created_at DESC LIMIT 200
        """,
        (profile_id,),
    )
    events = []
    for row in cursor.fetchall():
        event = _dict(row)
        event["metadata"] = _json(event.pop("metadata_json", None), {})
        if not is_superadmin:
            event.pop("contact_value", None)
            event.pop("body_text", None)
        events.append(_ready(event))
    item["events"] = events
    return item


def create_invite(cursor: Any, *, profile_id: str, created_by: str) -> dict[str, Any]:
    cursor.execute("SELECT display_name FROM creator_profiles WHERE id = %s", (profile_id,))
    profile = _dict(cursor.fetchone())
    if not profile:
        raise LookupError("Автор не найден")
    cursor.execute(
        "UPDATE creator_invites SET claimed_at = NOW() WHERE creator_profile_id = %s AND purpose = 'claim' AND claimed_at IS NULL",
        (profile_id,),
    )
    token = _new_token(cursor, profile_id=profile_id, purpose="claim", email=None,
                       created_by=created_by, hours=24 * 14)
    bot = str(os.getenv("TELEGRAM_BOT_USERNAME") or "LocalOspro_bot").lstrip("@")
    return {
        "display_name": profile["display_name"],
        "invite_url": f"{_base_url()}/creator/join/{token}",
        "telegram_url": f"https://t.me/{bot}?start=creator_claim_{token}",
        "expires_in_days": 14,
        "sent": False,
    }


def preview_invite(cursor: Any, token: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT i.id, i.creator_profile_id, i.expires_at, i.claimed_at, p.display_name,
               EXISTS(SELECT 1 FROM creator_accounts a WHERE a.creator_profile_id = p.id AND a.status = 'active') AS has_account
        FROM creator_invites i JOIN creator_profiles p ON p.id = i.creator_profile_id
        WHERE i.token_hash = %s AND i.purpose = 'claim'
        """,
        (_hash(token),),
    )
    invite = _dict(cursor.fetchone())
    if not invite or invite.get("claimed_at") or invite.get("expires_at") <= datetime.now(timezone.utc):
        raise LookupError("Приглашение недействительно или истекло")
    bot = str(os.getenv("TELEGRAM_BOT_USERNAME") or "LocalOspro_bot").lstrip("@")
    return _ready({
        "display_name": invite["display_name"], "expires_at": invite["expires_at"],
        "telegram_url": f"https://t.me/{bot}?start=creator_claim_{token}",
        "has_account": invite["has_account"],
    })


def _consume_claim(cursor: Any, token: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT i.id, i.creator_profile_id, i.expires_at, i.claimed_at, p.display_name
        FROM creator_invites i JOIN creator_profiles p ON p.id = i.creator_profile_id
        WHERE i.token_hash = %s AND i.purpose = 'claim' FOR UPDATE
        """,
        (_hash(token),),
    )
    invite = _dict(cursor.fetchone())
    if not invite or invite.get("claimed_at") or invite.get("expires_at") <= datetime.now(timezone.utc):
        raise LookupError("Приглашение уже использовано или истекло")
    return invite


def _session(cursor: Any, account_id: str, hours: int = 24 * 30) -> str:
    token = secrets.token_urlsafe(36)
    cursor.execute(
        "INSERT INTO creator_sessions (id, creator_account_id, token_hash, expires_at) VALUES (%s, %s, %s, %s)",
        (str(uuid.uuid4()), account_id, _hash(token), datetime.now(timezone.utc) + timedelta(hours=hours)),
    )
    return token


def claim_email(cursor: Any, *, invite_token: str, email: str, password: str) -> dict[str, Any]:
    email = str(email or "").strip().lower()
    if "@" not in email:
        raise ValueError("Укажите корректный email")
    if len(password or "") < 10:
        raise ValueError("Пароль должен содержать не менее 10 символов")
    invite = _consume_claim(cursor, invite_token)
    account_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO creator_accounts (id, creator_profile_id, email, password_hash, preferred_auth, status)
        VALUES (%s, %s, %s, %s, 'email', 'invited')
        ON CONFLICT (creator_profile_id) DO UPDATE SET email = EXCLUDED.email,
            password_hash = EXCLUDED.password_hash, preferred_auth = 'email', updated_at = NOW()
        RETURNING id
        """,
        (account_id, invite["creator_profile_id"], email, generate_password_hash(password)),
    )
    account_id = str(_dict(cursor.fetchone())["id"])
    cursor.execute("UPDATE creator_invites SET claimed_at = NOW(), claimed_account_id = %s WHERE id = %s", (account_id, invite["id"]))
    verify_token = _new_token(cursor, profile_id=str(invite["creator_profile_id"]), purpose="email_verify",
                              email=email, created_by=None, hours=24)
    link = f"{_base_url()}/creator/verify-email/{verify_token}"
    sent = send_email(email, "Подтвердите email автора в LocalOS",
                      f"Здравствуйте, {invite['display_name']}!\n\nПодтвердите email: {link}\n\nLocalOS")
    return {"verification_required": True, "email_sent": bool(sent), "email": email}


def verify_email(cursor: Any, token: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT i.id, i.creator_profile_id, a.id AS account_id FROM creator_invites i
        JOIN creator_accounts a ON a.creator_profile_id = i.creator_profile_id
        WHERE i.token_hash = %s AND i.purpose = 'email_verify' AND i.claimed_at IS NULL
          AND i.expires_at > NOW() AND LOWER(a.email) = LOWER(i.email) FOR UPDATE
        """,
        (_hash(token),),
    )
    row = _dict(cursor.fetchone())
    if not row:
        raise LookupError("Ссылка подтверждения недействительна")
    cursor.execute("UPDATE creator_invites SET claimed_at = NOW(), claimed_account_id = %s WHERE id = %s", (row["account_id"], row["id"]))
    cursor.execute("UPDATE creator_accounts SET status = 'active', email_verified_at = NOW(), last_login_at = NOW(), updated_at = NOW() WHERE id = %s", (row["account_id"],))
    activate_pending_offers(
        cursor,
        profile_id=str(row["creator_profile_id"]),
        account_id=str(row["account_id"]),
    )
    return {"token": _session(cursor, str(row["account_id"])), "redirect": "/creator"}


def claim_telegram(cursor: Any, *, invite_token: str, telegram_id: str,
                   telegram_username: str | None) -> dict[str, Any]:
    invite = _consume_claim(cursor, invite_token)
    account_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO creator_accounts (id, creator_profile_id, telegram_id, telegram_username, preferred_auth, status)
        VALUES (%s, %s, %s, %s, 'telegram', 'active')
        ON CONFLICT (creator_profile_id) DO UPDATE SET telegram_id = EXCLUDED.telegram_id,
            telegram_username = EXCLUDED.telegram_username, preferred_auth = 'telegram',
            status = 'active', updated_at = NOW()
        RETURNING id
        """,
        (account_id, invite["creator_profile_id"], telegram_id, telegram_username),
    )
    account_id = str(_dict(cursor.fetchone())["id"])
    cursor.execute("UPDATE creator_invites SET claimed_at = NOW(), claimed_account_id = %s WHERE id = %s", (account_id, invite["id"]))
    activate_pending_offers(cursor, profile_id=str(invite["creator_profile_id"]), account_id=account_id)
    token = _session(cursor, account_id, hours=1)
    return {"display_name": invite["display_name"], "portal_url": f"{_base_url()}/creator/login/telegram?token={token}"}


def telegram_creator_portal_link(cursor: Any, telegram_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT a.id, p.display_name FROM creator_accounts a
        JOIN creator_profiles p ON p.id = a.creator_profile_id
        WHERE a.telegram_id = %s AND a.status = 'active'
        """,
        (telegram_id,),
    )
    account = _dict(cursor.fetchone())
    if not account:
        return None
    token = _session(cursor, str(account["id"]), hours=1)
    return {"display_name": account["display_name"], "portal_url": f"{_base_url()}/creator/login/telegram?token={token}"}


def login_email(cursor: Any, *, email: str, password: str) -> dict[str, Any]:
    cursor.execute("SELECT id, password_hash, status FROM creator_accounts WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
    account = _dict(cursor.fetchone())
    if not account or not account.get("password_hash") or not check_password_hash(account["password_hash"], password):
        raise ValueError("Неверный email или пароль")
    if account.get("status") != "active":
        raise ValueError("Аккаунт не активирован")
    cursor.execute("UPDATE creator_accounts SET last_login_at = NOW(), updated_at = NOW() WHERE id = %s", (account["id"],))
    return {"token": _session(cursor, str(account["id"])), "redirect": "/creator"}


def request_password_reset(cursor: Any, email: str) -> dict[str, Any]:
    cursor.execute("SELECT id, creator_profile_id FROM creator_accounts WHERE LOWER(email) = LOWER(%s) AND status = 'active'", (email.strip(),))
    account = _dict(cursor.fetchone())
    if account:
        token = _new_token(cursor, profile_id=str(account["creator_profile_id"]), purpose="password_reset",
                           email=email.strip().lower(), created_by=None, hours=2)
        send_email(email, "Восстановление пароля LocalOS", f"Задайте новый пароль: {_base_url()}/creator/reset-password/{token}")
    return {"accepted": True}


def reset_password(cursor: Any, *, token: str, password: str) -> dict[str, Any]:
    if len(password or "") < 10:
        raise ValueError("Пароль должен содержать не менее 10 символов")
    cursor.execute(
        """
        SELECT i.id, a.id AS account_id FROM creator_invites i
        JOIN creator_accounts a ON a.creator_profile_id = i.creator_profile_id
        WHERE i.token_hash = %s AND i.purpose = 'password_reset' AND i.claimed_at IS NULL
          AND i.expires_at > NOW() FOR UPDATE
        """,
        (_hash(token),),
    )
    row = _dict(cursor.fetchone())
    if not row:
        raise LookupError("Ссылка недействительна")
    cursor.execute("UPDATE creator_accounts SET password_hash = %s, status = 'active', updated_at = NOW() WHERE id = %s", (generate_password_hash(password), row["account_id"]))
    cursor.execute("UPDATE creator_invites SET claimed_at = NOW(), claimed_account_id = %s WHERE id = %s", (row["account_id"], row["id"]))
    return {"token": _session(cursor, str(row["account_id"])), "redirect": "/creator"}


def authenticate_creator(cursor: Any, token: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT a.id, a.creator_profile_id, a.email, a.telegram_username, a.status,
               a.notification_preferences_json, p.display_name,
               preference.paused_until, preference.paused_indefinitely,
               preference.excluded_categories_json
        FROM creator_sessions s JOIN creator_accounts a ON a.id = s.creator_account_id
        JOIN creator_profiles p ON p.id = a.creator_profile_id
        LEFT JOIN creator_offer_preferences preference ON preference.creator_profile_id = p.id
        WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > NOW()
        """,
        (_hash(token),),
    )
    account = _dict(cursor.fetchone())
    if not account or account.get("status") != "active":
        raise PermissionError("Сессия истекла")
    cursor.execute("UPDATE creator_sessions SET last_seen_at = NOW() WHERE token_hash = %s", (_hash(token),))
    account["notification_preferences"] = _json(account.pop("notification_preferences_json", None), {})
    account["excluded_categories"] = _json(account.pop("excluded_categories_json", None), [])
    return _ready(account)


def _creator_profile(cursor: Any, profile_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT p.id, p.display_name, p.description, p.primary_city, p.primary_area, p.topics_json,
               t.home_city, t.home_district, t.metro_stations_json, t.content_geographies_json,
               t.audience_geography_json, t.audience_types_json, t.audience_size_band,
               t.content_styles_json, c.formats_json, c.accepts_barter, c.price_min, c.price_max,
               c.currency, c.media_kit_url, c.availability_text,
               COALESCE(ch.items, '[]'::jsonb) AS channels
        FROM creator_profiles p
        LEFT JOIN creator_profile_taxonomy t ON t.creator_profile_id = p.id
        LEFT JOIN creator_commercial_profiles c ON c.creator_profile_id = p.id
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(jsonb_build_object('platform', x.platform, 'url', x.canonical_url,
                'metrics', x.public_metrics_json, 'username', x.username) ORDER BY x.platform) AS items
            FROM creator_channels x WHERE x.creator_profile_id = p.id
        ) ch ON TRUE WHERE p.id = %s
        """,
        (profile_id,),
    )
    profile = _dict(cursor.fetchone())
    for key in ("topics_json", "metro_stations_json", "content_geographies_json", "audience_geography_json",
                "audience_types_json", "content_styles_json", "formats_json", "channels"):
        profile[key.removesuffix("_json")] = _json(profile.pop(key, None), [])
    return _ready(profile)


def list_creator_offers(cursor: Any, profile_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT recipient.id, recipient.status, recipient.updated_at,
               recipient.offer_snapshot_json, recipient.collaboration_id,
               campaign.title, campaign.goal, business.name AS business_name,
               business.city, business.address
        FROM creator_offer_recipients recipient
        JOIN creator_campaigns campaign ON campaign.id = recipient.campaign_id
        JOIN businesses business ON business.id = recipient.business_id
        WHERE recipient.creator_profile_id = %s AND recipient.status <> 'pending_account'
          AND campaign.status IN ('active', 'completed')
        ORDER BY recipient.updated_at DESC
        """,
        (profile_id,),
    )
    offers = []
    distributed_collaborations: set[str] = set()
    for row in cursor.fetchall():
        item = _dict(row)
        snapshot = _json(item.pop("offer_snapshot_json", None), {})
        item["offer"] = _json(snapshot.get("offer"), {})
        item["period"] = _json(snapshot.get("period"), {})
        item["offer_kind"] = "distributed"
        if item.get("collaboration_id"):
            distributed_collaborations.add(str(item["collaboration_id"]))
        offers.append(_ready(item))
    cursor.execute(
        """
        SELECT collaboration.id, collaboration.status, collaboration.review_status,
               collaboration.updated_at, collaboration.scheduled_visit_at,
               campaign.title, campaign.goal, campaign.offer_json, campaign.period_json,
               business.name AS business_name, business.city, business.address
        FROM creator_collaborations collaboration
        JOIN creator_campaigns campaign ON campaign.id = collaboration.campaign_id
        JOIN businesses business ON business.id = collaboration.business_id
        WHERE collaboration.creator_profile_id = %s AND collaboration.review_status = 'approved'
        ORDER BY collaboration.updated_at DESC
        """,
        (profile_id,),
    )
    for row in cursor.fetchall():
        item = _dict(row)
        if str(item.get("id")) in distributed_collaborations:
            continue
        item["offer"] = _json(item.pop("offer_json", None), {})
        item["period"] = _json(item.pop("period_json", None), {})
        item["offer_kind"] = "legacy"
        offers.append(_ready(item))
    return sorted(offers, key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def portal_home(cursor: Any, account: dict[str, Any]) -> dict[str, Any]:
    offers = list_creator_offers(cursor, str(account["creator_profile_id"]))
    active = {"interested", "needs_details", "selected", "agreed", "awaiting_content", "published", "measuring"}
    finished = {"completed", "declined", "not_selected", "expired"}
    return {
        "account": account,
        "profile": _creator_profile(cursor, str(account["creator_profile_id"])),
        "offers": {
            "new": [item for item in offers if item["status"] in {"available", "draft", "invited", "replied", "negotiating"}],
            "active": [item for item in offers if item["status"] in active],
            "finished": [item for item in offers if item["status"] in finished],
        },
    }


def _portal_deliverables(cursor: Any, collaboration_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, platform, deliverable_type, due_at, publication_url,
               verification_status, published_at, tracking_json
        FROM creator_deliverables
        WHERE collaboration_id = %s
        ORDER BY created_at
        """,
        (collaboration_id,),
    )
    deliverables = []
    for row in cursor.fetchall():
        item = _dict(row)
        item["tracking"] = _json(item.pop("tracking_json", None), {})
        cursor.execute(
            """
            SELECT id, checkpoint, due_at, status, completed_at
            FROM creator_measurement_checkpoints
            WHERE deliverable_id = %s
            ORDER BY due_at, checkpoint
            """,
            (item["id"],),
        )
        item["measurement_checkpoints"] = [_ready(_dict(checkpoint)) for checkpoint in cursor.fetchall()]
        cursor.execute(
            """
            SELECT metric_date, views, reach, reactions, comments, saves, clicks,
                   promo_uses, inquiries, bookings, source_type, confidence
            FROM creator_placement_metrics
            WHERE deliverable_id = %s
            ORDER BY metric_date DESC, created_at DESC
            """,
            (item["id"],),
        )
        item["metrics"] = [_ready(_dict(metric)) for metric in cursor.fetchall()]
        deliverables.append(_ready(item))
    return deliverables


def offer_detail(cursor: Any, *, profile_id: str, collaboration_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT recipient.*, collaboration.status AS collaboration_status,
               campaign.title, campaign.goal, business.name AS business_name,
               business.city, business.address, business.description AS business_description
        FROM creator_offer_recipients recipient
        JOIN creator_campaigns campaign ON campaign.id = recipient.campaign_id
        JOIN businesses business ON business.id = recipient.business_id
        LEFT JOIN creator_collaborations collaboration ON collaboration.id = recipient.collaboration_id
        WHERE recipient.id = %s AND recipient.creator_profile_id = %s
          AND recipient.status <> 'pending_account'
          AND campaign.status IN ('active', 'completed')
        """,
        (collaboration_id, profile_id),
    )
    distributed = _dict(cursor.fetchone())
    if distributed:
        snapshot = _json(distributed.pop("offer_snapshot_json", None), {})
        distributed["offer"] = _json(snapshot.get("offer"), {})
        distributed["period"] = _json(snapshot.get("period"), {})
        distributed["formats"] = _json(snapshot.get("formats"), [])
        distributed["constraints"] = _json(snapshot.get("constraints"), {})
        distributed["geography"] = _json(snapshot.get("geography"), {})
        distributed["audience"] = _json(snapshot.get("audience"), {})
        distributed["match"] = _json(distributed.pop("match_snapshot_json", None), {})
        distributed["offer_kind"] = "distributed"
        cursor.execute(
            "SELECT id, sender_type, body_text, created_at FROM creator_offer_messages WHERE offer_recipient_id = %s ORDER BY created_at",
            (collaboration_id,),
        )
        distributed["messages"] = [_ready(_dict(row)) for row in cursor.fetchall()]
        distributed["deliverables"] = []
        if distributed.get("collaboration_id"):
            distributed["deliverables"] = _portal_deliverables(cursor, str(distributed["collaboration_id"]))
        return _ready(distributed)
    cursor.execute(
        """
        SELECT collaboration.*, campaign.title, campaign.goal, campaign.formats_json,
               campaign.offer_json, campaign.period_json, campaign.constraints_json,
               business.name AS business_name, business.city, business.address, business.description AS business_description
        FROM creator_collaborations collaboration
        JOIN creator_campaigns campaign ON campaign.id = collaboration.campaign_id
        JOIN businesses business ON business.id = collaboration.business_id
        WHERE collaboration.id = %s AND collaboration.creator_profile_id = %s
          AND collaboration.review_status = 'approved'
        """,
        (collaboration_id, profile_id),
    )
    offer = _dict(cursor.fetchone())
    if not offer:
        raise LookupError("Предложение не найдено или ещё не одобрено")
    offer["offer_kind"] = "legacy"
    for key in ("agreed_terms_json", "formats_json", "offer_json", "period_json", "constraints_json"):
        offer[key.removesuffix("_json")] = _json(offer.pop(key, None), []) if key == "formats_json" else _json(offer.pop(key, None), {})
    cursor.execute("SELECT id, sender_type, body_text, created_at FROM creator_offer_messages WHERE collaboration_id = %s ORDER BY created_at", (collaboration_id,))
    offer["messages"] = [_ready(_dict(row)) for row in cursor.fetchall()]
    offer["deliverables"] = _portal_deliverables(cursor, collaboration_id)
    return _ready(offer)


def submit_creator_publication(
    cursor: Any,
    *,
    account: dict[str, Any],
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    offer = offer_detail(cursor, profile_id=str(account["creator_profile_id"]), collaboration_id=offer_id)
    collaboration_id = str(offer.get("collaboration_id") or (offer.get("id") if offer.get("offer_kind") == "legacy" else ""))
    if not collaboration_id:
        raise ValueError("Сначала LocalOS должен выбрать вас для сотрудничества")
    status = str(offer.get("collaboration_status") or offer.get("status") or "")
    allowed_statuses = {"agreed", "visit_scheduled", "awaiting_content", "published", "measuring"}
    if status not in allowed_statuses:
        raise ValueError("Публикацию можно передать после согласования с LocalOS")
    publication_url = _publication_url(payload.get("publication_url"))
    deliverable_id = str(payload.get("deliverable_id") or "").strip()
    platform = str(payload.get("platform") or "other").strip().lower() or "other"
    deliverable_type = str(payload.get("deliverable_type") or "post").strip() or "post"
    proof = Json({"submitted_by": "creator_portal", "submitted_at": datetime.now(timezone.utc).isoformat()})
    if deliverable_id:
        cursor.execute(
            """
            UPDATE creator_deliverables
            SET publication_url = %s, verification_status = 'submitted',
                platform = COALESCE(NULLIF(%s, ''), platform),
                deliverable_type = COALESCE(NULLIF(%s, ''), deliverable_type),
                proof_json = proof_json || %s::jsonb, published_at = COALESCE(published_at, NOW()),
                updated_at = NOW()
            WHERE id = %s AND collaboration_id = %s
            RETURNING id
            """,
            (publication_url, platform, deliverable_type, proof, deliverable_id, collaboration_id),
        )
        if not cursor.fetchone():
            raise LookupError("Материал не найден")
    else:
        deliverable_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO creator_deliverables (
                id, collaboration_id, platform, deliverable_type, publication_url,
                verification_status, proof_json, usage_rights_json, published_at
            ) VALUES (%s, %s, %s, %s, %s, 'submitted', %s, '{}'::jsonb, NOW())
            """,
            (deliverable_id, collaboration_id, platform, deliverable_type, publication_url, proof),
        )
    cursor.execute(
        """
        UPDATE creator_collaborations
        SET status = 'published', updated_at = NOW()
        WHERE id = %s AND creator_profile_id = %s
        """,
        (collaboration_id, account["creator_profile_id"]),
    )
    return offer_detail(cursor, profile_id=str(account["creator_profile_id"]), collaboration_id=offer_id)


def submit_creator_metrics(
    cursor: Any,
    *,
    account: dict[str, Any],
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    offer = offer_detail(cursor, profile_id=str(account["creator_profile_id"]), collaboration_id=offer_id)
    collaboration_id = str(offer.get("collaboration_id") or (offer.get("id") if offer.get("offer_kind") == "legacy" else ""))
    deliverable_id = str(payload.get("deliverable_id") or "").strip()
    if not collaboration_id or not deliverable_id:
        raise ValueError("Выберите опубликованный материал")
    cursor.execute(
        """
        SELECT collaboration.business_id
        FROM creator_deliverables deliverable
        JOIN creator_collaborations collaboration ON collaboration.id = deliverable.collaboration_id
        WHERE deliverable.id = %s AND deliverable.collaboration_id = %s
          AND collaboration.creator_profile_id = %s
        """,
        (deliverable_id, collaboration_id, account["creator_profile_id"]),
    )
    collaboration = _dict(cursor.fetchone())
    if not collaboration:
        raise LookupError("Материал не найден")
    add_metric_snapshot(
        cursor,
        business_id=str(collaboration["business_id"]),
        deliverable_id=deliverable_id,
        payload={
            **payload,
            "source_type": "creator_reported",
            "confidence": 0.7,
            "confirmed_revenue": None,
            "placement_cost": None,
        },
    )
    cursor.execute(
        """
        UPDATE creator_notification_outbox
        SET status = 'cancelled', updated_at = NOW(), last_error = 'Статистика уже передана'
        WHERE creator_account_id = %s AND event_type = 'measurement_due'
          AND status IN ('pending', 'failed')
          AND payload_json->>'deliverable_id' = %s
          AND (%s = '' OR payload_json->>'checkpoint' = %s)
        """,
        (account["id"], deliverable_id, str(payload.get("checkpoint") or ""), str(payload.get("checkpoint") or "")),
    )
    cursor.execute(
        "UPDATE creator_collaborations SET status = 'measuring', updated_at = NOW() WHERE id = %s",
        (collaboration_id,),
    )
    return offer_detail(cursor, profile_id=str(account["creator_profile_id"]), collaboration_id=offer_id)


def queue_due_measurement_reminders(cursor: Any, *, limit: int = 100) -> int:
    cursor.execute(
        """
        SELECT checkpoint.id AS checkpoint_id, checkpoint.checkpoint, deliverable.id AS deliverable_id,
               collaboration.id AS collaboration_id, recipient.id AS offer_recipient_id,
               account.id AS account_id, account.telegram_id, account.email,
               account.email_verified_at, account.notification_preferences_json
        FROM creator_measurement_checkpoints checkpoint
        JOIN creator_deliverables deliverable ON deliverable.id = checkpoint.deliverable_id
        JOIN creator_collaborations collaboration ON collaboration.id = deliverable.collaboration_id
        JOIN creator_accounts account
          ON account.creator_profile_id = collaboration.creator_profile_id AND account.status = 'active'
        LEFT JOIN creator_offer_recipients recipient ON recipient.collaboration_id = collaboration.id
        WHERE checkpoint.status = 'pending' AND checkpoint.due_at <= NOW()
          AND collaboration.status IN ('published', 'measuring')
        ORDER BY checkpoint.due_at
        LIMIT %s
        """,
        (max(1, min(int(limit), 500)),),
    )
    queued = 0
    for row in cursor.fetchall():
        item = _dict(row)
        preferences = _json(item.get("notification_preferences_json"), {})
        offer_id = str(item.get("offer_recipient_id") or item["collaboration_id"])
        portal_url = f"{_base_url()}/creator/offers/{offer_id}"
        channels = []
        if item.get("telegram_id") and preferences.get("telegram", True):
            channels.append("telegram")
        if item.get("email") and item.get("email_verified_at") and preferences.get("email", True):
            channels.append("email")
        for channel in channels:
            cursor.execute(
                """
                INSERT INTO creator_notification_outbox (
                    id, creator_account_id, collaboration_id, offer_recipient_id,
                    channel, event_type, payload_json, dedupe_key
                ) VALUES (%s, %s, %s, %s, %s, 'measurement_due', %s, %s)
                ON CONFLICT (dedupe_key) DO NOTHING
                """,
                (
                    str(uuid.uuid4()), item["account_id"], item["collaboration_id"],
                    item.get("offer_recipient_id"), channel,
                    Json({"portal_url": portal_url, "deliverable_id": str(item["deliverable_id"]), "checkpoint": item["checkpoint"]}),
                    f"measurement-due:{item['checkpoint_id']}:{channel}",
                ),
            )
            queued += cursor.rowcount
    return queued


def creator_respond(cursor: Any, *, account: dict[str, Any], collaboration_id: str,
                    action: str, message: str | None) -> dict[str, Any]:
    offer = offer_detail(cursor, profile_id=str(account["creator_profile_id"]), collaboration_id=collaboration_id)
    if offer.get("offer_kind") == "distributed":
        statuses = {
            "accept": "interested", "interest": "interested",
            "propose_changes": "needs_details", "needs_details": "needs_details",
            "decline": "declined", "block_category": "declined",
        }
        if action not in statuses:
            raise ValueError("Недопустимое действие")
        if offer.get("status") not in {"available", "needs_details"}:
            raise ValueError("Отклик по этому предложению уже закрыт")
        if action in {"propose_changes", "needs_details"} and not str(message or "").strip():
            raise ValueError("Опишите, что нужно уточнить")
        status = statuses[action]
        text = str(message or "").strip() or ("Хочу участвовать" if status == "interested" else "Предложение не подходит")
        cursor.execute(
            "UPDATE creator_offer_recipients SET status = %s, response_text = %s, responded_at = NOW(), updated_at = NOW() WHERE id = %s AND status IN ('available', 'needs_details') RETURNING id",
            (status, text, collaboration_id),
        )
        if not cursor.fetchone():
            raise ValueError("Отклик по этому предложению уже закрыт")
        cursor.execute(
            "INSERT INTO creator_offer_messages (id, offer_recipient_id, sender_type, sender_id, body_text) VALUES (%s, %s, 'creator', %s, %s)",
            (str(uuid.uuid4()), collaboration_id, account["id"], text),
        )
        cursor.execute(
            "UPDATE creator_notification_outbox SET status = 'cancelled', updated_at = NOW() WHERE offer_recipient_id = %s AND event_type IN ('offer_available', 'offer_reminder') AND status IN ('pending', 'failed')",
            (collaboration_id,),
        )
        if action == "block_category":
            category = str(_json(offer.get("offer"), {}).get("category") or _json(offer.get("offer"), {}).get("service") or "").strip()
            categories = sorted({*_text_list(account.get("excluded_categories")), category} - {""})
            update_offer_preferences(
                cursor,
                profile_id=str(account["creator_profile_id"]),
                payload={
                    "pause_mode": "indefinite" if account.get("paused_indefinitely") else "until" if account.get("paused_until") else "active",
                    "paused_until": account.get("paused_until"),
                    "excluded_categories": categories,
                },
            )
        set_relationship_stage(
            cursor,
            profile_id=str(account["creator_profile_id"]),
            stage="interested" if status == "interested" else "needs_details" if status == "needs_details" else "declined",
            reason=text,
        )
        return offer_detail(cursor, profile_id=str(account["creator_profile_id"]), collaboration_id=collaboration_id)
    statuses = {"accept": "agreed", "decline": "declined", "propose_changes": "negotiating"}
    if action not in statuses:
        raise ValueError("Недопустимое действие")
    if action == "propose_changes" and not str(message or "").strip():
        raise ValueError("Опишите предлагаемые изменения")
    cursor.execute("UPDATE creator_collaborations SET status = %s, updated_at = NOW() WHERE id = %s", (statuses[action], collaboration_id))
    cursor.execute("UPDATE creator_campaign_candidates SET status = %s, updated_at = NOW() WHERE id = %s",
                   ("agreed" if action == "accept" else "declined" if action == "decline" else "negotiating", offer["campaign_candidate_id"]))
    text = str(message or "").strip() or ("Предложение принято" if action == "accept" else "Предложение отклонено")
    cursor.execute("INSERT INTO creator_offer_messages (id, collaboration_id, sender_type, sender_id, body_text) VALUES (%s, %s, 'creator', %s, %s)",
                   (str(uuid.uuid4()), collaboration_id, account["id"], text))
    cursor.execute(
            "UPDATE creator_notification_outbox SET status = 'cancelled', updated_at = NOW() WHERE collaboration_id = %s AND event_type IN ('offer_approved', 'offer_reminder') AND status IN ('pending', 'failed')",
        (collaboration_id,),
    )
    set_relationship_stage(cursor, profile_id=str(account["creator_profile_id"]),
                           stage="interested" if action == "accept" else "declined" if action == "decline" else "needs_details",
                           reason=text)
    return offer_detail(cursor, profile_id=str(account["creator_profile_id"]), collaboration_id=collaboration_id)


def add_offer_message(cursor: Any, *, collaboration_id: str, sender_type: str,
                      sender_id: str, body: str, profile_id: str | None = None,
                      visible_to_business: bool = False) -> dict[str, Any]:
    body = str(body or "").strip()
    if not body:
        raise ValueError("Напишите сообщение")
    offer_kind = "legacy"
    if profile_id:
        offer_kind = str(offer_detail(cursor, profile_id=profile_id, collaboration_id=collaboration_id).get("offer_kind") or "legacy")
    message_id = str(uuid.uuid4())
    if offer_kind == "distributed":
        cursor.execute(
            "INSERT INTO creator_offer_messages (id, offer_recipient_id, sender_type, sender_id, body_text, visible_to_business) VALUES (%s, %s, %s, %s, %s, %s)",
            (message_id, collaboration_id, sender_type, sender_id, body, visible_to_business),
        )
    else:
        cursor.execute(
            "INSERT INTO creator_offer_messages (id, collaboration_id, sender_type, sender_id, body_text, visible_to_business) VALUES (%s, %s, %s, %s, %s, %s)",
            (message_id, collaboration_id, sender_type, sender_id, body, visible_to_business),
        )
    return {"id": message_id, "sender_type": sender_type, "body_text": body}


def update_creator_profile(cursor: Any, *, account: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(account["creator_profile_id"])
    allowed = {"display_name", "description", "primary_city", "primary_area"}
    changes = {key: payload[key] for key in allowed if key in payload}
    if changes:
        cursor.execute(
            """
            UPDATE creator_profiles SET display_name = COALESCE(%s, display_name),
                description = COALESCE(%s, description), primary_city = COALESCE(%s, primary_city),
                primary_area = COALESCE(%s, primary_area), updated_at = NOW() WHERE id = %s
            """,
            (changes.get("display_name"), changes.get("description"), changes.get("primary_city"), changes.get("primary_area"), profile_id),
        )
    topics = _text_list(payload.get("topics")) if "topics" in payload else None
    if topics is not None:
        cursor.execute(
            "UPDATE creator_profiles SET topics_json = %s, updated_at = NOW() WHERE id = %s",
            (Json(topics), profile_id),
        )
    taxonomy_keys = {"home_city", "home_district", "metro_stations", "content_geographies",
                     "audience_geography", "audience_types", "audience_size_band", "content_styles"}
    taxonomy = {key: payload[key] for key in taxonomy_keys if key in payload}
    if taxonomy:
        cursor.execute("SELECT * FROM creator_profile_taxonomy WHERE creator_profile_id = %s", (profile_id,))
        current_taxonomy = _dict(cursor.fetchone())
        cursor.execute(
            """
            INSERT INTO creator_profile_taxonomy (
                creator_profile_id, home_city, home_district, metro_stations_json,
                content_geographies_json, audience_geography_json, audience_types_json,
                audience_size_band, content_styles_json, classification_status,
                classification_version, reviewed_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'reviewed', 'creator-confirmed-v1', NOW(), NOW())
            ON CONFLICT (creator_profile_id) DO UPDATE SET
                home_city = COALESCE(EXCLUDED.home_city, creator_profile_taxonomy.home_city),
                home_district = COALESCE(EXCLUDED.home_district, creator_profile_taxonomy.home_district),
                metro_stations_json = COALESCE(EXCLUDED.metro_stations_json, creator_profile_taxonomy.metro_stations_json),
                content_geographies_json = COALESCE(EXCLUDED.content_geographies_json, creator_profile_taxonomy.content_geographies_json),
                audience_geography_json = COALESCE(EXCLUDED.audience_geography_json, creator_profile_taxonomy.audience_geography_json),
                audience_types_json = COALESCE(EXCLUDED.audience_types_json, creator_profile_taxonomy.audience_types_json),
                audience_size_band = COALESCE(EXCLUDED.audience_size_band, creator_profile_taxonomy.audience_size_band),
                content_styles_json = COALESCE(EXCLUDED.content_styles_json, creator_profile_taxonomy.content_styles_json),
                classification_status = 'reviewed', classification_version = 'creator-confirmed-v1',
                reviewed_at = NOW(), updated_at = NOW()
            """,
            (profile_id,
             taxonomy.get("home_city", current_taxonomy.get("home_city")),
             taxonomy.get("home_district", current_taxonomy.get("home_district")),
             Json(taxonomy.get("metro_stations", _json(current_taxonomy.get("metro_stations_json"), []))),
             Json(taxonomy.get("content_geographies", _json(current_taxonomy.get("content_geographies_json"), []))),
             Json(taxonomy.get("audience_geography", _json(current_taxonomy.get("audience_geography_json"), []))),
             Json(taxonomy.get("audience_types", _json(current_taxonomy.get("audience_types_json"), []))),
             taxonomy.get("audience_size_band", current_taxonomy.get("audience_size_band") or "unknown"),
             Json(taxonomy.get("content_styles", _json(current_taxonomy.get("content_styles_json"), [])))),
        )
    commercial_keys = {"formats", "accepts_barter", "price_min", "price_max", "currency", "media_kit_url", "availability_text"}
    commercial = {key: payload[key] for key in commercial_keys if key in payload}
    if commercial:
        cursor.execute("SELECT * FROM creator_commercial_profiles WHERE creator_profile_id = %s", (profile_id,))
        current_commercial = _dict(cursor.fetchone())
        cursor.execute(
            """
            INSERT INTO creator_commercial_profiles (
                id, creator_profile_id, formats_json, accepts_barter, price_min, price_max,
                currency, media_kit_url, availability_text, confirmation_status, confirmed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, 'RUB'), %s, %s, 'creator_confirmed', NOW())
            ON CONFLICT (creator_profile_id) DO UPDATE SET
                formats_json = COALESCE(EXCLUDED.formats_json, creator_commercial_profiles.formats_json),
                accepts_barter = COALESCE(EXCLUDED.accepts_barter, creator_commercial_profiles.accepts_barter),
                price_min = COALESCE(EXCLUDED.price_min, creator_commercial_profiles.price_min),
                price_max = COALESCE(EXCLUDED.price_max, creator_commercial_profiles.price_max),
                currency = COALESCE(EXCLUDED.currency, creator_commercial_profiles.currency),
                media_kit_url = COALESCE(EXCLUDED.media_kit_url, creator_commercial_profiles.media_kit_url),
                availability_text = COALESCE(EXCLUDED.availability_text, creator_commercial_profiles.availability_text),
                confirmation_status = 'creator_confirmed', confirmed_at = NOW(), updated_at = NOW()
            """,
            (str(uuid.uuid4()), profile_id,
             Json(commercial.get("formats", _json(current_commercial.get("formats_json"), []))),
             commercial.get("accepts_barter", current_commercial.get("accepts_barter")),
             commercial.get("price_min", current_commercial.get("price_min")),
             commercial.get("price_max", current_commercial.get("price_max")),
             commercial.get("currency", current_commercial.get("currency") or "RUB"),
             commercial.get("media_kit_url", current_commercial.get("media_kit_url")),
             commercial.get("availability_text", current_commercial.get("availability_text"))),
        )
    all_changes = {**changes, **taxonomy, **commercial}
    if topics is not None:
        all_changes["topics"] = topics
    if all_changes:
        cursor.execute(
            "INSERT INTO creator_profile_change_events (id, creator_profile_id, actor_type, actor_id, changed_fields_json, source) VALUES (%s, %s, 'creator', %s, %s, 'creator_portal')",
            (str(uuid.uuid4()), profile_id, account["id"], Json(all_changes)),
        )
    return _creator_profile(cursor, profile_id)


def update_notifications(cursor: Any, *, account: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    preferences = {"telegram": bool(payload.get("telegram", True)), "email": bool(payload.get("email", True))}
    cursor.execute("UPDATE creator_accounts SET notification_preferences_json = %s, updated_at = NOW() WHERE id = %s", (Json(preferences), account["id"]))
    return preferences


def review_offer(cursor: Any, *, business_id: str, collaboration_id: str,
                 reviewer_id: str, decision: str) -> dict[str, Any]:
    if decision not in {"approved", "rejected", "needs_review"}:
        raise ValueError("Недопустимое решение")
    cursor.execute(
        """
        UPDATE creator_collaborations SET review_status = %s, reviewed_by = %s,
            reviewed_at = CASE WHEN %s IN ('approved', 'rejected') THEN NOW() ELSE NULL END,
            updated_at = NOW() WHERE id = %s AND business_id = %s RETURNING creator_profile_id
        """,
        (decision, reviewer_id, decision, collaboration_id, business_id),
    )
    row = _dict(cursor.fetchone())
    if not row:
        raise LookupError("Предложение не найдено")
    queued = False
    if decision == "approved":
        cursor.execute("SELECT id, telegram_id, email, notification_preferences_json FROM creator_accounts WHERE creator_profile_id = %s AND status = 'active'", (row["creator_profile_id"],))
        account = _dict(cursor.fetchone())
        if account:
            preferences = _json(account.get("notification_preferences_json"), {})
            channel = None
            if account.get("telegram_id") and preferences.get("telegram", True):
                channel = "telegram"
            elif account.get("email") and preferences.get("email", True):
                channel = "email"
            if not channel:
                return {"review_status": decision, "notification_queued": False}
            cursor.execute(
                """
                INSERT INTO creator_notification_outbox
                    (id, creator_account_id, collaboration_id, channel, event_type, payload_json, dedupe_key)
                VALUES (%s, %s, %s, %s, 'offer_approved', %s, %s) ON CONFLICT (dedupe_key) DO NOTHING
                """,
                (str(uuid.uuid4()), account["id"], collaboration_id, channel,
                 Json({"portal_url": f"{_base_url()}/creator/offers/{collaboration_id}"}),
                 f"offer-approved:{collaboration_id}:{account['id']}"),
            )
            queued = True
    return {"review_status": decision, "notification_queued": queued}


def dispatch_notifications(cursor: Any, *, limit: int = 25) -> dict[str, int]:
    cursor.execute(
        """
        SELECT o.*, a.telegram_id, a.email, a.notification_preferences_json,
               p.display_name, c.status AS collaboration_status,
               recipient.status AS recipient_status,
               preference.paused_until, preference.paused_indefinitely,
               campaign.title, business.name AS business_name
        FROM creator_notification_outbox o
        JOIN creator_accounts a ON a.id = o.creator_account_id
        JOIN creator_profiles p ON p.id = a.creator_profile_id
        LEFT JOIN creator_collaborations c ON c.id = o.collaboration_id
        LEFT JOIN creator_offer_recipients recipient ON recipient.id = o.offer_recipient_id
        LEFT JOIN creator_campaigns campaign ON campaign.id = COALESCE(recipient.campaign_id, c.campaign_id)
        LEFT JOIN businesses business ON business.id = COALESCE(recipient.business_id, c.business_id)
        LEFT JOIN creator_offer_preferences preference ON preference.creator_profile_id = p.id
        WHERE o.status IN ('pending', 'failed') AND o.next_attempt_at <= NOW()
          AND a.status = 'active'
          AND (
              recipient.id IS NULL
              OR recipient.status = 'available'
              OR (o.event_type = 'offer_message' AND recipient.status IN ('interested', 'needs_details', 'selected'))
              OR (o.event_type = 'measurement_due' AND recipient.status = 'selected')
          )
        ORDER BY o.created_at FOR UPDATE OF o SKIP LOCKED LIMIT %s
        """,
        (limit,),
    )
    rows = [_dict(row) for row in cursor.fetchall()]
    result = {"processed": 0, "sent": 0, "failed": 0}
    bot_token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    for item in rows:
        result["processed"] += 1
        payload = _json(item.get("payload_json"), {})
        preferences = _json(item.get("notification_preferences_json"), {})
        paused = item.get("event_type") in {"offer_available", "offer_approved", "offer_reminder"} and (bool(item.get("paused_indefinitely")) or bool(
            item.get("paused_until") and item["paused_until"] > datetime.now(timezone.utc)
        ))
        channel_enabled = preferences.get(str(item.get("channel")), True)
        if paused or not channel_enabled:
            cursor.execute(
                "UPDATE creator_notification_outbox SET status = 'cancelled', updated_at = NOW(), last_error = %s WHERE id = %s",
                ("Автор поставил предложения на паузу" if paused else "Канал уведомлений выключен", item["id"]),
            )
            continue
        if item.get("event_type") == "offer_message":
            message = f"Здравствуйте, {item['display_name']}!\n\nLocalOS ответил по предложению «{item.get('title') or 'сотрудничество'}»: {str(payload.get('message') or '')[:300]}"
        elif item.get("event_type") == "measurement_due":
            message = f"Здравствуйте, {item['display_name']}!\n\nПора передать статистику публикации за {payload.get('checkpoint') or 'контрольный период'} по предложению «{item.get('title') or 'сотрудничество'}»."
        else:
            message = f"Здравствуйте, {item['display_name']}!\n\nДля вас есть новое предложение от {item.get('business_name') or 'LocalOS'}: {item.get('title') or 'сотрудничество'}"
        try:
            provider_id = None
            if item["channel"] == "telegram":
                if not bot_token or not item.get("telegram_id"):
                    raise RuntimeError("Telegram не подключён")
                response = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": item["telegram_id"], "text": message,
                          "reply_markup": {"inline_keyboard": [[{"text": "Открыть предложение", "url": payload["portal_url"]}]]}},
                    timeout=12,
                )
                response.raise_for_status()
                provider_id = str(response.json().get("result", {}).get("message_id") or "")
            else:
                subject = "Передайте статистику публикации" if item.get("event_type") == "measurement_due" else "Новое предложение в LocalOS"
                if not item.get("email") or not send_email(item["email"], subject, f"{message}\n\n{payload['portal_url']}"):
                    raise RuntimeError("Email не отправлен")
            cursor.execute("UPDATE creator_notification_outbox SET status = 'sent', attempts = attempts + 1, provider_message_id = %s, sent_at = NOW(), updated_at = NOW(), last_error = NULL WHERE id = %s", (provider_id, item["id"]))
            if item.get("collaboration_id"):
                cursor.execute("UPDATE creator_collaborations SET creator_notified_at = NOW(), status = CASE WHEN status = 'draft' THEN 'invited' ELSE status END, updated_at = NOW() WHERE id = %s", (item["collaboration_id"],))
            result["sent"] += 1
        except Exception as exc:
            attempts = int(item.get("attempts") or 0) + 1
            status = "failed" if attempts < 6 else "cancelled"
            delay = min(5 * (2 ** max(attempts - 1, 0)), 360)
            cursor.execute("UPDATE creator_notification_outbox SET status = %s, attempts = %s, next_attempt_at = NOW() + (%s * INTERVAL '1 minute'), last_error = %s, updated_at = NOW() WHERE id = %s", (status, attempts, delay, str(exc)[:500], item["id"]))
            result["failed"] += 1
    return result
