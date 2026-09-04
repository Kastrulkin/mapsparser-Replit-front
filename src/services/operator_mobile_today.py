from __future__ import annotations

import json
import re
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from services.community_pulse_sources import (
    industry_label,
    load_business_industry_keys,
    load_default_industry_sources,
)
from services.community_topic_trends import load_topic_trends
from services.growth_overview_service import load_growth_overview, load_growth_overview_for_scope
from services.operator_scope_summary import build_operator_scope_summary
from services.lead_journey_service import journey_enabled, serialize_action


PLATFORM_RADAR_BUSINESS_ID = "localos-platform-telegram-radar"
PUBLIC_RADAR_VISIBILITIES = {"platform_public", "public"}

TOPIC_STOPWORDS = {
    "будет", "были", "было", "быть", "ваш", "ведь", "всего", "где", "для", "если",
    "есть", "ещё", "или", "как", "когда", "которые", "можно", "надо", "наш", "него",
    "очень", "пока", "после", "почему", "при", "про", "свой", "так", "также", "только",
    "уже", "чтобы", "этого", "этой", "это", "business", "localos", "telegram",
}

STORY_FACT_CONTENT_TYPES = {
    "story", "child_story", "author_story", "brand_story", "family_tradition",
    "case", "before_after", "photo_report", "review_social_proof",
}
STORY_FACTS_QUESTION = (
    "Опишите реальную историю: что было в начале, что произошло и что изменилось. "
    "Имя можно не указывать."
)


def _needs_business_history(story: Any, context: Any) -> bool:
    story_text = " ".join(str(story or "").split())
    context_payload = _parse_json(context)
    completeness = (
        context_payload.get("profile_completeness")
        if isinstance(context_payload.get("profile_completeness"), dict)
        else {}
    )
    if completeness.get("ready") is True and len(story_text) >= 80:
        return False
    generic_markers = ("представляет", "компания занимается", "мы оказываем услуги")
    return len(story_text) < 80 or any(marker in story_text.lower() for marker in generic_markers)


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        try:
            return dict(value)
        except Exception:
            return {}
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    if isinstance(value, (list, tuple)):
        return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}
    return {}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    text = str(value or "").strip()
    return text or None


def _parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _requires_story_facts(item: dict[str, Any], metadata: dict[str, Any]) -> bool:
    stored_brief = metadata.get("content_brief_v1") if isinstance(metadata.get("content_brief_v1"), dict) else {}
    if stored_brief.get("requires_story_facts") is True:
        return True
    content_type = str(item.get("content_type") or "").strip().lower()
    if content_type in STORY_FACT_CONTENT_TYPES:
        return True
    description = " ".join(
        str(item.get(field) or "").strip().lower()
        for field in ("theme", "goal", "source_kind", "source_ref")
    )
    return any(marker in description for marker in ("истори", "кейс", "до/после", "до и после", "фотоотчёт"))


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    return bool(_row(cursor, cursor.fetchone()).get("table_ref"))


def _business_filter(scope: dict[str, Any]) -> tuple[bool, list[str]]:
    return (
        str(scope.get("kind") or "business") == "platform",
        [str(item) for item in scope.get("business_ids") or [] if str(item)],
    )


def _screen_from_url(value: Any) -> str:
    url = str(value or "").lower()
    if "review" in url:
        return "reviews"
    if "content" in url:
        return "content"
    if "partnership" in url or "prospecting" in url:
        return "partnerships"
    if "agent" in url or "automation" in url:
        return "agents"
    if "average-ticket" in url or "finance" in url:
        return "finance"
    if "card" in url or "profile" in url or "map" in url:
        return "cards"
    if "progress" in url:
        return "progress"
    return "tasks"


def _attention_screen(item: dict[str, Any]) -> str:
    key = str(item.get("id") or item.get("kind") or "").lower()
    if "review" in key:
        return "reviews"
    if "content" in key or "post" in key:
        return "content"
    if "outreach" in key or "partner" in key:
        return "partnerships"
    if "map" in key or "card" in key or "stale" in key:
        return "cards"
    return "tasks"


