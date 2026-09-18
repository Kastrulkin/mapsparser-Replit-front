"""Media transport helpers; runtime dependencies are bound by social_post_service."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any

from services.social_posts.recommendations_handoff import _publish_adapter


def _telegram_publish_error_state(status_code: int = 0, description: str = "") -> tuple[str, str]:
    clean_description = str(description or "").strip()
    normalized = clean_description.lower()
    recoverable_connection_markers = (
        "unauthorized",
        "forbidden",
        "chat not found",
        "bot was blocked",
        "not enough rights",
        "have no rights",
        "need administrator",
        "group chat was upgraded",
        "peer_id_invalid",
    )
    if int(status_code or 0) in {400, 401, 403} and any(marker in normalized for marker in recoverable_connection_markers):
        return "needs_manual_publish", "telegram_connection_invalid"
    if int(status_code or 0) in {401, 403}:
        return "needs_manual_publish", "telegram_connection_invalid"
    return "failed", "telegram_api_error"

def _selected_media_assets(cursor: Any, post: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    normalized_limit = max(1, min(int(limit or 10), 10))
    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def append_media(value: Any) -> None:
        if not isinstance(value, dict):
            return
        asset_id = str(value.get("id") or value.get("asset_id") or value.get("photo_asset_id") or "").strip()
        dedupe_key = asset_id or str(value.get("url") or value.get("original_url") or value.get("public_url") or "").strip()
        if not dedupe_key or dedupe_key in seen_ids or len(result) >= normalized_limit:
            return
        seen_ids.add(dedupe_key)
        versions = _json_dict(value.get("versions_json"))
        original = _json_dict(versions.get("original"))
        upload_metadata = _json_dict(_json_dict(value.get("metadata_json")).get("upload"))
        original_url = str(value.get("original_url") or value.get("url") or "").strip()
        public_url = str(value.get("public_url") or original.get("public_url") or "").strip()
        if not public_url and (original_url.startswith("https://") or original_url.startswith("http://")):
            public_url = original_url
        result.append(
            {
                "id": asset_id,
                "asset_version": int(value.get("asset_version") or 0),
                "content_hash": str(value.get("content_hash") or "").strip(),
                "original_url": original_url,
                "public_url": public_url,
                "storage_path": str(value.get("storage_path") or original.get("storage_path") or value.get("storage_key") or "").strip(),
                "mime_type": str(value.get("mime_type") or original.get("mime_type") or "image/jpeg").strip(),
                "original_name": str(value.get("original_name") or upload_metadata.get("original_name") or "").strip(),
            }
        )

    media_json = post.get("media_json")
    if isinstance(media_json, list):
        for item in media_json:
            append_media(item)
    elif isinstance(media_json, dict):
        append_media(media_json)
    if len(result) >= normalized_limit or not hasattr(cursor, "execute"):
        return result[:normalized_limit]

    business_id = str(post.get("business_id") or "").strip()
    post_id = str(post.get("id") or "").strip()
    item_id = str(post.get("content_plan_item_id") or "").strip()
    platform = str(post.get("platform") or "").strip()
    target_ids = [value for value in (post_id, item_id) if value]
    if not business_id or not target_ids:
        return result[:normalized_limit]
    try:
        cursor.execute(
            """
            SELECT pa.id, pa.asset_version, pa.content_hash, pa.original_url, pa.storage_key, pa.versions_json, pa.metadata_json,
                   usage.target_platform, usage.created_at
            FROM photo_asset_usage_events usage
            JOIN photo_assets pa
              ON pa.id = usage.photo_asset_id
             AND pa.business_id = usage.business_id
            WHERE usage.business_id = %s
              AND usage.usage_type = 'publication'
              AND usage.target_id = ANY(%s)
              AND (usage.target_platform IS NULL OR usage.target_platform = '' OR usage.target_platform = %s)
            ORDER BY usage.created_at DESC
            LIMIT %s
            """,
            (business_id, target_ids, platform, normalized_limit * 3),
        )
        for row in cursor.fetchall() or []:
            append_media(_row_to_dict(cursor, row))
    except Exception:
        return result[:normalized_limit]
    return result[:normalized_limit]


def _strict_selected_media_assets(cursor: Any, post: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    """Resolve publication media only from the authoritative selected-asset rows."""
    business_id = str(post.get("business_id") or "").strip()
    post_id = str(post.get("id") or "").strip()
    item_id = str(post.get("content_plan_item_id") or "").strip()
    platform = str(post.get("platform") or "").strip()
    normalized_limit = max(1, min(int(limit or 10), 10))
    if not business_id or not post_id or not platform or not hasattr(cursor, "execute"):
        raise ValueError("Выбранное медиа нельзя однозначно подтвердить; выберите файл заново.")
    inline_media = post.get("media_json")
    inline_items = inline_media if isinstance(inline_media, list) else [inline_media] if isinstance(inline_media, dict) else []
    inline_ids = [
        str(item.get("id") or item.get("asset_id") or item.get("photo_asset_id") or "").strip()
        for item in inline_items
        if isinstance(item, dict)
    ]
    if inline_items and (not inline_ids or len(inline_ids) != len(inline_items) or len(set(inline_ids)) != len(inline_ids)):
        raise ValueError("Выбранное медиа не содержит подтверждаемого ID; выберите файл заново.")
    if len(inline_ids) > normalized_limit:
        raise ValueError("Для публикации выбрано слишком много медиафайлов; выберите не более 10.")
    if inline_ids:
        cursor.execute(
            """
            SELECT id, asset_version, content_hash, original_url, storage_key, versions_json, metadata_json
            FROM photo_assets
            WHERE business_id=%s AND id = ANY(%s)
            """,
            (business_id, inline_ids),
        )
        by_id = {str(_row_to_dict(cursor, row).get("id") or ""): _row_to_dict(cursor, row) for row in cursor.fetchall() or []}
        rows = [by_id[asset_id] for asset_id in inline_ids if asset_id in by_id]
        if len(rows) != len(inline_ids):
            raise ValueError("Выбранное медиа больше недоступно; выберите файл заново.")
    else:
        cursor.execute(
        """
        SELECT pa.id, pa.asset_version, pa.content_hash, pa.original_url,
               pa.storage_key, pa.versions_json, pa.metadata_json,
               usage.created_at
        FROM photo_asset_usage_events usage
        JOIN photo_assets pa
          ON pa.id = usage.photo_asset_id
         AND pa.business_id = usage.business_id
        WHERE usage.business_id = %s
          AND usage.usage_type = 'publication'
          AND usage.target_id = ANY(%s)
          AND (usage.target_platform IS NULL OR usage.target_platform = '' OR usage.target_platform = %s)
        ORDER BY usage.created_at ASC, usage.id ASC
        LIMIT 101
        """,
            (business_id, [value for value in (post_id, item_id) if value], platform),
        )
        rows = cursor.fetchall() or []
        if len(rows) > 100:
            raise ValueError("Выбор медиа неоднозначен; выберите файлы заново.")
    unique_rows: list[Any] = []
    seen_asset_ids: set[str] = set()
    for row in rows:
        asset_id = str(_row_to_dict(cursor, row).get("id") or "").strip()
        if asset_id and asset_id not in seen_asset_ids:
            seen_asset_ids.add(asset_id)
            unique_rows.append(row)
    rows = unique_rows
    if len(rows) > normalized_limit:
        raise ValueError("Для публикации выбрано слишком много медиафайлов; выберите не более 10.")
    resolved: list[dict[str, Any]] = []
    for row in rows:
        item = _row_to_dict(cursor, row)
        versions = _json_dict(item.get("versions_json"))
        original = _json_dict(versions.get("original"))
        original_url = str(item.get("original_url") or "").strip()
        public_url = str(item.get("public_url") or original.get("public_url") or original_url).strip()
        storage_path = str(item.get("storage_key") or original.get("storage_path") or "").strip()
        content_hash = str(item.get("content_hash") or "").strip()
        asset_id = str(item.get("id") or "").strip()
        asset_version = int(item.get("asset_version") or 0)
        if not asset_id or asset_version < 1 or not content_hash or not (storage_path or public_url):
            raise ValueError("Выбранное медиа нельзя однозначно подтвердить; выберите файл заново.")
        resolved.append(
            {
                "id": asset_id,
                "asset_version": asset_version,
                "content_hash": content_hash,
                "storage_path": storage_path,
                "public_url": public_url,
                "original_url": original_url,
                "mime_type": str(item.get("mime_type") or original.get("mime_type") or "image/jpeg").strip(),
            }
        )
    return resolved


def _approved_media_assets(cursor: Any, post: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Load exactly the approved media identities; never follow a newer selection."""
    approved = snapshot.get("media")
    if not isinstance(approved, list):
        return None
    if not approved:
        return []
    business_id = str(post.get("business_id") or "").strip()
    if not business_id or len(approved) > 10:
        return None
    asset_ids = [str(item.get("asset_id") or "").strip() for item in approved if isinstance(item, dict)]
    if len(asset_ids) != len(approved) or len(set(asset_ids)) != len(asset_ids):
        return None
    cursor.execute(
        """
        SELECT id, asset_version, content_hash, original_url, storage_key, versions_json
        FROM photo_assets
        WHERE business_id=%s AND id = ANY(%s)
        """,
        (business_id, asset_ids),
    )
    available = {str(_row_to_dict(cursor, row).get("id") or ""): _row_to_dict(cursor, row) for row in cursor.fetchall() or []}
    resolved: list[dict[str, Any]] = []
    for approved_item in approved:
        if not isinstance(approved_item, dict):
            return None
        asset_id = str(approved_item.get("asset_id") or "").strip()
        item = available.get(asset_id)
        if not item:
            return None
        versions = _json_dict(item.get("versions_json"))
        original = _json_dict(versions.get("original"))
        current = {
            "asset_version": int(item.get("asset_version") or 0),
            "content_hash": str(item.get("content_hash") or "").strip(),
            "storage_path": str(item.get("storage_key") or original.get("storage_path") or "").strip(),
            "public_url": str(item.get("public_url") or original.get("public_url") or item.get("original_url") or "").strip(),
            "mime_type": str(item.get("mime_type") or original.get("mime_type") or "image/jpeg").strip(),
        }
        if any(str(current[key]) != str(approved_item.get(key) or "") for key in ("asset_version", "content_hash", "storage_path", "public_url", "mime_type")):
            return None
        current["id"] = asset_id
        resolved.append(current)
    return resolved


