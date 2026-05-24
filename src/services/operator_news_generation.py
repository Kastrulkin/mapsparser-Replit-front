from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Callable

from services.gigachat_client import analyze_text_with_gigachat
from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_manual_review import BILLING_URL, _build_ui_action
from services.operator_paid_preflight import build_paid_action_preflight


NEWS_GENERATE_ACTION_KEY = "news_generate"
NEWS_GENERATE_ESTIMATED_CREDITS = 1
NEWS_GENERATE_ACTUAL_CREDITS = 1
NEWS_DRAFTS_URL = "/dashboard/content-plan"


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    description = getattr(cursor, "description", None) or []
    columns = [col[0] for col in description]
    if isinstance(row, (list, tuple)) and columns:
        return {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
    return None


def classify_news_generate_intent(message: Any) -> bool:
    text = _clean_text(message).lower()
    if not text:
        return False
    if "новост" not in text:
        return False
    if "соцсет" in text or "пост" in text:
        return False
    return "сгенер" in text or "подготов" in text or "напиш" in text or "создай" in text


def extract_news_source_text(message: Any) -> str:
    text = _clean_text(message)
    if not text:
        return ""
    lowered = text.lower()
    markers = (
        "сгенерируй новость:",
        "подготовь новость:",
        "напиши новость:",
        "создай новость:",
        "новость:",
    )
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0:
            return text[index + len(marker):].strip()
    return text


def _extract_json_candidate(value: str) -> Any:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            return None
    return None


def _normalize_news_text(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    parsed = _extract_json_candidate(text)
    if isinstance(parsed, dict):
        for key in ("news", "text", "draft"):
            if key in parsed:
                text = _clean_text(parsed.get(key))
                break
    return text.replace('\\"', '"').replace("\\n", "\n").strip()


def _table_has_column(cursor: Any, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return bool(cursor.fetchone())


def _load_business_context(cursor: Any, business_id: str) -> dict[str, Any]:
    select_columns = ["id"]
    for column_name in ("name", "business_name", "description", "address"):
        if _table_has_column(cursor, "businesses", column_name):
            select_columns.append(column_name)
    cursor.execute(
        f"""
        SELECT {", ".join(select_columns)}
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    return _row_to_dict(cursor, cursor.fetchone()) or {"id": business_id}


def _ensure_usernews_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usernews (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            service_id TEXT,
            source_text TEXT,
            generated_text TEXT NOT NULL,
            approved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS business_id TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS original_generated_text TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS edited_before_approve BOOLEAN DEFAULT FALSE")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_key TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_version TEXT")


def _build_news_prompt(*, source_text: str, business: dict[str, Any]) -> str:
    business_name = _clean_text(business.get("name") or business.get("business_name") or "локального бизнеса")
    business_description = _clean_text(business.get("description"))
    return "\n".join(
        [
            "Ты - редактор LocalOS для локального бизнеса.",
            "Подготовь короткую профессиональную новость для публикации в карточке компании или локальном канале.",
            "Пиши на русском. Без эмодзи, без выдуманных фактов, без обещаний скидок, если их нет в исходных данных.",
            "Структура: заголовок одной строкой, затем 1-2 коротких абзаца.",
            "Верни СТРОГО JSON: {\"news\": \"текст новости\"}.",
            "",
            f"Бизнес: {business_name}",
            f"Описание бизнеса: {business_description or 'нет данных'}",
            "",
            f"Исходная информация:\n{source_text[:1500]}",
        ]
    )


def _default_news_generator(prompt: str, *, business_id: str, user_id: str) -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="news_generation",
        business_id=business_id,
        user_id=user_id,
    )


def _insert_news_draft(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    source_text: str,
    generated_text: str,
    prompt_key: str = "operator_news_generate",
) -> dict[str, Any]:
    _ensure_usernews_table(cursor)
    news_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO usernews (
            id, user_id, business_id, service_id, source_text, generated_text,
            original_generated_text, edited_before_approve, prompt_key, prompt_version,
            approved, created_at, updated_at
        )
        VALUES (%s, %s, %s, NULL, %s, %s, %s, FALSE, %s, 'v1', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING id, user_id, business_id, source_text, generated_text, approved, created_at, updated_at
        """,
        (
            news_id,
            user_id,
            business_id,
            source_text,
            generated_text,
            generated_text,
            prompt_key,
        ),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    if not row:
        row = {
            "id": news_id,
            "user_id": user_id,
            "business_id": business_id,
            "source_text": source_text,
            "generated_text": generated_text,
            "approved": 0,
        }
    return row


def generate_news_draft_from_operator(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    message: Any,
    channel: str = "web",
    news_generator: Callable[..., str] | None = None,
) -> dict[str, Any]:
    source_text = extract_news_source_text(message)
    if len(source_text) < 8:
        return {
            "status": "blocked",
            "intent": NEWS_GENERATE_ACTION_KEY,
            "chat_response": "Пришлите тему или исходную информацию, чтобы я подготовил новость.",
            "news_text": "",
            "blocked_reasons": ["news_source_text_required"],
        }

    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=NEWS_GENERATE_ACTION_KEY,
        estimated_credits=NEWS_GENERATE_ESTIMATED_CREDITS,
    )
    if preflight.get("status") != "ready":
        blocked = list(preflight.get("blocked_reasons") or [])
        if "insufficient_balance" in blocked:
            return {
                "status": "blocked",
                "intent": NEWS_GENERATE_ACTION_KEY,
                "chat_response": "Недостаточно кредитов для генерации новости. Пополните счёт или выберите тариф: /dashboard/billing",
                "billing_url": BILLING_URL,
                "preflight": preflight,
                "news_text": "",
                "charged_credits": 0,
                "credit_charged": False,
                "blocked_reasons": blocked,
                "ui_actions": [_build_ui_action("open_billing", "Пополнить счёт", href=BILLING_URL)],
            }
        return {
            "status": "blocked",
            "intent": NEWS_GENERATE_ACTION_KEY,
            "chat_response": "Не удалось запустить генерацию новости. Причины: " + ", ".join(blocked),
            "preflight": preflight,
            "news_text": "",
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
        }

    idempotency_key = _stable_id("operator_news_generate", business_id, user_id, source_text)
    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=NEWS_GENERATE_ACTION_KEY,
        estimated_credits=NEWS_GENERATE_ESTIMATED_CREDITS,
        idempotency_key=idempotency_key,
        metadata={"source": "operator_news_generate", "channel": channel},
    )
    if reservation.get("status") != "reserved":
        blocked = list(reservation.get("blocked_reasons") or [])
        return {
            "status": "blocked",
            "intent": NEWS_GENERATE_ACTION_KEY,
            "chat_response": "Не удалось зарезервировать кредиты для генерации новости. Причины: " + ", ".join(blocked),
            "preflight": preflight,
            "reservation_result": reservation,
            "news_text": "",
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
        }

    business = _load_business_context(cursor, business_id)
    generator = news_generator or _default_news_generator
    try:
        generated = generator(
            _build_news_prompt(source_text=source_text, business=business),
            business_id=business_id,
            user_id=user_id,
        )
        news_text = _normalize_news_text(generated)
    except Exception:
        release = finalize_reserved_action_credits(
            cursor,
            reservation_id=_clean_text(reservation.get("reservation_id")),
            business_id=business_id,
            user_id=user_id,
            finalization_mode="release",
            external_id=idempotency_key,
        )
        return {
            "status": "blocked",
            "intent": NEWS_GENERATE_ACTION_KEY,
            "chat_response": "Новость не удалось сгенерировать. Кредиты не списаны.",
            "preflight": preflight,
            "reservation_result": reservation,
            "finalization_result": release,
            "news_text": "",
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": ["news_generation_failed"],
        }

    if not news_text:
        release = finalize_reserved_action_credits(
            cursor,
            reservation_id=_clean_text(reservation.get("reservation_id")),
            business_id=business_id,
            user_id=user_id,
            finalization_mode="release",
            external_id=idempotency_key,
        )
        return {
            "status": "blocked",
            "intent": NEWS_GENERATE_ACTION_KEY,
            "chat_response": "Модель вернула пустую новость. Кредиты не списаны.",
            "preflight": preflight,
            "reservation_result": reservation,
            "finalization_result": release,
            "news_text": "",
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": ["empty_generated_news"],
        }

    news_draft = _insert_news_draft(
        cursor,
        business_id=business_id,
        user_id=user_id,
        source_text=source_text,
        generated_text=news_text,
    )
    finalization = finalize_reserved_action_credits(
        cursor,
        reservation_id=_clean_text(reservation.get("reservation_id")),
        business_id=business_id,
        user_id=user_id,
        actual_credits=NEWS_GENERATE_ACTUAL_CREDITS,
        finalization_mode="charge",
        external_id=idempotency_key,
    )
    charged = int(finalization.get("charge_credits") or 0)
    response_lines = [
        "Подготовил черновик новости.",
        "",
        news_text,
        "",
        f"Списано кредитов: {charged}.",
        "Публикация остаётся ручной: скопируйте текст и разместите его в нужном канале.",
    ]
    return {
        "status": "completed",
        "intent": NEWS_GENERATE_ACTION_KEY,
        "news_draft": news_draft,
        "news_text": news_text,
        "preflight": preflight,
        "reservation_result": reservation,
        "finalization_result": finalization,
        "charged_credits": charged,
        "credit_charged": finalization.get("status") == "charged",
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "ui_actions": [
            _build_ui_action("copy_news", "Скопировать новость", payload={"text": news_text}),
            _build_ui_action("open_news_drafts", "Открыть черновики", href=NEWS_DRAFTS_URL),
        ],
        "chat_response": "\n".join(response_lines),
        "blocked_reasons": [],
    }