def select_daily_focus(
    summary: dict[str, Any],
    progress: dict[str, Any] | None,
    scope: dict[str, Any],
    content_action: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    attention = summary.get("primary_action") if isinstance(summary.get("primary_action"), dict) else None
    growth = progress.get("focus_action") if isinstance(progress, dict) and isinstance(progress.get("focus_action"), dict) else None
    attention_score = 0
    if attention:
        severity = str(attention.get("severity") or "low").lower()
        attention_score = {"critical": 140, "high": 120, "medium": 85, "low": 20}.get(severity, 20)
        if int(attention.get("count") or 0) <= 0 and str(attention.get("id") or "").endswith("_ok"):
            attention_score = 0
    growth_score = int(growth.get("priority") or 0) if growth else 0

    def attention_focus() -> dict[str, Any] | None:
        if not attention or attention_score <= 0:
            return None
        affected_ids = [str(value) for value in attention.get("affected_business_ids") or [] if str(value)]
        return {
            "id": str(attention.get("id") or "attention"),
            "title": str(attention.get("title") or "Требуется внимание"),
            "reason": str(attention.get("description") or "Откройте задачу и проверьте детали."),
            "expected_outcome": "",
            "expected_result": "",
            "cta_label": "Открыть задачу",
            "screen": _attention_screen(attention),
            "priority": attention_score,
            "count": int(attention.get("count") or 0),
            "target_scope": attention.get("target_scope"),
            "affected_business_ids": affected_ids,
            "source": "operator",
        }

    candidates: list[dict[str, Any]] = []
    selected_attention = attention_focus()
    if selected_attention:
        candidates.append(selected_attention)
    if isinstance(content_action, dict):
        candidates.append(content_action)
    if growth:
        expected_outcome = str(growth.get("expected_outcome") or "Появится следующий подтверждённый результат.")
        candidates.append({
            "id": f"growth:{_screen_from_url(growth.get('cta_url'))}",
            "title": str(growth.get("title") or "Продолжайте рост бизнеса"),
            "reason": str(growth.get("reason") or "LocalOS выбрал следующий практический шаг."),
            "expected_outcome": expected_outcome,
            "expected_result": expected_outcome,
            "cta_label": str(growth.get("cta_label") or "Продолжить"),
            "screen": _screen_from_url(growth.get("cta_url")),
            "priority": growth_score,
            "estimated_effect": growth.get("estimated_effect"),
            "target_scope": growth.get("target_scope"),
            "affected_business_ids": growth.get("affected_business_ids") or [],
            "source": "growth",
        })
    if not candidates:
        return None
    return max(candidates, key=lambda item: int(item.get("priority") or 0))


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


def _short_ru_date(value: date) -> str:
    months = (
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    )
    return f"{value.day} {months[value.month - 1]}"


def _load_story_facts_action(
    cursor: Any,
    scope: dict[str, Any],
    observed_at: datetime,
) -> dict[str, Any] | None:
    try:
        if not _table_exists(cursor, "contentplanitems") or not _table_exists(cursor, "contentplans"):
            return None
        platform, business_ids = _business_filter(scope)
        today = observed_at.astimezone(timezone.utc).date()
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, b.name AS business_name,
                   i.scheduled_for, i.content_type, i.theme, i.goal,
                   i.source_kind, i.source_ref, i.metadata_json, i.status
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            LEFT JOIN businesses b ON b.id = i.business_id
            WHERE (%s OR i.business_id = ANY(%s))
              AND COALESCE(p.plan_status, '') <> 'archived'
              AND COALESCE(i.status, 'planned') NOT IN ('published', 'archived')
              AND i.scheduled_for BETWEEN %s AND %s
            ORDER BY i.scheduled_for ASC, i.updated_at DESC
            LIMIT 100
            """,
            (platform, business_ids, today - timedelta(days=3), today + timedelta(days=14)),
        )
        missing: list[dict[str, Any]] = []
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            metadata = _parse_json(item.get("metadata_json"))
            answers = metadata.get("brief_answers") if isinstance(metadata.get("brief_answers"), dict) else {}
            if not _requires_story_facts(item, metadata) or str(answers.get("story_facts") or "").strip():
                continue
            scheduled_for = _as_date(item.get("scheduled_for"))
            if not scheduled_for:
                continue
            missing.append({**item, "scheduled_for": scheduled_for})
        if not missing:
            return None

        item = missing[0]
        scheduled_for = item["scheduled_for"]
        priority = 125 if scheduled_for <= today else (115 if scheduled_for <= today + timedelta(days=7) else 95)
        theme = str(item.get("theme") or "ближайшей публикации").strip()
        business_id = str(item.get("business_id") or "")
        return {
            "id": f"content_story_facts:{item.get('id')}",
            "title": "Добавьте факты для истории",
            "reason": (
                f"Для «{theme}» на {_short_ru_date(scheduled_for)} не хватает реального эпизода. "
                "LocalOS не будет придумывать героя или результат."
            ),
            "expected_outcome": "После фактов LocalOS подготовит достоверный текст истории.",
            "expected_result": "После фактов LocalOS подготовит достоверный текст истории.",
            "cta_label": "Добавить факты",
            "screen": "content",
            "priority": priority,
            "count": len(missing),
            "item_id": str(item.get("id") or ""),
            "plan_id": str(item.get("plan_id") or ""),
            "question": STORY_FACTS_QUESTION,
            "target_scope": {"kind": "business", "id": business_id},
            "affected_business_ids": [business_id] if business_id else [],
            "source": "content",
        }
    except Exception:
        return None


def _load_business_history_reminders(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if str(scope.get("kind") or "business") == "platform":
        return []
    try:
        if not _table_exists(cursor, "outreach_sender_profiles"):
            return []
        business_ids = [str(item) for item in scope.get("business_ids") or [] if str(item)]
        if not business_ids:
            return []
        cursor.execute(
            """
            SELECT b.id AS business_id, b.name AS business_name,
                   p.competence_story, p.outreach_context_json
            FROM businesses b
            LEFT JOIN LATERAL (
                SELECT competence_story, outreach_context_json
                FROM outreach_sender_profiles
                WHERE client_business_id = b.id
                  AND workstream_type = 'client_partnership'
                  AND is_active = TRUE
                ORDER BY confirmed_at DESC NULLS LAST, updated_at DESC
                LIMIT 1
            ) p ON TRUE
            WHERE b.id = ANY(%s)
            ORDER BY b.name
            """,
            (business_ids,),
        )
        reminders: list[dict[str, Any]] = []
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            if not _needs_business_history(item.get("competence_story"), item.get("outreach_context_json")):
                continue
            business_id = str(item.get("business_id") or "")
            reminders.append({
                "id": f"business-history:{business_id}",
                "title": "Расскажите о бизнесе",
                "description": (
                    "Добавьте историю, факты и примеры. "
                    "ЛокалОС будет точнее готовить контент и предложения партнёрам."
                ),
                "cta_label": "Добавить историю",
                "screen": "partnerships",
                "business_id": business_id,
                "business_name": item.get("business_name"),
                "target_scope": {"kind": "business", "id": business_id},
            })
        return reminders[:5]
    except Exception:
        return []


def _load_progress(scope: dict[str, Any], loader: Callable[[str], dict[str, Any]]) -> dict[str, Any] | None:
    if str(scope.get("kind") or "business") == "platform":
        return None
    business_ids = [str(item) for item in scope.get("business_ids") or [] if str(item)]
    business_id = str(scope.get("id") or "") if scope.get("kind") == "business" else (business_ids[0] if business_ids else "")
    if not business_id:
        return None
    try:
        if loader is load_growth_overview:
            return load_growth_overview_for_scope(scope)
        return loader(business_id)
    except Exception:
        return None


def _load_active_work(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    platform, business_ids = _business_filter(scope)
    work: list[dict[str, Any]] = []
    if _table_exists(cursor, "parsequeue"):
        cursor.execute(
            """
            SELECT q.id, q.business_id, b.name AS business_name, q.status,
                   q.task_type, q.created_at, q.updated_at
            FROM parsequeue q
            LEFT JOIN businesses b ON b.id = q.business_id
            WHERE (%s OR q.business_id = ANY(%s))
              AND q.status IN ('pending', 'queued', 'processing', 'running')
            ORDER BY q.updated_at DESC
            LIMIT 8
            """,
            (platform, business_ids),
        )
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            status = str(item.get("status") or "pending")
            work.append({
                "id": f"parse:{item.get('id')}",
                "kind": "map_refresh",
                "title": "Обновляет данные карточки",
                "stage": "Ждёт запуска" if status in {"pending", "queued"} else "Собирает данные Яндекса и 2ГИС",
                "status": "in_progress",
                "progress": None,
                "business_id": item.get("business_id"),
                "business_name": item.get("business_name"),
                "occurred_at": _iso(item.get("updated_at") or item.get("created_at")),
                "screen": "cards",
            })
    if _table_exists(cursor, "agent_runs") and _table_exists(cursor, "agent_blueprints"):
        cursor.execute(
            """
            SELECT r.id, bp.business_id, b.name AS business_name, bp.name AS agent_name,
                   r.status, r.started_at, r.updated_at
            FROM agent_runs r
            JOIN agent_blueprints bp ON bp.id = r.blueprint_id
            LEFT JOIN businesses b ON b.id = bp.business_id
            WHERE (%s OR bp.business_id = ANY(%s))
              AND r.status IN ('pending', 'queued', 'running', 'processing')
            ORDER BY COALESCE(r.started_at, r.updated_at) DESC
            LIMIT 8
            """,
            (platform, business_ids),
        )
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            status = str(item.get("status") or "pending")
            work.append({
                "id": f"agent:{item.get('id')}",
                "kind": "agent_run",
                "title": str(item.get("agent_name") or "ИИ-сотрудник выполняет задачу"),
                "stage": "Ждёт запуска" if status in {"pending", "queued"} else "Выполняет работу",
                "status": "in_progress",
                "progress": None,
                "business_id": item.get("business_id"),
                "business_name": item.get("business_name"),
                "occurred_at": _iso(item.get("started_at") or item.get("updated_at")),
                "screen": "agents",
            })
    work.sort(key=lambda item: str(item.get("occurred_at") or ""), reverse=True)
    return work[:5]


def _change_item(
    *,
    item_id: str,
    kind: str,
    title: str,
    description: str,
    source: str,
    occurred_at: Any,
    screen: str,
    business_id: Any = None,
    business_name: Any = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "kind": kind,
        "title": title,
        "description": description,
        "source": source,
        "occurred_at": _iso(occurred_at),
        "screen": screen,
        "business_id": business_id,
        "business_name": business_name,
    }


def _load_changes(cursor: Any, scope: dict[str, Any], cutoff: datetime) -> list[dict[str, Any]]:
    platform, business_ids = _business_filter(scope)
    changes: list[dict[str, Any]] = []
    if _table_exists(cursor, "externalbusinessreviews"):
        cursor.execute(
            """
            SELECT r.business_id, b.name AS business_name, COUNT(*) AS count,
                   MAX(r.created_at) AS occurred_at
            FROM externalbusinessreviews r
            LEFT JOIN businesses b ON b.id = r.business_id
            WHERE (%s OR r.business_id = ANY(%s)) AND r.created_at >= %s
            GROUP BY r.business_id, b.name
            ORDER BY occurred_at DESC
            LIMIT 6
            """,
            (platform, business_ids, cutoff),
        )
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            count = int(item.get("count") or 0)
            changes.append(_change_item(
                item_id=f"reviews:{item.get('business_id')}:{_iso(item.get('occurred_at'))}",
                kind="reviews_loaded",
                title=f"Загружено новых отзывов: {count}",
                description="Это отзывы, которые появились в LocalOS после последнего сбора данных.",
                source="Отзывы с карт",
                occurred_at=item.get("occurred_at"),
                screen="reviews",
                business_id=item.get("business_id"),
                business_name=item.get("business_name"),
            ))
    if _table_exists(cursor, "prospectingleads"):
        cursor.execute(
            """
            SELECT l.business_id, b.name AS business_name, COUNT(*) AS count,
                   MAX(l.updated_at) AS occurred_at
            FROM prospectingleads l
            LEFT JOIN businesses b ON b.id = l.business_id
            WHERE (%s OR l.business_id = ANY(%s))
              AND l.updated_at >= %s
              AND COALESCE(l.pipeline_status, '') IN ('replied', 'responded', 'converted')
            GROUP BY l.business_id, b.name
            ORDER BY occurred_at DESC
            LIMIT 6
            """,
            (platform, business_ids, cutoff),
        )
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            count = int(item.get("count") or 0)
            changes.append(_change_item(
                item_id=f"partner-replies:{item.get('business_id')}:{_iso(item.get('occurred_at'))}",
                kind="partnership_reply",
                title=f"Новых ответов от партнёров: {count}",
                description="Следующие касания остановлены до вашего решения.",
                source="Партнёрства",
                occurred_at=item.get("occurred_at"),
                screen="partnerships",
                business_id=item.get("business_id"),
                business_name=item.get("business_name"),
            ))
    if _table_exists(cursor, "financialtransactions"):
        cursor.execute(
            """
            SELECT t.business_id, b.name AS business_name, COUNT(*) AS count,
                   COALESCE(SUM(t.amount), 0) AS amount, MAX(t.created_at) AS occurred_at
            FROM financialtransactions t
            LEFT JOIN businesses b ON b.id = t.business_id
            WHERE (%s OR t.business_id = ANY(%s))
              AND t.created_at >= %s AND t.transaction_type = 'income'
            GROUP BY t.business_id, b.name
            ORDER BY occurred_at DESC
            LIMIT 6
            """,
            (platform, business_ids, cutoff),
        )
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            count = int(item.get("count") or 0)
            amount = float(item.get("amount") or 0)
            changes.append(_change_item(
                item_id=f"sales:{item.get('business_id')}:{_iso(item.get('occurred_at'))}",
                kind="sales_loaded",
                title=f"Добавлено продаж: {count}",
                description=f"В финансовой картине появилось {amount:,.0f} ₽ новых поступлений.".replace(",", " "),
                source="Финансы LocalOS",
                occurred_at=item.get("occurred_at"),
                screen="finance",
                business_id=item.get("business_id"),
                business_name=item.get("business_name"),
            ))
    if _table_exists(cursor, "business_action_events"):
        cursor.execute(
            """
            SELECT e.id, e.business_id, b.name AS business_name, e.action_type,
                   e.source_type, e.occurred_at
            FROM business_action_events e
            LEFT JOIN businesses b ON b.id = e.business_id
            WHERE (%s OR e.business_id = ANY(%s))
              AND e.occurred_at >= %s AND e.status = 'external_change_detected'
            ORDER BY e.occurred_at DESC
            LIMIT 8
            """,
            (platform, business_ids, cutoff),
        )
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            changes.append(_change_item(
                item_id=f"external:{item.get('id')}",
                kind="external_change",
                title="Обнаружено изменение в карточке",
                description="LocalOS заметил изменение по новому снимку и не приписывает его себе.",
                source=str(item.get("source_type") or "Карты"),
                occurred_at=item.get("occurred_at"),
                screen="cards",
                business_id=item.get("business_id"),
                business_name=item.get("business_name"),
            ))
    changes.sort(key=lambda item: str(item.get("occurred_at") or ""), reverse=True)
    seen: set[str] = set()
    result = []
    for item in changes:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        result.append(item)
    return result[:8]


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-zа-яё0-9]{4,}", str(value or "").lower())
        if token not in TOPIC_STOPWORDS
    }


PULSE_STRONG_BUSINESS_MARKERS = (
    "администратор", "аренд", "бизнес", "выруч", "график", "загруз", "закуп",
    "запис", "зарплат", "карт", "клиентская база", "кпи", "лояльност",
    "маркетинг", "маркиров", "налог", "найм", "оборудован", "перезапис",
    "поставщик", "прибыл", "продаж", "расход", "рейтинг", "себестоим",
    "сотрудник", "соцсет", "средний чек", "управлен", "crm", "2гис", "яндекс",
)


def _is_business_pulse_material(item: dict[str, Any]) -> bool:
    text = re.sub(r"\s+", " ", str(item.get("message_text") or "")).lower()
    return any(marker in text for marker in PULSE_STRONG_BUSINESS_MARKERS)


def _short_topic(value: Any, limit: int = 90) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    shortened = cleaned[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,.;:—–-")
    return f"{shortened}…" if shortened else f"{cleaned[:limit].rstrip()}…"


def _topic_hint(item: dict[str, Any]) -> str:
    raw = _parse_json(item.get("raw_payload_json"))
    for key in ("topic", "topic_title", "theme", "summary_title"):
        value = str(raw.get(key) or "").strip()
        if value:
            return _short_topic(value)
    reason = str(item.get("reason") or "").strip()
    if ":" in reason:
        markers = reason.split(":", 1)[1].split(",")
        if markers and markers[0].strip():
            return markers[0].strip().capitalize()
    text = str(item.get("message_text") or "")
    for fragment in re.split(r"[\n.!?]+", text):
        cleaned = re.sub(r"\s+", " ", fragment).strip(" —–-:;·•\t")
        if len(cleaned) >= 16 and re.search(r"[a-zа-яё]{4,}", cleaned.lower()):
            return _short_topic(cleaned)
    terms = sorted(_tokens(text))
    return " ".join(terms[:3]).capitalize() if terms else "Обсуждение предпринимателей"


def _cluster_pulse(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in rows:
        hint = _topic_hint(item)
        item_tokens = _tokens(hint)
        target = None
        for group in groups:
            overlap = item_tokens.intersection(group["tokens"])
            if hint.lower() == str(group["hint"]).lower() or len(overlap) >= 2:
                target = group
                break
        if target is None:
            target = {"hint": hint, "tokens": set(item_tokens), "items": []}
            groups.append(target)
        target["tokens"].update(item_tokens)
        target["items"].append(item)

    pulse = []
    for group in groups:
        items = list(group["items"])
        sources = {str(item.get("source_id") or item.get("chat_title") or "") for item in items}
        if len(items) < 3 and len(sources) < 2:
            continue
        source_counts = Counter(str(item.get("chat_title") or "Telegram") for item in items)
        primary_source = source_counts.most_common(1)[0][0]
        latest = max(str(_iso(item.get("message_date") or item.get("created_at")) or "") for item in items)
        top_terms = Counter(
            token
            for item in items
            for token in _tokens(str(item.get("message_text") or ""))
        ).most_common(3)
        title = str(group["hint"] or "").strip()
        if title == "Обсуждение предпринимателей" and top_terms:
            title = " ".join(term for term, _count in top_terms).capitalize()
        links = []
        primary_link = None
        for item in items:
            link = str(item.get("message_link") or "").strip()
            username = str(item.get("telegram_username") or "").strip().lstrip("@")
            source_url = link or (f"https://t.me/{username}" if username else "")
            if source_url and source_url not in links:
                links.append(source_url)
            if source_url and str(item.get("chat_title") or "Telegram") == primary_source and primary_link is None:
                primary_link = source_url
        score = len(items) * 10 + len(sources) * 8 + max(int(item.get("priority_score") or item.get("score") or 0) for item in items)
        pulse.append({
            "id": f"pulse:{re.sub(r'[^a-zа-яё0-9]+', '-', title.lower()).strip('-')[:64]}:{latest[:10]}",
            "eyebrow": "Обсуждали",
            "title": title,
            "description": f"Тему поднимали в {len(sources)} отраслевых источниках за последние сутки.",
            "message_count": len(items),
            "sources_count": len(sources),
            "source_name": primary_source,
            "source_url": primary_link or (links[0] if links else None),
            "source_links": [primary_link or links[0]] if primary_link or links else [],
            "last_discussed_at": latest,
            "score": score,
            "provenance": [
                {
                    "message_id": item.get("telegram_message_id"),
                    "source_id": item.get("source_id"),
                    "source_name": item.get("chat_title"),
                    "message_link": item.get("message_link"),
                    "message_date": _iso(item.get("message_date")),
                }
                for item in items[:10]
            ],
        })
    pulse.sort(key=lambda item: (int(item.get("score") or 0), str(item.get("last_discussed_at") or "")), reverse=True)
    return pulse[:3]


def _knowledge_pulse_rows(
    cursor: Any,
    scope: dict[str, Any],
    cutoff: datetime,
) -> tuple[list[dict[str, Any]], set[str]]:
    if not _table_exists(cursor, "knowledge_sources") or not _table_exists(cursor, "knowledge_documents"):
        return [], set()
    source_ids, industry_keys = _knowledge_source_ids(cursor, scope)
    if not source_ids:
        return [], industry_keys
    cursor.execute(
        """
        SELECT document.external_id AS telegram_message_id,
               document.source_id, source.title AS chat_title,
               document.published_at AS message_date,
               document.created_at, document.content_text AS message_text,
               COALESCE(document.permalink, source.canonical_url) AS message_link,
               document.metadata_json AS raw_payload_json,
               source.canonical_url
        FROM knowledge_documents document
        JOIN knowledge_sources source ON source.id = document.source_id
        WHERE document.source_id = ANY(%s::uuid[])
          AND document.invalidated_at IS NULL
          AND document.sensitivity_class = 'public'
          AND source.source_type = 'telegram'
          AND source.visibility IN ('public', 'platform_public')
          AND source.sensitivity_class = 'public'
          AND source.status = 'active'
          AND COALESCE(document.published_at, document.created_at) >= %s
        ORDER BY COALESCE(document.published_at, document.created_at) DESC
        LIMIT 480
        """,
        (source_ids, cutoff),
    )
    rows = []
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        canonical_url = str(item.get("canonical_url") or "").rstrip("/")
        item["telegram_username"] = canonical_url.rsplit("/", 1)[-1] if canonical_url else ""
        rows.append(item)
    return rows, industry_keys


def _knowledge_source_ids(cursor: Any, scope: dict[str, Any]) -> tuple[list[str], set[str]]:
    """Return public Telegram sources available in the verified control scope."""
    platform, business_ids = _business_filter(scope)
    if platform:
        cursor.execute(
            """
            SELECT id
            FROM knowledge_sources
            WHERE source_type = 'telegram'
              AND visibility IN ('public', 'platform_public')
              AND sensitivity_class = 'public'
              AND status = 'active'
            ORDER BY last_collected_at DESC NULLS LAST, id
            """
        )
        return [str(_row(cursor, value).get("id") or "") for value in cursor.fetchall() or [] if _row(cursor, value).get("id")], set()
    industry_keys = load_business_industry_keys(cursor, business_ids)
    default_sources = load_default_industry_sources(cursor, industry_keys)
    source_ids = [str(item.get("id") or "") for item in default_sources if item.get("id")]
    if _table_exists(cursor, "knowledge_source_subscriptions") and business_ids:
        cursor.execute(
            """
            SELECT DISTINCT subscription.source_id
            FROM knowledge_source_subscriptions subscription
            JOIN knowledge_sources source ON source.id = subscription.source_id
            WHERE subscription.business_id = ANY(%s)
              AND subscription.is_active = TRUE
              AND source.source_type = 'telegram'
              AND source.visibility IN ('public', 'platform_public')
              AND source.sensitivity_class = 'public'
              AND source.status = 'active'
            """,
            (business_ids,),
        )
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            source_id = str(item.get("source_id") or "")
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)
    return source_ids, industry_keys


def _feed_cursor(value: Any) -> tuple[datetime, str] | None:
    try:
        payload = json.loads(urlsafe_b64decode(str(value or "") + "===").decode("utf-8"))
        observed_at = datetime.fromisoformat(str(payload.get("at") or "").replace("Z", "+00:00"))
        item_id = str(payload.get("id") or "")
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        return observed_at, item_id
    except Exception:
        return None


def _encode_feed_cursor(observed_at: Any, item_id: Any) -> str | None:
    timestamp = _iso(observed_at)
    if not timestamp or not item_id:
        return None
    payload = json.dumps({"at": timestamp, "id": str(item_id)}, separators=(",", ":"), ensure_ascii=True)
    return urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _telegram_document_link(item: dict[str, Any]) -> str | None:
    permalink = str(item.get("permalink") or "").strip()
    if permalink.startswith("https://t.me/"):
        return permalink
    source_url = str(item.get("source_url") or "").strip().rstrip("/")
    external_id = str(item.get("external_id") or "").strip()
    if source_url.startswith("https://t.me/") and external_id.isdigit():
        return f"{source_url}/{external_id}"
    return source_url if source_url.startswith("https://t.me/") else None


def _load_feed_inbound_items(cursor: Any, scope: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    business_ids = [str(value) for value in scope.get("business_ids") or [] if value]
    if scope.get("kind") == "business" and scope.get("id"):
        business_ids = [str(scope["id"])]
    if not business_ids:
        return []
    cursor.execute("SELECT TO_REGCLASS('public.outreach_inbound_events') AS table_name")
    existing = _row(cursor, cursor.fetchone())
    if not existing.get("table_name"):
        return []
    cursor.execute(
        """
        SELECT inbound.id, inbound.channel, inbound.classification,
               inbound.raw_payload_json, inbound.occurred_at,
               lead.name AS sender_name, workstream.workstream_type,
               workstream.client_business_id AS business_id
        FROM outreach_inbound_events inbound
        JOIN lead_workstreams workstream ON workstream.id = inbound.workstream_id
        LEFT JOIN prospectingleads lead ON lead.id = inbound.lead_id
        WHERE workstream.client_business_id = ANY(%s)
          AND inbound.is_human = TRUE
        ORDER BY inbound.occurred_at DESC, inbound.created_at DESC
        LIMIT %s
        """,
        (business_ids, min(max(int(limit or 20), 1), 50)),
    )
    items = []
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        raw = _parse_json(item.get("raw_payload_json"))
        text = next((str(raw.get(key) or "").strip() for key in ("reply", "raw_reply", "text", "message") if str(raw.get(key) or "").strip()), "")
        items.append({
            "id": str(item.get("id") or ""),
            "channel": str(item.get("channel") or ""),
            "classification": str(item.get("classification") or "human_unknown"),
            "sender_name": str(item.get("sender_name") or "Новый ответ"),
            "text": text or "Получен ответ. Откройте рабочую область, чтобы продолжить.",
            "received_at": _iso(item.get("occurred_at")),
            "flow_type": "influencer" if str(item.get("workstream_type") or "") == "creator_collaboration" else "partnership",
            "target": {"screen": "influencers" if str(item.get("workstream_type") or "") == "creator_collaboration" else "partnerships", "item_id": str(item.get("id") or "")},
        })
    return items


def build_mobile_feed(
    cursor: Any,
    *,
    scope: dict[str, Any],
    limit: int = 20,
    page_cursor: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the public community feed without trusting client business IDs."""
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    cutoff = observed_at.astimezone(timezone.utc) - timedelta(hours=24)
    source_ids, _industry_keys = _knowledge_source_ids(cursor, scope)
    topics = _load_community_pulse(cursor, scope, cutoff)
    topic_trends = load_topic_trends(cursor, source_ids, observed_at)
    inbound_items = _load_feed_inbound_items(cursor, scope, limit=limit)
    if not source_ids:
        return {
            "scope": scope,
            "topics": topics,
            "topic_trends": topic_trends,
            "items": [],
            "inbound_items": inbound_items,
            "counts": {"returned": 0},
            "cursor": None,
            "as_of": observed_at.astimezone(timezone.utc).isoformat(),
            "freshness": {"status": "empty", "updated_at": None},
            "data_warnings": [],
            "available_actions": ["community_sources.manage"] if scope.get("kind") == "business" else [],
            "filters": {"platforms": ["telegram"]},
        }

    bounded_limit = min(max(int(limit or 20), 1), 50)
    decoded_cursor = _feed_cursor(page_cursor)
    page_filter = ""
    params: list[Any] = [source_ids]
    if decoded_cursor and decoded_cursor[1]:
        page_filter = "AND (COALESCE(document.published_at, document.created_at), document.id) < (%s, %s::uuid)"
        params.extend([decoded_cursor[0], decoded_cursor[1]])
    params.append(bounded_limit + 1)
    cursor.execute(
        f"""
        SELECT document.id, document.external_id, document.title,
               document.content_text, document.permalink,
               COALESCE(document.published_at, document.created_at) AS published_at,
               source.id AS source_id, source.title AS source_name,
               source.canonical_url AS source_url
        FROM knowledge_documents document
        JOIN knowledge_sources source ON source.id = document.source_id
        WHERE document.source_id = ANY(%s::uuid[])
          AND document.document_type = 'telegram_message'
          AND document.invalidated_at IS NULL
          AND document.sensitivity_class = 'public'
          AND source.source_type = 'telegram'
          AND source.visibility IN ('public', 'platform_public')
          AND source.status = 'active'
          AND LENGTH(BTRIM(document.content_text)) > 0
          {page_filter}
        ORDER BY COALESCE(document.published_at, document.created_at) DESC, document.id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    raw_items = [_row(cursor, value) for value in cursor.fetchall() or []]
    has_more = len(raw_items) > bounded_limit
    raw_items = raw_items[:bounded_limit]
    items = []
    for item in raw_items:
        link = _telegram_document_link(item)
        if not link:
            continue
        items.append({
            "id": str(item.get("id") or ""),
            "platform": "telegram",
            "source_id": str(item.get("source_id") or ""),
            "source_name": str(item.get("source_name") or "Telegram"),
            "source_url": item.get("source_url"),
            "title": item.get("title"),
            "text": str(item.get("content_text") or "").strip(),
            "published_at": _iso(item.get("published_at")),
            "url": link,
        })
    last = raw_items[-1] if raw_items else None
    next_cursor = _encode_feed_cursor(last.get("published_at"), last.get("id")) if has_more and last else None
    latest_at = items[0].get("published_at") if items else None
    return {
        "scope": scope,
        "topics": topics,
        "topic_trends": topic_trends,
        "items": items,
        "inbound_items": inbound_items,
        "counts": {"returned": len(items)},
        "cursor": next_cursor,
        "as_of": observed_at.astimezone(timezone.utc).isoformat(),
        "freshness": {"status": "live" if latest_at else "empty", "updated_at": latest_at},
        "data_warnings": [],
        "available_actions": ["community_sources.manage"] if scope.get("kind") == "business" else [],
        "filters": {"platforms": ["telegram"]},
    }


def _pulse_overview(rows: list[dict[str, Any]], industry_keys: set[str]) -> list[dict[str, Any]]:
    if not rows:
        return []
    label = industry_label(industry_keys)

    def rank(item: dict[str, Any]) -> tuple[int, int, str]:
        metadata = _parse_json(item.get("raw_payload_json"))
        priority = int(metadata.get("priority_score") or metadata.get("relevance_score") or 0)
        engagement = int(metadata.get("raw_engagement") or metadata.get("views") or 0)
        observed_at = str(_iso(item.get("message_date") or item.get("created_at")) or "")
        return priority, engagement, observed_at

    highlights = []
    used_sources: set[str] = set()
    used_topics: list[set[str]] = []
    for item in sorted(rows, key=rank, reverse=True):
        title = _topic_hint(item)
        topic_tokens = _tokens(title)
        if any(len(topic_tokens.intersection(existing)) >= 2 for existing in used_topics):
            continue
        source_id = str(item.get("source_id") or item.get("chat_title") or "")
        if source_id in used_sources and len(used_sources) < 3:
            continue
        link = str(item.get("message_link") or "").strip() or None
        text = re.sub(r"\s+", " ", str(item.get("message_text") or "")).strip()
        description = text
        if description.lower().startswith(title.lower()):
            description = description[len(title):].lstrip(" .!?:—–-")
        if len(description) > 180:
            description = description[:177].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"
        if len(description) < 24:
            description = f"Важный материал из отраслевого источника «{item.get('chat_title') or label}»."
        observed_at = str(_iso(item.get("message_date") or item.get("created_at")) or "")
        highlights.append({
            "id": f"pulse:highlight:{item.get('source_id')}:{item.get('telegram_message_id') or observed_at}",
            "eyebrow": "Главное за день" if not highlights else "Говорили о",
            "title": title,
            "description": description,
            "message_count": None,
            "sources_count": None,
            "source_name": str(item.get("chat_title") or label),
            "source_url": link,
            "source_links": [link] if link else [],
            "last_discussed_at": observed_at,
            "score": rank(item)[0],
            "provenance": [{
                "message_id": item.get("telegram_message_id"),
                "source_id": item.get("source_id"),
                "source_name": item.get("chat_title"),
                "message_link": link,
                "message_date": observed_at,
            }],
        })
        used_sources.add(source_id)
        used_topics.append(topic_tokens)
        if len(highlights) >= 3:
            break
    return highlights


def _load_community_pulse(cursor: Any, scope: dict[str, Any], cutoff: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    platform, business_ids = _business_filter(scope)
    if _table_exists(cursor, "telegram_opportunities") and _table_exists(cursor, "telegram_opportunity_sources"):
        cursor.execute(
            """
            SELECT o.id, o.business_id, o.source_id, o.telegram_message_id,
                   o.chat_title, o.message_date, o.message_text, o.message_link,
                   o.signal_type, o.score, o.reason, o.priority_score,
                   o.raw_payload_json, o.created_at, s.telegram_username
            FROM telegram_opportunities o
            JOIN telegram_opportunity_sources s ON s.id = o.source_id
            WHERE COALESCE(o.message_date, o.created_at) >= %s
              AND s.is_active = TRUE
              AND (
                    (%s = FALSE AND o.business_id = ANY(%s))
                    OR (
                        o.business_id = %s
                        AND COALESCE(s.monitor_config_json->>'visibility', '') = ANY(%s)
                    )
              )
              AND (
                    s.account_id IS NULL
                    OR EXISTS (
                        SELECT 1 FROM telegram_account_permissions p
                        WHERE p.account_id = s.account_id AND p.radar_enabled = TRUE
                    )
                )
            ORDER BY COALESCE(o.message_date, o.created_at) DESC
            LIMIT 240
            """,
            (cutoff, platform, business_ids, PLATFORM_RADAR_BUSINESS_ID, sorted(PUBLIC_RADAR_VISIBILITIES)),
        )
        rows.extend(_row(cursor, value) for value in cursor.fetchall() or [])
    knowledge_rows, industry_keys = _knowledge_pulse_rows(cursor, scope, cutoff)
    relevant_knowledge_rows = [item for item in knowledge_rows if _is_business_pulse_material(item)]
    rows.extend(relevant_knowledge_rows)
    unique_rows = []
    seen = set()
    for item in rows:
        key = (str(item.get("source_id") or ""), str(item.get("telegram_message_id") or item.get("message_link") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(item)
    clustered = _cluster_pulse(unique_rows)
    return clustered or _pulse_overview(relevant_knowledge_rows, industry_keys)


def _load_completed_results(
    cursor: Any,
    scope: dict[str, Any],
    progress: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    platform, business_ids = _business_filter(scope)
    results: list[dict[str, Any]] = []
    if isinstance(progress, dict):
        for item in progress.get("recent_achievements") or []:
            if not isinstance(item, dict):
                continue
            results.append({
                "id": str(item.get("key") or "achievement"),
                "kind": "growth_achievement",
                "title": str(item.get("title") or "Получен результат"),
                "description": str(item.get("description") or "Результат подтверждён данными LocalOS."),
                "source": "Прогресс LocalOS",
                "occurred_at": _iso(item.get("occurred_at")),
                "screen": "progress",
                "area": item.get("area"),
            })
    if _table_exists(cursor, "business_action_events"):
        cursor.execute(
            """
            SELECT e.id, e.business_id, b.name AS business_name, e.action_type,
                   e.source_type, e.occurred_at
            FROM business_action_events e
            LEFT JOIN businesses b ON b.id = e.business_id
            WHERE (%s OR e.business_id = ANY(%s)) AND e.status = 'confirmed'
            ORDER BY e.occurred_at DESC
            LIMIT 12
            """,
            (platform, business_ids),
        )
        labels = {
            "service_optimization_applied": ("Услуги обновлены", "services"),
            "content_published": ("Публикация подтверждена", "content"),
            "map_change_confirmed": ("Изменение карточки подтверждено", "cards"),
        }
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            label, screen = labels.get(str(item.get("action_type") or ""), ("Подтверждённое действие завершено", "tasks"))
            results.append({
                "id": f"action:{item.get('id')}",
                "kind": "confirmed_action",
                "title": label,
                "description": "Результат сохранён с источником и историей изменений.",
                "source": str(item.get("source_type") or "LocalOS"),
                "occurred_at": _iso(item.get("occurred_at")),
                "screen": screen,
                "business_id": item.get("business_id"),
                "business_name": item.get("business_name"),
            })
    results.sort(key=lambda item: str(item.get("occurred_at") or ""), reverse=True)
    unique = []
    seen: set[str] = set()
    for item in results:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        unique.append(item)
    return unique[:6]


def _progress_summary(progress: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(progress, dict):
        return None
    summary = progress.get("summary") if isinstance(progress.get("summary"), dict) else {}
    completed = int(summary.get("completed_milestones") or 0)
    total = int(summary.get("total_milestones") or 0)
    return {
        **summary,
        "completed_milestones": completed,
        "total_milestones": total,
        "percent": round(completed / total * 100) if total > 0 else 0,
    }


def _mobile_progress_areas(progress: dict[str, Any]) -> list[dict[str, Any]]:
    areas: list[dict[str, Any]] = []
    for value in progress.get("areas") or []:
        if not isinstance(value, dict):
            continue
        area = dict(value)
        action = area.get("action")
        if isinstance(action, dict):
            area["action"] = {**action, "screen": _screen_from_url(action.get("cta_url"))}
        areas.append(area)
    return areas


def _load_journey_actions(cursor: Any, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not journey_enabled() or not _table_exists(cursor, "journey_actions"):
        return []
    business_ids = [str(value) for value in scope.get("business_ids") or [] if str(value)]
    if scope.get("kind") == "business" and scope.get("id"):
        business_ids = [str(scope["id"])]
    if not business_ids:
        return []
    cursor.execute(
        """
        SELECT * FROM journey_actions
        WHERE business_id = ANY(%s)
          AND status IN ('ready', 'in_progress', 'waiting', 'blocked')
        ORDER BY CASE WHEN due_at IS NOT NULL AND due_at <= NOW() THEN 0 ELSE 1 END,
                 priority DESC, due_at NULLS LAST, created_at
        LIMIT 20
        """,
        (business_ids,),
    )
    return [serialize_action(_row(cursor, value)) for value in (cursor.fetchall() or [])]


def _journey_focus(action: dict[str, Any] | None) -> dict[str, Any] | None:
    if not action:
        return None
    return {
        "id": action.get("id"),
        "title": action.get("title"),
        "reason": action.get("description"),
        "expected_outcome": "После подтверждения LocalOS зафиксирует результат и покажет следующий шаг.",
        "expected_result": "После подтверждения LocalOS зафиксирует результат и покажет следующий шаг.",
        "cta_label": action.get("cta_label"),
        "screen": "journey_action",
        "priority": int(action.get("priority") or 0) + 150,
        "target_scope": {"kind": "business", "id": action.get("business_id")},
        "source": "lead_journey",
        "action_id": action.get("id"),
    }


def build_mobile_today(
    cursor: Any,
    *,
    scope: dict[str, Any],
    user_id: str,
    now: datetime | None = None,
    growth_loader: Callable[[str], dict[str, Any]] = load_growth_overview,
) -> dict[str, Any]:
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    cutoff = observed_at.astimezone(timezone.utc) - timedelta(hours=24)
    summary = build_operator_scope_summary(cursor, scope=scope, user_id=user_id)
    progress = _load_progress(scope, growth_loader)
    content_action = _load_story_facts_action(cursor, scope, observed_at)
    journey_actions = _load_journey_actions(cursor, scope)
    focus = _journey_focus(journey_actions[0] if journey_actions else None) or select_daily_focus(summary, progress, scope, content_action)
    return {
        "scope": scope,
        "as_of": observed_at.astimezone(timezone.utc).isoformat(),
        "period": {"kind": "rolling_24h", "since": cutoff.isoformat()},
        "focus_action": focus,
        "journey_actions": journey_actions,
        "growth_loop": progress.get("growth_loop") if isinstance(progress, dict) else None,
        "data_health": progress.get("data_health") if isinstance(progress, dict) else None,
        "analytics_level": progress.get("analytics_level") if isinstance(progress, dict) else None,
        "rhythm": progress.get("rhythm") if isinstance(progress, dict) else None,
        "analytics_modules": progress.get("analytics_modules") if isinstance(progress, dict) else [],
        "data_rhythm": progress.get("data_rhythm") if isinstance(progress, dict) else None,
        "network_summary": progress.get("network_summary") if isinstance(progress, dict) else None,
        "problem_locations": progress.get("problem_locations") if isinstance(progress, dict) else [],
        "location_breakdown": progress.get("location_breakdown") if isinstance(progress, dict) else [],
        "active_work": _load_active_work(cursor, scope),
        "changes_24h": _load_changes(cursor, scope, cutoff),
        "community_pulse": _load_community_pulse(cursor, scope, cutoff),
        "profile_reminders": _load_business_history_reminders(cursor, scope),
        "completed_results": _load_completed_results(cursor, scope, progress),
        "progress_summary": _progress_summary(progress),
        "freshness": summary.get("freshness") or {"status": "live"},
        "data_warnings": summary.get("data_warnings") or [],
    }


def build_mobile_progress(
    cursor: Any,
    *,
    scope: dict[str, Any],
    user_id: str,
    growth_loader: Callable[[str], dict[str, Any]] = load_growth_overview,
) -> dict[str, Any]:
    summary = build_operator_scope_summary(cursor, scope=scope, user_id=user_id)
    progress = _load_progress(scope, growth_loader)
    observed_at = datetime.now(timezone.utc)
    content_action = _load_story_facts_action(cursor, scope, observed_at)
    focus = select_daily_focus(summary, progress, scope, content_action)
    if not isinstance(progress, dict):
        return {
            "scope": scope,
            "status": "hidden" if scope.get("kind") == "platform" else "unavailable",
            "as_of": datetime.now(timezone.utc).isoformat(),
            "focus_action": focus,
            "growth_loop": None,
            "data_health": None,
            "analytics_modules": [],
            "data_rhythm": None,
            "network_summary": None,
            "problem_locations": [],
            "location_breakdown": [],
            "summary": None,
            "areas": [],
            "recent_results": [],
            "data_warnings": summary.get("data_warnings") or [],
        }
    return {
        "scope": scope,
        "status": "available",
        "as_of": str(progress.get("generated_at") or datetime.now(timezone.utc).isoformat()),
        "focus_action": focus,
        "growth_loop": progress.get("growth_loop"),
        "data_health": progress.get("data_health"),
        "analytics_level": progress.get("analytics_level"),
        "rhythm": progress.get("rhythm"),
        "analytics_modules": progress.get("analytics_modules") or [],
        "data_rhythm": progress.get("data_rhythm"),
        "network_summary": progress.get("network_summary"),
        "problem_locations": progress.get("problem_locations") or [],
        "location_breakdown": progress.get("location_breakdown") or [],
        "summary": _progress_summary(progress),
        "areas": _mobile_progress_areas(progress),
        "recent_results": progress.get("recent_achievements") or [],
        "data_warnings": summary.get("data_warnings") or [],
    }
