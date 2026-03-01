#!/usr/bin/env python3
"""
Telegram-бот для управления аккаунтом BeautyBot
Функционал:
- Привязка аккаунта через токен
- Добавление транзакций (фото/текст)
- Оптимизация услуг
- Настройки компании
"""
import os
import json
import uuid
import base64
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from database_manager import get_db_connection
from core.action_orchestrator import ActionOrchestrator
from core.helpers import get_user_language
from services.gigachat_client import analyze_screenshot_with_gigachat, analyze_text_with_gigachat

# Автоматически подгружаем переменные окружения из .env,
# как это сделано в main.py, чтобы GigaChat-ключи и другие
# настройки, заданные в проекте, были доступны и боту.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ Для автоматической загрузки .env установите пакет python-dotenv")

# Токен бота и базовый URL API из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')

# Словарь для хранения состояния пользователей (telegram_id -> state)
user_states = {}
OPENCLAW_ORCHESTRATOR = ActionOrchestrator({})
REVIEW_REPLY_TONES = [
    ("friendly", "Дружелюбный"),
    ("professional", "Профессиональный"),
    ("premium", "Премиум"),
    ("business", "Деловой"),
]


def _row_get(row, key: str, index: int | None = None, default=None):
    if row is None:
        return default
    if hasattr(row, "get"):
        try:
            return row.get(key, default)
        except Exception:
            pass
    if index is not None and isinstance(row, (tuple, list)):
        try:
            return row[index]
        except Exception:
            return default
    return default


def _get_prompt_from_db(prompt_type: str, fallback: str = None) -> str:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT prompt_text FROM AIPrompts WHERE prompt_type = %s", (prompt_type,))
        row = cursor.fetchone()
    except Exception:
        return fallback or ""
    finally:
        try:
            conn.close()
        except Exception:
            pass

    prompt_text = _row_get(row, "prompt_text", 0, "")
    prompt_text = str(prompt_text or "").strip()
    return prompt_text or (fallback or "")


def _extract_json_candidate(raw_text: str):
    if not isinstance(raw_text, str):
        return None
    txt = raw_text.strip()
    if not txt:
        return None
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass
    start = txt.find("{")
    end = txt.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(txt[start:end])
        except Exception:
            return None
    return None


def _format_prompt_with_replacements(template: str, mapping: dict) -> str:
    prompt = str(template or "")
    for key, value in (mapping or {}).items():
        prompt = prompt.replace("{" + str(key) + "}", str(value or ""))
    return prompt


def _load_review_examples(user_id: str, limit: int = 5) -> list[str]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT example_text
            FROM UserExamples
            WHERE user_id = %s AND example_type = 'review'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (str(user_id), int(limit)),
        )
        rows = cursor.fetchall() or []
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    examples = []
    for row in rows:
        text = str(_row_get(row, "example_text", 0, "") or "").strip()
        if text:
            examples.append(text)
    return examples


def _telegram_capability_reviews_reply(envelope: dict, user_data: dict) -> dict:
    payload = envelope.get("payload") or {}
    review_text = str(payload.get("review") or "").strip()
    tone = str(payload.get("tone") or "профессиональный").strip()
    language = get_user_language(
        str(user_data.get("user_id") or ""),
        str(payload.get("language") or "").strip() or None,
    )
    examples = payload.get("examples")
    if not isinstance(examples, list) or not examples:
        examples = _load_review_examples(str(user_data.get("user_id") or ""), limit=5)
    if not review_text:
        raise ValueError("review is required for reviews.reply")

    language_names = {
        "ru": "Russian",
        "en": "English",
        "es": "Spanish",
        "de": "German",
        "fr": "French",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
    }
    prompt_template = _get_prompt_from_db("review_reply", None)
    if not prompt_template:
        raise ValueError("Промпт review_reply не настроен в админ-панели.")

    prompt = _format_prompt_with_replacements(
        prompt_template,
        {
            "tone": tone,
            "language_name": language_names.get(language, "Russian"),
            "examples_text": "\n".join([str(x) for x in examples[:5] if str(x).strip()]),
            "review_text": review_text[:1000],
        },
    )
    result_text = analyze_text_with_gigachat(
        prompt,
        task_type="review_reply",
        business_id=str(envelope.get("tenant_id") or ""),
        user_id=str(user_data.get("user_id") or ""),
    )
    parsed = _extract_json_candidate(result_text if isinstance(result_text, str) else "")
    if isinstance(parsed, dict) and parsed.get("error"):
        raise ValueError(str(parsed.get("error")))

    reply_text = ""
    if isinstance(parsed, dict):
        reply_text = str(parsed.get("reply") or parsed.get("text") or "").strip()
    if not reply_text:
        reply_text = str(result_text or "").strip()
    if not reply_text:
        raise ValueError("Не удалось сгенерировать ответ")

    return {
        "result": {"reply": reply_text},
        "billing": {
            "total_tokens": 0,
            "cost": 0.0,
            "tool_calls": 1,
            "tariff_id": str(((envelope.get("billing") or {}).get("tariff_id") or "")),
        },
    }


OPENCLAW_ORCHESTRATOR.handlers["reviews.reply"] = _telegram_capability_reviews_reply

def get_user_id_from_telegram(telegram_id: str):
    """Получить user_id из telegram_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Users WHERE telegram_id = %s", (telegram_id,))
    user_row = cursor.fetchone()
    conn.close()
    return _row_get(user_row, "id", 0)


def list_user_businesses(telegram_id: str) -> list[dict]:
    db_user_id = get_user_id_from_telegram(telegram_id)
    if not db_user_id:
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, name
            FROM Businesses
            WHERE owner_id = %s
            ORDER BY created_at ASC NULLS LAST, name ASC
            """,
            (db_user_id,),
        )
        items = []
        for row in cursor.fetchall() or []:
            items.append(
                {
                    "id": str(_row_get(row, "id", 0) or ""),
                    "name": str(_row_get(row, "name", 1) or "Без названия").strip(),
                }
            )
        return items
    finally:
        conn.close()


def resolve_business_context(telegram_id: str, preferred: str = ""):
    """Определить бизнес пользователя для команд OpenClaw."""
    db_user_id = get_user_id_from_telegram(telegram_id)
    if not db_user_id:
        return None

    preferred = str(preferred or "").strip().lower()
    active_business_id = str((user_states.get(str(telegram_id), {}) or {}).get("active_business_id") or "").strip()
    businesses = list_user_businesses(telegram_id)
    if not businesses:
        return {
            "user_id": db_user_id,
            "business_id": None,
            "business_name": None,
            "business_count": 0,
        }

    normalized = [(item["id"], item["name"]) for item in businesses]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if preferred:
            for business_id, business_name in normalized:
                if preferred == business_id.lower() or preferred == business_name.lower():
                    user_states.setdefault(str(telegram_id), {})["active_business_id"] = business_id
                    return {
                        "user_id": db_user_id,
                        "business_id": business_id,
                        "business_name": business_name,
                        "business_count": len(normalized),
                    }
            for business_id, business_name in normalized:
                if preferred in business_name.lower():
                    user_states.setdefault(str(telegram_id), {})["active_business_id"] = business_id
                    return {
                        "user_id": db_user_id,
                        "business_id": business_id,
                        "business_name": business_name,
                        "business_count": len(normalized),
                    }

        if active_business_id:
            for business_id, business_name in normalized:
                if business_id == active_business_id:
                    return {
                        "user_id": db_user_id,
                        "business_id": business_id,
                        "business_name": business_name,
                        "business_count": len(normalized),
                    }

        if not businesses:
            return {
                "user_id": db_user_id,
                "business_id": None,
                "business_name": None,
                "business_count": 0,
            }

        latest_business_id = None
        try:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'telegrambindtokens'
                """
            )
            token_columns = {str(_row_get(row, "column_name", 0) or "") for row in (cursor.fetchall() or [])}
            if "business_id" in token_columns:
                cursor.execute(
                    """
                    SELECT business_id
                    FROM TelegramBindTokens
                    WHERE user_id = %s
                      AND used = 1
                      AND business_id IS NOT NULL
                      AND NULLIF(TRIM(CAST(business_id AS TEXT)), '') IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (db_user_id,),
                )
                latest_row = cursor.fetchone()
                latest_business_id = str(_row_get(latest_row, "business_id", 0) or "")
        except Exception:
            latest_business_id = None

        selected_business_id = None
        selected_business_name = None
        if latest_business_id:
            for business_id, business_name in normalized:
                if business_id == latest_business_id:
                    selected_business_id = business_id
                    selected_business_name = business_name
                    break
        if not selected_business_id:
            selected_business_id, selected_business_name = normalized[0]
        user_states.setdefault(str(telegram_id), {})["active_business_id"] = selected_business_id

        return {
            "user_id": db_user_id,
            "business_id": selected_business_id,
            "business_name": selected_business_name,
            "business_count": len(normalized),
        }
    finally:
        conn.close()


