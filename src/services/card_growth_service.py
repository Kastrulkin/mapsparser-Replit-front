"""Managed, evidence-backed growth state for map listings."""
from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from psycopg2.extras import Json

from core.card_platform_policy import POLICY_VERSION, PROVIDERS, provider_rules


GOALS = {"inquiries", "bookings", "orders", "directions", "website_visits"}
GOAL_LABELS = {
    "inquiries": "Больше обращений",
    "bookings": "Больше записей",
    "orders": "Больше заказов",
    "directions": "Больше построенных маршрутов",
    "website_visits": "Больше переходов на сайт",
}
GATE_LABELS = {
    0: "Данные доступны",
    1: "Карточка корректна",
    2: "Можно обратиться",
    3: "Предложение понятно",
    4: "Есть доверие",
    5: "Есть доказательства",
    6: "Есть повод вернуться",
}
PROVIDER_LABELS = {"google": "Google", "yandex": "Яндекс", "2gis": "2ГИС"}


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS relation", (f"public.{table_name}",))
    return bool(_row(cursor, cursor.fetchone()).get("relation"))


def _columns(cursor: Any, table_name: str) -> set[str]:
    cursor.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
        (table_name.lower(),),
    )
    return {str(_row(cursor, value).get("column_name") or "") for value in (cursor.fetchall() or [])}


def _json(value: Any, fallback: Any = None) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback
    return fallback


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _provider(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if "google" in normalized:
        return "google"
    if "yandex" in normalized or normalized in {"ya", "maps"}:
        return "yandex"
    if "2gis" in normalized or "doublegis" in normalized:
        return "2gis"
    return None


def _provider_from_url(value: Any) -> str | None:
    url = str(value or "").lower()
    if "google." in url or "goo.gl" in url:
        return "google"
    if "yandex." in url or "ya.ru" in url:
        return "yandex"
    if "2gis." in url:
        return "2gis"
    return None


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _count_json(value: Any) -> int:
    parsed = _json(value, value)
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, dict):
        return len(parsed)
    return 0


def _count_priced_items(value: Any) -> int:
    parsed = _json(value, value)
    items = parsed if isinstance(parsed, list) else list(parsed.values()) if isinstance(parsed, dict) else []
    return sum(
        1
        for item in items
        if isinstance(item, dict) and any(item.get(key) not in (None, "") for key in ("price", "price_from", "price_to", "cost"))
    )


def _fact(
    value: Any,
    state: str,
    source: str,
    observed_at: Any,
    confidence: float,
    rule_ids: list[str],
    evidence: str = "",
) -> dict[str, Any]:
    return {
        "value": value,
        "state": state,
        "source": source,
        "observed_at": observed_at.isoformat() if hasattr(observed_at, "isoformat") else observed_at,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "rule_ids": rule_ids,
        "evidence": evidence,
    }


def _rule_ids(provider: str, fact: str) -> list[str]:
    return [str(item["rule_id"]) for item in provider_rules(provider) if item["fact"] == fact]


def _latest_sources(cursor: Any, business_id: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    links: dict[str, dict[str, Any]] = {}
    parses: dict[str, dict[str, Any]] = {}
    if _table_exists(cursor, "businessmaplinks"):
        cursor.execute(
            "SELECT url, map_type, created_at FROM businessmaplinks WHERE business_id=%s ORDER BY created_at DESC",
            (business_id,),
        )
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            provider = _provider(item.get("map_type")) or _provider_from_url(item.get("url"))
            if provider and provider not in links:
                links[provider] = item
    if _table_exists(cursor, "mapparseresults"):
        cursor.execute("SELECT * FROM mapparseresults WHERE business_id=%s ORDER BY created_at DESC", (business_id,))
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            provider = _provider(item.get("map_type")) or _provider_from_url(item.get("url"))
            if provider and provider not in parses:
                parses[provider] = item
    if _table_exists(cursor, "cards"):
        cursor.execute("SELECT * FROM cards WHERE business_id=%s ORDER BY is_latest DESC NULLS LAST, updated_at DESC, created_at DESC", (business_id,))
        for value in cursor.fetchall() or []:
            item = _row(cursor, value)
            provider = _provider_from_url(item.get("url"))
            if provider and provider not in parses:
                item["services_count"] = _count_json(item.get("products"))
                item["photos_count"] = _count_json(item.get("photos"))
                item["news_count"] = _count_json(item.get("news"))
                item["working_hours"] = item.get("hours") or item.get("hours_full")
                item["website"] = item.get("site")
                item["created_at"] = item.get("updated_at") or item.get("created_at")
                parses[provider] = item
    return links, parses


def _review_state(cursor: Any, business_id: str, provider: str) -> tuple[int | None, int | None, datetime | None]:
    if not _table_exists(cursor, "externalbusinessreviews"):
        return None, None, None
    sources = {
        "google": ["google_business", "google_maps", "google"],
        "yandex": ["yandex_maps", "yandex_business"],
        "2gis": ["2gis"],
    }[provider]
    columns = _columns(cursor, "externalbusinessreviews")
    current_clause = "AND COALESCE(is_current, TRUE)=TRUE" if "is_current" in columns else ""
    cursor.execute(
        f"""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE COALESCE(NULLIF(TRIM(response_text), ''), '') IN ('', '—')) AS unanswered,
               MAX(COALESCE(published_at, created_at)) AS observed_at
        FROM externalbusinessreviews
        WHERE business_id=%s AND source=ANY(%s) {current_clause}
        """,
        (business_id, sources),
    )
    item = _row(cursor, cursor.fetchone())
    total = int(item.get("total") or 0)
    return total, int(item.get("unanswered") or 0), _datetime(item.get("observed_at"))


def _priced_services(cursor: Any, business_id: str) -> tuple[int, int]:
    if not _table_exists(cursor, "userservices"):
        return 0, 0
    columns = _columns(cursor, "userservices")
    active_clause = "AND COALESCE(is_active, TRUE)=TRUE" if "is_active" in columns else ""
    price_columns = [name for name in ("price", "price_from", "price_to", "cost") if name in columns]
    price_expression = " OR ".join(f"{name} IS NOT NULL" for name in price_columns) or "FALSE"
    cursor.execute(
        f"SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE {price_expression}) AS priced FROM userservices WHERE business_id=%s {active_clause}",
        (business_id,),
    )
    item = _row(cursor, cursor.fetchone())
    return int(item.get("total") or 0), int(item.get("priced") or 0)


def _latest_search_queries(cursor: Any, business_id: str, provider: str) -> list[dict[str, Any]]:
    if provider != "google" or not _table_exists(cursor, "externalbusinessstats"):
        return []
    cursor.execute(
        """
        SELECT raw_payload FROM externalbusinessstats
        WHERE business_id=%s AND source=ANY(%s)
        ORDER BY date::date DESC, updated_at DESC LIMIT 1
        """,
        (business_id, ["google_business", "google_maps", "google"]),
    )
    item = _row(cursor, cursor.fetchone())
    raw = _json(item.get("raw_payload"), {}) or {}
    queries = raw.get("search_queries") if isinstance(raw.get("search_queries"), list) else []
    return [query for query in queries if isinstance(query, dict)][:100]


def _business(cursor: Any, business_id: str) -> dict[str, Any]:
    cursor.execute("SELECT id, name, business_type, city, address, phone, website, working_hours, network_id FROM businesses WHERE id=%s", (business_id,))
    return _row(cursor, cursor.fetchone())


def _parse_values(parse: dict[str, Any]) -> dict[str, Any]:
    overview = _json(parse.get("overview"), {}) or _json(parse.get("analysis_json"), {}) or {}
    categories = _json(parse.get("categories"), parse.get("categories"))
    if not categories:
        categories = overview.get("categories") or overview.get("category")
    services_count = int(parse.get("services_count") or _count_json(parse.get("products")) or 0)
    photos_count = int(parse.get("photos_count") or _count_json(parse.get("photos")) or 0)
    news_count = int(parse.get("news_count") or parse.get("posts_count") or _count_json(parse.get("news")) or 0)
    prices_count = int(parse.get("prices_count") or _count_priced_items(parse.get("products")) or 0)
    return {
        "rating": _number(parse.get("rating")),
        "reviews_count": int(parse.get("reviews_count") or 0),
        "unanswered_reviews": int(parse.get("unanswered_reviews_count") or 0),
        "services_count": services_count,
        "photos_count": photos_count,
        "publications_count": news_count,
        "prices_count": prices_count,
        "category": categories,
        "phone": parse.get("phone") or overview.get("phone"),
        "website": parse.get("website") or parse.get("site") or overview.get("website") or overview.get("site"),
        "working_hours": parse.get("working_hours") or parse.get("hours") or overview.get("working_hours") or overview.get("hours"),
        "verified": parse.get("is_verified") if isinstance(parse.get("is_verified"), bool) else overview.get("is_verified"),
        "duplicate": overview.get("is_duplicate") if isinstance(overview.get("is_duplicate"), bool) else None,
    }


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((len(ordered) - 1) * ratio)))
    return round(ordered[index], 2)


