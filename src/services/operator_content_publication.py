"""Chat tools for preparing, publishing, and reconciling content per channel."""
import hashlib
import json

from services.operator_audio import authorize_actor
from services.operator_conversations import _row


PLATFORM_LABELS = {
    "telegram": "Telegram", "vk": "VK", "max": "MAX",
    "google_business": "Google", "yandex_maps": "Яндекс Карты",
    "two_gis": "2ГИС", "instagram": "Instagram", "facebook": "Facebook",
}


def _load_posts(cursor, *, business_id, user_id, post_ids=None, item_id=""):
    authorize_actor(cursor, user_id, business_id)
    filters = ["business_id=%s"]
    params = [business_id]
    if item_id:
        filters.append("content_plan_item_id=%s")
        params.append(item_id)
    if post_ids is not None:
        if not post_ids or len(post_ids) > 20:
            raise ValueError("Выберите от одного до двадцати постов")
        filters.append("id=ANY(%s)")
        params.append(post_ids)
    cursor.execute(
        "SELECT id,business_id,content_plan_item_id,platform,status,publish_mode,scheduled_for,"
        "base_text,platform_text,media_json,provider_post_url,provider_post_id,updated_at,metadata_json "
        "FROM social_posts WHERE " + " AND ".join(filters) + " ORDER BY scheduled_for,id",
        tuple(params),
    )
    rows = [_row(cursor, row) for row in cursor.fetchall()]
    if post_ids is not None and len(rows) != len(set(post_ids)):
        raise ValueError("Один из выбранных постов недоступен для этого бизнеса")
    return rows


def _handoff_status(metadata):
    from services.content_delivery_status import delivery_status
    return delivery_status(metadata.get('metadata_json'))


def _snapshot(post):
    fields = {
        "id": str(post.get("id") or ""),
        "platform": str(post.get("platform") or ""),
        "status": str(post.get("status") or ""),
        "publish_mode": str(post.get("publish_mode") or ""),
        "scheduled_for": str(post.get("scheduled_for") or ""),
        "base_text": str(post.get("base_text") or ""),
        "platform_text": str(post.get("platform_text") or ""),
        "media_json": post.get("media_json") or [],
        "updated_at": str(post.get("updated_at") or ""),
    }
    encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str)
    return {"id": fields["id"], "digest": hashlib.sha256(encoded.encode()).hexdigest()}


def list_channel_posts(cursor, *, business_id, user_id, item_id=""):
    posts = _load_posts(cursor, business_id=business_id, user_id=user_id, item_id=item_id)
    if not posts:
        return {"status": "completed", "posts": [], "chat_response": "Для этого поста пока не подготовлены версии по каналам. Сначала подготовьте каналы в контент-плане."}
    result = []
    for post in posts:
        result.append({
            "id": str(post["id"]), "platform": post.get("platform"),
            "platform_label": PLATFORM_LABELS.get(str(post.get("platform") or ""), str(post.get("platform") or "")),
            "status": post.get("status"), "publish_mode": post.get("publish_mode"),
            "scheduled_for": str(post.get("scheduled_for") or ""),
            "text": str(post.get("platform_text") or post.get("base_text") or ""),
            "has_media": bool(post.get("media_json")),
            "handoff_status": _handoff_status(post),
            "provider_post_url": post.get("provider_post_url") or "",
            "version": _snapshot(post)["digest"],
            "updated_at": str(post.get("updated_at") or ""),
        })
    return {"status": "completed", "posts": result, "external_writes_performed": False}


