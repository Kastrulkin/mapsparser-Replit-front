from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from services.community_pulse_sources import (
    industry_label,
    load_business_industry_keys,
    load_default_industry_sources,
)
from services.growth_overview_service import load_growth_overview, load_growth_overview_for_scope
from services.operator_scope_summary import build_operator_scope_summary


PLATFORM_RADAR_BUSINESS_ID = "localos-platform-telegram-radar"
PUBLIC_RADAR_VISIBILITIES = {"platform_public", "public"}

TOPIC_STOPWORDS = {
    "будет", "были", "было", "быть", "ваш", "ведь", "всего", "где", "для", "если",
    "есть", "ещё", "или", "как", "когда", "которые", "можно", "надо", "наш", "него",
    "очень", "пока", "после", "почему", "при", "про", "свой", "так", "также", "только",
    "уже", "чтобы", "этого", "этой", "это", "business", "localos", "telegram",
}


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
) -> dict[str, Any] | None:
    attention = summary.get("primary_action") if isinstance(summary.get("primary_action"), dict) else None
    growth = progress.get("focus_action") if isinstance(progress, dict) and isinstance(progress.get("focus_action"), dict) else None
    kind = str(scope.get("kind") or "business")

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
            "expected_outcome": "Проблема будет разобрана, а следующий шаг останется под контролем.",
            "expected_result": "Проблема будет разобрана, а следующий шаг останется под контролем.",
            "cta_label": "Открыть задачу",
            "screen": _attention_screen(attention),
            "priority": attention_score,
            "count": int(attention.get("count") or 0),
            "target_scope": attention.get("target_scope"),
            "affected_business_ids": affected_ids,
            "source": "operator",
        }

    if kind == "platform" or not growth or attention_score >= growth_score:
        selected_attention = attention_focus()
        if selected_attention:
            return selected_attention
    if not growth:
        return None
    expected_outcome = str(growth.get("expected_outcome") or "Появится следующий подтверждённый результат.")
    return {
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
    }


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


def _topic_hint(item: dict[str, Any]) -> str:
    raw = _parse_json(item.get("raw_payload_json"))
    for key in ("topic", "topic_title", "theme", "summary_title"):
        value = str(raw.get(key) or "").strip()
        if value:
            return value[:90]
    reason = str(item.get("reason") or "").strip()
    if ":" in reason:
        markers = reason.split(":", 1)[1].split(",")
        if markers and markers[0].strip():
            return markers[0].strip().capitalize()
    text = str(item.get("message_text") or "")
    for fragment in re.split(r"[\n.!?]+", text):
        cleaned = re.sub(r"\s+", " ", fragment).strip(" —–-:;·•\t")
        if len(cleaned) >= 16 and re.search(r"[a-zа-яё]{4,}", cleaned.lower()):
            return cleaned[:90]
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
    platform, business_ids = _business_filter(scope)
    if platform:
        return [], set()
    industry_keys = load_business_industry_keys(cursor, business_ids)
    default_sources = load_default_industry_sources(cursor, industry_keys)
    source_ids = [str(item.get("id") or "") for item in default_sources if item.get("id")]
    if _table_exists(cursor, "knowledge_source_subscriptions") and business_ids:
        cursor.execute(
            """
            SELECT DISTINCT source_id
            FROM knowledge_source_subscriptions
            WHERE business_id = ANY(%s) AND is_active = TRUE
            """,
            (business_ids,),
        )
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            source_id = str(item.get("source_id") or "")
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)
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
    rows.extend(knowledge_rows)
    unique_rows = []
    seen = set()
    for item in rows:
        key = (str(item.get("source_id") or ""), str(item.get("telegram_message_id") or item.get("message_link") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(item)
    clustered = _cluster_pulse(unique_rows)
    return clustered or _pulse_overview(knowledge_rows, industry_keys)


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
    focus = select_daily_focus(summary, progress, scope)
    return {
        "scope": scope,
        "as_of": observed_at.astimezone(timezone.utc).isoformat(),
        "period": {"kind": "rolling_24h", "since": cutoff.isoformat()},
        "focus_action": focus,
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
    focus = select_daily_focus(summary, progress, scope)
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