def _normalized_category(value: Any) -> str:
    category = str(value or "").strip().lower()
    groups = (
        ("beauty", ("салон", "красот", "парикмах", "барбер", "spa", "спа", "космет")),
        ("education", ("школ", "образован", "обучен", "детский центр", "курс")),
        ("transport", ("трансфер", "такси", "перевоз", "автобус", "travel", "тур")),
        ("food", ("ресторан", "кафе", "кофейн", "достав", "еда", "бар")),
        ("health", ("мед", "клиник", "стомат", "врач", "диагност")),
        ("fitness", ("фитнес", "спорт", "йога", "танц")),
        ("entertainment", ("парк", "музей", "каток", "театр", "концерт", "развлеч")),
        ("hospitality", ("отел", "гостини", "хостел", "апарт")),
        ("retail", ("магазин", "товар", "маркет")),
    )
    return next((name for name, markers in groups if any(marker in category for marker in markers)), category)


def _benchmark(cursor: Any, business: dict[str, Any], provider: str) -> dict[str, Any]:
    if not _table_exists(cursor, "mapparseresults"):
        return {"status": "unavailable", "sample_size": 0, "period_days": 90}
    provider_pattern = {"google": "%google%", "yandex": "%yandex%", "2gis": "%2gis%"}[provider]
    cursor.execute(
        """
        SELECT DISTINCT ON (p.business_id)
               p.rating, p.reviews_count, p.photos_count, p.services_count,
               b.business_type, b.city
        FROM mapparseresults p JOIN businesses b ON b.id=p.business_id
        WHERE p.business_id<>%s
          AND p.created_at>=NOW()-INTERVAL '90 days'
          AND LOWER(COALESCE(p.map_type, '')) LIKE %s
        ORDER BY p.business_id, p.created_at DESC
        """,
        (business["id"], provider_pattern),
    )
    candidates = [_row(cursor, value) for value in (cursor.fetchall() or [])]
    category = _normalized_category(business.get("business_type"))
    same_category = [item for item in candidates if _normalized_category(item.get("business_type")) == category]
    city = str(business.get("city") or "").strip().lower()
    same_city = [item for item in same_category if city and str(item.get("city") or "").strip().lower() == city]
    selected = same_city if len(same_city) >= 10 else same_category
    selected_scope = "city_category" if len(same_city) >= 10 else "national_category"
    metrics: dict[str, Any] = {}
    for key in ("rating", "reviews_count", "photos_count", "services_count"):
        values = [_number(item.get(key)) for item in selected]
        clean = [value for value in values if value is not None]
        metrics[key] = {"median": _percentile(clean, 0.5), "p75": _percentile(clean, 0.75)}
    return {
        "status": "ready" if len(selected) >= 10 else "small_sample",
        "scope": selected_scope,
        "sample_size": len(selected),
        "period_days": 90,
        "metrics": metrics,
        "disclaimer": "Ориентир по сопоставимым карточкам, а не доказательство причины результата.",
    }


