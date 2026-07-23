from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.operator_attention import STALE_DAYS, build_attention_brief


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    if isinstance(row, (tuple, list)):
        return {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
    return {}


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    return bool(_row_to_dict(cursor, cursor.fetchone()).get("table_ref"))


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    text = str(value or "").strip()
    return text or None


def _age_days(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if not parsed.tzinfo:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() // 86400))


def _metric(
    key: str,
    label: str,
    value: Any,
    *,
    source: str,
    scope: str,
    updated_at: Any = None,
    status: str = "available",
    explanation: str = "",
) -> dict[str, Any]:
    source_labels = {
        "cards.latest": "Карты",
        "externalbusinessreviews": "Отзывы LocalOS",
        "businesses.network_id": "Структура LocalOS",
        "operator.summary": "Оператор LocalOS",
        "businesses": "Бизнесы LocalOS",
        "networks": "Сети LocalOS",
        "action_requests": "Подтверждения LocalOS",
        "parsequeue": "Очередь обновлений",
        "outreach_campaign_touches": "Аутрич LocalOS",
        "social_posts": "Контент LocalOS",
    }
    observed_at = updated_at or datetime.now(timezone.utc)
    return {
        "key": key,
        "label": label,
        "value": value,
        "source": source,
        "source_label": source_labels.get(source, source),
        "scope": scope,
        "updated_at": _iso(observed_at),
        "freshness_days": _age_days(observed_at),
        "status": status,
        "explanation": explanation,
    }


def _available_actions(kind: str) -> list[dict[str, Any]]:
    common = [
        {"key": "reviews", "label": "Отзывы", "href": "/dashboard/card?tab=reviews"},
        {"key": "cards", "label": "Карточки", "href": "/dashboard/card"},
        {"key": "content", "label": "Контент", "href": "/dashboard/content"},
        {"key": "approvals", "label": "Подтверждения", "href": "/dashboard/operator"},
    ]
    if kind == "business":
        return [
            {"key": "ask", "label": "Спросить LocalOS", "callback": "client_ask"},
            *common,
            {"key": "services", "label": "Услуги", "href": "/dashboard/card?tab=services"},
            {"key": "finance", "label": "Финансы", "href": "/dashboard/finance"},
            {"key": "partnerships", "label": "Партнёрства", "href": "/dashboard/partnerships"},
            {"key": "agents", "label": "ИИ-сотрудники", "href": "/dashboard/agents"},
            {"key": "settings", "label": "Настройки", "href": "/dashboard/settings"},
        ]
    if kind == "network":
        return [
            {"key": "locations", "label": "Точки сети", "callback": "control_locations"},
            {"key": "network", "label": "Открыть сеть", "href": "/dashboard/network"},
            {"key": "approvals", "label": "Подтверждения", "href": "/dashboard/operator"},
            {"key": "content", "label": "Контент", "href": "/dashboard/content"},
            {"key": "finance", "label": "Финансы", "href": "/dashboard/finance"},
            {"key": "partnerships", "label": "Партнёрства", "href": "/dashboard/partnerships"},
            {"key": "agents", "label": "ИИ-сотрудники", "href": "/dashboard/agents"},
            {"key": "settings", "label": "Настройки", "href": "/dashboard/settings"},
        ]
    return [
        {"key": "businesses", "label": "Бизнесы", "callback": "control_switch"},
        {"key": "approvals", "label": "Подтверждения", "href": "/dashboard/operator"},
        {"key": "content", "label": "Публикации", "href": "/dashboard/content"},
        {"key": "outreach", "label": "Аутрич", "href": "/dashboard/bazich?tab=prospecting"},
        {"key": "agents", "label": "ИИ-сотрудники", "href": "/dashboard/agents"},
        {"key": "settings", "label": "Настройки", "href": "/dashboard/settings"},
        {"key": "diagnostics", "label": "Диагностика", "callback": "menu_diagnostics"},
    ]


def _business_source_metrics(cursor: Any, business_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    metrics: list[dict[str, Any]] = []
    warnings: list[str] = []
    cursor.execute(
        """
        SELECT rating, reviews_count, created_at
        FROM cards
        WHERE business_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (business_id,),
    )
    card = _row_to_dict(cursor, cursor.fetchone())
    if card:
        metrics.extend(
            [
                _metric(
                    "provider_rating",
                    "Рейтинг на карте",
                    card.get("rating"),
                    source="cards.latest",
                    scope="business",
                    updated_at=card.get("created_at"),
                ),
                _metric(
                    "provider_reviews_total",
                    "Отзывов на карте",
                    int(card.get("reviews_count") or 0),
                    source="cards.latest",
                    scope="business",
                    updated_at=card.get("created_at"),
                    explanation="Общее число, показанное провайдером карт на момент последнего сбора.",
                ),
            ]
        )
    else:
        metrics.append(
            _metric(
                "provider_reviews_total",
                "Отзывов на карте",
                None,
                source="cards.latest",
                scope="business",
                status="unknown",
                explanation="Карточка ещё не загружена.",
            )
        )

    if _table_exists(cursor, "externalbusinessreviews"):
        cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE COALESCE(TRIM(response_text), '') = '') AS unanswered,
                   MAX(COALESCE(updated_at, created_at)) AS updated_at
            FROM externalbusinessreviews
            WHERE business_id = %s
            """,
            (business_id,),
        )
        reviews = _row_to_dict(cursor, cursor.fetchone())
        imported_total = int(reviews.get("total") or 0)
        metrics.extend(
            [
                _metric(
                    "imported_reviews_total",
                    "Загружено в LocalOS",
                    imported_total,
                    source="externalbusinessreviews",
                    scope="business",
                    updated_at=reviews.get("updated_at"),
                ),
                _metric(
                    "imported_reviews_unanswered",
                    "Без ответа в LocalOS",
                    int(reviews.get("unanswered") or 0),
                    source="externalbusinessreviews",
                    scope="business",
                    updated_at=reviews.get("updated_at"),
                ),
            ]
        )
        provider_metric = next((item for item in metrics if item["key"] == "provider_reviews_total"), None)
        provider_total = provider_metric.get("value") if provider_metric else None
        if provider_total is not None and int(provider_total) != imported_total:
            warnings.append(
                f"На карте указано {int(provider_total)} отзывов, в LocalOS загружено {imported_total}. "
                "Это разные показатели; для полного списка нужно обновить данные."
            )
    return metrics, warnings


def _business_summary(cursor: Any, scope: dict[str, Any], user_id: str) -> dict[str, Any]:
    business_id = str(scope.get("id") or "")
    brief = build_attention_brief(cursor, business_id, user_id)
    metrics, warnings = _business_source_metrics(cursor, business_id)
    items = [item for item in (brief.get("items") or []) if isinstance(item, dict)][:3]
    primary = items[0] if items else None
    freshness = brief.get("freshness") if isinstance(brief.get("freshness"), dict) else {}
    return {
        "scope": scope,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "freshness": freshness,
        "metrics": metrics,
        "attention_items": items,
        "primary_action": primary,
        "available_actions": _available_actions("business"),
        "data_warnings": warnings,
    }


def _network_rows(cursor: Any, business_ids: list[str]) -> list[dict[str, Any]]:
    if not business_ids:
        return []
    cursor.execute(
        """
        SELECT
            b.id,
            b.name,
            card.rating,
            card.reviews_count,
            card.created_at AS card_updated_at,
            COALESCE(reviews.imported_total, 0) AS imported_total,
            COALESCE(reviews.unanswered, 0) AS unanswered
        FROM businesses b
        LEFT JOIN LATERAL (
            SELECT rating, reviews_count, created_at
            FROM cards
            WHERE business_id = b.id
            ORDER BY created_at DESC
            LIMIT 1
        ) card ON TRUE
        LEFT JOIN LATERAL (
            SELECT COUNT(*) AS imported_total,
                   COUNT(*) FILTER (WHERE COALESCE(TRIM(response_text), '') = '') AS unanswered
            FROM externalbusinessreviews
            WHERE business_id = b.id
        ) reviews ON TRUE
        WHERE b.id = ANY(%s)
        ORDER BY b.name
        """,
        (business_ids,),
    )
    return [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]


def _network_summary(cursor: Any, scope: dict[str, Any]) -> dict[str, Any]:
    business_ids = [str(item) for item in (scope.get("business_ids") or []) if str(item)]
    rows = _network_rows(cursor, business_ids)
    stale_count = sum(1 for item in rows if _age_days(item.get("card_updated_at")) is None or int(_age_days(item.get("card_updated_at")) or 0) > STALE_DAYS)
    unanswered = sum(int(item.get("unanswered") or 0) for item in rows)
    needing_attention = []
    for item in rows:
        reasons = []
        if int(item.get("unanswered") or 0) > 0:
            reasons.append(f"без ответа: {int(item.get('unanswered') or 0)}")
        age = _age_days(item.get("card_updated_at"))
        if age is None:
            reasons.append("нет данных карты")
        elif age > STALE_DAYS:
            reasons.append(f"данные старше {age} дн.")
        rating = item.get("rating")
        if rating is not None and float(rating) < 4.3:
            reasons.append(f"рейтинг {rating}")
        if reasons:
            needing_attention.append(
                {
                    "id": str(item.get("id") or ""),
                    "title": str(item.get("name") or "Точка"),
                    "description": ", ".join(reasons),
                    "severity": "high" if int(item.get("unanswered") or 0) > 0 else "medium",
                    "count": int(item.get("unanswered") or 0),
                    "target_scope": {"kind": "business", "id": str(item.get("id") or "")},
                }
            )
    needing_attention.sort(key=lambda item: (0 if item["severity"] == "high" else 1, -int(item["count"])))
    metrics = [
        _metric("locations_total", "Точек в сети", len(rows), source="businesses.network_id", scope="network"),
        _metric("locations_attention", "Требуют внимания", len(needing_attention), source="operator.summary", scope="network"),
        _metric("reviews_unanswered", "Отзывы без ответа", unanswered, source="externalbusinessreviews", scope="network"),
        _metric("locations_stale", "Данные устарели", stale_count, source="cards.latest", scope="network"),
    ]
    primary = needing_attention[0] if needing_attention else {
        "id": "network_ok",
        "title": "Срочных задач нет",
        "description": "По сохранённым данным точки сети не требуют срочного вмешательства.",
        "severity": "low",
        "count": 0,
    }
    return {
        "scope": scope,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "freshness": {"is_stale": stale_count > 0, "stale_locations_count": stale_count, "stale_after_days": STALE_DAYS},
        "metrics": metrics,
        "attention_items": needing_attention[:5],
        "primary_action": primary,
        "available_actions": _available_actions("network"),
        "data_warnings": [],
    }


def _safe_count(cursor: Any, table_name: str, query: str, params: tuple[Any, ...] = ()) -> int:
    if not _table_exists(cursor, table_name):
        return 0
    cursor.execute(query, params)
    return int(_row_to_dict(cursor, cursor.fetchone()).get("cnt") or 0)


def _platform_summary(cursor: Any, scope: dict[str, Any]) -> dict[str, Any]:
    cursor.execute("SELECT COUNT(*) AS cnt FROM businesses WHERE COALESCE(is_active, TRUE) = TRUE")
    businesses_count = int(_row_to_dict(cursor, cursor.fetchone()).get("cnt") or 0)
    cursor.execute("SELECT COUNT(*) AS cnt FROM networks")
    networks_count = int(_row_to_dict(cursor, cursor.fetchone()).get("cnt") or 0)
    pending_approvals = _safe_count(
        cursor,
        "action_requests",
        "SELECT COUNT(*) AS cnt FROM action_requests WHERE status = 'pending_human'",
    )
    failed_jobs = _safe_count(
        cursor,
        "parsequeue",
        "SELECT COUNT(*) AS cnt FROM parsequeue WHERE status IN ('error', 'failed', 'captcha_required')",
    )
    outreach_replies = _safe_count(
        cursor,
        "outreach_campaign_touches",
        "SELECT COUNT(*) AS cnt FROM outreach_campaign_touches WHERE status IN ('replied', 'reply_received', 'needs_attention')",
    )
    pending_posts = _safe_count(
        cursor,
        "social_posts",
        "SELECT COUNT(*) AS cnt FROM social_posts WHERE status IN ('draft', 'needs_review', 'failed')",
    )
    metrics = [
        _metric("businesses_total", "Активных бизнесов", businesses_count, source="businesses", scope="platform"),
        _metric("networks_total", "Сетей", networks_count, source="networks", scope="platform"),
        _metric("pending_approvals", "Ждут подтверждения", pending_approvals, source="action_requests", scope="platform"),
        _metric("failed_jobs", "Ошибки обновлений", failed_jobs, source="parsequeue", scope="platform"),
        _metric("outreach_replies", "Ответы и внимание в аутриче", outreach_replies, source="outreach_campaign_touches", scope="platform"),
        _metric("pending_posts", "Публикации к разбору", pending_posts, source="social_posts", scope="platform"),
    ]
    attention = []
    for key, title, description, count in (
        ("failed_jobs", "Ошибки обновлений", "Есть failed/captcha задачи, которые нужно разобрать.", failed_jobs),
        ("pending_approvals", "Действия ждут решения", "Операции не выполнятся без ручного подтверждения.", pending_approvals),
        ("outreach_replies", "Ответы в аутриче", "Новые ответы останавливают следующие касания и требуют разбора.", outreach_replies),
        ("pending_posts", "Публикации требуют внимания", "Проверьте черновики и ошибки публикаций.", pending_posts),
    ):
        if count > 0:
            attention.append({"id": key, "title": title, "description": description, "count": count, "severity": "high" if key == "failed_jobs" else "medium"})
    if not attention:
        attention.append({"id": "platform_ok", "title": "Срочных задач нет", "description": "По операционным очередям критичных сигналов нет.", "count": 0, "severity": "low"})
    return {
        "scope": scope,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "freshness": {"mode": "live_database", "is_stale": False},
        "metrics": metrics,
        "attention_items": attention[:5],
        "primary_action": attention[0],
        "available_actions": _available_actions("platform"),
        "data_warnings": [],
    }


def build_operator_scope_summary(cursor: Any, *, scope: dict[str, Any], user_id: str) -> dict[str, Any]:
    kind = str(scope.get("kind") or "business")
    if kind == "platform":
        return _platform_summary(cursor, scope)
    if kind == "network":
        return _network_summary(cursor, scope)
    return _business_summary(cursor, scope, user_id)


def format_scope_summary_for_telegram(summary: dict[str, Any]) -> str:
    scope = summary.get("scope") if isinstance(summary.get("scope"), dict) else {}
    kind = str(scope.get("kind") or "business")
    if kind == "platform":
        header = f"LocalOS · Вся платформа · {next((item.get('value') for item in summary.get('metrics') or [] if item.get('key') == 'businesses_total'), 0)} бизнесов"
    elif kind == "network":
        header = f"LocalOS · Сеть «{scope.get('name') or 'Сеть'}» · {len(scope.get('business_ids') or [])} точек"
    else:
        header = f"LocalOS · {scope.get('name') or 'Бизнес'}"
    lines = [header, "", "Что важно сейчас"]
    for item in (summary.get("attention_items") or [])[:3]:
        count = int(item.get("count") or 0)
        suffix = f" — {count}" if count > 0 else ""
        lines.append(f"• {item.get('title') or 'Задача'}{suffix}")
        if item.get("description"):
            lines.append(f"  {item.get('description')}")
    metrics = summary.get("metrics") or []
    if metrics:
        lines.extend(["", "Данные"])
        for metric in metrics[:6]:
            value = metric.get("value")
            rendered = "нет данных" if value is None else str(value)
            updated = str(metric.get("updated_at") or "")
            freshness = f" · на {updated[8:10]}.{updated[5:7]} {updated[11:16]}" if len(updated) >= 16 else ""
            source = str(metric.get("source_label") or metric.get("source") or "LocalOS")
            lines.append(f"• {metric.get('label')}: {rendered}{freshness} · {source}")
    warnings = [str(item) for item in (summary.get("data_warnings") or []) if str(item).strip()]
    if warnings:
        lines.extend(["", "Важно", *[f"• {item}" for item in warnings[:2]]])
    return "\n".join(lines)