def edit_channel_text(cursor, *, business_id, user_id, message, arguments):
    posts = _load_posts(cursor, business_id=business_id, user_id=user_id, post_ids=[str(arguments.get('post_id') or '')])
    post = posts[0]
    if post.get('status') in {'published', 'publishing'}:
        return {'status':'blocked','chat_response':'Опубликованный или размещаемый вариант нельзя изменить.','external_writes_performed':False}
    if str(arguments.get('version') or '') != _snapshot(post)['digest']:
        return {'status':'blocked','chat_response':'Вариант изменился после просмотра. Обновите список каналов перед правкой.','external_writes_performed':False}
    text = str(arguments.get('text') or '').strip()
    if not text or len(text) > 12000:
        return {'status':'clarification_required','chat_response':'Нужен текст версии до 12 000 символов.','external_writes_performed':False}
    normalize = lambda value: ' '.join(str(value or '').casefold().replace('ё','е').split())
    if normalize(text) not in normalize(message):
        return {'status':'clarification_required','chat_response':'Передайте точную новую формулировку текста, чтобы я не добавлял детали от себя.','external_writes_performed':False}
    cursor.execute('''UPDATE social_posts SET platform_text=%s,status='needs_review',approved_at=NULL,approval_id=NULL,
        automation_task_id=NULL,last_error=NULL,updated_at=NOW() WHERE id=%s AND business_id=%s
        AND status NOT IN ('published','publishing')
        AND (%s = '' OR updated_at = %s::timestamptz) RETURNING id''',
        (text, post['id'], business_id, str(post.get('updated_at') or ''), str(post.get('updated_at') or '')))
    if not cursor.fetchone():
        return {'status':'blocked','chat_response':'Вариант уже изменился или опубликован. Обновите список каналов.','external_writes_performed':False}
    platform = PLATFORM_LABELS.get(str(post.get('platform') or ''), str(post.get('platform') or ''))
    return {'status':'completed','chat_response':f'Сохранил новый текст варианта для {platform}. Статус вернулся на проверку; опубликованным его не отмечал.',
            'post_id':str(post['id']),'external_writes_performed':False,
            'result_ref':{'href':'/dashboard/content','label':'Открыть контент','entity_type':'content'}}


def prepare_channels(*, user_id, item_id, platforms):
    if not isinstance(platforms, list) or not platforms:
        return {"status": "clarification_required", "chat_response": "Уточните каналы для подготовки поста."}
    from services.social_post_service import prepare_social_posts_for_item
    result = prepare_social_posts_for_item(user_id, item_id, platforms, replace_platforms=False)
    posts = result.get("posts") or []
    previews = []
    for post in posts:
        label = PLATFORM_LABELS.get(str(post.get("platform") or ""), str(post.get("platform") or ""))
        text = str(post.get("platform_text") or post.get("base_text") or "").strip()
        previews.append(f"{label} · {post.get('status') or 'черновик'}\n{text}\nФото: {'прикреплено' if post.get('media_json') else 'не прикреплено'}")
    return {
        "status": "completed" if posts else "blocked",
        "posts": [{
            "platform": post.get("platform"),
            "platform_label": PLATFORM_LABELS.get(str(post.get("platform") or ""), str(post.get("platform") or "")),
            "status": post.get("status"),
            "text": post.get("platform_text") or post.get("base_text") or "",
            "has_media": bool(post.get("media_json")),
        } for post in posts],
        "chat_response": ("Подготовил варианты по каналам. Публикация не выполнялась:\n\n" + "\n\n".join(previews)) if previews else "Не удалось подготовить версии. Проверьте текст поста и выбранные каналы.",
        "external_writes_performed": False,
        "result_ref": {"href": "/dashboard/content", "label": "Открыть контент"},
    }


def prepare_publish(cursor, *, business_id, user_id, post_ids):
    posts = _load_posts(cursor, business_id=business_id, user_id=user_id, post_ids=post_ids)
    blocked = [post for post in posts if post.get("status") in {"published", "publishing"}]
    if blocked:
        return {"status": "blocked", "chat_response": "Часть выбранных каналов уже опубликована или находится в процессе. Обновите список и подтвердите только оставшиеся каналы."}
    from services.social_post_service import get_social_channel_readiness
    readiness_payload = get_social_channel_readiness(user_id, business_id)
    channel_readiness = {
        str(item.get("platform") or item.get("channel") or ""): item
        for item in readiness_payload.get("channel_readiness") or [] if isinstance(item, dict)
    }
    summaries = []
    for post in posts:
        label = PLATFORM_LABELS.get(str(post.get("platform") or ""), str(post.get("platform") or ""))
        text = str(post.get("platform_text") or post.get("base_text") or "").strip()
        if not text:
            return {"status": "blocked", "chat_response": f"Для канала {label} не сохранён текст. Сначала подготовьте публикацию."}
        readiness = channel_readiness.get(str(post.get("platform") or ""), {})
        ready = bool(readiness.get("ready"))
        readiness_label = "подключение готово" if ready else str(readiness.get("status") or "состояние подключения не подтверждено")
        if post.get("publish_mode") == "api" and not ready:
            return {"status": "blocked", "chat_response": f"Канал {label} не готов к публикации через подключение ({readiness_label}). Исправьте подключение или выберите ручное размещение в меню «Контент». Ничего не отправлял.", "external_writes_performed": False}
        mode_label = "через подключение" if post.get("publish_mode") == "api" else "потребуется ручное размещение"
        summaries.append(f"{label} · {str(post.get('scheduled_for') or '')[:10]}\n{text}\nФото: {'прикреплено' if post.get('media_json') else 'не прикреплено'}\nСпособ: {mode_label}; {readiness_label}")
    summary = "Подтвердите размещение только этих вариантов:\n\n" + "\n\n".join(summaries)
    return {
        "status": "approval_required", "chat_response": summary,
        "approval": {"status": "pending", "capability": "content.publish_external", "summary": summary,
                     "envelope": {"business_id": business_id, "post_ids": [str(post["id"]) for post in posts],
                                  "snapshots": [_snapshot(post) for post in posts]}},
        "external_writes_performed": False,
    }