def _provider_state(cursor: Any, business: dict[str, Any], provider: str, link: dict[str, Any] | None, parse: dict[str, Any] | None) -> dict[str, Any]:
    observed_at = _datetime((parse or {}).get("created_at") or (parse or {}).get("updated_at"))
    age_days = (datetime.now(timezone.utc).date() - observed_at.date()).days if observed_at else None
    parse_status = str((parse or {}).get("status") or "").lower()
    blocked = parse_status in {"error", "failed", "captcha", "blocked"}
    stale = age_days is not None and age_days > 90
    reliable = bool(parse) and not blocked and not stale
    confidence = 1.0 if observed_at and age_days is not None and age_days <= 45 else 0.75 if reliable else 0.0
    source = f"mapparseresults.{provider}" if parse else f"businessmaplinks.{provider}" if link else "registry"
    values = _parse_values(parse or {})
    review_total, unanswered, review_at = _review_state(cursor, str(business["id"]), provider)
    if review_total is not None:
        values["reviews_count"] = review_total
        values["unanswered_reviews"] = unanswered or 0
        observed_at = max([item for item in (observed_at, review_at) if item], default=observed_at)
    internal_services, priced_services = _priced_services(cursor, str(business["id"]))
    search_queries = _latest_search_queries(cursor, str(business["id"]), provider)
    if values["services_count"] <= 0 and internal_services > 0:
        values["services_count"] = internal_services
        services_state = "unknown"
    else:
        services_state = "observed" if values["services_count"] > 0 else "missing" if reliable else "unknown"

    def present(value: Any) -> str:
        return "observed" if bool(value) else "missing" if reliable else "unknown"

    facts = {
        "access": _fact(bool(link), "observed" if link else "missing", source, observed_at or (link or {}).get("created_at"), 1.0, _rule_ids(provider, "access"), "Карточка подключена" if link else "Ссылка на площадку не добавлена"),
        "duplicate": _fact(values["duplicate"], "observed" if values["duplicate"] is False else "missing" if values["duplicate"] is True else "unknown", source, observed_at, confidence, _rule_ids(provider, "duplicate"), "Дубли не обнаружены" if values["duplicate"] is False else "Площадка не передала надёжный признак дубля"),
        "category": _fact(values["category"], present(values["category"]), source, observed_at, confidence, _rule_ids(provider, "category")),
        "contacts": _fact({"phone": values["phone"], "website": values["website"]}, present(values["phone"] or values["website"]), source, observed_at, confidence, _rule_ids(provider, "contacts"), "Контакты из профиля бизнеса не доказывают, что они опубликованы на площадке" if not values["phone"] and not values["website"] and (business.get("phone") or business.get("website")) else ""),
        "schedule": _fact(values["working_hours"], present(values["working_hours"]), source, observed_at, confidence, _rule_ids(provider, "schedule"), "Внутреннее расписание не доказывает, что часы обновлены на площадке" if not values["working_hours"] and business.get("working_hours") else ""),
        "action_path": _fact(bool(values["phone"] or values["website"]), present(values["phone"] or values["website"]), source, observed_at, confidence, _rule_ids(provider, "action_path")),
        "services": _fact(values["services_count"], services_state, source, observed_at, confidence if services_state != "unknown" else 0.5, _rule_ids(provider, "services"), "Внутренние услуги не доказывают их публикацию на площадке" if services_state == "unknown" and internal_services else ""),
        "prices": _fact(values["prices_count"], "observed" if values["prices_count"] > 0 else "unknown" if priced_services > 0 else "missing" if reliable and values["services_count"] > 0 else "unknown", source, observed_at, confidence if values["prices_count"] else 0.5 if priced_services else confidence, _rule_ids(provider, "prices"), "Во внутреннем справочнике цены есть, но нужна проверка площадки" if priced_services and not values["prices_count"] else ""),
        "reviews": _fact({"count": values["reviews_count"], "rating": values["rating"]}, "observed" if review_total is not None or reliable else "unknown", source, observed_at, confidence, _rule_ids(provider, "reviews")),
        "review_responses": _fact({"unanswered": values["unanswered_reviews"]}, "missing" if values["unanswered_reviews"] > 0 else "observed" if review_total is not None else "unknown", source, observed_at, confidence, _rule_ids(provider, "review_responses")),
        "photos": _fact(values["photos_count"], "observed" if values["photos_count"] > 0 else "missing" if reliable else "unknown", source, observed_at, confidence, _rule_ids(provider, "photos")),
        "publications": _fact(values["publications_count"], "not_applicable" if provider == "2gis" else "observed" if values["publications_count"] > 0 else "missing" if reliable else "unknown", source, observed_at, confidence, _rule_ids(provider, "publications"), "У 2ГИС нет органического канала новостей" if provider == "2gis" else "Публикации оцениваются как конверсионный контент, а не обязательный фактор позиции" if provider == "yandex" else ""),
    }
    if provider in {"google", "yandex"}:
        verified = values["verified"]
        facts["verified"] = _fact(verified, "observed" if verified is True else "missing" if verified is False else "unknown", source, observed_at, confidence, _rule_ids(provider, "verified"))
    if blocked:
        for key, item in facts.items():
            if key != "access" and item["state"] != "not_applicable":
                item["state"] = "blocked"
                item["confidence"] = 0.0
                item["evidence"] = "Последнее обновление площадки завершилось ошибкой"
    return {
        "provider": provider,
        "provider_label": PROVIDER_LABELS[provider],
        "source_state": "blocked" if blocked else "observed" if reliable else "unknown",
        "connected": bool(link),
        "observed_at": observed_at.isoformat() if observed_at else None,
        "age_days": age_days,
        "facts": facts,
        "metrics": {
            "rating": values["rating"],
            "reviews_count": values["reviews_count"],
            "unanswered_reviews": values["unanswered_reviews"],
            "services_count": values["services_count"],
            "photos_count": values["photos_count"],
            "publications_count": values["publications_count"],
            "prices_count": values["prices_count"],
            "search_queries": search_queries,
        },
        "benchmark": _benchmark(cursor, business, provider),
    }


def recommend_goal(business_type: Any) -> str:
    category = str(business_type or "").lower()
    if any(marker in category for marker in ("салон", "красот", "школ", "образован", "мед", "клиник", "фитнес", "spa", "спа")):
        return "bookings"
    if any(marker in category for marker in ("ресторан", "кафе", "достав", "магазин", "товар")):
        return "orders"
    if any(marker in category for marker in ("парк", "музей", "каток", "достопримеч")):
        return "directions"
    return "inquiries"


def _goal_relevance(goal: str, fact: str) -> int:
    if fact in {"contacts", "action_path"}:
        return 20
    if goal in {"bookings", "orders"} and fact in {"services", "prices"}:
        return 16
    if goal == "directions" and fact in {"schedule", "photos"}:
        return 14
    if goal == "website_visits" and fact == "publications":
        return 10
    return 0