def _media_asset_file(asset: dict[str, Any]) -> dict[str, Any]:
    storage_path = str(asset.get("storage_path") or "").strip()
    content = load_media_file(storage_path) if storage_path else None
    public_url = str(asset.get("public_url") or "").strip()
    if content is None and (public_url.startswith("https://") or public_url.startswith("http://")):
        try:
            response = outbound_urlopen(public_url, timeout=20)
            try:
                content = response.read()
            finally:
                response.close()
        except Exception:
            content = None
    if not content:
        return {}
    mime_type = str(asset.get("mime_type") or "image/jpeg").strip().lower()
    extensions = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    extension = extensions.get(mime_type, "jpg")
    filename = str(asset.get("original_name") or "").strip() or f"{str(asset.get('id') or 'photo').strip()}.{extension}"
    return {"content": content, "mime_type": mime_type, "filename": filename}

def _multipart_form_data(
    fields: dict[str, Any],
    files: list[dict[str, Any]],
) -> tuple[bytes, str]:
    boundary = f"----LocalOS{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    for file_data in files:
        field_name = str(file_data.get("field_name") or "file").strip()
        filename = str(file_data.get("filename") or "photo.jpg").replace('"', "")
        mime_type = str(file_data.get("mime_type") or "application/octet-stream").strip()
        content = file_data.get("content")
        if not isinstance(content, bytes):
            continue
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"

