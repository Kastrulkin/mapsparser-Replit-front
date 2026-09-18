"""Non-secret, immutable approval descriptors for social API publication."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from auth_encryption import decrypt_auth_data
from core.telegram_token_store import decode_telegram_bot_token


SNAPSHOT_SCHEMA = "localos_social_publish_approval_v1"
SENSITIVE_MARKERS = ("token", "secret", "password", "credential", "auth_data")


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bot_numeric_id(token: str) -> str:
    candidate = str(token or "").partition(":")[0].strip()
    return candidate if candidate.isdigit() else ""


def _account_auth_data(account: dict[str, Any]) -> dict[str, Any]:
    encrypted = str(account.get("auth_data_encrypted") or "").strip()
    if not encrypted:
        return {}
    try:
        decoded = decrypt_auth_data(encrypted)
    except Exception:
        return {}
    return _json_dict(decoded)


def _active_account(cursor: Any, business_id: str, sources: tuple[str, ...]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, business_id, source, external_id, auth_data_encrypted
        FROM externalbusinessaccounts
        WHERE business_id=%s
          AND source = ANY(%s)
          AND COALESCE(is_active, TRUE)
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT 1
        """,
        (business_id, list(sources)),
    )
    row = cursor.fetchone()
    if not row:
        return {}
    if hasattr(row, "keys"):
        return dict(row)
    return {
        "id": row[0],
        "business_id": row[1],
        "source": row[2],
        "external_id": row[3],
        "auth_data_encrypted": row[4],
    }


def _media_descriptor(cursor: Any, post: dict[str, Any]) -> list[dict[str, str | int]]:
    from services.social_posts.media_delivery import _strict_selected_media_assets

    platform = str(post.get("platform") or "").strip()
    selected = _strict_selected_media_assets(cursor, post, limit=1 if platform in {"google_business", "facebook", "instagram"} else 10)
    media: list[dict[str, str | int]] = []
    for asset in selected:
        asset_id = str(asset.get("id") or "").strip()
        content_hash = str(asset.get("content_hash") or "").strip()
        storage_path = str(asset.get("storage_path") or "").strip()
        public_url = str(asset.get("public_url") or "").strip()
        asset_version = int(asset.get("asset_version") or 0)
        requires_public_url = platform in {"google_business", "facebook", "instagram"}
        if not asset_id or not content_hash or asset_version < 1 or not (storage_path or public_url) or (requires_public_url and not public_url.startswith(("https://", "http://"))):
            raise ValueError("Выбранное медиа нельзя однозначно подтвердить; выберите файл заново.")
        media.append(
            {
                "asset_id": asset_id,
                "asset_version": asset_version,
                "content_hash": content_hash,
                "storage_path": storage_path,
                "public_url": public_url,
                "mime_type": str(asset.get("mime_type") or "").strip(),
            }
        )
    return media