def _action_copy(provider: str, fact: str, state: str) -> tuple[str, str, str, str]:
    label = PROVIDER_LABELS[provider]
    copies = {
        "access": (f"Подключите карточку {label}", "Без подключения LocalOS не может проверить карточку и отслеживать результат.", "Добавить площадку", "/dashboard/profile"),
        "verified": (f"Проверьте управление карточкой в {label}", "Площадка не подтверждает, что карточка находится под управлением бизнеса.", "Открыть карточку", "/dashboard/card"),
        "duplicate": (f"Проверьте дубли в {label}", "Дубль может разделять отзывы и вводить клиентов в заблуждение.", "Проверить карточку", "/dashboard/card"),
        "category": (f"Уточните основную категорию в {label}", "Категория должна точно описывать основную деятельность этой точки.", "Проверить категорию", "/dashboard/card"),
        "contacts": (f"Заполните контакты в {label}", "Клиент должен сразу понимать, как связаться с этой точкой.", "Проверить контакты", "/dashboard/card"),
        "schedule": (f"Уточните часы работы в {label}", "Актуальное расписание снижает риск потерянного визита.", "Проверить расписание", "/dashboard/card"),
        "action_path": (f"Добавьте понятный путь обращения в {label}", "Телефон, сайт или запись должны вести к конкретной точке и работать без лишних шагов.", "Проверить запись", "/dashboard/card"),
        "services": (f"Опубликуйте основные услуги в {label}", "По карточке пока нельзя уверенно понять, что именно предлагает бизнес.", "Открыть услуги", "/dashboard/card?tab=services"),
        "prices": (f"Добавьте цены в {label}", "Цена или понятный ориентир помогают принять решение до обращения.", "Открыть услуги", "/dashboard/card?tab=services"),
        "reviews": (f"Начните системно собирать отзывы в {label}", "Для этой карточки доверие пока подтверждено слабее, чем у сопоставимых компаний.", "Открыть отзывы", "/dashboard/card?tab=reviews"),
        "review_responses": (f"Ответьте на отзывы в {label}", "На карточке есть отзывы без ответа.", "Открыть отзывы", "/dashboard/card?tab=reviews&review_filter=needs_reply"),
        "photos": (f"Добавьте полезные фотографии в {label}", "Покажите вход, пространство, команду, процесс и результат, чтобы клиенту было проще выбрать.", "Открыть фотографии", "/dashboard/content?tab=media"),
        "publications": (f"Подготовьте актуальную публикацию для {label}", "Публикация должна дать конкретный повод обратиться сейчас; она не заменяет заполнение карточки.", "Открыть контент", "/dashboard/content"),
    }
    title, reason, cta_label, cta_url = copies[fact]
    if state == "blocked":
        return f"Восстановите обновление {label}", "Площадка временно не отдаёт достоверные данные. Сначала восстановите источник.", "Проверить подключение", "/dashboard/card"
    return title, reason, cta_label, cta_url


def _actions_for_location(location: dict[str, Any], goal: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for provider_state in location["providers"]:
        provider = str(provider_state["provider"])
        source_state = str(provider_state.get("source_state") or "unknown")
        if source_state in {"unknown", "blocked"}:
            label = PROVIDER_LABELS[provider]
            actions.append({
                "id": f"card-growth:{location['business_id']}:{provider}:refresh",
                "business_id": location["business_id"],
                "business_name": location["business_name"],
                "provider": provider,
                "provider_label": label,
                "fact": "access",
                "gate": 0,
                "gate_label": GATE_LABELS[0],
                "title": f"{'Восстановите обновление' if source_state == 'blocked' else 'Обновите данные'} {label}",
                "reason": "Последнее обновление завершилось ошибкой." if source_state == "blocked" else "Для выбора первого исправления нужен свежий снимок карточки.",
                "expected_outcome": "Получить достоверное состояние карточки и выбрать первое исправление.",
                "metric": _goal_metric(goal),
                "measurement_days": [14, 28],
                "cta_label": "Проверить подключение" if source_state == "blocked" else "Обновить данные",
                "cta_url": "/dashboard/card",
                "screen": "cards",
                "priority": 11100 if source_state == "blocked" else 11000,
                "rule_id": f"{provider}.access",
                "rule_url": next((item["url"] for item in provider_rules(provider) if item["fact"] == "access"), None),
                "influence": "eligibility",
                "confidence": 1.0,
                "target_scope": {"kind": "business", "id": location["business_id"]},
                "affected_business_ids": [location["business_id"]],
            })
            continue
        benchmark = provider_state.get("benchmark") or {}
        benchmark_metrics = benchmark.get("metrics") if isinstance(benchmark.get("metrics"), dict) else {}
        for rule in provider_rules(provider):
            fact_name = str(rule["fact"])
            fact = provider_state["facts"].get(fact_name)
            if not isinstance(fact, dict) or fact.get("state") not in {"missing", "blocked"}:
                continue
            title, reason, cta_label, cta_url = _action_copy(provider, fact_name, str(fact["state"]))
            benchmark_gap = 0
            metric_name = {"reviews": "reviews_count", "photos": "photos_count", "services": "services_count"}.get(fact_name)
            if metric_name and benchmark.get("sample_size", 0) >= 10:
                current = _number(provider_state.get("metrics", {}).get(metric_name)) or 0
                median = _number((benchmark_metrics.get(metric_name) or {}).get("median"))
                if median is not None and current < median:
                    benchmark_gap = 10
                    reason += f" У сопоставимых карточек медиана: {median:g}."
            gate = int(rule["gate"])
            confidence = float(fact.get("confidence") or 0)
            priority = 10000 - gate * 1000 + int(rule["impact"]) + _goal_relevance(goal, fact_name) + benchmark_gap + round(confidence * 10)
            actions.append({
                "id": f"card-growth:{location['business_id']}:{provider}:{fact_name}",
                "business_id": location["business_id"],
                "business_name": location["business_name"],
                "provider": provider,
                "provider_label": PROVIDER_LABELS[provider],
                "fact": fact_name,
                "gate": gate,
                "gate_label": GATE_LABELS[gate],
                "title": title,
                "reason": reason,
                "expected_outcome": _expected_outcome(goal),
                "metric": _goal_metric(goal),
                "measurement_days": [14, 28, 60] if fact_name in {"reviews", "review_responses"} else [14, 28],
                "cta_label": cta_label,
                "cta_url": cta_url,
                "screen": "reviews" if "reviews" in cta_url else "cards" if "/card" in cta_url else "content" if "/content" in cta_url else "settings",
                "priority": priority,
                "rule_id": rule["rule_id"],
                "rule_url": rule["url"],
                "influence": rule["influence"],
                "confidence": confidence,
                "target_scope": {"kind": "business", "id": location["business_id"]},
                "affected_business_ids": [location["business_id"]],
            })
    return sorted(actions, key=lambda item: (-int(item["priority"]), str(item["business_id"]), str(item["provider"]), str(item["fact"])))


def _goal_metric(goal: str) -> str:
    return {
        "inquiries": "actions_total",
        "bookings": "bookings_or_inquiries",
        "orders": "orders_or_inquiries",
        "directions": "directions",
        "website_visits": "website_clicks",
    }[goal]


def _expected_outcome(goal: str) -> str:
    return {
        "inquiries": "Упростить обращение и проверить изменение подтверждённых действий в карточке.",
        "bookings": "Упростить запись и проверить изменение записей или обращений.",
        "orders": "Упростить заказ и проверить изменение заказов или обращений.",
        "directions": "Сделать визит понятнее и проверить изменение построенных маршрутов.",
        "website_visits": "Сделать переход на сайт заметнее и проверить изменение кликов.",
    }[goal]


def _baseline(cursor: Any, business_id: str, end: date | None = None) -> dict[str, Any]:
    end_date = end or datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=27)
    previous_start = start_date - timedelta(days=28)
    if not _table_exists(cursor, "externalbusinessstats"):
        return {"period": {"start": start_date.isoformat(), "end": end_date.isoformat()}, "status": "unavailable", "providers": {}}
    cursor.execute(
        """
        SELECT source,
               SUM(CASE WHEN date::date BETWEEN %s AND %s THEN COALESCE(views_total, 0) ELSE 0 END) AS views,
               SUM(CASE WHEN date::date BETWEEN %s AND %s THEN COALESCE(clicks_total, 0) ELSE 0 END) AS clicks,
               SUM(CASE WHEN date::date BETWEEN %s AND %s THEN COALESCE(actions_total, 0) ELSE 0 END) AS actions,
               SUM(CASE WHEN date::date BETWEEN %s AND %s THEN COALESCE(views_total, 0) ELSE 0 END) AS previous_views,
               SUM(CASE WHEN date::date BETWEEN %s AND %s THEN COALESCE(clicks_total, 0) ELSE 0 END) AS previous_clicks,
               SUM(CASE WHEN date::date BETWEEN %s AND %s THEN COALESCE(actions_total, 0) ELSE 0 END) AS previous_actions,
               COUNT(*) FILTER (WHERE date::date BETWEEN %s AND %s) AS points
        FROM externalbusinessstats
        WHERE business_id=%s AND date::date BETWEEN %s AND %s
        GROUP BY source
        """,
        (
            start_date, end_date, start_date, end_date, start_date, end_date,
            previous_start, start_date - timedelta(days=1), previous_start, start_date - timedelta(days=1), previous_start, start_date - timedelta(days=1),
            start_date, end_date, business_id, previous_start, end_date,
        ),
    )
    providers: dict[str, Any] = {}
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        provider = _provider(item.get("source"))
        if not provider:
            continue
        providers[provider] = {
            "views": int(item.get("views") or 0),
            "clicks": int(item.get("clicks") or 0),
            "actions": int(item.get("actions") or 0),
            "previous_views": int(item.get("previous_views") or 0),
            "previous_clicks": int(item.get("previous_clicks") or 0),
            "previous_actions": int(item.get("previous_actions") or 0),
            "points": int(item.get("points") or 0),
        }
    cursor.execute(
        """
        SELECT source, date, raw_payload
        FROM externalbusinessstats
        WHERE business_id=%s AND date::date BETWEEN %s AND %s
        """,
        (business_id, previous_start, end_date),
    )
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        provider = _provider(item.get("source"))
        if not provider or provider not in providers:
            continue
        raw = _json(item.get("raw_payload"), {}) or {}
        metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}
        if not metrics:
            continue
        try:
            item_date = date.fromisoformat(str(item.get("date"))[:10])
        except ValueError:
            continue
        bucket = "details" if item_date >= start_date else "previous_details"
        details = providers[provider].setdefault(bucket, {})
        for key in ("calls", "website_clicks", "directions", "messages", "bookings"):
            if key in metrics:
                details[key] = int(details.get(key) or 0) + int(metrics.get(key) or 0)
    try:
        year_ago_end = end_date.replace(year=end_date.year - 1)
        year_ago_start = start_date.replace(year=start_date.year - 1)
    except ValueError:
        year_ago_end = end_date - timedelta(days=365)
        year_ago_start = start_date - timedelta(days=365)
    return {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat(), "days": 28},
        "previous_period": {"start": previous_start.isoformat(), "end": (start_date - timedelta(days=1)).isoformat()},
        "year_ago_period": {"start": year_ago_start.isoformat(), "end": year_ago_end.isoformat()},
        "status": "observed" if providers else "unknown",
        "providers": providers,
        "year_ago_providers": _stats_window(cursor, business_id, year_ago_start, year_ago_end),
        "disclaimer": "Показы и нажатия не являются подтверждёнными клиентами или продажами.",
    }


