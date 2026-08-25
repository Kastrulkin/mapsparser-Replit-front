from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any

from psycopg2.extras import Json


CONTENT_URL = "https://localos.pro/dashboard/content"
OUTREACH_URL = "https://localos.pro/dashboard/bazich?tab=prospecting"
TELEGRAM_RADAR_URL = "https://localos.pro/dashboard/telegram-radar"
AUTOMATIC_OUTREACH_CHANNELS = {"telegram", "email", "vk"}
TERMINAL_CAMPAIGN_STATUSES = {"cancelled", "completed", "stopped", "lost"}

PLATFORM_LABELS = {
    "telegram": "Telegram",
    "vk": "VK",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "email": "Email",
    "whatsapp": "WhatsApp",
    "max": "MAX",
    "sms": "SMS",
    "manual": "вручную",
    "yandex_maps": "Яндекс Карты",
    "two_gis": "2ГИС",
    "google_business": "Google Business",
}
REPLY_CLASSIFICATION_LABELS = {
    "interested": "заинтересован",
    "question": "задал вопрос",
    "positive_reply": "положительный ответ",
    "meeting_request": "предлагает встречу",
    "not_interested": "не заинтересован",
    "unsubscribe": "просит больше не писать",
    "hard_no": "отказ",
    "wrong_person": "нужен другой контакт",
    "follow_up_later": "просит написать позже",
    "reply": "ответ",
}


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    columns = [column[0] for column in (getattr(cursor, "description", None) or [])]
    if isinstance(row, (tuple, list)):
        return {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
    return {}


def _payload_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _compact_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def _platform_label(value: Any) -> str:
    key = str(value or "").strip().lower()
    return PLATFORM_LABELS.get(key, key or "канал")


def _plural_ru(number: int, one: str, few: str, many: str) -> str:
    modulo_100 = number % 100
    modulo_10 = number % 10
    if 11 <= modulo_100 <= 14:
        return many
    if modulo_10 == 1:
        return one
    if 2 <= modulo_10 <= 4:
        return few
    return many


def _content_action(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").strip().lower()
    publish_mode = str(item.get("publish_mode") or "").strip().lower()
    if not bool(item.get("dispatch_enabled", True)) and publish_mode == "api":
        return "автопубликация выключена — проверить и запустить вручную"
    if status in {"draft", "needs_review"}:
        return "проверить и подтвердить текст"
    if status == "approved":
        return "поставить подтверждённый пост в очередь"
    if status == "needs_manual_publish":
        return "опубликовать вручную"
    if status == "needs_supervised_publish":
        return "открыть контролируемое размещение"
    if status == "failed":
        return "исправить ошибку публикации"
    if publish_mode != "api":
        return "опубликовать вручную"
    return "проверить готовность к публикации"


def _outreach_action(item: dict[str, Any]) -> str:
    channel = str(item.get("channel") or "").strip().lower()
    status = str(item.get("touch_status") or "").strip().lower()
    queue_status = str(item.get("queue_status") or "").strip().lower()
    if not bool(item.get("dispatch_enabled", True)) and channel in AUTOMATIC_OUTREACH_CHANNELS:
        return "автоматическая отправка выключена — проверить кампанию"
    if status in {"awaiting_manual_send", "manual"} or channel not in AUTOMATIC_OUTREACH_CHANNELS:
        return "отправить вручную"
    if status == "draft" or not queue_status:
        return "проверить и подтвердить цепочку"
    if status in {"paused", "needs_attention", "manual_expired", "failed"}:
        return "устранить блокировку"
    return "проверить касание"


def _is_automatic_content(item: dict[str, Any]) -> bool:
    return (
        str(item.get("publish_mode") or "").strip().lower() == "api"
        and str(item.get("status") or "").strip().lower() in {"queued", "publishing"}
        and bool(item.get("approved_at"))
        and bool(item.get("dispatch_enabled", True))
    )


def _is_automatic_outreach(item: dict[str, Any]) -> bool:
    return (
        str(item.get("channel") or "").strip().lower() in AUTOMATIC_OUTREACH_CHANNELS
        and str(item.get("queue_status") or "").strip().lower() in {"queued", "retry", "sending"}
        and str(item.get("campaign_status") or "").strip().lower() not in TERMINAL_CAMPAIGN_STATUSES
        and bool(item.get("dispatch_enabled", True))
    )


def _format_content_items(items: list[dict[str, Any]], *, automatic: bool, limit: int = 6) -> list[str]:
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for item in items:
        if _is_automatic_content(item) != automatic:
            continue
        business_name = _compact_text(item.get("business_name") or "Бизнес", 48)
        title = _compact_text(item.get("title") or "Без темы", 90)
        action = "выйдет автоматически" if automatic else _content_action(item)
        key = (business_name, title, action)
        grouped.setdefault(key, [])
        channel = _platform_label(item.get("platform"))
        if channel not in grouped[key]:
            grouped[key].append(channel)
    lines: list[str] = []
    for (business_name, title, action), channels in list(grouped.items())[:limit]:
        lines.append(f"• {business_name} — «{title}» → {', '.join(channels)}: {action}")
    remaining = max(0, len(grouped) - limit)
    if remaining:
        lines.append(f"• Ещё {remaining} публикаций — в разделе «Контент»")
    return lines


def _format_outreach_items(items: list[dict[str, Any]], *, automatic: bool, limit: int = 8) -> list[str]:
    filtered = [item for item in items if _is_automatic_outreach(item) == automatic]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in filtered:
        channel = _platform_label(item.get("channel"))
        action = "уйдут автоматически" if automatic else _outreach_action(item)
        grouped.setdefault((channel, action), []).append(item)

    lines: list[str] = []
    for (channel, action), group in list(grouped.items())[:limit]:
        count = len(group)
        times = sorted({str(item.get("local_time") or "").strip() for item in group if str(item.get("local_time") or "").strip()})
        if len(times) > 1:
            timing = f" · по расписанию {times[0]}–{times[-1]}"
        elif times:
            timing = f" · по расписанию на {times[0]}"
        else:
            timing = ""
        if action == "автоматическая отправка выключена — проверить кампанию":
            action_text = "не будут отправлены — автоматическая отправка выключена"
        elif action == "отправить вручную":
            action_text = "нужно отправить вручную"
        else:
            action_text = action
        touch_word = _plural_ru(count, "касание", "касания", "касаний")
        lines.append(f"• {count} {touch_word} · {channel}{timing}: {action_text}")
    remaining = max(0, len(grouped) - limit)
    if remaining:
        lines.append(f"• Ещё {remaining} групп касаний")
    return lines


def format_superadmin_morning_operations(
    content_items: list[dict[str, Any]],
    outreach_items: list[dict[str, Any]],
) -> str:
    automatic_content = _format_content_items(content_items, automatic=True)
    manual_content = _format_content_items(content_items, automatic=False)
    automatic_outreach = _format_outreach_items(outreach_items, automatic=True)
    manual_outreach = _format_outreach_items(outreach_items, automatic=False)

    sections: list[str] = []
    if automatic_content or manual_content:
        content_lines = ["📝 Публикации на сегодня"]
        if automatic_content:
            content_lines.extend(["Выйдут автоматически:", *automatic_content])
        if manual_content:
            content_lines.extend(["Требуют решения:", *manual_content])
        sections.append("\n".join(content_lines))

    if automatic_outreach or manual_outreach:
        outreach_lines = ["📨 Аутрич на сегодня"]
        if automatic_outreach:
            outreach_lines.extend(["Уйдут автоматически:", *automatic_outreach])
        if manual_outreach:
            outreach_lines.extend(["Требуют решения:", *manual_outreach])
        sections.append("\n".join(outreach_lines))

    return "\n\n".join(sections)


def format_superadmin_platform_attention(summary: dict[str, Any]) -> str:
    attention_items = [item for item in (summary.get("attention_items") or []) if int(item.get("count") or 0) > 0]
    by_key = {str(item.get("id") or ""): item for item in attention_items}
    ordered = [
        by_key[key]
        for key in ("outreach_replies", "reviews_unanswered", "pending_approvals", "failed_jobs", "outreach_attention", "pending_posts")
        if key in by_key
    ]
    ordered.extend(item for item in attention_items if item not in ordered)
    if not ordered:
        return "Сегодня всё под контролем\nПо операционным очередям срочных сигналов нет."

    lines = ["Сейчас важнее всего"]
    for index, item in enumerate(ordered[:4]):
        key = str(item.get("id") or "")
        count = int(item.get("count") or 0)
        rendered_count = f"{count:,}".replace(",", " ")
        if key == "outreach_replies":
            reply_word = _plural_ru(count, "новый ответ", "новых ответа", "новых ответов")
            title = "Новый ответ в аутриче" if count == 1 else f"{rendered_count} {reply_word} в аутриче"
            description = "Следующие касания остановлены. Нужно прочитать ответ и выбрать дальнейшее действие."
            icon = "💬"
        elif key == "reviews_unanswered":
            review_word = _plural_ru(count, "отзыв", "отзыва", "отзывов")
            title = f"{rendered_count} {review_word} без ответа"
            affected = int(item.get("affected_businesses") or 0)
            business_word = _plural_ru(affected, "бизнеса", "бизнесов", "бизнесов")
            affected_text = f" у {affected:,} {business_word}".replace(",", " ") if affected else ""
            description = f"Нужно подготовить ответы{affected_text} и проверить их перед публикацией."
            icon = "⭐"
        elif key == "pending_approvals":
            action_word = _plural_ru(count, "действие", "действия", "действий")
            title = f"{rendered_count} {action_word} ждут подтверждения"
            description = "LocalOS подготовил изменения, но не выполнит их без вашего решения."
            icon = "🟠"
        elif key == "failed_jobs":
            job_word = _plural_ru(count, "задание", "задания", "заданий")
            title = f"{rendered_count} {job_word} обновления завершились с ошибкой"
            affected = int(item.get("affected_businesses") or 0)
            business_word = _plural_ru(affected, "бизнес", "бизнеса", "бизнесов")
            affected_text = f" Затронуто {affected:,} {business_word}.".replace(",", " ") if affected else ""
            description = f"Причины — ошибки получения данных и captcha.{affected_text}"
            icon = "🔴"
        elif key == "pending_posts":
            publication_word = _plural_ru(count, "публикация", "публикации", "публикаций")
            title = f"{rendered_count} {publication_word} требуют проверки"
            description = "Проверьте черновики и ошибки перед размещением."
            icon = "📝"
        elif key == "outreach_attention":
            touch_word = _plural_ru(count, "касание", "касания", "касаний")
            title = f"{rendered_count} {touch_word} в аутриче требуют разбора"
            description = "Это ошибки доставки или истёкшие ручные действия, а не ответы клиентов."
            icon = "⚠️"
        else:
            title = str(item.get("title") or "Требуется внимание")
            description = str(item.get("description") or "").strip()
            icon = "🟠"
        if index == 1:
            lines.extend(["", "Ещё требуют внимания"])
        lines.extend([f"{icon} {title}", description])

    metrics = {str(item.get("key") or ""): item.get("value") for item in (summary.get("metrics") or [])}
    businesses = int(metrics.get("businesses_total") or 0)
    networks = int(metrics.get("networks_total") or 0)
    lines.extend(["", "Под контролем", f"{businesses:,} клиентских аккаунтов · {networks:,} сетей".replace(",", " ")])
    return "\n".join(lines)


def collect_superadmin_morning_operations(conn: Any, local_today: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            post.id,
            business.name AS business_name,
            post.platform,
            post.publish_mode,
            post.status,
            post.approved_at,
            COALESCE(
                NULLIF(BTRIM(plan_item.theme), ''),
                NULLIF(BTRIM(post.platform_text), ''),
                NULLIF(BTRIM(post.base_text), ''),
                'Без темы'
            ) AS title
        FROM social_posts post
        LEFT JOIN businesses business ON business.id = post.business_id
        LEFT JOIN contentplanitems plan_item ON plan_item.id = post.content_plan_item_id
        WHERE DATE(post.scheduled_for AT TIME ZONE 'Europe/Moscow') = %s
          AND post.status NOT IN ('published')
        ORDER BY business.name, title, post.platform
        """,
        (local_today,),
    )
    content_items = [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]

    cursor.execute(
        """
        SELECT
            touch.id,
            lead.name AS lead_name,
            COALESCE(business.name, 'LocalOS') AS business_name,
            touch.channel,
            touch.status AS touch_status,
            campaign.status AS campaign_status,
            campaign.scope_type,
            campaign.business_id,
            latest_queue.delivery_status AS queue_status,
            TO_CHAR(touch.scheduled_at AT TIME ZONE 'Europe/Moscow', 'HH24:MI') AS local_time
        FROM outreach_campaign_touches touch
        JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
        JOIN prospectingleads lead ON lead.id = campaign.lead_id
        LEFT JOIN businesses business ON business.id = campaign.business_id
        LEFT JOIN LATERAL (
            SELECT queue.delivery_status
            FROM outreachsendqueue queue
            WHERE queue.campaign_touch_id = touch.id
            ORDER BY queue.created_at DESC
            LIMIT 1
        ) latest_queue ON TRUE
        WHERE DATE(touch.scheduled_at AT TIME ZONE 'Europe/Moscow') = %s
          AND touch.status NOT IN (
              'sent', 'delivered', 'manual_sent', 'manual_skipped',
              'cancelled', 'skipped', 'reply_cancelled'
          )
          AND campaign.status NOT IN ('cancelled', 'completed', 'stopped', 'lost')
        ORDER BY touch.scheduled_at, lead.name
        """,
        (local_today,),
    )
    outreach_items = [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]
    social_dispatch_enabled = str(os.getenv("SOCIAL_POST_DISPATCH_ENABLED") or "false").strip().lower() in {
        "1", "true", "yes", "on",
    }
    outreach_dispatch_enabled = str(os.getenv("OUTREACH_DISPATCH_ENABLED") or "false").strip().lower() in {
        "1", "true", "yes", "on",
    }
    platform_dispatch_enabled = str(
        os.getenv("OUTREACH_DISPATCH_PLATFORM_SCOPE_ENABLED") or "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    allowed_business_ids = {
        item.strip()
        for item in str(os.getenv("OUTREACH_DISPATCH_BUSINESS_IDS") or "").split(",")
        if item.strip()
    }
    for item in content_items:
        item["dispatch_enabled"] = social_dispatch_enabled
    for item in outreach_items:
        scope_type = str(item.get("scope_type") or "").strip().lower()
        scope_allowed = (
            platform_dispatch_enabled
            if scope_type == "platform"
            else str(item.get("business_id") or "").strip() in allowed_business_ids
        )
        item["dispatch_enabled"] = outreach_dispatch_enabled and scope_allowed
    return content_items, outreach_items


def build_superadmin_morning_operations_block(conn: Any, local_today: date) -> str:
    try:
        content_items, outreach_items = collect_superadmin_morning_operations(conn, local_today)
        return format_superadmin_morning_operations(content_items, outreach_items)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return (
            "📅 План на сегодня\n"
            "Не удалось собрать публикации и аутрич. Проверьте разделы вручную:\n"
            f"Контент: {CONTENT_URL}\n"
            f"Аутрич: {OUTREACH_URL}"
        )


def load_superadmin_telegram_recipients(conn: Any) -> list[str]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT BTRIM(CAST(telegram_id AS TEXT)) AS telegram_id
        FROM users
        WHERE is_superadmin IS TRUE
          AND COALESCE(is_active, TRUE) IS TRUE
          AND telegram_id IS NOT NULL
          AND BTRIM(CAST(telegram_id AS TEXT)) <> ''
        ORDER BY telegram_id
        """
    )
    recipients: list[str] = []
    for row in cursor.fetchall() or []:
        payload = _row_to_dict(cursor, row)
        telegram_id = str(payload.get("telegram_id") or "").strip()
        if telegram_id:
            recipients.append(telegram_id)
    return recipients


def collect_pending_community_source_notifications(conn: Any, limit: int = 20) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            subscription.business_id,
            subscription.source_id,
            subscription.topics_json,
            subscription.schedule_json,
            source.title AS source_title,
            source.canonical_url,
            business.name AS business_name,
            COALESCE(NULLIF(BTRIM(actor.name), ''), NULLIF(BTRIM(actor.email), ''), 'Пользователь') AS submitted_by
        FROM knowledge_source_subscriptions subscription
        JOIN knowledge_sources source ON source.id = subscription.source_id
        JOIN businesses business ON business.id = subscription.business_id
        LEFT JOIN users actor
          ON actor.id = NULLIF(subscription.schedule_json->>'submitted_by_user_id', '')
        WHERE subscription.is_active IS TRUE
          AND source.source_type = 'telegram'
          AND source.visibility = 'public'
          AND subscription.schedule_json->>'superadmin_notification_status' = 'pending'
        ORDER BY subscription.updated_at
        LIMIT %s
        """,
        (max(1, min(int(limit), 100)),),
    )
    return [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]


def format_community_source_notification(item: dict[str, Any]) -> str:
    topics_value = item.get("topics_json")
    if isinstance(topics_value, str):
        try:
            topics_value = json.loads(topics_value)
        except Exception:
            topics_value = []
    topics = [str(value).strip() for value in (topics_value or []) if str(value).strip()]
    topic_line = f"Темы: {', '.join(topics[:6])}\n" if topics else ""
    return (
        "📡 Пользователь добавил источник в Telegram-радар\n\n"
        f"Бизнес: {_compact_text(item.get('business_name') or 'Без названия', 100)}\n"
        f"Добавил: {_compact_text(item.get('submitted_by') or 'Пользователь', 100)}\n"
        f"Источник: {_compact_text(item.get('source_title') or 'Telegram', 120)}\n"
        f"Ссылка: {str(item.get('canonical_url') or '').strip()}\n"
        f"{topic_line}\n"
        "Источник уже подключён к личному Пульсу и подборке тем. Проверьте, подходит ли он для общей отраслевой базы.\n"
        f"Открыть Telegram-радар: {TELEGRAM_RADAR_URL}"
    )


def mark_community_source_notification_sent(
    conn: Any,
    *,
    business_id: str,
    source_id: str,
    telegram_ids: list[str],
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE knowledge_source_subscriptions
        SET schedule_json = COALESCE(schedule_json, '{}'::jsonb) || %s,
            updated_at = NOW()
        WHERE business_id = %s AND source_id = %s
          AND schedule_json->>'superadmin_notification_status' = 'pending'
        """,
        (
            Json({
                "superadmin_notification_status": "sent",
                "superadmin_notified_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "superadmin_notified_telegram_ids": telegram_ids,
            }),
            business_id,
            source_id,
        ),
    )


def collect_pending_outreach_reply_notifications(conn: Any, limit: int = 20) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            inbound.id,
            inbound.channel,
            inbound.classification,
            inbound.stops_campaign,
            inbound.raw_payload_json,
            inbound.occurred_at,
            lead.name AS lead_name,
            COALESCE(business.name, 'LocalOS') AS business_name,
            COALESCE(NULLIF(BTRIM(touch.approved_text), ''), touch.generated_text, '') AS outbound_text,
            room.slug AS room_slug,
            external_task.external_url AS yougile_task_url
        FROM outreach_inbound_events inbound
        LEFT JOIN outreach_campaigns campaign ON campaign.id = inbound.campaign_id
        LEFT JOIN lead_workstreams workstream ON workstream.id = inbound.workstream_id
        JOIN prospectingleads lead ON lead.id = inbound.lead_id
        LEFT JOIN outreach_campaign_touches touch ON touch.id = inbound.touch_id
        LEFT JOIN businesses business
          ON business.id = COALESCE(campaign.business_id, workstream.client_business_id)
        LEFT JOIN sales_rooms room ON room.workstream_id = inbound.workstream_id
        LEFT JOIN outreach_external_task_bindings external_task
          ON external_task.workstream_id = inbound.workstream_id
         AND external_task.provider = 'yougile' AND external_task.status = 'active'
        WHERE inbound.event_type = 'reply'
          AND inbound.is_human IS TRUE
          AND inbound.created_at >= NOW() - INTERVAL '24 hours'
          AND NOT jsonb_exists(
              COALESCE(inbound.raw_payload_json, '{}'::jsonb),
              'superadmin_notified_at'
          )
        ORDER BY inbound.created_at
        LIMIT %s
        """,
        (max(1, min(int(limit), 100)),),
    )
    return [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]


def format_outreach_reply_notification(item: dict[str, Any]) -> str:
    payload = _payload_dict(item.get("raw_payload_json"))
    raw_reply = _compact_text(payload.get("raw_reply") or "Ответ без текста", 500)
    outbound_text = _compact_text(item.get("outbound_text") or "Текст исходного касания не найден", 260)
    lead_name = _compact_text(item.get("lead_name") or "Получатель", 80)
    business_name = _compact_text(item.get("business_name") or "LocalOS", 60)
    channel = _platform_label(item.get("channel"))
    classification_key = str(item.get("classification") or "reply").strip()
    classification = REPLY_CLASSIFICATION_LABELS.get(classification_key, classification_key)
    stopped = bool(item.get("stops_campaign"))
    stop_line = (
        "Следующие касания остановлены."
        if stopped
        else "Кампания требует проверки: автоматическая остановка не применена."
    )
    room_slug = str(item.get("room_slug") or "").strip()
    links = []
    if room_slug:
        links.append(f"Комната: https://localos.pro/room/{room_slug}")
    if item.get("yougile_task_url"):
        links.append(f"YouGile: {item.get('yougile_task_url')}")
    link_block = "\n" + "\n".join(links) if links else f"\nОткрыть лид: {OUTREACH_URL}"
    return (
        "💬 Пришёл ответ на аутрич\n\n"
        f"{business_name} → {lead_name} · {channel}\n"
        f"На сообщение: «{outbound_text}»\n\n"
        f"Ответ: «{raw_reply}»\n\n"
        f"Классификация: {classification}. {stop_line}"
        f"{link_block}"
    )


def mark_outreach_reply_notification_sent(conn: Any, event_id: str, telegram_ids: list[str]) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE outreach_inbound_events
        SET raw_payload_json = COALESCE(raw_payload_json, '{}'::jsonb) || %s
        WHERE id = %s
        """,
        (
            Json(
                {
                    "superadmin_notified_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "superadmin_notified_telegram_ids": telegram_ids,
                }
            ),
            event_id,
        ),
    )
