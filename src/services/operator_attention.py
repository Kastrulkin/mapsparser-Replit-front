from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


STALE_DAYS = 2


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


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return bool(row.get("table_ref"))


def _table_has_column(cursor: Any, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1 AS found
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return bool(row.get("found"))


def _parse_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None
    return None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_dt(value: Any) -> str | None:
    parsed = _parse_dt(value)
    if not parsed:
        return None
    return parsed.isoformat()


def _age_days(value: Any) -> int | None:
    parsed = _parse_dt(value)
    if not parsed:
        return None
    delta = datetime.now(timezone.utc) - parsed
    return max(0, int(delta.total_seconds() // 86400))


def _count_unanswered_from_reviews(reviews_obj: Any) -> int:
    if not isinstance(reviews_obj, list):
        return 0
    count = 0
    for item in reviews_obj:
        if not isinstance(item, dict):
            continue
        response = str(item.get("response_text") or item.get("org_reply") or "").strip()
        if not response:
            count += 1
    return count


def _load_business(cursor: Any, business_id: str) -> dict[str, Any]:
    select_columns = ["id"]
    for column_name in ("name", "business_name", "description"):
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
    return _row_to_dict(cursor, cursor.fetchone()) or {}


def _load_latest_card(cursor: Any, business_id: str) -> dict[str, Any]:
    if not _table_exists(cursor, "cards"):
        return {}
    if not _table_has_column(cursor, "cards", "business_id"):
        return {}
    select_columns = ["id", "created_at"]
    for column_name in ("rating", "reviews_count", "overview", "photos", "news", "reviews"):
        if _table_has_column(cursor, "cards", column_name):
            select_columns.append(column_name)
    cursor.execute(
        f"""
        SELECT {", ".join(select_columns)}
        FROM cards
        WHERE business_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    if not row:
        return {}
    overview = _parse_json(row.get("overview"))
    photos = _parse_json(row.get("photos"))
    news = _parse_json(row.get("news"))
    reviews = _parse_json(row.get("reviews"))
    row["overview"] = overview if isinstance(overview, dict) else {}
    row["photos_count"] = len(photos) if isinstance(photos, list) else int(row["overview"].get("photos_count") or 0)
    row["news_count"] = len(news) if isinstance(news, list) else int(row["overview"].get("news_count") or 0)
    row["unanswered_reviews_count"] = _count_unanswered_from_reviews(reviews)
    row["created_at_iso"] = _iso_dt(row.get("created_at"))
    row["age_days"] = _age_days(row.get("created_at"))
    return row


def _load_review_counts(cursor: Any, business_id: str, latest_card: dict[str, Any]) -> dict[str, Any]:
    fallback = {
        "total": int(latest_card.get("reviews_count") or 0),
        "with_response": 0,
        "without_response": int(latest_card.get("unanswered_reviews_count") or 0),
        "latest_seen_at": latest_card.get("created_at_iso"),
        "source": "cards",
    }
    if not _table_exists(cursor, "externalbusinessreviews"):
        return fallback
    if not _table_has_column(cursor, "externalbusinessreviews", "response_text"):
        return fallback
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN COALESCE(TRIM(response_text), '') != '' THEN 1 ELSE 0 END) AS with_response,
            SUM(CASE WHEN COALESCE(TRIM(response_text), '') = '' THEN 1 ELSE 0 END) AS without_response,
            MAX(COALESCE(updated_at, created_at)) AS latest_seen_at
        FROM externalbusinessreviews
        WHERE business_id = %s
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return {
        "total": int(row.get("total") or 0),
        "with_response": int(row.get("with_response") or 0),
        "without_response": int(row.get("without_response") or 0),
        "latest_seen_at": _iso_dt(row.get("latest_seen_at")) or latest_card.get("created_at_iso"),
        "source": "externalbusinessreviews",
    }


def _count_pending_news(cursor: Any, business_id: str, user_id: str) -> int:
    if not _table_exists(cursor, "usernews"):
        return 0
    if _table_has_column(cursor, "usernews", "business_id"):
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM usernews
            WHERE business_id = %s
              AND COALESCE(approved, 0) = 0
            """,
            (business_id,),
        )
    else:
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM usernews
            WHERE user_id = %s
              AND COALESCE(approved, 0) = 0
            """,
            (user_id,),
        )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return int(row.get("cnt") or 0)


def _count_reply_drafts(cursor: Any, business_id: str) -> int:
    if not _table_exists(cursor, "reviewreplydrafts"):
        return 0
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM reviewreplydrafts
        WHERE business_id = %s
          AND status IN ('draft', 'generated', 'pending_review')
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return int(row.get("cnt") or 0)


def _count_pending_approvals(cursor: Any, business_id: str) -> int:
    if not _table_exists(cursor, "action_requests"):
        return 0
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM action_requests
        WHERE tenant_id = %s
          AND status = 'pending_human'
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return int(row.get("cnt") or 0)


def _count_partnership_leads(cursor: Any, business_id: str) -> dict[str, int]:
    result = {"total": 0, "ready": 0}
    if not _table_exists(cursor, "prospectingleads"):
        return result
    has_intent = _table_has_column(cursor, "prospectingleads", "intent")
    has_partnership_stage = _table_has_column(cursor, "prospectingleads", "partnership_stage")
    has_status = _table_has_column(cursor, "prospectingleads", "status")
    ready_expr = "0"
    if has_partnership_stage and has_status:
        ready_expr = """
            SUM(
                CASE
                    WHEN COALESCE(partnership_stage, status, '') IN (
                        'selected_for_outreach',
                        'channel_selected',
                        'proposal_draft_ready',
                        'shortlist_approved'
                    )
                    THEN 1
                    ELSE 0
                END
            )
        """
    elif has_partnership_stage:
        ready_expr = """
            SUM(
                CASE
                    WHEN COALESCE(partnership_stage, '') IN (
                        'selected_for_outreach',
                        'channel_selected',
                        'proposal_draft_ready',
                        'shortlist_approved'
                    )
                    THEN 1
                    ELSE 0
                END
            )
        """
    elif has_status:
        ready_expr = """
            SUM(
                CASE
                    WHEN COALESCE(status, '') IN (
                        'selected_for_outreach',
                        'channel_selected',
                        'proposal_draft_ready',
                        'shortlist_approved'
                    )
                    THEN 1
                    ELSE 0
                END
            )
        """
    intent_filter = "AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'" if has_intent else ""
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total,
            {ready_expr} AS ready
        FROM prospectingleads
        WHERE business_id = %s
          {intent_filter}
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    result["total"] = int(row.get("total") or 0)
    result["ready"] = int(row.get("ready") or 0)
    return result


def _attention_item(
    item_id: str,
    category: str,
    severity: str,
    title: str,
    description: str,
    count: int,
    cta_label: str,
    cta_href: str,
    action_class: str = "free_cached",
) -> dict[str, Any]:
    return {
        "id": item_id,
        "category": category,
        "severity": severity,
        "title": title,
        "description": description,
        "count": int(count or 0),
        "cta": {"label": cta_label, "href": cta_href},
        "action_class": action_class,
    }


def build_attention_brief(cursor: Any, business_id: str, user_id: str) -> dict[str, Any]:
    business = _load_business(cursor, business_id)
    latest_card = _load_latest_card(cursor, business_id)
    reviews = _load_review_counts(cursor, business_id, latest_card)
    pending_news = _count_pending_news(cursor, business_id, user_id)
    reply_drafts = _count_reply_drafts(cursor, business_id)
    pending_approvals = _count_pending_approvals(cursor, business_id)
    partnerships = _count_partnership_leads(cursor, business_id)

    items: list[dict[str, Any]] = []
    if reviews["without_response"] > 0:
        items.append(
            _attention_item(
                "reviews_without_response",
                "reviews",
                "high",
                "Отзывы без ответа",
                "Это последние сохранённые данные в LocalOS. Для свежего среза нужно обновление карт за кредиты.",
                reviews["without_response"],
                "Открыть карточку",
                "/dashboard/card",
            )
        )
    if pending_approvals > 0:
        items.append(
            _attention_item(
                "pending_approvals",
                "approvals",
                "high",
                "Действия ждут подтверждения",
                "Есть операции, которые нельзя выполнить без ручного решения владельца.",
                pending_approvals,
                "Открыть настройки",
                "/dashboard/settings",
                "approval_required",
            )
        )
    if reply_drafts > 0:
        items.append(
            _attention_item(
                "review_reply_drafts",
                "reviews",
                "medium",
                "Черновики ответов готовы",
                "LocalOS может подготовить тексты, но публикация в карты остаётся ручной через копирование.",
                reply_drafts,
                "Открыть карточку",
                "/dashboard/card",
                "manual_external",
            )
        )
    if pending_news > 0:
        items.append(
            _attention_item(
                "pending_news",
                "content",
                "medium",
                "Черновики новостей ждут решения",
                "Проверьте сохранённые материалы перед публикацией или дальнейшей работой.",
                pending_news,
                "Открыть рост",
                "/dashboard/progress",
            )
        )
    if partnerships["ready"] > 0:
        items.append(
            _attention_item(
                "partnership_leads_ready",
                "partnerships",
                "medium",
                "Партнёрства готовы к разбору",
                "В shortlist есть партнёры, с которыми можно перейти к выбору канала или черновику сообщения.",
                partnerships["ready"],
                "Открыть партнёрства",
                "/dashboard/partnerships",
            )
        )

    card_age_days = latest_card.get("age_days")
    data_is_stale = card_age_days is None or int(card_age_days or 0) > STALE_DAYS
    if data_is_stale:
        items.append(
            _attention_item(
                "map_data_stale",
                "maps",
                "low",
                "Данные карт стоит обновить",
                "Сейчас показаны последние известные данные. Обновление карт относится к платным внешним действиям.",
                int(card_age_days or 0),
                "Показать старые данные",
                "/dashboard/card",
                "paid_external",
            )
        )

    if not items:
        items.append(
            _attention_item(
                "no_urgent_items",
                "status",
                "low",
                "Срочных задач не найдено",
                "По сохранённым данным нет отзывов без ответа, ожидающих подтверждений или черновиков на разбор.",
                0,
                "Открыть прогресс",
                "/dashboard/progress",
            )
        )

    primary = items[0]
    business_name = str(business.get("name") or business.get("business_name") or "Бизнес").strip()
    brief = {
        "business": {
            "id": business_id,
            "name": business_name,
        },
        "intent": "attention_brief",
        "query": "Что требует моего внимания сегодня?",
        "action_class": "free_cached",
        "data_mode": "cached",
        "summary": {
            "title": "Что важно сегодня",
            "text": f"Нашёл {len(items)} пунктов по последним сохранённым данным. Первый шаг: {primary['title'].lower()}.",
            "signals_count": sum(int(item.get("count") or 0) for item in items if item.get("id") != "map_data_stale"),
            "primary_action": primary,
        },
        "metrics": {
            "reviews_total": reviews["total"],
            "reviews_without_response": reviews["without_response"],
            "pending_approvals": pending_approvals,
            "pending_news": pending_news,
            "review_reply_drafts": reply_drafts,
            "partnership_leads_total": partnerships["total"],
            "partnership_leads_ready": partnerships["ready"],
        },
        "freshness": {
            "latest_card_at": latest_card.get("created_at_iso"),
            "latest_reviews_at": reviews.get("latest_seen_at"),
            "card_age_days": card_age_days,
            "is_stale": data_is_stale,
            "stale_after_days": STALE_DAYS,
            "paid_refresh_required_for_fresh_data": True,
            "message": "Показываю последние известные данные бесплатно. Обновление карт сейчас будет платным действием и потребует consent-политики.",
        },
        "items": items,
        "limits": {
            "external_writes_performed": False,
            "paid_actions_performed": False,
            "manual_publication_only": True,
        },
    }
    return brief