def _ensure_callback_recovery_history_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS callback_recovery_history (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            triggered_by TEXT NOT NULL,
            send_telegram_report BOOLEAN NOT NULL DEFAULT FALSE,
            include_retry BOOLEAN NOT NULL DEFAULT TRUE,
            replayed_count INTEGER NOT NULL DEFAULT 0,
            sent_count INTEGER NOT NULL DEFAULT 0,
            retried_count INTEGER NOT NULL DEFAULT 0,
            dlq_count INTEGER NOT NULL DEFAULT 0,
            telegram_sent_count INTEGER NOT NULL DEFAULT 0,
            action_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            report_text TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_callback_recovery_history_tenant_created
        ON callback_recovery_history (tenant_id, created_at DESC)
        """
    )


def _ensure_support_export_send_history_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS support_export_send_history (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            triggered_by TEXT NOT NULL,
            action_id TEXT NULL,
            telegram_sent_count INTEGER NOT NULL DEFAULT 0,
            target_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            report_text TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_support_export_send_history_tenant_created
        ON support_export_send_history (tenant_id, created_at DESC)
        """
    )


def _load_callback_recovery_history_items(cursor, tenant_id: str, limit: int) -> list[dict]:
    _ensure_callback_recovery_history_table(cursor)
    cursor.execute(
        """
        SELECT id, tenant_id, triggered_by, send_telegram_report, include_retry,
               replayed_count, sent_count, retried_count, dlq_count, telegram_sent_count,
               action_ids_json, report_text, created_at
        FROM callback_recovery_history
        WHERE tenant_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (str(tenant_id), int(limit)),
    )
    items = []
    for row in cursor.fetchall() or []:
        items.append(
            {
                "id": str(_row_get(row, "id", 0) or ""),
                "created_at": str(_row_get(row, "created_at", 12) or ""),
                "replayed_count": int(_row_get(row, "replayed_count", 5, 0) or 0),
                "sent_count": int(_row_get(row, "sent_count", 6, 0) or 0),
                "retried_count": int(_row_get(row, "retried_count", 7, 0) or 0),
                "dlq_count": int(_row_get(row, "dlq_count", 8, 0) or 0),
            }
        )
    return items


def _send_telegram_plain_message(chat_id: str, text: str) -> bool:
    chat_id = str(chat_id or "").strip()
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return response.ok
    except Exception:
        return False


def _get_superadmin_telegram_ids(cursor) -> list[str]:
    env_ids = {
        x.strip()
        for x in str(os.getenv("OPENCLAW_SUPERADMIN_TELEGRAM_IDS", "")).split(",")
        if x and x.strip()
    }
    target_ids = set(env_ids)
    cursor.execute(
        """
        SELECT telegram_id
        FROM users
        WHERE is_superadmin = TRUE
          AND telegram_id IS NOT NULL
          AND NULLIF(TRIM(CAST(telegram_id AS TEXT)), '') IS NOT NULL
        """
    )
    for row in cursor.fetchall() or []:
        telegram_id = str(_row_get(row, "telegram_id", 0) or "").strip()
        if telegram_id:
            target_ids.add(telegram_id)
    return sorted(target_ids)


def _format_incident_snapshot_digest(snapshot: dict | None) -> str:
    snapshot = snapshot or {}
    overview = dict(snapshot.get("overview") or {})
    action_id = str(snapshot.get("action_id") or "")
    action_short = action_id[:8] if action_id else "unknown"
    capability = str(snapshot.get("capability") or "unknown")
    status = str(snapshot.get("status") or "unknown")
    recent_timeline = list(snapshot.get("recent_timeline") or [])
    last_event = "-"
    if recent_timeline:
        tail = dict(recent_timeline[-1] or {})
        last_event = f"{tail.get('source') or '-'}:{tail.get('event_type') or '-'}:{tail.get('status') or '-'}"
    return (
        f"- {action_short} | {capability} | status={status} | "
        f"attempts={int(overview.get('callback_attempts_total') or 0)} "
        f"(failed={int(overview.get('callback_attempts_failed') or 0)}) | last={last_event}"
    )


def _build_openclaw_support_report(user_data: dict, tenant_id: str) -> tuple[dict, str]:
    metrics_payload = OPENCLAW_ORCHESTRATOR.get_callback_metrics(
        user_data,
        tenant_id=str(tenant_id),
        window_minutes=60,
    )
    if not metrics_payload.get("success"):
        return metrics_payload, ""

    outbox_retry = OPENCLAW_ORCHESTRATOR.list_callback_outbox(
        user_data,
        tenant_id=str(tenant_id),
        status="retry",
        limit=10,
        offset=0,
    )
    if not outbox_retry.get("success"):
        return outbox_retry, ""

    outbox_dlq = OPENCLAW_ORCHESTRATOR.list_callback_outbox(
        user_data,
        tenant_id=str(tenant_id),
        status="dlq",
        limit=10,
        offset=0,
    )
    if not outbox_dlq.get("success"):
        return outbox_dlq, ""

    db = get_db_connection()
    try:
        cursor = db.cursor()
        recovery_items = _load_callback_recovery_history_items(cursor, str(tenant_id), 3)
    finally:
        db.close()

    metrics = dict(metrics_payload.get("metrics") or {})
    retry_items = list(outbox_retry.get("items") or [])
    dlq_items = list(outbox_dlq.get("items") or [])
    lines = [
        "OpenClaw support snapshot",
        f"tenant_id: {tenant_id}",
        f"generated_at: {datetime.utcnow().isoformat()}",
        "",
        "Callback metrics:",
        f"- sent={int(metrics.get('sent') or 0)} retry={int(metrics.get('retry') or 0)} dlq={int(metrics.get('dlq') or 0)} pending={int(metrics.get('pending') or 0)}",
    ]
    if retry_items:
        lines.extend(["", "Retry queue:"])
        lines.extend(
            f"- {str(item.get('action_id') or '')[:8]} | {item.get('event_type') or '-'} | attempts={int(item.get('attempts') or 0)}"
            for item in retry_items[:5]
        )
    if dlq_items:
        lines.extend(["", "DLQ:"])
        lines.extend(
            f"- {str(item.get('action_id') or '')[:8]} | {item.get('event_type') or '-'} | attempts={int(item.get('attempts') or 0)}"
            for item in dlq_items[:5]
        )
    if recovery_items:
        lines.extend(["", "Recent recovery:"])
        lines.extend(
            f"- {item.get('created_at') or '-'} | replay/sent/retry/dlq={int(item.get('replayed_count') or 0)}/{int(item.get('sent_count') or 0)}/{int(item.get('retried_count') or 0)}/{int(item.get('dlq_count') or 0)}"
            for item in recovery_items[:3]
        )

    bundle = {
        "success": True,
        "tenant_id": str(tenant_id),
        "metrics": metrics,
        "retry_items": retry_items,
        "dlq_items": dlq_items,
        "recovery_items": recovery_items,
    }
    return bundle, "\n".join(lines)


def get_openclaw_runtime():
    return {
        "orchestrator": OPENCLAW_ORCHESTRATOR,
        "build_support_report": _build_openclaw_support_report,
        "send_telegram": _send_telegram_plain_message,
        "get_superadmin_ids": _get_superadmin_telegram_ids,
        "ensure_support_history": _ensure_support_export_send_history_table,
        "ensure_recovery_history": _ensure_callback_recovery_history_table,
        "format_snapshot_digest": _format_incident_snapshot_digest,
    }


async def _require_bound_business(update: Update, context: ContextTypes.DEFAULT_TYPE):
    preferred = " ".join(context.args or []).strip()
    ctx = resolve_business_context(str(update.effective_user.id), preferred)
    if not ctx:
        await update.message.reply_text("❌ Аккаунт не привязан. Используйте /start <код_привязки>.")
        return None
    if not ctx.get("business_id"):
        await update.message.reply_text("❌ Для аккаунта не найден бизнес. Сначала создайте бизнес в LocalOS.")
        return None
    return ctx


def _build_openclaw_status_text(business_ctx: dict) -> tuple[bool, str]:
    runtime = get_openclaw_runtime()
    user_data = {"user_id": business_ctx["user_id"]}
    bundle, _report_text = runtime["build_support_report"](
        user_data,
        str(business_ctx["business_id"]),
    )
    if not bundle.get("success"):
        return False, "❌ Не удалось получить OpenClaw статус."

    metrics = dict(bundle.get("metrics") or {})
    retry_items = list(bundle.get("retry_items") or [])
    dlq_items = list(bundle.get("dlq_items") or [])
    recovery_items = list(bundle.get("recovery_items") or [])

    lines = [
        "🤖 OpenClaw status",
        f"Бизнес: {business_ctx['business_name']}",
        f"Tenant: {business_ctx['business_id']}",
        "",
        "Очередь callback:",
        f"- sent={int(metrics.get('sent') or 0)} retry={int(metrics.get('retry') or 0)} dlq={int(metrics.get('dlq') or 0)} pending={int(metrics.get('pending') or 0)}",
    ]
    if retry_items or dlq_items:
        lines.extend(
            [
                "",
                "Проблемные события:",
                f"- retry items: {len(retry_items)}",
                f"- dlq items: {len(dlq_items)}",
            ]
        )
    if recovery_items:
        latest = dict(recovery_items[0] or {})
        lines.extend(
            [
                "",
                "Последний recovery:",
                f"- {latest.get('created_at') or '-'}",
                f"- replay/sent/retry/dlq={int(latest.get('replayed_count') or 0)}/{int(latest.get('sent_count') or 0)}/{int(latest.get('retried_count') or 0)}/{int(latest.get('dlq_count') or 0)}",
            ]
        )
    lines.extend(
        [
            "",
            "Команды:",
            "/support_export — отправить support snapshot суперадмину",
            "/recovery_report — выполнить recovery callback и вернуть отчёт",
        ]
    )
    return True, "\n".join(lines)


def _perform_support_export(business_ctx: dict) -> tuple[bool, str]:
    runtime = get_openclaw_runtime()
    user_data = {"user_id": business_ctx["user_id"]}
    bundle, report_text = runtime["build_support_report"](
        user_data,
        str(business_ctx["business_id"]),
    )
    if not bundle.get("success"):
        return False, "❌ Не удалось собрать support snapshot."

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        target_ids = runtime["get_superadmin_ids"](cursor)
        sent_count = 0
        for telegram_id in target_ids:
            if runtime["send_telegram"](telegram_id, report_text):
                sent_count += 1

        history_id = str(uuid.uuid4())
        runtime["ensure_support_history"](cursor)
        cursor.execute(
            """
            INSERT INTO support_export_send_history (
                id, tenant_id, triggered_by, action_id, telegram_sent_count, target_ids_json, report_text
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                history_id,
                str(business_ctx["business_id"]),
                str(business_ctx["user_id"]),
                "",
                int(sent_count),
                json.dumps(list(target_ids), ensure_ascii=False),
                report_text,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return True, "\n".join(
        [
            "✅ Support snapshot отправлен.",
            f"Бизнес: {business_ctx['business_name']}",
            f"Получатели: {int(sent_count)}/{len(target_ids)}",
            f"History ID: {history_id}",
        ]
    )


def _perform_recovery_report(business_ctx: dict) -> tuple[bool, str]:
    runtime = get_openclaw_runtime()
    orchestrator = runtime["orchestrator"]
    user_data = {"user_id": business_ctx["user_id"]}
    tenant_id = str(business_ctx["business_id"])

    pre_metrics = orchestrator.get_callback_metrics(user_data, tenant_id=tenant_id, window_minutes=60)
    if not pre_metrics.get("success"):
        return False, "❌ Не удалось получить pre-metrics для recovery."

    outbox_items = []
    for status_name in ("dlq", "retry"):
        listing = orchestrator.list_callback_outbox(
            user_data,
            tenant_id=tenant_id,
            status=status_name,
            limit=200,
            offset=0,
        )
        if not listing.get("success"):
            return False, f"❌ Не удалось загрузить outbox ({status_name})."
        outbox_items.extend(listing.get("items") or [])

    action_ids = []
    seen_action_ids = set()
    for item in outbox_items:
        action_id = str(item.get("action_id") or "").strip()
        if not action_id or action_id in seen_action_ids:
            continue
        seen_action_ids.add(action_id)
        action_ids.append(action_id)
    action_ids = action_ids[:2]

    before_snapshots = []
    for action_id in action_ids:
        snapshot = orchestrator.get_action_incident_snapshot(action_id, user_data)
        if snapshot.get("success"):
            before_snapshots.append(snapshot)

    replay = orchestrator.replay_callback_outbox(
        user_data,
        tenant_id=tenant_id,
        include_retry=True,
        limit=200,
    )
    if not replay.get("success"):
        return False, "❌ Recovery replay завершился ошибкой."

    dispatch = orchestrator.dispatch_callback_outbox_for_tenant(
        user_data,
        tenant_id=tenant_id,
        batch_size=200,
    )
    if not dispatch.get("success"):
        return False, "❌ Recovery dispatch завершился ошибкой."

    post_metrics = orchestrator.get_callback_metrics(user_data, tenant_id=tenant_id, window_minutes=60)
    if not post_metrics.get("success"):
        return False, "❌ Не удалось получить post-metrics для recovery."

    after_snapshots = []
    for action_id in action_ids:
        snapshot = orchestrator.get_action_incident_snapshot(action_id, user_data)
        if snapshot.get("success"):
            after_snapshots.append(snapshot)

    before_metric_summary = dict(pre_metrics.get("metrics") or {})
    after_metric_summary = dict(post_metrics.get("metrics") or {})
    lines = [
        "OpenClaw recovery report",
        f"Бизнес: {business_ctx['business_name']}",
        f"tenant_id: {tenant_id}",
        "",
        "Metrics before:",
        f"- sent={int(before_metric_summary.get('sent') or 0)} retry={int(before_metric_summary.get('retry') or 0)} dlq={int(before_metric_summary.get('dlq') or 0)} pending={int(before_metric_summary.get('pending') or 0)}",
        "Metrics after:",
        f"- sent={int(after_metric_summary.get('sent') or 0)} retry={int(after_metric_summary.get('retry') or 0)} dlq={int(after_metric_summary.get('dlq') or 0)} pending={int(after_metric_summary.get('pending') or 0)}",
        "",
        "Recovery result:",
        f"- replayed={int(replay.get('replayed_count') or 0)}",
        f"- dispatched sent={int(dispatch.get('sent') or 0)} retried={int(dispatch.get('retried') or 0)} dlq={int(dispatch.get('dlq') or 0)} picked={int(dispatch.get('picked') or 0)}",
    ]
    if before_snapshots:
        lines.extend(["", "Before:"])
        lines.extend(runtime["format_snapshot_digest"](item) for item in before_snapshots)
    if after_snapshots:
        lines.extend(["", "After:"])
        lines.extend(runtime["format_snapshot_digest"](item) for item in after_snapshots)
    report_text = "\n".join(lines)

    history_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        runtime["ensure_recovery_history"](cursor)
        cursor.execute(
            """
            INSERT INTO callback_recovery_history (
                id, tenant_id, triggered_by, send_telegram_report, include_retry,
                replayed_count, sent_count, retried_count, dlq_count, telegram_sent_count,
                action_ids_json, report_text
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                history_id,
                tenant_id,
                str(business_ctx["user_id"]),
                False,
                True,
                int(replay.get("replayed_count") or 0),
                int(dispatch.get("sent") or 0),
                int(dispatch.get("retried") or 0),
                int(dispatch.get("dlq") or 0),
                0,
                json.dumps(action_ids, ensure_ascii=False),
                report_text,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return True, f"✅ Recovery выполнен.\nHistory ID: {history_id}\n\n{report_text[:3000]}"


def _build_review_tone_markup() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"openclaw_review_tone_{tone_key}")]
        for tone_key, label in REVIEW_REPLY_TONES
    ]
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="openclaw_review_cancel")])
    return InlineKeyboardMarkup(keyboard)


def _perform_reviews_reply(business_ctx: dict, review_text: str, tone: str = "professional") -> tuple[bool, str]:
    review_text = str(review_text or "").strip()
    if not review_text:
        return False, "❌ Текст отзыва пустой."

    tone_map = {
        "friendly": "дружелюбный",
        "professional": "профессиональный",
        "premium": "премиум",
        "business": "деловой",
    }
    envelope = {
        "tenant_id": str(business_ctx["business_id"]),
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "actor": {
            "id": str(business_ctx["user_id"]),
            "type": "user",
            "role": "owner",
            "channel": "telegram",
            "telegram_id": str(business_ctx.get("telegram_id") or ""),
        },
        "capability": "reviews.reply",
        "approval": {"mode": "auto", "ttl_sec": 1800},
        "billing": {"tariff_id": "telegram-review-reply", "reserve_tokens": 1200},
        "payload": {
            "review": review_text,
            "tone": tone_map.get(str(tone or "").strip().lower(), "профессиональный"),
            "publish": False,
        },
    }
    result = OPENCLAW_ORCHESTRATOR.execute(
        envelope,
        {
            "user_id": str(business_ctx["user_id"]),
            "telegram_id": str(business_ctx.get("telegram_id") or ""),
            "is_superadmin": False,
        },
    )
    if not result.get("success") or result.get("status") == "failed":
        return False, f"❌ Не удалось сгенерировать ответ: {result.get('error') or 'неизвестная ошибка'}"

    action_id = str(result.get("action_id") or "")
    reply_payload = result.get("result") or {}
    reply_text = str((reply_payload or {}).get("reply") or "").strip()
    if not reply_text:
        return False, "❌ Ответ сгенерирован пустым."

    return True, "\n".join(
        [
            "💬 Ответ на отзыв",
            f"Бизнес: {business_ctx['business_name']}",
            f"Action: {action_id}",
            "",
            reply_text[:3000],
        ]
    )


def build_openclaw_menu(telegram_id: str) -> tuple[str, InlineKeyboardMarkup]:
    ctx = resolve_business_context(str(telegram_id))
    active_name = str((ctx or {}).get("business_name") or "Не выбран")
    active_id = str((ctx or {}).get("business_id") or "")
    text = (
        "🤖 OpenClaw Control\n\n"
        f"Активный бизнес: {active_name}\n"
        f"{active_id}\n\n"
        "Доступны быстрые действия:"
    )
    keyboard = [
        [InlineKeyboardButton("📊 Статус", callback_data="openclaw_status")],
        [InlineKeyboardButton("💬 Ответ на отзыв", callback_data="openclaw_review_start")],
        [InlineKeyboardButton("📤 Support snapshot", callback_data="openclaw_support_export")],
        [InlineKeyboardButton("🛠 Recovery report", callback_data="openclaw_recovery_report")],
        [InlineKeyboardButton("🏢 Выбрать бизнес", callback_data="openclaw_businesses")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


async def openclaw_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Краткий статус OpenClaw для привязанного бизнеса."""
    business_ctx = await _require_bound_business(update, context)
    if not business_ctx:
        return

    try:
        ok, text = _build_openclaw_status_text(business_ctx)
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка OpenClaw status: {e}")


async def businesses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список бизнесов и текущий активный tenant."""
    telegram_id = str(update.effective_user.id)
    items = list_user_businesses(telegram_id)
    if not items:
        await update.message.reply_text("❌ Бизнесы не найдены или аккаунт не привязан.")
        return

    current_ctx = resolve_business_context(telegram_id)
    current_id = str((current_ctx or {}).get("business_id") or "")
    lines = ["🏢 Ваши бизнесы:"]
    for item in items:
        marker = "✅" if item["id"] == current_id else "•"
        lines.append(f"{marker} {item['name']} — {item['id']}")
    lines.extend(
        [
            "",
            "Для переключения:",
            "/use_business <id или часть названия>",
        ]
    )
    await update.message.reply_text("\n".join(lines))


async def use_business_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрать активный бизнес для Telegram-команд."""
    query = " ".join(context.args or []).strip()
    if not query:
        await update.message.reply_text("❌ Укажите business_id или часть названия: /use_business <значение>")
        return
    ctx = resolve_business_context(str(update.effective_user.id), query)
    if not ctx or not ctx.get("business_id"):
        await update.message.reply_text("❌ Не удалось найти бизнес по этому значению.")
        return
    await update.message.reply_text(
        f"✅ Активный бизнес переключён:\n{ctx['business_name']}\n{ctx['business_id']}"
    )


async def support_export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Собрать support-export и отправить суперадмину."""
    business_ctx = await _require_bound_business(update, context)
    if not business_ctx:
        return

    await update.message.reply_text("⏳ Формирую support snapshot...")
    try:
        ok, text = _perform_support_export(business_ctx)
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка support export: {e}")


async def recovery_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнить recovery callback queue и вернуть отчёт в чат."""
    business_ctx = await _require_bound_business(update, context)
    if not business_ctx:
        return

    await update.message.reply_text("⏳ Выполняю recovery callback очереди...")
    try:
        ok, text = _perform_recovery_report(business_ctx)
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка recovery report: {e}")


async def reply_review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chat-first flow: сгенерировать ответ на отзыв."""
    business_ctx = await _require_bound_business(update, context)
    if not business_ctx:
        return

    review_text = " ".join(context.args or []).strip()
    state_ref = user_states.setdefault(str(update.effective_user.id), {})
    state_ref["active_business_id"] = str(business_ctx["business_id"])

    if review_text:
        state_ref.update(
            {
                "state": "waiting_review_reply_tone",
                "business_id": str(business_ctx["business_id"]),
                "pending_review_text": review_text,
            }
        )
        await update.message.reply_text(
            "Выберите тон ответа:",
            reply_markup=_build_review_tone_markup(),
        )
        return

    state_ref.update(
        {
            "state": "waiting_review_reply_text",
            "business_id": str(business_ctx["business_id"]),
        }
    )
    await update.message.reply_text(
        "💬 Отправьте текст отзыва. Затем я предложу выбрать тон и сгенерирую ответ."
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    args = context.args
    
    # Если передан токен привязки
    if args and len(args) > 0:
        bind_token = args[0]
        await handle_bind_token(update, context, bind_token, user_id)
        return
    
    # Проверяем, привязан ли аккаунт
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text(
            "👋 Привет! Для использования бота нужно связать ваш Telegram-аккаунт с аккаунтом на сайте.\n\n"
            "📱 Перейдите в личный кабинет на сайте и найдите раздел 'Telegram-бот' для получения кода привязки.\n\n"
            "Или отправьте команду:\n/start <ваш_код_привязки>"
        )
        return
    
    # Показываем главное меню
    await show_main_menu(update, context, user_id, db_user_id)

async def handle_bind_token(update: Update, context: ContextTypes.DEFAULT_TYPE, bind_token: str, telegram_id: str):
    """Обработка токена привязки"""
    try:
        # Вызываем API для проверки токена
        response = requests.post(
            f"{API_BASE_URL}/api/telegram/bind/verify",
            json={"token": bind_token, "telegram_id": telegram_id},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            await update.message.reply_text(
                f"✅ Аккаунт успешно привязан!\n\n"
                f"👤 Пользователь: {data.get('user', {}).get('name', 'Не указано')}\n"
                f"📧 Email: {data.get('user', {}).get('email', 'Не указано')}\n\n"
                f"Теперь вы можете использовать все функции бота!"
            )
            await show_main_menu(update, context, telegram_id, data.get('user', {}).get('id'))
        else:
            error_data = response.json()
            await update.message.reply_text(f"❌ Ошибка привязки: {error_data.get('error', 'Неизвестная ошибка')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка подключения к серверу: {str(e)}")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: str, db_user_id: str = None):
    """Показать главное меню"""
    if not db_user_id:
        db_user_id = get_user_id_from_telegram(telegram_id)
        if not db_user_id:
            await update.message.reply_text("❌ Аккаунт не привязан. Используйте /start <код_привязки>")
            return
    
    keyboard = [
        [InlineKeyboardButton("💰 Добавить транзакцию", callback_data="menu_transaction")],
        [InlineKeyboardButton("📊 Оптимизировать услуги", callback_data="menu_optimize")],
        [InlineKeyboardButton("⚙️ Настройки компании", callback_data="menu_settings")],
        [InlineKeyboardButton("📈 Статистика", callback_data="menu_stats")],
        [InlineKeyboardButton("🤖 OpenClaw Control", callback_data="menu_openclaw")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🏠 *Главное меню*\n\nВыберите действие:"
    
    if hasattr(update, 'message') and update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    data = query.data
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await query.edit_message_text("❌ Аккаунт не привязан. Используйте /start <код_привязки>")
        return
    
    if data == "menu_transaction":
        await show_business_selection(update, context, user_id, db_user_id, "transaction")
    elif data == "menu_optimize":
        await show_business_selection(update, context, user_id, db_user_id, "optimize")
    elif data == "menu_settings":
        await show_business_selection(update, context, user_id, db_user_id, "settings")
    elif data == "menu_openclaw":
        text, reply_markup = build_openclaw_menu(user_id)
        await query.edit_message_text(text, reply_markup=reply_markup)
    elif data == "menu_stats":
        await query.edit_message_text("📈 Статистика пока в разработке. Используйте личный кабинет на сайте.")
        await show_main_menu(update, context, user_id, db_user_id)
    elif data == "openclaw_status":
        business_ctx = resolve_business_context(user_id)
        if not business_ctx or not business_ctx.get("business_id"):
            await query.edit_message_text("❌ Для аккаунта не найден бизнес. Сначала создайте бизнес в LocalOS.")
            return
        ok, text = _build_openclaw_status_text(business_ctx)
        menu_text, reply_markup = build_openclaw_menu(user_id)
        await query.edit_message_text(
            f"{text}\n\n──────────\n\n{menu_text}",
            reply_markup=reply_markup,
        )
    elif data == "openclaw_review_start":
        business_ctx = resolve_business_context(user_id)
        if not business_ctx or not business_ctx.get("business_id"):
            await query.edit_message_text("❌ Для аккаунта не найден бизнес. Сначала создайте бизнес в LocalOS.")
            return
        state_ref = user_states.setdefault(user_id, {})
        state_ref.update(
            {
                "state": "waiting_review_reply_text",
                "business_id": str(business_ctx["business_id"]),
                "active_business_id": str(business_ctx["business_id"]),
            }
        )
        await query.edit_message_text(
            "💬 Отправьте текст отзыва следующим сообщением. Затем выберете тон и я сгенерирую ответ."
        )
    elif data == "openclaw_review_cancel":
        state_ref = user_states.setdefault(user_id, {})
        state_ref["state"] = "idle"
        state_ref.pop("pending_review_text", None)
        menu_text, reply_markup = build_openclaw_menu(user_id)
        await query.edit_message_text(
            f"❌ Генерация ответа отменена.\n\n{menu_text}",
            reply_markup=reply_markup,
        )
    elif data.startswith("openclaw_review_tone_"):
        state_ref = user_states.setdefault(user_id, {})
        review_text = str(state_ref.get("pending_review_text") or "").strip()
        business_ctx = resolve_business_context(user_id)
        if not business_ctx or not business_ctx.get("business_id"):
            await query.edit_message_text("❌ Для аккаунта не найден бизнес. Сначала создайте бизнес в LocalOS.")
            return
        if not review_text:
            await query.edit_message_text("❌ Не найден текст отзыва. Начните заново через кнопку 'Ответ на отзыв'.")
            return
        tone = data.replace("openclaw_review_tone_", "", 1)
        ok, text = _perform_reviews_reply(
            {
                **business_ctx,
                "telegram_id": user_id,
            },
            review_text,
            tone=tone,
        )
        state_ref["state"] = "idle"
        state_ref.pop("pending_review_text", None)
        menu_text, reply_markup = build_openclaw_menu(user_id)
        safe_text = text[:3200]
        await query.edit_message_text(
            f"{safe_text}\n\n──────────\n\n{menu_text}",
            reply_markup=reply_markup,
        )
    elif data == "openclaw_support_export":
        business_ctx = resolve_business_context(user_id)
        if not business_ctx or not business_ctx.get("business_id"):
            await query.edit_message_text("❌ Для аккаунта не найден бизнес. Сначала создайте бизнес в LocalOS.")
            return
        ok, text = _perform_support_export(business_ctx)
        menu_text, reply_markup = build_openclaw_menu(user_id)
        await query.edit_message_text(
            f"{text}\n\n──────────\n\n{menu_text}",
            reply_markup=reply_markup,
        )
    elif data == "openclaw_recovery_report":
        business_ctx = resolve_business_context(user_id)
        if not business_ctx or not business_ctx.get("business_id"):
            await query.edit_message_text("❌ Для аккаунта не найден бизнес. Сначала создайте бизнес в LocalOS.")
            return
        ok, text = _perform_recovery_report(business_ctx)
        menu_text, reply_markup = build_openclaw_menu(user_id)
        safe_text = text[:3200]
        await query.edit_message_text(
            f"{safe_text}\n\n──────────\n\n{menu_text}",
            reply_markup=reply_markup,
        )
    elif data == "openclaw_businesses":
        items = list_user_businesses(user_id)
        if not items:
            await query.edit_message_text("❌ Бизнесы не найдены или аккаунт не привязан.")
            return
        current_ctx = resolve_business_context(user_id)
        current_id = str((current_ctx or {}).get("business_id") or "")
        keyboard = []
        for item in items[:20]:
            marker = "✅ " if item["id"] == current_id else ""
            keyboard.append(
                [InlineKeyboardButton(f"{marker}{item['name']}", callback_data=f"openclaw_use_{item['id']}")]
            )
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_openclaw")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        lines = ["🏢 Выберите активный бизнес"]
        for item in items[:10]:
            marker = "✅" if item["id"] == current_id else "•"
            lines.append(f"{marker} {item['name']}")
        await query.edit_message_text("\n".join(lines), reply_markup=reply_markup)
    elif data.startswith("openclaw_use_"):
        business_id = data.replace("openclaw_use_", "", 1)
        ctx = resolve_business_context(user_id, business_id)
        if not ctx or not ctx.get("business_id"):
            await query.edit_message_text("❌ Не удалось переключить бизнес.")
            return
        text, reply_markup = build_openclaw_menu(user_id)
        await query.edit_message_text(
            f"✅ Активный бизнес переключён.\n\n{text}",
            reply_markup=reply_markup,
        )
    elif data.startswith("business_"):
        parts = data.split("_")
        if len(parts) >= 3:
            action = parts[1]  # transaction, optimize, settings
            business_id = "_".join(parts[2:])  # На случай если в ID есть подчеркивания
            user_states.setdefault(user_id, {})["active_business_id"] = business_id
            
            if action == "transaction":
                user_states[user_id] = {
                    'state': 'waiting_transaction',
                    'business_id': business_id,
                    'active_business_id': business_id,
                }
                await query.edit_message_text(
                    "💰 *Добавление транзакции*\n\n"
                    "Отправьте фото или текст — как вам удобнее:\n\n"
                    "📷 *Фото:* чека, документа или ваших записей (мобиль распознает)\n\n"
                    "📝 *Текст в формате:*\n"
                    "   Сумма: 1000\n"
                    "   Услуга: Стрижка мужская\n"
                    "   (или Услуги: Стрижка, Окрашивание)\n"
                    "   Мастер: Имя (опционально)\n"
                    "   Дата: YYYY-MM-DD (опционально)\n\n"
                    "Или /cancel для отмены",
                    parse_mode='Markdown'
                )
            elif action == "optimize":
                user_states[user_id] = {
                    'state': 'waiting_optimize',
                    'business_id': business_id,
                    'active_business_id': business_id,
                }
                await query.edit_message_text(
                    "📊 *Оптимизация услуг*\n\n"
                    "Отправьте:\n"
                    "1. 📷 Фото прайс-листа, или\n"
                    "2. 📝 Текст со списком услуг\n\n"
                    "Бот проанализирует и предложит SEO-оптимизированные названия.\n\n"
                    "Или /cancel для отмены",
                    parse_mode='Markdown'
                )
            elif action == "settings":
                await show_settings_menu(update, context, user_id, business_id)
    elif data.startswith("setting_"):
        parts = data.split("_")
        if len(parts) >= 3:
            setting_type = parts[1]  # name, address, maps, etc
            business_id = "_".join(parts[2:])
            user_states[user_id] = {
                'state': f'waiting_setting_{setting_type}',
                'business_id': business_id,
                'active_business_id': business_id,
            }
            
            setting_names = {
                'name': 'название компании',
                'address': 'адрес',
                'maps': 'ссылку на карты',
                'phone': 'телефон',
                'hours': 'часы работы'
            }
            
            await query.edit_message_text(
                f"⚙️ *Изменение {setting_names.get(setting_type, setting_type)}*\n\n"
                f"Отправьте новое значение:\n\n"
                f"Или /cancel для отмены",
                parse_mode='Markdown'
            )
    elif data == "back_to_menu":
        await show_main_menu(update, context, user_id, db_user_id)

async def show_business_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: str, db_user_id: str, action: str):
    """Показать выбор бизнеса"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM Businesses WHERE owner_id = %s", (db_user_id,))
    businesses = cursor.fetchall()
    conn.close()
    
    if not businesses:
        text = "У вас пока нет бизнесов. Создайте бизнес на сайте."
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(text)
        return
    
    keyboard = []
    for row in businesses:
        business_id = str(_row_get(row, "id", 0) or "")
        business_name = str(_row_get(row, "name", 1) or "Без названия")
        keyboard.append([InlineKeyboardButton(
            business_name, 
            callback_data=f"business_{action}_{business_id}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    action_names = {
        "transaction": "добавления транзакции",
        "optimize": "оптимизации услуг",
        "settings": "настроек компании"
    }
    
    text = f"Выберите бизнес для {action_names.get(action, action)}:"
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: str, business_id: str):
    """Показать меню настроек компании"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, address, working_hours FROM Businesses WHERE id = %s", (business_id,))
    business = cursor.fetchone()
    conn.close()
    
    if not business:
        await update.callback_query.edit_message_text("❌ Бизнес не найден")
        return
    
    keyboard = [
        [InlineKeyboardButton("📝 Название", callback_data=f"setting_name_{business_id}")],
        [InlineKeyboardButton("📍 Адрес", callback_data=f"setting_address_{business_id}")],
        [InlineKeyboardButton("🗺️ Ссылка на карты", callback_data=f"setting_maps_{business_id}")],
        [InlineKeyboardButton("📞 Телефон", callback_data=f"setting_phone_{business_id}")],
        [InlineKeyboardButton("🕐 Часы работы", callback_data=f"setting_hours_{business_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"⚙️ *Настройки компании*\n\n"
    text += f"📝 Название: {_row_get(business, 'name', 0) or 'Не указано'}\n"
    text += f"📍 Адрес: {_row_get(business, 'address', 1) or 'Не указано'}\n"
    text += f"🕐 Часы работы: {_row_get(business, 'working_hours', 2) or 'Не указано'}\n\n"
    text += "Выберите параметр для изменения:"
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото"""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_states:
        await update.message.reply_text("Используйте /start для начала работы")
        return
    
    state = user_states[user_id].get('state', '')
    
    if state == 'waiting_transaction':
        await handle_transaction_photo(update, context, user_id)
    elif state == 'waiting_optimize':
        await handle_optimize_photo(update, context, user_id)
    else:
        await update.message.reply_text("Неожиданное фото. Используйте /start для начала работы")

async def handle_transaction_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str):
    """Обработка фото транзакции"""
    business_id = user_states[user_id].get('business_id')
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text("❌ Аккаунт не привязан")
        return
    
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    await update.message.reply_text("⏳ Обрабатываю фото...")
    
    try:
        photo_bytes = await file.download_as_bytearray()
        image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        # Читаем промпт
        try:
            with open('prompts/transaction-analysis-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except:
            prompt = "Проанализируй фото и извлеки информацию о транзакции (дата, сумма, услуги, мастер)."
        
        result = analyze_screenshot_with_gigachat(
            image_base64, 
            prompt,
            business_id=business_id,
            user_id=db_user_id
        )
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Ошибка анализа: {result['error']}")
            return
        
        # Парсим результат
        analysis_result = json.loads(result) if isinstance(result, str) else result
        transactions = analysis_result.get('transactions', [])
        
        if not transactions:
            await update.message.reply_text("❌ Не удалось распознать транзакции на фото")
            return
        
        # Сохраняем транзакции
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем наличие полей (PG: information_schema)
        try:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'financialtransactions'
            """)
            columns = [str(_row_get(row, 'column_name', 0) or '') for row in cursor.fetchall()]
        except Exception:
            cursor.execute("PRAGMA table_info(FinancialTransactions)")
            columns = [str(_row_get(row, '', 1) or '') for row in cursor.fetchall()]
        has_master_id = 'master_id' in columns
        has_business_id = 'business_id' in columns
        
        saved_count = 0
        for trans in transactions:
            transaction_id = str(uuid.uuid4())
            
            master_id = None
            if trans.get('master_name') and has_master_id:
                cursor.execute("SELECT id FROM Masters WHERE name = %s AND business_id = %s LIMIT 1", 
                             (trans['master_name'], business_id))
                master_row = cursor.fetchone()
                if master_row:
                    master_id = _row_get(master_row, 'id', 0)
            
            if has_master_id and has_business_id:
                cursor.execute("""
                    INSERT INTO FinancialTransactions 
                    (id, user_id, business_id, transaction_date, amount, client_type, services, notes, master_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id, db_user_id, business_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0), trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])), trans.get('notes', ''),
                    master_id
                ))
            elif has_master_id:
                cursor.execute("""
                    INSERT INTO FinancialTransactions 
                    (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id, db_user_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0), trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])), trans.get('notes', ''),
                    master_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO FinancialTransactions 
                    (id, user_id, transaction_date, amount, client_type, services, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id, db_user_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0), trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])), trans.get('notes', '')
                ))
            saved_count += 1
            
            # Добавляем услуги из транзакции в UserServices, если их там еще нет
            services_list = trans.get('services', [])
            if services_list and business_id:
                # Проверяем наличие поля business_id в UserServices (PG: information_schema)
                try:
                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'userservices'
                    """)
                    service_columns = [str(_row_get(row, 'column_name', 0) or '') for row in cursor.fetchall()]
                except Exception:
                    cursor.execute("PRAGMA table_info(UserServices)")
                    service_columns = [str(_row_get(row, '', 1) or '') for row in cursor.fetchall()]
                has_business_id_in_services = 'business_id' in service_columns
                
                for service_name in services_list:
                    if not service_name or not isinstance(service_name, str):
                        continue
                    
                    # Проверяем, есть ли уже такая услуга для этого бизнеса
                    if has_business_id_in_services:
                        cursor.execute("""
                            SELECT id FROM UserServices 
                            WHERE business_id = %s AND name = %s AND user_id = %s
                            LIMIT 1
                        """, (business_id, service_name.strip(), db_user_id))
                    else:
                        cursor.execute("""
                            SELECT id FROM UserServices 
                            WHERE name = %s AND user_id = %s
                            LIMIT 1
                        """, (service_name.strip(), db_user_id))
                    
                    existing_service = cursor.fetchone()
                    
                    if not existing_service:
                        # Добавляем новую услугу
                        service_id = str(uuid.uuid4())
                        if has_business_id_in_services:
                            cursor.execute("""
                                INSERT INTO UserServices 
                                (id, user_id, business_id, category, name, description, keywords, price, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                            """, (service_id, db_user_id, business_id, 'Общие услуги', service_name.strip(), '', '[]', ''))
                        else:
                            cursor.execute("""
                                INSERT INTO UserServices 
                                (id, user_id, category, name, description, keywords, price, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                            """, (service_id, db_user_id, 'Общие услуги', service_name.strip(), '', '[]', ''))
        
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Успешно добавлено {saved_count} транзакций!\n\n"
            f"Используйте /start для возврата в меню"
        )
        
        user_states[user_id] = {'state': 'idle'}
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обработки фото: {str(e)}")