def _stats_window(cursor: Any, business_id: str, start_date: date, end_date: date) -> dict[str, Any]:
    if not _table_exists(cursor, "externalbusinessstats"):
        return {}
    cursor.execute(
        """
        SELECT source, views_total, clicks_total, actions_total, raw_payload
        FROM externalbusinessstats
        WHERE business_id=%s AND date::date BETWEEN %s AND %s
        """,
        (business_id, start_date, end_date),
    )
    providers: dict[str, Any] = {}
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        provider = _provider(item.get("source"))
        if not provider:
            continue
        target = providers.setdefault(provider, {"views": 0, "clicks": 0, "actions": 0, "details": {}, "points": 0})
        target["views"] += int(item.get("views_total") or 0)
        target["clicks"] += int(item.get("clicks_total") or 0)
        target["actions"] += int(item.get("actions_total") or 0)
        target["points"] += 1
        raw = _json(item.get("raw_payload"), {}) or {}
        metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}
        for key in ("calls", "website_clicks", "directions", "messages", "bookings"):
            if key in metrics:
                target["details"][key] = int(target["details"].get(key) or 0) + int(metrics.get(key) or 0)
    return providers


def _goal_value(goal: str, values: dict[str, Any]) -> tuple[int | None, str]:
    details = values.get("details") if isinstance(values.get("details"), dict) else {}
    if goal == "website_visits" and "website_clicks" in details:
        return int(details.get("website_clicks") or 0), "website_clicks"
    if goal == "directions" and "directions" in details:
        return int(details.get("directions") or 0), "directions"
    if goal == "bookings" and "bookings" in details:
        return int(details.get("bookings") or 0), "bookings"
    if goal in {"inquiries", "orders", "bookings"}:
        return int(values.get("actions") or 0), "platform_actions"
    return None, "unavailable"


def _active_cycle(cursor: Any, business_id: str) -> dict[str, Any] | None:
    if not _table_exists(cursor, "card_growth_cycles"):
        return None
    cursor.execute(
        "SELECT * FROM card_growth_cycles WHERE business_id=%s AND status IN ('active','waiting_for_measurement') ORDER BY created_at DESC LIMIT 1",
        (business_id,),
    )
    item = _row(cursor, cursor.fetchone())
    return item or None