def publish_confirmed(cursor, *, business_id, user_id, envelope):
    if envelope.get("business_id") != business_id:
        return {"status": "blocked", "blocked_reasons": ["business_mismatch"], "external_writes_performed": False}
    posts = _load_posts(cursor, business_id=business_id, user_id=user_id, post_ids=envelope.get("post_ids"))
    expected = {item.get("id"): item.get("digest") for item in envelope.get("snapshots") or [] if isinstance(item, dict)}
    if len(expected) != len(posts) or any(expected.get(str(post["id"])) != _snapshot(post)["digest"] for post in posts):
        return {"status": "blocked", "chat_response": "Пост, фото, дата или статус изменились после предпросмотра. Ничего не размещал; обновите предпросмотр и подтвердите заново.", "external_writes_performed": False}
    from services.social_post_service import approve_social_post, publish_social_post, move_social_post_to_manual_publish
    results = []
    for post in posts:
        post_id = str(post["id"])
        platform = PLATFORM_LABELS.get(str(post.get("platform") or ""), str(post.get("platform") or ""))
        try:
            approved = approve_social_post(user_id, post_id)
            if str(approved.get("publish_mode") or "") == "api":
                outcome = publish_social_post(user_id, post_id)
                results.append({"id": post_id, "platform": platform, "status": outcome.get("status"),
                                "url": outcome.get("provider_post_url") or "", "error": outcome.get("last_error") or ""})
            else:
                outcome = move_social_post_to_manual_publish(user_id, post_id, "Пользователь подтвердил размещение; площадка требует ручной публикации.")
                results.append({"id": post_id, "platform": platform, "status": outcome.get("status"), "manual": True})
        except Exception:
            results.append({"id": post_id, "platform": platform, "status": "failed",
                            "error": "Не удалось завершить действие; проверьте подключение и статус в разделе «Контент»."})
    completed = [item for item in results if item.get("status") == "published"]
    manual = [item for item in results if item.get("manual")]
    failed = [item for item in results if item.get("status") == "failed"]
    uncertain = [item for item in results if item.get("status") in {"publishing", "unknown"}]
    other = [item for item in results if item not in completed + manual + failed + uncertain]
    pending = len(uncertain) + len(other)
    status = "blocked" if failed or pending else "completed"
    message = f"Опубликовано через подключение: {len(completed)}. Нужно разместить вручную: {len(manual)}. Ошибок: {len(failed)}."
    if pending:
        message += f" Неопределённый результат: {pending}; сначала сверьте площадку. Повторно не отправляйте."
    message += " Ссылки и статусы сохранены отдельно по каналам."
    return {"status": status, "results": results,
            "chat_response": message,
            "external_writes_performed": bool(completed),
            "result_ref": {"href": "/dashboard/content", "label": "Открыть контент"}}


def reconcile_manual(*, user_id, post_id, provider_post_url="", provider_post_id="", content_confirmed=False):
    from services.social_post_service import mark_manual_published
    post = mark_manual_published(user_id, post_id, provider_post_url=provider_post_url,
                                 provider_post_id=provider_post_id, content_confirmed=content_confirmed)
    return {"status": "completed", "chat_response": "Ручную публикацию подтвердил и отметил отдельно для этого канала.",
            "post": {"id": post.get("id"), "platform": post.get("platform"), "status": post.get("status"),
                     "provider_post_url": post.get("provider_post_url") or ""},
            "external_writes_performed": False, "result_ref": {"href": "/dashboard/content", "label": "Открыть контент"}}