async def handle_optimize_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str):
    """Обработка фото для оптимизации"""
    business_id = user_states[user_id].get('business_id')
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text("❌ Аккаунт не привязан")
        return
    
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    await update.message.reply_text("⏳ Анализирую прайс-лист...")
    
    try:
        photo_bytes = await file.download_as_bytearray()
        image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        # Читаем промпт оптимизации
        try:
            with open('prompts/seo-optimization-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except:
            prompt = "Оптимизируй прайс-лист услуг для локального SEO."
        
        result = analyze_screenshot_with_gigachat(
            image_base64, 
            prompt, 
            task_type="service_optimization",
            business_id=business_id,
            user_id=db_user_id
        )
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Ошибка анализа: {result['error']}")
            return
        
        # Парсим результат
        analysis_result = json.loads(result) if isinstance(result, str) else result
        services = analysis_result.get('services', [])
        
        if not services:
            await update.message.reply_text("❌ Не удалось распознать услуги на фото")
            return
        
        # Формируем ответ
        text = "📊 *Результаты оптимизации:*\n\n"
        for i, service in enumerate(services[:10], 1):  # Показываем первые 10
            text += f"{i}. *{service.get('original_name', 'N/A')}*\n"
            text += f"   → {service.get('optimized_name', 'N/A')}\n\n"
        
        if len(services) > 10:
            text += f"\n... и ещё {len(services) - 10} услуг\n"
        
        text += "\n💡 Полные результаты доступны в личном кабинете на сайте."
        
        await update.message.reply_text(text, parse_mode='Markdown')
        user_states[user_id] = {'state': 'idle'}
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обработки фото: {str(e)}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    # Обработка команды /cancel
    if text.startswith('/cancel'):
        user_states[user_id] = {'state': 'idle'}
        await update.message.reply_text("❌ Операция отменена. Используйте /start для возврата в меню.")
        return
    
    if user_id not in user_states:
        await update.message.reply_text("Используйте /start для начала работы")
        return
    
    state = user_states[user_id].get('state', '')
    
    if state == 'waiting_transaction':
        await handle_transaction_text(update, context, user_id, text)
    elif state == 'waiting_optimize':
        await handle_optimize_text(update, context, user_id, text)
    elif state == 'waiting_review_reply_text':
        await handle_review_reply_text(update, context, user_id, text)
    elif state.startswith('waiting_setting_'):
        await handle_setting_text(update, context, user_id, text, state)
    else:
        await update.message.reply_text("Неожиданное сообщение. Используйте /start для начала работы")


async def handle_review_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str):
    review_text = str(text or "").strip()
    if not review_text:
        await update.message.reply_text("❌ Текст отзыва пустой. Отправьте нормальный текст.")
        return

    state_ref = user_states.setdefault(user_id, {})
    state_ref["state"] = "waiting_review_reply_tone"
    state_ref["pending_review_text"] = review_text
    await update.message.reply_text(
        "Выберите тон ответа:",
        reply_markup=_build_review_tone_markup(),
    )