def _measurement(cycle: dict[str, Any] | None) -> dict[str, Any]:
    if not cycle:
        return {"status": "goal_not_confirmed", "checkpoints": []}
    started = _datetime(cycle.get("action_completed_at")) or _datetime(cycle.get("started_at")) or datetime.now(timezone.utc)
    checkpoints = []
    configured_days = _json(cycle.get("measurement_days_json"), [14, 28])
    measurement_days = [int(days) for days in configured_days if str(days).isdigit()] if isinstance(configured_days, list) else [14, 28]
    result = _json(cycle.get("measurement_json"), {}) or {}
    completed_days = int(result.get("checkpoint_days") or 0)
    for days in measurement_days or [14, 28]:
        due = started + timedelta(days=days)
        status = "completed" if days <= completed_days else "due" if due <= datetime.now(timezone.utc) else "waiting"
        checkpoints.append({"days": days, "due_at": due.isoformat(), "status": status})
    return {
        "status": str(cycle.get("status") or "active"),
        "checkpoints": checkpoints,
        "decision": cycle.get("decision"),
        "decision_reason": cycle.get("decision_reason"),
        "result": result or None,
    }


def build_card_growth(cursor: Any, scope: dict[str, Any]) -> dict[str, Any]:
    locations = scope.get("locations") if isinstance(scope.get("locations"), list) else []
    if not locations and scope.get("business_id"):
        locations = [{"id": scope["business_id"], "name": scope.get("business_name") or "Точка"}]
    location_states = []
    all_actions = []
    goals = []
    for location_ref in locations:
        business_id = str(location_ref.get("id") or "")
        if not business_id:
            continue
        business = _business(cursor, business_id)
        if not business:
            continue
        links, parses = _latest_sources(cursor, business_id)
        providers = [_provider_state(cursor, business, provider, links.get(provider), parses.get(provider)) for provider in PROVIDERS if links.get(provider) or parses.get(provider)]
        cycle = _active_cycle(cursor, business_id)
        recommended = recommend_goal(business.get("business_type"))
        goal = str(cycle.get("goal") if cycle else recommended)
        goals.append(goal)
        state = {
            "business_id": business_id,
            "business_name": str(business.get("name") or location_ref.get("name") or "Точка"),
            "goal": goal,
            "goal_status": str(cycle.get("goal_status") or "recommended") if cycle else "recommended",
            "providers": providers,
            "cycle_id": str(cycle.get("id")) if cycle else None,
            "measurement": _measurement(cycle),
        }
        actions = _actions_for_location(state, goal)
        if not providers:
            actions = [{
                "id": f"card-growth:{business_id}:select-provider",
                "business_id": business_id,
                "business_name": state["business_name"],
                "provider": None,
                "provider_label": "Карты",
                "fact": "access",
                "gate": 0,
                "gate_label": GATE_LABELS[0],
                "title": "Добавьте площадку для проверки",
                "reason": "LocalOS пока не знает, какие карточки принадлежат этой точке. Добавьте Google, Яндекс или 2ГИС, чтобы получить первый снимок.",
                "expected_outcome": "Получить свежие данные карточки и определить первое исправление.",
                "metric": _goal_metric(goal),
                "measurement_days": [14, 28],
                "cta_label": "Добавить площадку",
                "cta_url": "/dashboard/profile",
                "screen": "settings",
                "priority": 1100,
                "rule_id": "platform.access",
                "rule_url": None,
                "influence": "eligibility",
                "confidence": 1.0,
                "target_scope": {"kind": "business", "id": business_id},
                "affected_business_ids": [business_id],
            }]
        state["focus_action"] = actions[0] if actions else None
        state["next_actions"] = actions[1:4]
        state["critical"] = any(item.get("gate", 99) <= 1 for item in actions)
        location_states.append(state)
        all_actions.extend(actions)
    all_actions.sort(key=lambda item: (-int(item["priority"]), str(item["business_id"]), str(item["provider"])))
    focus = all_actions[0] if all_actions else None
    goal_status = "confirmed" if location_states and all(item["goal_status"] == "confirmed" for item in location_states) else "recommended"
    return {
        "policy_version": POLICY_VERSION,
        "goal": {
            "value": goals[0] if len(set(goals)) == 1 and goals else None,
            "label": GOAL_LABELS.get(goals[0], "") if len(set(goals)) == 1 and goals else "Цели различаются по точкам",
            "status": goal_status,
            "options": [{"value": key, "label": label} for key, label in GOAL_LABELS.items()],
        },
        "card_state": {
            "scope_kind": scope.get("kind") or "business",
            "locations": location_states,
            "critical_locations": [item["business_id"] for item in location_states if item["critical"]],
            "status": "needs_attention" if all_actions else "healthy",
        },
        "baseline": _baseline(cursor, str(location_states[0]["business_id"])) if len(location_states) == 1 else {"status": "per_location", "locations": {item["business_id"]: _baseline(cursor, item["business_id"]) for item in location_states}},
        "focus_action": focus,
        "next_actions": all_actions[1:4],
        "measurement": location_states[0]["measurement"] if len(location_states) == 1 else {"status": "per_location", "locations": {item["business_id"]: item["measurement"] for item in location_states}},
    }