def _telegram_binding(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    cursor.execute("SELECT telegram_chat_id, telegram_bot_token FROM businesses WHERE id=%s", (post.get("business_id"),))
    row = cursor.fetchone()
    if not row:
        raise ValueError("Бизнес не найден для привязки публикации.")
    if hasattr(row, "keys"):
        chat_id = str(row.get("telegram_chat_id") or "").strip()
        encrypted_token = row.get("telegram_bot_token")
    else:
        chat_id = str(row[0] or "").strip()
        encrypted_token = row[1]
    business_token = decode_telegram_bot_token(encrypted_token)
    token_source = "business_bot" if business_token else "global_owner_bot"
    current_token = business_token or str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    bot_id = _bot_numeric_id(current_token)
    if not chat_id or not current_token or not bot_id:
        raise ValueError("Сначала подключите Telegram-бота и точный chat_id, затем явно подтвердите отправку.")
    return {
        "provider": "telegram",
        "recipient": {"chat_id": chat_id},
        "sender": {"transport_source": token_source, "bot_numeric_id": bot_id},
    }


def _external_binding(cursor: Any, post: dict[str, Any]) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    sources = {
        "vk": ("vk", "vk_group", "vk_business"),
        "google_business": ("google_business",),
        "facebook": ("meta", "facebook", "instagram"),
        "instagram": ("meta", "facebook", "instagram"),
    }.get(platform, ())
    account = _active_account(cursor, str(post.get("business_id") or ""), sources)
    auth_data = _account_auth_data(account)
    account_id = str(account.get("id") or "").strip()
    external_id = str(account.get("external_id") or "").strip()
    if not account_id:
        raise ValueError("Сначала подключите точный аккаунт публикации, затем явно подтвердите отправку.")
    recipient = ""
    if platform == "vk":
        group_id = str(auth_data.get("group_id") or auth_data.get("community_id") or external_id).strip()
        recipient = str(auth_data.get("owner_id") or (f"-{group_id.lstrip('-')}" if group_id else "")).strip()
    elif platform == "google_business":
        recipient = external_id
    elif platform == "facebook":
        recipient = str(auth_data.get("page_id") or external_id).strip()
    elif platform == "instagram":
        recipient = str(auth_data.get("ig_user_id") or auth_data.get("instagram_business_account_id") or "").strip()
    if not recipient:
        raise ValueError("Для канала не задан точный получатель; подключите его и подтвердите отправку заново.")
    return {
        "provider": platform,
        "account": {"id": account_id, "source": str(account.get("source") or "").strip(), "external_id": external_id},
        "recipient": {"id": recipient},
    }


def build_approval_snapshot(cursor: Any, post: dict[str, Any], approval_id: str) -> dict[str, Any]:
    platform = str(post.get("platform") or "").strip()
    publish_mode = str(post.get("publish_mode") or "").strip()
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    if publish_mode != "api":
        raise ValueError("Для ручного канала подтверждение отправки не создаётся.")
    try:
        binding = _telegram_binding(cursor, post) if platform == "telegram" else _external_binding(cursor, post)
    except ValueError:
        binding = {"provider": platform, "state": "connection_unbound"}
    payload = {
        "schema": SNAPSHOT_SCHEMA,
        "approval_id": str(approval_id or "").strip(),
        "business_id": str(post.get("business_id") or "").strip(),
        "platform": platform,
        "publish_mode": publish_mode,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "binding": binding,
        "media": _media_descriptor(cursor, post),
    }
    payload["hash"] = _canonical_hash(payload)
    return payload


def snapshot_is_well_formed(snapshot: Any, post: dict[str, Any]) -> bool:
    if not isinstance(snapshot, dict):
        return False
    if snapshot.get("schema") != SNAPSHOT_SCHEMA or not str(snapshot.get("hash") or ""):
        return False
    if str(snapshot.get("approval_id") or "") != str(post.get("approval_id") or ""):
        return False
    text = str(post.get("platform_text") or post.get("base_text") or "").strip()
    if (
        str(snapshot.get("business_id") or "") != str(post.get("business_id") or "")
        or str(snapshot.get("platform") or "") != str(post.get("platform") or "")
        or str(snapshot.get("publish_mode") or "") != str(post.get("publish_mode") or "")
        or str(snapshot.get("text_sha256") or "") != hashlib.sha256(text.encode("utf-8")).hexdigest()
    ):
        return False
    expected = dict(snapshot)
    supplied_hash = str(expected.pop("hash", "") or "")
    if supplied_hash != _canonical_hash(expected):
        return False
    return not _contains_sensitive_key(snapshot)


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key or "").strip().lower()
            if any(marker in normalized for marker in SENSITIVE_MARKERS):
                return True
            if _contains_sensitive_key(nested):
                return True
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def approval_binding_drift_result(provider_status: str) -> dict[str, Any]:
    return {
        "status": "needs_review",
        "last_error": "Цель или медиа публикации изменились после подтверждения.",
        "metadata_json": {"provider_status": provider_status},
        "publish_outcome": "not_attempted",
    }