async def handle_transaction_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str):
    """Обработка текста транзакции"""
    business_id = user_states[user_id].get('business_id')
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text("❌ Аккаунт не привязан")
        return
    
    if not business_id:
        await update.message.reply_text("❌ Бизнес не выбран. Пожалуйста, выберите бизнес в меню /start")
        return
    
    # Парсим текст
    transaction_data = {
        'transaction_date': datetime.now().strftime('%Y-%m-%d'),
        'amount': 0,
        'client_type': 'new',
        'services': [],
        'master_name': None,
        'notes': ''
    }
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if 'дата' in key:
                transaction_data['transaction_date'] = value
            elif 'сумма' in key:
                try:
                    transaction_data['amount'] = float(value.replace('₽', '').replace('руб', '').strip())
                except:
                    pass
            elif 'услуги' in key or 'услуга' in key:
                # Поддерживаем как единственное, так и множественное число
                if ',' in value:
                    transaction_data['services'] = [s.strip() for s in value.split(',')]
                else:
                    # Если одна услуга без запятых
                    transaction_data['services'] = [value.strip()]
            elif 'мастер' in key:
                transaction_data['master_name'] = value
            elif 'тип' in key and 'клиент' in key:
                transaction_data['client_type'] = value if value in ['new', 'returning'] else 'new'
            else:
                transaction_data['notes'] += line + ' '
        else:
            # Строка без двоеточия - возможно, это дата в свободном формате
            # Проверяем, содержит ли строка признаки даты
            line_lower = line.lower()
            months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                     'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
                     'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                     'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
            if any(month in line_lower for month in months) and any(char.isdigit() for char in line):
                # Это похоже на дату - сохраняем в notes, но не парсим
                transaction_data['notes'] += line + ' '
    
    if transaction_data['amount'] == 0:
        await update.message.reply_text("❌ Пожалуйста, укажите сумму транзакции")
        return
    
    # Логирование для отладки
    print(f"[DEBUG] handle_transaction_text: business_id={business_id}, services={transaction_data['services']}, amount={transaction_data['amount']}")
    
    # Сохраняем транзакцию
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем наличие полей (PG: information_schema)
    try:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'financialtransactions'
        """)
        columns = [str(_row_get(row, 'column_name', 0) or '') for row in cursor.fetchall()]
    except Exception:
        cursor.execute("PRAGMA table_info(FinancialTransactions)")
        columns = [str(_row_get(row, '', 1) or '') for row in cursor.fetchall()]
    columns_set = set(columns)
    has_master_id = 'master_id' in columns_set
    has_business_id = 'business_id' in columns_set
    has_user_id = 'user_id' in columns_set
    has_services_col = 'services' in columns_set
    has_notes_col = 'notes' in columns_set
    has_transaction_date_col = 'transaction_date' in columns_set
    has_date_col = 'date' in columns_set
    has_description_col = 'description' in columns_set
    has_transaction_type_col = 'transaction_type' in columns_set
    
    transaction_id = str(uuid.uuid4())
    
    master_id = None
    if transaction_data.get('master_name') and has_master_id:
        cursor.execute("SELECT id FROM Masters WHERE name = %s AND business_id = %s LIMIT 1", 
                     (transaction_data['master_name'], business_id))
        master_row = cursor.fetchone()
        if master_row:
            master_id = _row_get(master_row, 'id', 0)
    
    # Формируем описание, если нет колонок services/notes
    description_parts = []
    if transaction_data.get('services'):
        description_parts.append("Услуги: " + ", ".join(transaction_data['services']))
    if transaction_data.get('master_name'):
        description_parts.append(f"Мастер: {transaction_data['master_name']}")
    if transaction_data.get('notes'):
        description_parts.append(f"Заметки: {transaction_data['notes'].strip()}")
    description_text = "; ".join(description_parts) if description_parts else ""
    
    # Значения по умолчанию
    transaction_type_value = 'income' if has_transaction_type_col else None
    date_value = transaction_data['transaction_date'] if has_date_col else None
    
    # Формируем динамический INSERT под доступные колонки
    insert_columns = ['id']
    insert_values = [transaction_id]
    
    if has_user_id:
        insert_columns.append('user_id')
        insert_values.append(db_user_id)
    if has_business_id:
        insert_columns.append('business_id')
        insert_values.append(business_id)
    if has_transaction_date_col:
        insert_columns.append('transaction_date')
        insert_values.append(transaction_data['transaction_date'])
    elif has_date_col and date_value:
        insert_columns.append('date')
        insert_values.append(date_value)
    
    insert_columns.append('amount')
    insert_values.append(transaction_data['amount'])
    
    insert_columns.append('client_type')
    insert_values.append(transaction_data['client_type'])
    
    if has_services_col:
        insert_columns.append('services')
        insert_values.append(json.dumps(transaction_data['services']))
    if has_notes_col:
        insert_columns.append('notes')
        insert_values.append(transaction_data['notes'])
    if has_description_col:
        insert_columns.append('description')
        insert_values.append(description_text)
    if has_transaction_type_col and transaction_type_value:
        insert_columns.append('transaction_type')
        insert_values.append(transaction_type_value)
    if has_master_id:
        insert_columns.append('master_id')
        insert_values.append(master_id)
    
    placeholders = ",".join(["%s"] * len(insert_columns))
    sql = f"INSERT INTO FinancialTransactions ({', '.join(insert_columns)}) VALUES ({placeholders})"
    cursor.execute(sql, insert_values)
    
    # Добавляем услуги из транзакции в UserServices, если их там еще нет
    services_list = transaction_data.get('services', [])
    added_services_count = 0
    
    if services_list and business_id:
        # Проверяем наличие поля business_id в UserServices (PG: information_schema)
        try:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'userservices'
            """)
            service_columns = [str(_row_get(row, 'column_name', 0) or '') for row in cursor.fetchall()]
        except Exception:
            cursor.execute("PRAGMA table_info(UserServices)")
            service_columns = [str(_row_get(row, '', 1) or '') for row in cursor.fetchall()]
        has_business_id_in_services = 'business_id' in service_columns
        
        print(f"[DEBUG] Adding services: {services_list}, business_id={business_id}, has_business_id_in_services={has_business_id_in_services}")
        
        for service_name in services_list:
            if not service_name or not isinstance(service_name, str):
                continue
            
            service_name_clean = service_name.strip()
            if not service_name_clean:
                continue
            
            # Проверяем, есть ли уже такая услуга для этого бизнеса
            if has_business_id_in_services:
                cursor.execute("""
                    SELECT id FROM UserServices 
                    WHERE business_id = %s AND name = %s AND user_id = %s
                    LIMIT 1
                """, (business_id, service_name_clean, db_user_id))
            else:
                cursor.execute("""
                    SELECT id FROM UserServices 
                    WHERE name = %s AND user_id = %s
                    LIMIT 1
                """, (service_name_clean, db_user_id))
            
            existing_service = cursor.fetchone()
            
            if not existing_service:
                # Добавляем новую услугу
                service_id = str(uuid.uuid4())
                if has_business_id_in_services:
                    cursor.execute("""
                        INSERT INTO UserServices 
                        (id, user_id, business_id, category, name, description, keywords, price, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (service_id, db_user_id, business_id, 'Общие услуги', service_name_clean, '', '[]', ''))
                    print(f"[DEBUG] Added service: {service_name_clean} for business_id={business_id}")
                else:
                    cursor.execute("""
                        INSERT INTO UserServices 
                        (id, user_id, category, name, description, keywords, price, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (service_id, db_user_id, 'Общие услуги', service_name_clean, '', '[]', ''))
                    print(f"[DEBUG] Added service: {service_name_clean} (no business_id)")
                added_services_count += 1
            else:
                print(f"[DEBUG] Service already exists: {service_name_clean}")
    else:
        print(f"[DEBUG] No services to add: services_list={services_list}, business_id={business_id}")
    
    conn.commit()
    conn.close()
    
    services_msg = ""
    if added_services_count > 0:
        services_msg = f"\n\n➕ Добавлено новых услуг: {added_services_count}"
    
    await update.message.reply_text(
        f"✅ Транзакция добавлена!{services_msg}\n\n"
        f"💰 Сумма: {transaction_data['amount']} ₽\n"
        f"📅 Дата: {transaction_data['transaction_date']}\n\n"
        f"Используйте /start для возврата в меню"
    )
    
    user_states[user_id] = {'state': 'idle'}

async def handle_optimize_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str):
    """Обработка текста для оптимизации"""
    business_id = user_states[user_id].get('business_id')
    db_user_id = get_user_id_from_telegram(user_id)

    if not db_user_id:
        await update.message.reply_text("❌ Аккаунт не привязан")
        return

    await update.message.reply_text("⏳ Анализирую услуги...")
    
    try:
        # Читаем промпт
        try:
            with open('prompts/seo-optimization-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except:
            prompt = "Оптимизируй список услуг для локального SEO."
        
        full_prompt = f"{prompt}\n\nСписок услуг:\n{text}"
        result = analyze_text_with_gigachat(
            full_prompt, 
            task_type="service_optimization",
            business_id=business_id,
            user_id=db_user_id
        )
        
        if 'error' in result:
            await update.message.reply_text(f"❌ Ошибка анализа: {result['error']}")
            return
        
        # Парсим результат
        analysis_result = json.loads(result) if isinstance(result, str) else result
        services = analysis_result.get('services', [])
        
        if not services:
            await update.message.reply_text("❌ Не удалось распознать услуги")
            return
        
        # Формируем ответ
        response_text = "📊 *Результаты оптимизации:*\n\n"
        for i, service in enumerate(services[:10], 1):
            response_text += f"{i}. *{service.get('original_name', 'N/A')}*\n"
            response_text += f"   → {service.get('optimized_name', 'N/A')}\n\n"
        
        if len(services) > 10:
            response_text += f"\n... и ещё {len(services) - 10} услуг\n"
        
        response_text += "\n💡 Полные результаты доступны в личном кабинете на сайте."
        
        await update.message.reply_text(response_text, parse_mode='Markdown')
        user_states[user_id] = {'state': 'idle'}
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обработки: {str(e)}")

async def handle_setting_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str, state: str):
    """Обработка изменения настройки компании"""
    business_id = user_states[user_id].get('business_id')
    setting_type = state.replace('waiting_setting_', '')
    db_user_id = get_user_id_from_telegram(user_id)
    
    if not db_user_id:
        await update.message.reply_text("❌ Аккаунт не привязан")
        return
    
    try:
        # Обновляем через API
        update_data = {}
        if setting_type == 'name':
            update_data['businessName'] = text
        elif setting_type == 'address':
            update_data['address'] = text
        elif setting_type == 'maps':
            update_data['yandexUrl'] = text
        elif setting_type == 'phone':
            update_data['phone'] = text
        elif setting_type == 'hours':
            update_data['workingHours'] = text
        
        # Получаем токен сессии для API (упрощенная версия - напрямую в БД)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if setting_type in ['name', 'address', 'hours']:
            field_map = {
                'name': 'name',
                'address': 'address',
                'hours': 'working_hours'
            }
            field = field_map.get(setting_type)
            if field:
                cursor.execute(f"UPDATE Businesses SET {field} = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", 
                             (text, business_id))
                conn.commit()
        
        conn.close()
        
        setting_names = {
            'name': 'название',
            'address': 'адрес',
            'maps': 'ссылку на карты',
            'phone': 'телефон',
            'hours': 'часы работы'
        }
        
        await update.message.reply_text(
            f"✅ {setting_names.get(setting_type, setting_type).capitalize()} успешно обновлено!\n\n"
            f"Используйте /start для возврата в меню"
        )
        
        user_states[user_id] = {'state': 'idle'}
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка обновления: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
🤖 *BeautyBot Telegram-бот*