def _telegram_api_call(
    bot_token: str,
    method: str,
    payload: dict[str, Any],
    files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    request_files = files if isinstance(files, list) else []
    if request_files:
        request_data, content_type = _multipart_form_data(payload, request_files)
    else:
        request_data = json.dumps(payload).encode("utf-8")
        content_type = "application/json"
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/{method}",
        data=request_data,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        response = telegram_urlopen(request, timeout=20)
        try:
            body = response.read().decode("utf-8", errors="ignore")
            parsed, parsed_ok = _provider_json_object(body)
            status_code = int(getattr(response, "status", 500) or 500)
        finally:
            response.close()
    except urllib.error.HTTPError:
        error = sys.exc_info()[1]
        body = ""
        try:
            body = error.read().decode("utf-8", errors="ignore")
        except Exception:
            body = str(error)
        status_code = int(getattr(error, "code", 0) or 0)
        description = str(_json_dict(body).get("description") or body or str(error))[:1000]
        status, provider_status = _telegram_publish_error_state(status_code, description)
        return {
            "ok": False,
            "status": status,
            "provider_status": provider_status,
            "error": description,
            "status_code": status_code,
            "publish_outcome": _http_publish_outcome(status_code),
        }
    except (urllib.error.URLError, TimeoutError):
        return {"ok": False, "status": "failed", "provider_status": "telegram_network_error", "error": str(sys.exc_info()[1]), "publish_outcome": "uncertain"}
    except Exception:
        return {"ok": False, "status": "failed", "provider_status": "telegram_unexpected_error", "error": str(sys.exc_info()[1]), "publish_outcome": "uncertain"}
    if not parsed_ok:
        return {
            "ok": False,
            "status": "failed",
            "provider_status": "telegram_response_parse_failed",
            "error": "Telegram вернул непонятный ответ после попытки публикации.",
            "status_code": status_code,
            "publish_outcome": "uncertain",
        }
    if not (200 <= status_code < 300) or not bool(parsed.get("ok")):
        description = str(parsed.get("description") or body or f"Telegram HTTP {status_code}")[:1000]
        status, provider_status = _telegram_publish_error_state(status_code, description)
        return {
            "ok": False,
            "status": status,
            "provider_status": provider_status,
            "error": description,
            "status_code": status_code,
            "publish_outcome": "rejected" if 200 <= status_code < 300 else _http_publish_outcome(status_code),
        }
    return {"ok": True, "result": parsed.get("result"), "response": parsed}


def send_telegram_photo_message(
    *,
    bot_token: str,
    chat_id: str,
    media_asset: dict[str, Any],
    caption: str = "",
) -> dict[str, Any]:
    file_data = _media_asset_file(media_asset)
    if not file_data:
        return {"success": False, "message_id": 0, "reason_code": "media_unavailable"}
    response = _telegram_api_call(
        bot_token,
        "sendPhoto",
        {"chat_id": str(chat_id or "").strip(), "caption": str(caption or "")[:1024]},
        [{**file_data, "field_name": "photo"}],
    )
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    return {
        "success": bool(response.get("ok")),
        "message_id": int(result.get("message_id") or 0),
        "reason_code": str(response.get("provider_status") or response.get("error") or ""),
    }

@_publish_adapter
def _publish_telegram_media_post(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    media_assets: list[dict[str, Any]],
    transport_source: str,
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for index, asset in enumerate(media_assets[:10]):
        file_data = _media_asset_file(asset)
        if not file_data:
            continue
        files.append({**file_data, "field_name": f"photo{index}"})
    if not files:
        return {
            "status": "needs_review",
            "last_error": "Выбранное фото недоступно. Замените его или загрузите заново.",
            "metadata_json": {"provider_status": "telegram_media_unavailable"},
            "publish_outcome": "not_attempted",
        }

    caption = text if len(text) <= 1024 else ""
    if len(files) == 1:
        media_result = _telegram_api_call(
            bot_token,
            "sendPhoto",
            {"chat_id": chat_id, "caption": caption},
            [{**files[0], "field_name": "photo"}],
        )
    else:
        media_payload = []
        for index, file_data in enumerate(files):
            item = {"type": "photo", "media": f"attach://{file_data['field_name']}"}
            if index == 0 and caption:
                item["caption"] = caption
            media_payload.append(item)
        media_result = _telegram_api_call(
            bot_token,
            "sendMediaGroup",
            {"chat_id": chat_id, "media": json.dumps(media_payload, ensure_ascii=False)},
            files,
        )
    if not bool(media_result.get("ok")):
        return {
            "status": str(media_result.get("status") or "failed"),
            "last_error": str(media_result.get("error") or "Telegram не принял фото."),
            "metadata_json": {"provider_status": str(media_result.get("provider_status") or "telegram_media_error")},
            "publish_outcome": str(media_result.get("publish_outcome") or "uncertain"),
        }

    raw_media_result = media_result.get("result")
    messages = raw_media_result if isinstance(raw_media_result, list) else [raw_media_result]
    message_ids = [str(item.get("message_id") or "").strip() for item in messages if isinstance(item, dict) and str(item.get("message_id") or "").strip()]
    delivery_warning = ""
    text_response: dict[str, Any] | None = None
    if not caption:
        text_response = _telegram_api_call(
            bot_token,
            "sendMessage",
            {"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        )
        if bool(text_response.get("ok")) and isinstance(text_response.get("result"), dict):
            text_message_id = str(text_response.get("result", {}).get("message_id") or "").strip()
            if text_message_id:
                message_ids.append(text_message_id)
        else:
            delivery_warning = str(text_response.get("error") or "Фото опубликовано, но полный текст не отправился.")
    first_message_id = message_ids[0] if message_ids else ""
    return {
        "status": "published",
        "provider_post_id": first_message_id,
        "provider_post_url": _telegram_post_url(chat_id, first_message_id),
        "last_error": delivery_warning,
        "publish_outcome": "accepted" if first_message_id.isdigit() and int(first_message_id) > 0 else "uncertain",
        "metadata_json": {
            "provider_status": "telegram_published" if not delivery_warning else "telegram_published_with_warning",
            "telegram_transport": transport_source,
            "provider_write_performed": True,
            "external_publish_performed": True,
            "media_attachment_count": len(files),
            "telegram_message_ids": message_ids,
            "delivery_warning": delivery_warning,
        },
    }

def _vk_api_request(url: str, data: dict[str, Any] | None = None, files: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    request_files = files if isinstance(files, list) else []
    if request_files:
        body, content_type = _multipart_form_data(data or {}, request_files)
    elif data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"
    else:
        body = None
        content_type = ""
    headers = {"Content-Type": content_type} if content_type else {}
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    try:
        response = outbound_urlopen(request, timeout=20)
        try:
            return _json_dict(response.read().decode("utf-8", errors="ignore"))
        finally:
            response.close()
    except Exception:
        return {"error": {"error_msg": str(sys.exc_info()[1])}}

def _upload_vk_wall_photos(
    *,
    token: str,
    owner_id: str,
    api_version: str,
    media_assets: list[dict[str, Any]],
) -> dict[str, Any]:
    group_id = owner_id[1:] if owner_id.startswith("-") else owner_id
    query = urllib.parse.urlencode({"access_token": token, "group_id": group_id, "v": api_version})
    server_payload = _vk_api_request(f"https://api.vk.com/method/photos.getWallUploadServer?{query}")
    upload_url = str(_json_dict(server_payload.get("response")).get("upload_url") or "").strip()
    if not upload_url:
        return {"success": False, "status": "vk_upload_server_failed", "error": str(_json_dict(server_payload.get("error")).get("error_msg") or "VK не вернул адрес загрузки фото.")}
    attachments: list[str] = []
    for asset in media_assets[:10]:
        file_data = _media_asset_file(asset)
        if not file_data:
            return {"success": False, "status": "vk_media_unavailable", "error": "Выбранное фото недоступно. Замените его или загрузите заново."}
        uploaded = _vk_api_request(upload_url, files=[{**file_data, "field_name": "photo"}])
        if uploaded.get("error"):
            return {"success": False, "status": "vk_media_upload_failed", "error": str(_json_dict(uploaded.get("error")).get("error_msg") or "VK не принял фото.")}
        saved = _vk_api_request(
            "https://api.vk.com/method/photos.saveWallPhoto",
            data={
                "access_token": token,
                "group_id": group_id,
                "server": uploaded.get("server"),
                "photo": uploaded.get("photo"),
                "hash": uploaded.get("hash"),
                "v": api_version,
            },
        )
        if saved.get("error"):
            return {"success": False, "status": "vk_media_save_failed", "error": str(_json_dict(saved.get("error")).get("error_msg") or "VK не сохранил фото.")}
        saved_items = saved.get("response") if isinstance(saved.get("response"), list) else []
        if not saved_items or not isinstance(saved_items[0], dict):
            return {"success": False, "status": "vk_media_save_empty", "error": "VK не вернул сохранённое фото."}
        saved_photo = saved_items[0]
        photo_owner_id = str(saved_photo.get("owner_id") or owner_id).strip()
        photo_id = str(saved_photo.get("id") or "").strip()
        if not photo_id:
            return {"success": False, "status": "vk_media_save_empty", "error": "VK не вернул ID фото."}
        attachments.append(f"photo{photo_owner_id}_{photo_id}")
    return {"success": True, "attachments": attachments}