def _row_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if not row:
        return {}
    if hasattr(row, "keys"):
        return dict(row)
    columns = [item[0] for item in (cursor.description or [])]
    return dict(zip(columns, row))


def frozen_external_account(
    cursor: Any,
    post: dict[str, Any],
    snapshot: dict[str, Any],
    platform: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    binding = _json_dict(snapshot.get("binding"))
    account_binding = _json_dict(binding.get("account"))
    account_id = str(account_binding.get("id") or "").strip()
    business_id = str(post.get("business_id") or "").strip()
    if str(binding.get("provider") or "").strip() != platform or not account_id or not business_id:
        return {}, {}
    cursor.execute(
        """
        SELECT id, business_id, source, external_id, display_name, auth_data_encrypted, last_error
        FROM externalbusinessaccounts
        WHERE id=%s AND business_id=%s AND COALESCE(is_active, TRUE)
        LIMIT 1
        """,
        (account_id, business_id),
    )
    account = _row_dict(cursor, cursor.fetchone())
    if (
        not account
        or str(account.get("source") or "").strip() != str(account_binding.get("source") or "").strip()
        or str(account.get("external_id") or "").strip() != str(account_binding.get("external_id") or "").strip()
    ):
        return {}, {}
    return account, binding


def vk_publish_binding(account: dict[str, Any], auth_data: dict[str, Any]) -> dict[str, Any]:
    if not account:
        return {"ready": False, "status": "missing_connection"}
    token = str(auth_data.get("access_token") or auth_data.get("token") or "").strip()
    group_id = str(auth_data.get("group_id") or auth_data.get("community_id") or account.get("external_id") or "").strip()
    owner_id = str(auth_data.get("owner_id") or "").strip()
    if not owner_id and group_id:
        owner_id = f"-{group_id.lstrip('-')}"
    if not token:
        return {"ready": False, "status": "missing_keys", "owner_id": owner_id}
    if not owner_id:
        return {"ready": False, "status": "missing_binding", "token": token}
    if auth_scope_is_explicit(auth_data) and not auth_scope_allows(auth_data, {"wall", "wall.post"}):
        return {"ready": False, "status": "missing_permissions", "token": token, "owner_id": owner_id}
    return {"ready": True, "status": "ready", "token": token, "owner_id": owner_id}


def vk_uses_community_token(auth_data: dict[str, Any]) -> bool:
    return str(auth_data.get("auth_mode") or "").strip().lower() in {"community_token", "group_token"} or str(auth_data.get("token_type") or "").strip().lower() in {"community", "group", "group_token"}


def meta_publish_status(account: dict[str, Any], auth_data: dict[str, Any], platform: str) -> str:
    if not account:
        return "missing_connection"
    if not str(auth_data.get("access_token") or auth_data.get("token") or "").strip():
        return "missing_keys"
    if platform == "instagram" and not str(auth_data.get("ig_user_id") or auth_data.get("instagram_business_account_id") or "").strip():
        return "missing_binding"
    if platform == "facebook" and not str(auth_data.get("page_id") or account.get("external_id") or "").strip():
        return "missing_binding"
    required = {"instagram_content_publish"} if platform == "instagram" else {"pages_manage_posts", "pages_read_engagement"}
    return "ready" if not auth_scope_is_explicit(auth_data) or auth_scope_allows(auth_data, required) else "missing_permissions"


def meta_channel_readiness(account: dict[str, Any], auth_data: dict[str, Any], platform: str) -> dict[str, Any]:
    status = meta_publish_status(account, auth_data, platform)
    return {"ready": status == "ready", "status": status}


def auth_scope_is_explicit(auth_data: dict[str, Any]) -> bool:
    return any(key in auth_data and auth_data.get(key) for key in ("scope", "scopes", "permissions", "granted_scopes", "granted_permissions"))


def auth_scope_allows(auth_data: dict[str, Any], accepted: set[str]) -> bool:
    accepted_normalized = {str(item or "").strip().lower() for item in accepted if str(item or "").strip()}
    return bool(_auth_scope_tokens(auth_data).intersection(accepted_normalized))


def _auth_scope_tokens(auth_data: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("scope", "scopes", "permissions", "granted_scopes", "granted_permissions"):
        _collect_scope_tokens(auth_data.get(key), tokens)
    return tokens


def _collect_scope_tokens(value: Any, tokens: set[str]) -> None:
    if isinstance(value, dict):
        for nested_value in value.values():
            _collect_scope_tokens(nested_value, tokens)
    elif isinstance(value, (list, tuple, set)):
        for nested_value in value:
            _collect_scope_tokens(nested_value, tokens)
    elif value is not None:
        for token in str(value).replace(",", " ").replace(";", " ").split():
            if token.strip():
                tokens.add(token.strip().lower())


def current_snapshot_matches(cursor: Any, post: dict[str, Any], snapshot: Any) -> bool:
    if not snapshot_is_well_formed(snapshot, post):
        return False
    try:
        current = build_approval_snapshot(cursor, post, str(post.get("approval_id") or ""))
    except ValueError:
        return False
    return str(current.get("hash") or "") == str(snapshot.get("hash") or "")


def snapshot_is_sendable(snapshot: Any, post: dict[str, Any]) -> bool:
    if not snapshot_is_well_formed(snapshot, post):
        return False
    binding = _json_dict(snapshot.get("binding"))
    platform = str(post.get("platform") or "").strip()
    if str(binding.get("provider") or "").strip() != platform or binding.get("state") == "connection_unbound":
        return False
    recipient = _json_dict(binding.get("recipient"))
    if platform == "telegram":
        sender = _json_dict(binding.get("sender"))
        return bool(str(recipient.get("chat_id") or "").strip() and str(sender.get("bot_numeric_id") or "").strip())
    account = _json_dict(binding.get("account"))
    return bool(str(recipient.get("id") or "").strip() and str(account.get("id") or "").strip())


def queue_snapshot_is_current(cursor: Any, post: dict[str, Any]) -> bool:
    snapshot = _json_dict(_json_dict(post.get("metadata_json")).get("approval_publish_snapshot"))
    return current_snapshot_matches(cursor, post, snapshot)


def invalidate_queued_approval(cursor: Any, post: dict[str, Any]) -> Any:
    snapshot = _json_dict(_json_dict(post.get("metadata_json")).get("approval_publish_snapshot"))
    cursor.execute(
        """
        UPDATE social_posts
        SET status='needs_review', approved_at=NULL, approval_id=NULL,
            metadata_json=(COALESCE(metadata_json, '{}'::jsonb) - 'approval_publish_snapshot' - 'publish_attempt')
                || jsonb_build_object('approval_binding_invalidated', jsonb_build_object('reason', 'approval_snapshot_missing_or_drifted')),
            last_error=%s, updated_at=NOW()
        WHERE id=%s AND status IN ('approved','queued') AND approval_id=%s
          AND COALESCE(metadata_json -> 'approval_publish_snapshot' ->> 'hash', '')=%s
        RETURNING *
        """,
        (
            "Цель или медиа публикации изменились. Проверьте и подтвердите отправку заново.",
            str(post.get("id") or ""),
            str(post.get("approval_id") or ""),
            str(snapshot.get("hash") or ""),
        ),
    )
    return cursor.fetchone()


def run_post_batch(post_ids: list[str], action: Any, normalize_ids: Any, summarize: Any, queue_groups: Any, error_message: Any) -> dict[str, Any]:
    posts: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for post_id in normalize_ids(post_ids):
        try:
            posts.append(action(post_id))
        except Exception:
            failed.append({"id": post_id, "error": error_message()})
    return {"posts": posts, "failed": failed, "summary": summarize(posts), "queue_groups": queue_groups(posts)}