*Команды:*
/start - Главное меню
/help - Справка
/cancel - Отменить текущую операцию
/businesses - Показать ваши бизнесы
/use_business - Выбрать активный бизнес
/status - Статус OpenClaw по вашему бизнесу
/reply_review - Сгенерировать ответ на отзыв
/support_export - Отправить support snapshot суперадмину
/recovery_report - Выполнить recovery callback-очереди

*Функции:*
💰 Добавление транзакций (фото/текст)
📊 Оптимизация услуг для SEO
⚙️ Настройки компании
📈 Статистика (в разработке)

*Поддержка:*
Если возникли проблемы, обратитесь в поддержку через личный кабинет на сайте.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[str(update.effective_user.id)] = {'state': 'idle'}
    await update.message.reply_text("❌ Операция отменена")

def main():
    """Запуск бота"""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️  TELEGRAM_BOT_TOKEN не установлен. Бот не будет запущен.")
        print("💡 Установите токен: export TELEGRAM_BOT_TOKEN='ваш_токен'")
        print("💡 Или добавьте в .env файл: TELEGRAM_BOT_TOKEN=ваш_токен")
        return
    
    try:
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(CommandHandler("businesses", businesses_command))
        application.add_handler(CommandHandler("use_business", use_business_command))
        application.add_handler(CommandHandler("status", openclaw_status_command))
        application.add_handler(CommandHandler("reply_review", reply_review_command))
        application.add_handler(CommandHandler("support_export", support_export_command))
        application.add_handler(CommandHandler("recovery_report", recovery_report_command))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        print("🤖 Telegram-бот запущен...")
        print(f"📡 API Base URL: {API_BASE_URL}")
        print("✅ Бот готов к работе. Ожидаю сообщения...")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        print(f"💡 Проверьте:")
        print(f"   1. Правильность токена TELEGRAM_BOT_TOKEN")
        print(f"   2. Установлена ли зависимость: pip install python-telegram-bot>=20.0")
        print(f"   3. Доступность интернета для подключения к Telegram API")
        raise

if __name__ == "__main__":
    main()