def confirm_growth_goal(cursor: Any, *, business_id: str, user_id: str, goal: str) -> dict[str, Any]:
    if goal not in GOALS:
        raise ValueError("Неизвестная цель роста")
    business = _business(cursor, business_id)
    if not business:
        raise ValueError("Бизнес не найден")
    cursor.execute(
        "UPDATE card_growth_cycles SET status='cancelled', updated_at=NOW() WHERE business_id=%s AND status IN ('active','waiting_for_measurement') AND goal<>%s",
        (business_id, goal),
    )
    cursor.execute(
        "SELECT * FROM card_growth_cycles WHERE business_id=%s AND status IN ('active','waiting_for_measurement') AND goal=%s ORDER BY created_at DESC LIMIT 1",
        (business_id, goal),
    )
    existing = _row(cursor, cursor.fetchone())
    if existing and str(existing.get("goal_status") or "") == "confirmed":
        return {"cycle": _serialize_cycle(existing), "created": False}
    end_date = datetime.now(timezone.utc).date()
    baseline = _baseline(cursor, business_id, end_date)
    if existing:
        cycle_id = str(existing["id"])
        cursor.execute(
            """
            UPDATE card_growth_cycles
            SET goal_status='confirmed', policy_version=%s, baseline_start=%s,
                baseline_end=%s, baseline_json=%s, created_by=%s, started_at=NOW(), updated_at=NOW()
            WHERE id=%s
            RETURNING *
            """,
            (POLICY_VERSION, end_date - timedelta(days=27), end_date, Json(baseline), user_id, cycle_id),
        )
    else:
        cycle_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO card_growth_cycles (
                id, business_id, goal, goal_status, status, policy_version,
                baseline_start, baseline_end, baseline_json, created_by
            ) VALUES (%s,%s,%s,'confirmed','active',%s,%s,%s,%s,%s)
            RETURNING *
            """,
            (cycle_id, business_id, goal, POLICY_VERSION, end_date - timedelta(days=27), end_date, Json(baseline), user_id),
        )
    cycle = _row(cursor, cursor.fetchone())
    scope = {"kind": "business", "business_id": business_id, "business_name": business.get("name"), "locations": [{"id": business_id, "name": business.get("name")}]}
    growth = build_card_growth(cursor, scope)
    for provider_state in growth["card_state"]["locations"][0]["providers"]:
        cursor.execute(
            """
            INSERT INTO card_state_snapshots (
                id, business_id, growth_cycle_id, provider, policy_version, snapshot_kind,
                source_state, source_observed_at, facts_json, metrics_json, benchmark_json
            ) VALUES (%s,%s,%s,%s,%s,'baseline',%s,%s,%s,%s,%s)
            ON CONFLICT (growth_cycle_id, provider, snapshot_kind) WHERE growth_cycle_id IS NOT NULL DO NOTHING
            """,
            (
                str(uuid.uuid4()), business_id, cycle_id, provider_state["provider"], POLICY_VERSION,
                provider_state["source_state"], provider_state["observed_at"], Json(provider_state["facts"]),
                Json(provider_state["metrics"]), Json(provider_state["benchmark"]),
            ),
        )
    focus = growth.get("focus_action")
    if isinstance(focus, dict):
        from services.lead_journey_service import ensure_action
        action_payload = {
            "cycle_key": cycle_id,
            "managed_growth_cycle": True,
            "task_title": focus["title"],
            "task_reason": focus["reason"],
            "tasks": [focus],
            "tasks_total": 1,
            "task_index": 0,
            "goal": goal,
            "baseline": baseline,
            "measurement_days": focus["measurement_days"],
        }
        cursor.execute(
            "UPDATE card_growth_cycles SET focus_action_json=%s, measurement_days_json=%s, updated_at=NOW() WHERE id=%s",
            (Json(focus), Json(focus["measurement_days"]), cycle_id),
        )
        cursor.execute(
            """
            SELECT * FROM journey_actions
            WHERE business_id=%s AND flow_type='maps'
              AND status IN ('ready','in_progress','waiting','blocked')
            ORDER BY created_at LIMIT 1
            """,
            (business_id,),
        )
        active_action = _row(cursor, cursor.fetchone())
        if active_action:
            preserved_payload = _json(active_action.get("payload_json"), {}) or {}
            cursor.execute(
                "UPDATE journey_actions SET growth_cycle_id=%s, payload_json=%s, updated_at=NOW() WHERE id=%s",
                (cycle_id, Json({**preserved_payload, **action_payload}), active_action["id"]),
            )
        else:
            action = ensure_action(
                cursor,
                journey_id=None,
                business_id=business_id,
                user_id=user_id,
                lead_id=None,
                flow_type="maps",
                entity_type="card_growth_cycle",
                entity_id=cycle_id,
                action_type="complete_map_task",
                payload=action_payload,
            )
            cursor.execute("UPDATE journey_actions SET growth_cycle_id=%s WHERE id=%s", (cycle_id, action["id"]))
    return {"cycle": _serialize_cycle(cycle), "created": True}


def _serialize_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(cycle.get("id") or ""),
        "business_id": str(cycle.get("business_id") or ""),
        "goal": str(cycle.get("goal") or ""),
        "goal_label": GOAL_LABELS.get(str(cycle.get("goal") or ""), ""),
        "goal_status": str(cycle.get("goal_status") or ""),
        "status": str(cycle.get("status") or ""),
        "policy_version": str(cycle.get("policy_version") or ""),
        "baseline_start": str(cycle.get("baseline_start") or ""),
        "baseline_end": str(cycle.get("baseline_end") or ""),
        "baseline": _json(cycle.get("baseline_json"), {}) or {},
        "focus_action": _json(cycle.get("focus_action_json"), {}) or {},
        "measurement_days": _json(cycle.get("measurement_days_json"), [14, 28]) or [14, 28],
        "measurement": _json(cycle.get("measurement_json"), {}) or {},
        "decision": cycle.get("decision"),
        "decision_reason": cycle.get("decision_reason"),
        "started_at": cycle.get("started_at").isoformat() if hasattr(cycle.get("started_at"), "isoformat") else cycle.get("started_at"),
        "action_completed_at": cycle.get("action_completed_at").isoformat() if hasattr(cycle.get("action_completed_at"), "isoformat") else cycle.get("action_completed_at"),
    }


def mark_growth_cycle_waiting(cursor: Any, cycle_id: str) -> None:
    if not cycle_id or not _table_exists(cursor, "card_growth_cycles"):
        return
    cursor.execute(
        "UPDATE card_growth_cycles SET status='waiting_for_measurement', action_completed_at=COALESCE(action_completed_at, NOW()), updated_at=NOW() WHERE id=%s AND status='active'",
        (cycle_id,),
    )


def record_growth_measurement(cursor: Any, cycle_id: str, checkpoint_days: int) -> dict[str, Any]:
    if not cycle_id or not _table_exists(cursor, "card_growth_cycles"):
        return {"status": "unavailable"}
    cursor.execute("SELECT * FROM card_growth_cycles WHERE id=%s FOR UPDATE", (cycle_id,))
    cycle = _row(cursor, cursor.fetchone())
    if not cycle:
        return {"status": "unavailable"}
    business_id = str(cycle["business_id"])
    business = _business(cursor, business_id)
    scope = {
        "kind": "business",
        "business_id": business_id,
        "business_name": business.get("name"),
        "locations": [{"id": business_id, "name": business.get("name")}],
    }
    growth = build_card_growth(cursor, scope)
    current_performance = _baseline(cursor, business_id)
    started_at = _datetime(cycle.get("action_completed_at")) or _datetime(cycle.get("started_at")) or datetime.now(timezone.utc)
    current_start = started_at.date()
    current_end = min(datetime.now(timezone.utc).date(), current_start + timedelta(days=max(1, checkpoint_days) - 1))
    observed_days = max(1, (current_end - current_start).days + 1)
    comparison_end = current_start - timedelta(days=1)
    comparison_start = comparison_end - timedelta(days=observed_days - 1)
    current_window = _stats_window(cursor, business_id, current_start, current_end)
    comparison_window = _stats_window(cursor, business_id, comparison_start, comparison_end)
    deltas: dict[str, Any] = {}
    has_comparable_data = False
    for provider in PROVIDERS:
        before = comparison_window.get(provider) if isinstance(comparison_window.get(provider), dict) else {}
        after = current_window.get(provider) if isinstance(current_window.get(provider), dict) else {}
        if not before or not after:
            continue
        before_goal, metric_kind = _goal_value(str(cycle.get("goal") or "inquiries"), before)
        after_goal, _ = _goal_value(str(cycle.get("goal") or "inquiries"), after)
        if before_goal is None or after_goal is None:
            continue
        has_comparable_data = True
        deltas[provider] = {
            "views": int(after.get("views") or 0) - int(before.get("views") or 0),
            "clicks": int(after.get("clicks") or 0) - int(before.get("clicks") or 0),
            "actions": int(after.get("actions") or 0) - int(before.get("actions") or 0),
            "goal_metric": metric_kind,
            "goal_before": before_goal,
            "goal_after": after_goal,
            "goal_delta": after_goal - before_goal,
        }
    if not has_comparable_data:
        decision = "insufficient_data"
        decision_reason = "Недостаточно сопоставимых данных площадок для вывода о результате."
    elif sum(int(item.get("goal_delta") or 0) for item in deltas.values()) > 0:
        decision = "continue"
        decision_reason = "Подтверждённые действия в карточках выросли относительно базового периода."
    elif checkpoint_days < 28:
        decision = "adjust"
        decision_reason = "На первой контрольной точке роста действий пока нет; проверим следующий период."
    else:
        decision = "replace"
        decision_reason = "За контрольный период роста действий не зафиксировано; нужна другая гипотеза."
    snapshot_kind = f"checkpoint_{checkpoint_days}d"
    location = growth["card_state"]["locations"][0]
    for provider_state in location["providers"]:
        cursor.execute(
            """
            INSERT INTO card_state_snapshots (
                id, business_id, growth_cycle_id, provider, policy_version, snapshot_kind,
                source_state, source_observed_at, facts_json, metrics_json, benchmark_json
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (growth_cycle_id, provider, snapshot_kind) WHERE growth_cycle_id IS NOT NULL
            DO UPDATE SET source_state=EXCLUDED.source_state,
                          source_observed_at=EXCLUDED.source_observed_at,
                          facts_json=EXCLUDED.facts_json,
                          metrics_json=EXCLUDED.metrics_json,
                          benchmark_json=EXCLUDED.benchmark_json,
                          created_at=NOW()
            """,
            (
                str(uuid.uuid4()), business_id, cycle_id, provider_state["provider"], POLICY_VERSION,
                snapshot_kind, provider_state["source_state"], provider_state["observed_at"],
                Json(provider_state["facts"]), Json({**provider_state["metrics"], "performance": current_performance, "delta": deltas.get(provider_state["provider"])}),
                Json(provider_state["benchmark"]),
            ),
        )
    result = {
        "status": "measured" if has_comparable_data else "insufficient_data",
        "checkpoint_days": checkpoint_days,
        "period": {"start": current_start.isoformat(), "end": current_end.isoformat(), "days": observed_days},
        "comparison_period": {"start": comparison_start.isoformat(), "end": comparison_end.isoformat(), "days": observed_days},
        "decision": decision,
        "decision_reason": decision_reason,
        "deltas": deltas,
        "performance": current_performance,
        "disclaimer": "Платформенные действия не являются подтверждёнными клиентами, заказами или продажами.",
    }
    cursor.execute(
        "UPDATE card_growth_cycles SET decision=%s, decision_reason=%s, measurement_json=%s, updated_at=NOW() WHERE id=%s",
        (decision, decision_reason, Json(result), cycle_id),
    )
    return result


def complete_growth_cycle(cursor: Any, cycle_id: str) -> None:
    if not cycle_id or not _table_exists(cursor, "card_growth_cycles"):
        return
    cursor.execute(
        "UPDATE card_growth_cycles SET status='completed', completed_at=NOW(), updated_at=NOW() WHERE id=%s",
        (cycle_id,),
    )


def prepare_next_growth_cycle(cursor: Any, cycle_id: str, user_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM card_growth_cycles WHERE id=%s", (cycle_id,))
    previous = _row(cursor, cursor.fetchone())
    if not previous:
        return {}
    business_id = str(previous["business_id"])
    business = _business(cursor, business_id)
    end_date = datetime.now(timezone.utc).date()
    baseline = _baseline(cursor, business_id, end_date)
    next_cycle_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO card_growth_cycles (
            id, business_id, goal, goal_status, status, policy_version,
            baseline_start, baseline_end, baseline_json, created_by
        ) VALUES (%s,%s,%s,'confirmed','active',%s,%s,%s,%s,%s)
        """,
        (
            next_cycle_id, business_id, previous["goal"], POLICY_VERSION,
            end_date - timedelta(days=27), end_date, Json(baseline), user_id,
        ),
    )
    scope = {
        "kind": "business",
        "business_id": business_id,
        "business_name": business.get("name"),
        "locations": [{"id": business_id, "name": business.get("name")}],
    }
    growth = build_card_growth(cursor, scope)
    focus = growth.get("focus_action")
    if not isinstance(focus, dict):
        focus = {
            "title": "Проверьте актуальность карточки через 28 дней",
            "reason": "Критичных разрывов сейчас не обнаружено. Следующий шаг — контрольный снимок без лишних изменений.",
            "measurement_days": [28],
        }
    cursor.execute(
        "UPDATE card_growth_cycles SET focus_action_json=%s, measurement_days_json=%s, updated_at=NOW() WHERE id=%s",
        (Json(focus), Json(focus.get("measurement_days") or [14, 28]), next_cycle_id),
    )
    for provider_state in growth["card_state"]["locations"][0]["providers"]:
        cursor.execute(
            """
            INSERT INTO card_state_snapshots (
                id, business_id, growth_cycle_id, provider, policy_version, snapshot_kind,
                source_state, source_observed_at, facts_json, metrics_json, benchmark_json
            ) VALUES (%s,%s,%s,%s,%s,'baseline',%s,%s,%s,%s,%s)
            ON CONFLICT (growth_cycle_id, provider, snapshot_kind) WHERE growth_cycle_id IS NOT NULL DO NOTHING
            """,
            (
                str(uuid.uuid4()), business_id, next_cycle_id, provider_state["provider"], POLICY_VERSION,
                provider_state["source_state"], provider_state["observed_at"], Json(provider_state["facts"]),
                Json(provider_state["metrics"]), Json(provider_state["benchmark"]),
            ),
        )
    return {
        "entity_id": next_cycle_id,
        "growth_cycle_id": next_cycle_id,
        "cycle_key": next_cycle_id,
        "managed_growth_cycle": True,
        "task_title": focus["title"],
        "task_reason": focus["reason"],
        "tasks": [focus],
        "tasks_total": 1,
        "task_index": 0,
        "goal": previous["goal"],
        "baseline": baseline,
        "measurement_days": focus.get("measurement_days") or [14, 28],
    }
