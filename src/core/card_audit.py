import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database_manager import DatabaseManager


CATEGORY_BASELINE_REVENUE = {
    "beauty": 180000.0,
    "beauty salon": 180000.0,
    "salon": 180000.0,
    "barbershop": 190000.0,
    "nail": 140000.0,
    "cosmetology": 220000.0,
    "massage": 160000.0,
    "cafe": 260000.0,
    "coffee": 180000.0,
    "restaurant": 420000.0,
    "school": 240000.0,
    "education": 240000.0,
    "fitness": 260000.0,
    "gym": 260000.0,
    "medical": 320000.0,
    "clinic": 320000.0,
    "dental": 340000.0,
    "auto": 280000.0,
    "repair": 200000.0,
}

YMAP_SOURCES = ("yandex_maps", "yandex_business_goods", "yandex_business_services")


def _safe_json(value: Any) -> Any:
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


def _to_dict(cursor, row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (f"public.{table_name}",))
    row = _to_dict(cursor, cursor.fetchone())
    return bool((row or {}).get("exists"))


def _extract_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = re.sub(r"[^\d.,-]", "", str(value or "")).replace(",", ".")
    if not raw:
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _coerce_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _extract_yandex_org_id_from_url(url: Any) -> Optional[str]:
    text = str(url or "").strip()
    if not text:
        return None
    match = re.search(r"/org/(?:[^/]+/)?(\d+)", text)
    if match:
        return match.group(1)
    return None


def _extract_contact_links(value: Any) -> List[str]:
    links: List[str] = []

    def _walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            text = node.strip()
            if text:
                links.append(text)
            return
        if isinstance(node, dict):
            for item in node.values():
                _walk(item)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(value)
    deduped: List[str] = []
    seen = set()
    for item in links:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _extract_telegram_whatsapp_email_from_links(links: List[str]) -> Dict[str, Optional[str]]:
    telegram = None
    whatsapp = None
    email = None
    for raw in links:
        value = str(raw or "").strip()
        low = value.lower()
        if not telegram and ("t.me/" in low or "telegram.me/" in low):
            telegram = value
        if not whatsapp and ("wa.me/" in low or "whatsapp.com/" in low or "api.whatsapp.com/" in low):
            whatsapp = value
        if not email:
            if low.startswith("mailto:"):
                email = value.split(":", 1)[1].strip()
            elif "@" in value and " " not in value and "/" not in value:
                email = value
    return {"telegram_url": telegram, "whatsapp_url": whatsapp, "email": email}


def _resolve_lead_business_snapshot(lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Try to resolve an existing LocalOS business for a lead and enrich preview metrics.
    Returns partial snapshot; empty dict means no business match found.
    """
    explicit_business_id = str(lead.get("business_id") or "").strip()
    source_external_id = str(
        lead.get("source_external_id")
        or lead.get("google_id")
        or _extract_yandex_org_id_from_url(lead.get("source_url"))
        or ""
    ).strip()
    source_url = str(lead.get("source_url") or "").strip()
    lead_name = str(lead.get("name") or "").strip()
    lead_city = str(lead.get("city") or "").strip()

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'businesses'
            """
        )
        business_columns = set()
        for row in cursor.fetchall():
            if hasattr(row, "get"):
                column_name = row.get("column_name")
            else:
                column_name = row[0] if row else None
            if column_name:
                business_columns.add(str(column_name))

        business = None
        if explicit_business_id:
            cursor.execute(
                """
                SELECT *
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (explicit_business_id,),
            )
            business = _to_dict(cursor, cursor.fetchone())

        if not business and source_external_id and "yandex_org_id" in business_columns:
            cursor.execute(
                """
                SELECT *
                FROM businesses
                WHERE yandex_org_id = %s
                LIMIT 1
                """,
                (source_external_id,),
            )
            business = _to_dict(cursor, cursor.fetchone())

        if not business and source_url and "yandex_url" in business_columns:
            if source_external_id:
                cursor.execute(
                    """
                    SELECT *
                    FROM businesses
                    WHERE yandex_url = %s
                       OR yandex_url ILIKE %s
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (source_url, f"%{source_external_id}%"),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM businesses
                    WHERE yandex_url = %s
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (source_url,),
                )
            business = _to_dict(cursor, cursor.fetchone())

        if not business and lead_name:
            cursor.execute(
                """
                SELECT *
                FROM businesses
                WHERE LOWER(name) = LOWER(%s)
                  AND (%s = '' OR LOWER(COALESCE(city, '')) = LOWER(%s))
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT 1
                """,
                (lead_name, lead_city, lead_city),
            )
            business = _to_dict(cursor, cursor.fetchone())

        if not business:
            return {}

        business_id = business.get("id")
        if not business_id:
            return {}

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_services,
                COUNT(*) FILTER (WHERE is_active IS TRUE OR is_active IS NULL) AS active_services,
                COUNT(*) FILTER (
                    WHERE (is_active IS TRUE OR is_active IS NULL)
                      AND TRIM(COALESCE(price::text, '')) <> ''
                ) AS priced_services
            FROM userservices
            WHERE business_id = %s
            """,
            (business_id,),
        )
        services_row = _to_dict(cursor, cursor.fetchone()) or {}
        total_services = int(services_row.get("total_services") or 0)
        active_services = int(services_row.get("active_services") or 0)
        if active_services <= 0 and total_services > 0:
            active_services = total_services

        cursor.execute(
            """
            SELECT *
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        latest_card = _to_dict(cursor, cursor.fetchone()) or {}

        cursor.execute(
            """
            SELECT id, status, updated_at, retry_after, error_message
            FROM parsequeue
            WHERE business_id = %s
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        latest_parse = _to_dict(cursor, cursor.fetchone()) or {}

        photos_payload = _safe_json(latest_card.get("photos"))
        news_payload = _safe_json(latest_card.get("news"))
        overview_payload = _safe_json(latest_card.get("overview")) or {}
        overview_social_links = overview_payload.get("social_links") if isinstance(overview_payload, dict) else None
        social_links = _extract_contact_links(overview_social_links)
        parsed_contacts = _extract_telegram_whatsapp_email_from_links(social_links)

        services_preview: List[Dict[str, Any]] = []
        cursor.execute(
            """
            SELECT name, description, price, source
            FROM userservices
            WHERE business_id = %s
              AND (is_active IS TRUE OR is_active IS NULL)
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 8
            """,
            (business_id,),
        )
        for row in cursor.fetchall():
            service_row = _to_dict(cursor, row) or {}
            name = str(service_row.get("name") or "").strip()
            if not name:
                continue
            description = str(service_row.get("description") or "").strip()
            price = str(service_row.get("price") or "").strip()
            source = str(service_row.get("source") or "").strip()
            note_parts = []
            if price:
                note_parts.append(f"Цена: {price}")
            if source:
                note_parts.append(f"Источник: {source}")
            services_preview.append(
                {
                    "current_name": name,
                    "suggested_name": name,
                    "note": " • ".join(note_parts) if note_parts else "Парсинг карточки",
                    "description": description or None,
                }
            )

        reviews_preview: List[Dict[str, Any]] = []
        if _table_exists(cursor, "externalbusinessreviews"):
            cursor.execute(
                """
                WITH preferred_source AS (
                    SELECT CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM externalbusinessreviews r2
                            WHERE r2.business_id = %s
                              AND r2.source = 'yandex_maps'
                        ) THEN 'yandex_maps'
                        ELSE 'yandex_business'
                    END AS source
                )
                SELECT text AS review_text, response_text, rating
                FROM externalbusinessreviews r, preferred_source ps
                WHERE r.business_id = %s
                  AND r.source = ps.source
                ORDER BY published_at DESC NULLS LAST, created_at DESC
                LIMIT 6
                """,
                (business_id, business_id),
            )
            for row in cursor.fetchall():
                review_row = _to_dict(cursor, row) or {}
                review_text = str(review_row.get("review_text") or "").strip()
                if not review_text:
                    continue
                response_text = str(review_row.get("response_text") or "").strip() or "Ответа пока нет"
                rating = review_row.get("rating")
                rating_suffix = ""
                if rating is not None and str(rating).strip() != "":
                    rating_suffix = f" (оценка: {rating})"
                reviews_preview.append(
                    {
                        "review": f"{review_text}{rating_suffix}",
                        "reply_preview": response_text,
                    }
                )

        news_preview: List[Dict[str, Any]] = []
        if isinstance(news_payload, list):
            for item in news_payload[:6]:
                if isinstance(item, dict):
                    title = str(item.get("title") or item.get("name") or "").strip() or "Новость"
                    body = str(item.get("body") or item.get("text") or item.get("description") or "").strip()
                    if title or body:
                        news_preview.append({"title": title, "body": body or "Без текста"})
                elif isinstance(item, str):
                    text = item.strip()
                    if text:
                        news_preview.append({"title": "Новость", "body": text})

        return {
            "business": business,
            "services_count": active_services,
            "priced_services_count": int(services_row.get("priced_services") or 0),
            "rating": _extract_numeric(latest_card.get("rating")) if latest_card.get("rating") is not None else _extract_numeric(business.get("yandex_rating")),
            "reviews_count": int(latest_card.get("reviews_count") or business.get("yandex_reviews_total") or 0),
            "unanswered_reviews_count": int(latest_card.get("unanswered_reviews_count") or 0),
            "photos_count": len(photos_payload) if isinstance(photos_payload, list) else 0,
            "news_count": len(news_payload) if isinstance(news_payload, list) else 0,
            "has_recent_activity": bool(latest_card.get("updated_at") or latest_parse.get("updated_at")),
            "last_parse_at": latest_parse.get("updated_at") or latest_card.get("updated_at") or business.get("updated_at"),
            "last_parse_status": latest_parse.get("status") or "completed",
            "last_parse_task_id": latest_parse.get("id"),
            "last_parse_retry_after": latest_parse.get("retry_after"),
            "last_parse_error": latest_parse.get("error_message"),
            "source_url": business.get("yandex_url") or source_url,
            "parsed_contacts": {
                "phone": str(latest_card.get("phone") or business.get("phone") or "").strip() or None,
                "website": str(latest_card.get("site") or business.get("website") or "").strip() or None,
                "email": parsed_contacts.get("email"),
                "telegram_url": parsed_contacts.get("telegram_url"),
                "whatsapp_url": parsed_contacts.get("whatsapp_url"),
                "social_links": social_links,
            },
            "services_preview": services_preview,
            "reviews_preview": reviews_preview,
            "news_preview": news_preview,
        }
    except Exception as exc:
        print(f"lead preview business resolution fallback: {exc}")
        return {}
    finally:
        db.close()


def _lead_demo_services_preview(business_type: str) -> List[Dict[str, Any]]:
    normalized = business_type.lower()
    if "school" in normalized or "education" in normalized:
        return [
            {
                "current_name": "Курс / занятие без структуры",
                "suggested_name": "Пробное занятие для новых учеников",
                "note": "Лучше вынести понятную точку входа, чтобы карточка конвертировала первый интерес.",
            },
            {
                "current_name": "Общее направление обучения",
                "suggested_name": "Индивидуальные занятия по ключевому предмету",
                "note": "Показывайте конкретные направления, а не только общий профиль школы.",
            },
            {
                "current_name": "Без цены или формата",
                "suggested_name": "Абонемент на месяц / курс с понятным форматом",
                "note": "Цена и формат повышают доверие и сокращают лишние вопросы.",
            },
        ]
    if any(token in normalized for token in ("beauty", "salon", "nail", "cosmetology", "massage", "barber")):
        return [
            {
                "current_name": "Общая услуга без структуры",
                "suggested_name": "Базовая услуга с понятным названием и сегментом",
                "note": "Карточка лучше работает, когда названия услуг сразу отвечают на запрос клиента.",
            },
            {
                "current_name": "Услуга без цены",
                "suggested_name": "Ключевая процедура с ценой или ценовым диапазоном",
                "note": "Даже ориентировочная цена снижает трение перед первым контактом.",
            },
            {
                "current_name": "Нет отдельных направлений",
                "suggested_name": "Выделенные услуги по основным направлениям салона",
                "note": "Разделите ключевые услуги на отдельные позиции вместо одного общего описания.",
            },
        ]
    if any(token in normalized for token in ("cafe", "coffee", "restaurant")):
        return [
            {
                "current_name": "Общий формат заведения",
                "suggested_name": "Завтраки / бизнес-ланч / фирменные позиции",
                "note": "Показывайте поводы прийти, а не только сам факт существования заведения.",
            },
            {
                "current_name": "Меню без акцентов",
                "suggested_name": "Хиты меню с понятной ценой",
                "note": "Лучше выделить 3–5 ключевых позиций, чем оставлять абстрактное меню.",
            },
        ]
    return [
        {
            "current_name": "Общее описание без структуры",
            "suggested_name": "Ключевая услуга с понятным названием",
            "note": "Нужны конкретные точки входа, чтобы карточка отвечала на поисковый запрос.",
        },
        {
            "current_name": "Нет цены или формата",
            "suggested_name": "Понятный формат услуги с диапазоном цены",
            "note": "Это повышает доверие и сокращает путь до первого обращения.",
        },
    ]


def _lead_demo_reviews_preview(lead_name: str, business_type: str, rating: Optional[float], reviews_count: int) -> List[Dict[str, Any]]:
    trust_line = "Рейтинг уже помогает карточке, но ответы усиливают доверие." if (rating or 0) >= 4.7 else "Даже при хорошем продукте слабая работа с отзывами снижает доверие."
    return [
        {
            "review": f"Нравится формат {business_type.lower() if business_type else 'услуг'}, но хотелось бы больше ясности по условиям и цене.",
            "reply_preview": f"Спасибо за обратную связь. Мы готовы подробнее объяснить формат, стоимость и подобрать удобный вариант под ваш запрос.",
        },
        {
            "review": f"Интересный вариант, но по карточке не до конца понятно, чем {lead_name} отличается от конкурентов.",
            "reply_preview": f"Спасибо, это важный комментарий. Мы усиливаем карточку и уточняем ключевые преимущества, чтобы выбор был понятнее уже на этапе просмотра.",
        },
        {
            "review": trust_line,
            "reply_preview": "Регулярные ответы на отзывы делают карточку живой и помогают перевести интерес в обращение.",
        },
    ]


def _lead_demo_news_preview(business_type: str) -> List[Dict[str, Any]]:
    return [
        {
            "title": "Пример новости: что нового в карточке",
            "body": f"Покажите актуальное предложение по направлению «{business_type}», чтобы карточка выглядела живой и помогала принять решение.",
        },
        {
            "title": "Пример новости: повод обратиться сейчас",
            "body": "Добавьте короткий инфоповод: сезонное предложение, новый формат, удобное время или обновлённую услугу.",
        },
    ]


def _infer_baseline_revenue(*, business_type: Any, average_check: Optional[float], current_revenue: Optional[float], services_count: int, reviews_count: int) -> Dict[str, Any]:
    if current_revenue and current_revenue > 0:
        return {"value": round(current_revenue), "source": "actual"}

    normalized_type = str(business_type or "").strip().lower()
    baseline = 0.0
    baseline_source = None

    if average_check and average_check > 0:
        estimated_purchases = max(20, services_count * 8, min(reviews_count, 80))
        baseline = average_check * estimated_purchases
        baseline_source = "estimated_from_average_check"
    else:
        for key, value in CATEGORY_BASELINE_REVENUE.items():
            if key in normalized_type:
                baseline = value
                baseline_source = "category_baseline"
                break

    if baseline <= 0:
        baseline = 120000.0
        baseline_source = "default_baseline"

    return {"value": round(baseline), "source": baseline_source}


def estimate_card_revenue_gap(
    *,
    rating: Optional[float],
    services_count: int,
    priced_services_count: int,
    unanswered_reviews_count: int,
    reviews_count: int,
    photos_count: int,
    news_count: int,
    average_check: Optional[float],
    current_revenue: Optional[float],
    business_type: Optional[str],
) -> Dict[str, Any]:
    baseline = _infer_baseline_revenue(
        business_type=business_type,
        average_check=average_check,
        current_revenue=current_revenue,
        services_count=services_count,
        reviews_count=reviews_count,
    )
    baseline_value = float(baseline["value"])

    rating_penalty_min = 0.0
    rating_penalty_max = 0.0
    if rating is not None:
        if rating < 4.4:
            rating_penalty_min, rating_penalty_max = 0.06, 0.15
        elif rating < 4.7:
            rating_penalty_min, rating_penalty_max = 0.02, 0.06
        else:
            rating_penalty_min, rating_penalty_max = 0.0, 0.02
        if unanswered_reviews_count >= 5:
            rating_penalty_max += 0.02

    content_penalty_min = 0.0
    content_penalty_max = 0.0
    if photos_count <= 0:
        content_penalty_min += 0.03
        content_penalty_max += 0.06
    elif photos_count < 5:
        content_penalty_min += 0.01
        content_penalty_max += 0.03
    if news_count <= 0:
        content_penalty_min += 0.01
        content_penalty_max += 0.03
    if not reviews_count:
        content_penalty_min += 0.01
        content_penalty_max += 0.02
    if unanswered_reviews_count >= 5:
        content_penalty_min += 0.01
        content_penalty_max += 0.03
    content_penalty_max = min(content_penalty_max, 0.10)

    service_penalty_min = 0.0
    service_penalty_max = 0.0
    if services_count <= 0:
        service_penalty_min += 0.08
        service_penalty_max += 0.15
    elif services_count < 5:
        service_penalty_min += 0.04
        service_penalty_max += 0.10
    if services_count > 0 and priced_services_count <= 0:
        service_penalty_min += 0.02
        service_penalty_max += 0.05
    elif services_count > 0 and priced_services_count < max(1, services_count // 2):
        service_penalty_min += 0.01
        service_penalty_max += 0.03
    service_penalty_max = min(service_penalty_max, 0.15)

    rating_min = round(baseline_value * rating_penalty_min)
    rating_max = round(baseline_value * rating_penalty_max)
    content_min = round(baseline_value * content_penalty_min)
    content_max = round(baseline_value * content_penalty_max)
    service_min = round(baseline_value * service_penalty_min)
    service_max = round(baseline_value * service_penalty_max)
    return {
        "mode": "estimate_v1",
        "baseline_monthly_revenue": baseline,
        "rating_gap": {"min": rating_min, "max": rating_max},
        "content_gap": {"min": content_min, "max": content_max},
        "service_gap": {"min": service_min, "max": service_max},
        "total_min": rating_min + content_min + service_min,
        "total_max": rating_max + content_max + service_max,
        "confidence": "medium",
        "disclaimer": "Оценка ориентировочная и основана на модели карточки, а не на полном доступе к вашим продажам.",
        "currency": "RUB",
    }


def build_lead_card_preview_snapshot(lead: Dict[str, Any]) -> Dict[str, Any]:
    lead_name = str(lead.get("name") or "Лид").strip() or "Лид"
    business_type = str(lead.get("category") or lead.get("business_type") or "").strip() or "Локальный бизнес"
    city = str(lead.get("city") or "").strip()
    snapshot = _resolve_lead_business_snapshot(lead)
    business = snapshot.get("business") or {}

    rating_raw = snapshot.get("rating") if snapshot.get("rating") is not None else lead.get("rating")
    rating = float(rating_raw) if rating_raw is not None else None
    reviews_count = int(snapshot.get("reviews_count") if snapshot.get("reviews_count") is not None else (lead.get("reviews_count") or 0))
    parsed_contacts = snapshot.get("parsed_contacts") or {}
    has_website = bool(str(lead.get("website") or parsed_contacts.get("website") or business.get("website") or "").strip())
    has_phone = bool(str(lead.get("phone") or parsed_contacts.get("phone") or business.get("phone") or "").strip())
    has_email = bool(str(lead.get("email") or parsed_contacts.get("email") or business.get("email") or "").strip())
    has_messenger = bool(
        str(lead.get("telegram_url") or parsed_contacts.get("telegram_url") or "").strip()
        or str(lead.get("whatsapp_url") or parsed_contacts.get("whatsapp_url") or "").strip()
        or _safe_json(lead.get("messenger_links_json"))
        or parsed_contacts.get("social_links")
    )

    services_count = int(snapshot.get("services_count") or 0)
    priced_services_count = int(snapshot.get("priced_services_count") or 0)
    unanswered_reviews_count = int(snapshot.get("unanswered_reviews_count") or 0)
    photos_count = int(snapshot.get("photos_count") or 0)
    news_count = int(snapshot.get("news_count") or 0)
    has_recent_activity = bool(snapshot.get("has_recent_activity"))

    profile_score = 100
    if not has_website:
        profile_score -= 12
    if not has_phone:
        profile_score -= 10
    if not (has_email or has_messenger):
        profile_score -= 8
    if not str(lead.get("source_url") or "").strip():
        profile_score -= 10
    if not str(lead.get("address") or "").strip():
        profile_score -= 8
    profile_score = max(35, min(100, profile_score))

    reputation_score = 100
    if rating is None:
        reputation_score -= 18
    elif rating < 4.4:
        reputation_score -= 28
    elif rating < 4.7:
        reputation_score -= 12
    if reviews_count < 10:
        reputation_score -= 16
    elif reviews_count < 20:
        reputation_score -= 8
    reputation_score = max(30, min(100, reputation_score))

    service_score = 48
    if services_count <= 0:
        service_score -= 20
    if priced_services_count <= 0:
        service_score -= 8
    service_score = max(20, min(100, service_score))

    activity_score = 42
    if has_recent_activity:
        activity_score += 12
    if news_count > 0:
        activity_score += 6
    activity_score = max(20, min(100, activity_score))

    summary_score = round(
        profile_score * 0.20
        + reputation_score * 0.35
        + service_score * 0.30
        + activity_score * 0.15
    )

    if summary_score >= 80:
        health_level = "strong"
        health_label = "Сильная карточка"
    elif summary_score >= 55:
        health_level = "growth"
        health_label = "Есть точки роста"
    else:
        health_level = "risk"
        health_label = "Карточка теряет клиентов"

    findings: List[Dict[str, Any]] = []
    if services_count <= 0:
        findings.append(
            {
                "code": "services_missing",
                "severity": "high",
                "title": "Услуги не заполнены",
                "description": "В карточке не видно структурированного списка услуг. Это снижает конверсию и затрудняет принятие решения.",
            }
        )
    if not has_website or not has_phone:
        findings.append(
            {
                "code": "profile_incomplete",
                "severity": "high" if not has_website and not has_phone else "medium",
                "title": "Карточка заполнена не полностью",
                "description": "Не хватает части базовых контактов. Это снижает доверие и уменьшает число входящих действий.",
            }
        )
    if rating is None or rating < 4.7:
        findings.append(
            {
                "code": "rating_below_target",
                "severity": "high" if (rating is None or rating < 4.4) else "medium",
                "title": "Рейтинг ниже целевого уровня",
                "description": "Текущий рейтинг и уровень доверия ниже зоны, где карточка получает максимум переходов.",
            }
        )
    if reviews_count < 20:
        findings.append(
            {
                "code": "reviews_too_few",
                "severity": "medium",
                "title": "Недостаточно отзывов",
                "description": "Социального доказательства мало. Карточка выглядит менее надёжно для новых клиентов.",
            }
        )

    revenue_potential = estimate_card_revenue_gap(
        rating=rating,
        services_count=services_count,
        priced_services_count=priced_services_count,
        unanswered_reviews_count=unanswered_reviews_count,
        reviews_count=reviews_count,
        photos_count=photos_count,
        news_count=news_count,
        average_check=None,
        current_revenue=None,
        business_type=business_type,
    )

    top_driver = "заполнении карточки"
    if revenue_potential["rating_gap"]["max"] >= max(
        revenue_potential["content_gap"]["max"],
        revenue_potential["service_gap"]["max"],
    ):
        top_driver = "рейтинге и доверии"
    elif revenue_potential["service_gap"]["max"] >= revenue_potential["content_gap"]["max"]:
        top_driver = "структуре услуг"

    summary_text = (
        f"Это демо-аудит лида: карточка {lead_name} выглядит неполной, основной потенциал роста сейчас в {top_driver}. "
        f"Такой экран можно использовать в разговоре как наглядный пример точек роста."
    )

    recommended_actions: List[Dict[str, Any]] = [
        {
            "priority": "high",
            "title": "Заполнить и структурировать услуги",
            "description": "Добавьте основные услуги с понятными названиями и ценами, чтобы карточка лучше конвертировала просмотры в обращения.",
        },
        {
            "priority": "high" if rating is None or rating < 4.4 else "medium",
            "title": "Усилить рейтинг и работу с отзывами",
            "description": "Соберите свежие отзывы и закройте негатив корректными ответами, чтобы поднять доверие к карточке.",
        },
        {
            "priority": "medium",
            "title": "Закрыть пробелы в карточке",
            "description": "Проверьте контакты, сайт и базовое наполнение карточки — это быстрые улучшения с ощутимым эффектом.",
        },
    ]
    services_preview = snapshot.get("services_preview") or _lead_demo_services_preview(business_type)
    reviews_preview = snapshot.get("reviews_preview") or _lead_demo_reviews_preview(lead_name, business_type, rating, reviews_count)
    news_preview = snapshot.get("news_preview") or _lead_demo_news_preview(business_type)
    last_parse_status = snapshot.get("last_parse_status") or "lead_preview"
    no_new_services_found = bool(
        services_count <= 0 and str(last_parse_status).lower() not in {"lead_preview", "preview"}
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "business": {
            "id": lead.get("id"),
            "name": lead_name,
            "business_type": business_type,
            "city": city or None,
        },
        "parse_context": {
            "last_parse_at": snapshot.get("last_parse_at") or lead.get("updated_at") or lead.get("created_at"),
            "last_parse_status": last_parse_status,
            "last_parse_task_id": snapshot.get("last_parse_task_id"),
            "last_parse_retry_after": snapshot.get("last_parse_retry_after"),
            "last_parse_error": snapshot.get("last_parse_error"),
            "no_new_services_found": no_new_services_found,
        },
        "summary_score": summary_score,
        "health_level": health_level,
        "health_label": health_label,
        "summary_text": summary_text,
        "subscores": {
            "profile": profile_score,
            "reputation": reputation_score,
            "services": service_score,
            "activity": activity_score,
        },
        "findings": findings[:5],
        "current_state": {
            "rating": rating,
            "reviews_count": reviews_count,
            "unanswered_reviews_count": unanswered_reviews_count,
            "services_count": services_count,
            "services_with_price_count": priced_services_count,
            "has_website": has_website,
            "has_recent_activity": has_recent_activity,
            "photos_state": "unknown",
        },
        "revenue_potential": revenue_potential,
        "recommended_actions": recommended_actions,
        "services_preview": services_preview,
        "reviews_preview": reviews_preview,
        "news_preview": news_preview,
        "preview_meta": {
            "business_id": business.get("id"),
            "has_phone": has_phone,
            "has_email": has_email,
            "has_messenger": has_messenger,
            "source": lead.get("source"),
            "source_url": snapshot.get("source_url") or lead.get("source_url"),
        },
    }


def build_card_audit_snapshot(business_id: str) -> Dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, name, business_type, city, website
            FROM businesses
            WHERE id = %s
            """,
            (business_id,),
        )
        business = _to_dict(cursor, cursor.fetchone())
        if not business:
            raise ValueError("Бизнес не найден")

        cursor.execute(
            """
            SELECT rating, reviews_count, overview, products, news, photos, updated_at
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        latest_card = _to_dict(cursor, cursor.fetchone()) or {}

        cursor.execute(
            """
            SELECT status, updated_at
            FROM parsequeue
            WHERE business_id = %s
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        latest_parse = _to_dict(cursor, cursor.fetchone()) or {}

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_services,
                COUNT(*) FILTER (WHERE is_active IS TRUE OR is_active IS NULL) AS active_services,
                COUNT(*) FILTER (
                    WHERE (is_active IS TRUE OR is_active IS NULL)
                      AND COALESCE(TRIM(price), '') <> ''
                ) AS priced_services,
                MAX(updated_at) AS last_service_update,
                COUNT(*) FILTER (
                    WHERE (is_active IS TRUE OR is_active IS NULL)
                      AND source = ANY(%s)
                ) AS active_yandex_services
            FROM userservices
            WHERE business_id = %s
            """,
            (list(YMAP_SOURCES), business_id),
        )
        services_row = _to_dict(cursor, cursor.fetchone()) or {}

        unanswered_reviews_count = 0
        if _table_exists(cursor, "externalbusinessreviews"):
            cursor.execute(
                """
                WITH preferred_source AS (
                    SELECT CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM externalbusinessreviews r2
                            WHERE r2.business_id = %s
                              AND r2.source = 'yandex_maps'
                        ) THEN 'yandex_maps'
                        ELSE 'yandex_business'
                    END AS source
                )
                SELECT COUNT(*) AS cnt
                FROM externalbusinessreviews r, preferred_source ps
                WHERE r.business_id = %s
                  AND r.source = ps.source
                  AND (r.response_text IS NULL OR TRIM(COALESCE(r.response_text, '')) = '')
                """,
                (business_id, business_id),
            )
            unanswered_reviews_count = int((_to_dict(cursor, cursor.fetchone()) or {}).get("cnt") or 0)

        cursor.execute(
            """
            SELECT data
            FROM businessoptimizationwizard
            WHERE business_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        wizard_row = _to_dict(cursor, cursor.fetchone()) or {}
        wizard_data = _safe_json(wizard_row.get("data")) or {}

        overview = _safe_json(latest_card.get("overview")) or {}
        photos = _safe_json(latest_card.get("photos"))
        news = _safe_json(latest_card.get("news"))

        photos_count = len(photos) if isinstance(photos, list) else int(overview.get("photos_count") or 0)
        if isinstance(news, list):
            news_count = len(news)
        elif isinstance(news, dict):
            news_count = len(news)
        else:
            news_count = 0

        rating = latest_card.get("rating")
        rating_value = float(rating) if rating is not None else None
        reviews_count = int(latest_card.get("reviews_count") or 0)
        total_services = int(services_row.get("total_services") or 0)
        services_count = int(services_row.get("active_services") or 0)
        if services_count <= 0 and total_services > 0:
            # В части проектов данные уже записаны, но флаг активности не выставлен.
            # Для аудита считаем такие услуги как доступные, чтобы не давать ложное
            # "услуги не заполнены".
            services_count = total_services
        priced_services_count = int(services_row.get("priced_services") or 0)
        active_yandex_services = int(services_row.get("active_yandex_services") or 0)

        average_check = _extract_numeric(wizard_data.get("average_check"))
        current_revenue = _extract_numeric(wizard_data.get("revenue"))

        has_website = bool(str(business.get("website") or "").strip())
        parse_dt = _coerce_dt(latest_parse.get("updated_at"))
        now = datetime.now(timezone.utc)
        has_recent_activity = bool(parse_dt and parse_dt >= now - timedelta(days=45)) or news_count > 0

        photos_state = "good" if photos_count >= 5 else "weak" if photos_count > 0 else "missing"

        profile_score = 100
        if not has_website:
            profile_score -= 12
        if not overview:
            profile_score -= 12
        if photos_count <= 0:
            profile_score -= 18
        elif photos_count < 5:
            profile_score -= 8
        if latest_parse.get("status") not in ("completed", "success"):
            profile_score -= 8
        profile_score = max(0, min(100, profile_score))

        reputation_score = 100
        if rating_value is None:
            reputation_score -= 30
        elif rating_value < 4.4:
            reputation_score -= 30
        elif rating_value < 4.7:
            reputation_score -= 14
        if reviews_count < 20:
            reputation_score -= 10
        if unanswered_reviews_count > 0:
            reputation_score -= min(22, unanswered_reviews_count * 3)
        reputation_score = max(0, min(100, reputation_score))

        service_score = 100
        if services_count <= 0:
            service_score -= 45
        elif services_count < 5:
            service_score -= 22
        if services_count > 0 and priced_services_count <= 0:
            service_score -= 12
        elif services_count > 0 and priced_services_count < max(1, services_count // 2):
            service_score -= 6
        service_score = max(0, min(100, service_score))

        activity_score = 100
        if not has_recent_activity:
            activity_score -= 20
        if news_count <= 0:
            activity_score -= 10
        activity_score = max(0, min(100, activity_score))

        summary_score = int(round(
            profile_score * 0.20
            + reputation_score * 0.35
            + service_score * 0.30
            + activity_score * 0.15
        ))

        if summary_score >= 80:
            health_level = "strong"
            health_label = "Сильная карточка"
        elif summary_score >= 55:
            health_level = "growth"
            health_label = "Есть точки роста"
        else:
            health_level = "risk"
            health_label = "Карточка теряет клиентов"

        findings: List[Dict[str, Any]] = []
        if not has_website or not overview:
            findings.append({
                "code": "profile_incomplete",
                "severity": "medium",
                "title": "Карточка заполнена не полностью",
                "description": "Не все базовые данные карточки заполнены. Это снижает доверие и качество первого контакта с клиентом.",
            })

        if services_count <= 0:
            findings.append({
                "code": "services_missing",
                "severity": "high",
                "title": "Услуги не заполнены",
                "description": "В карточке нет активного списка услуг. Это снижает понятность предложения и конверсию.",
            })
        elif services_count < 5:
            findings.append({
                "code": "services_unstructured",
                "severity": "high",
                "title": "Список услуг слишком короткий",
                "description": f"Сейчас активных услуг: {services_count}. Карточка выглядит неполной и теряет коммерческие запросы.",
            })

        if services_count > 0 and priced_services_count <= 0:
            findings.append({
                "code": "prices_missing",
                "severity": "medium",
                "title": "Услуги без цен",
                "description": "У активных услуг нет цен. Карточка выглядит менее понятной и хуже конвертирует в обращение.",
            })

        if rating_value is not None and rating_value < 4.4:
            findings.append({
                "code": "rating_below_target",
                "severity": "high",
                "title": "Рейтинг ниже зоны доверия",
                "description": f"Текущий рейтинг {rating_value:.1f}. При таком уровне падает доверие и видимость карточки.",
            })
        elif rating_value is not None and rating_value < 4.7:
            findings.append({
                "code": "rating_gap",
                "severity": "medium",
                "title": "Рейтинг можно усилить",
                "description": f"Текущий рейтинг {rating_value:.1f}. До сильной зоны не хватает примерно {4.7 - rating_value:.1f} звезды.",
            })

        if reviews_count < 20:
            findings.append({
                "code": "reviews_too_few",
                "severity": "medium",
                "title": "Недостаточно отзывов для сильного доверия",
                "description": f"Сейчас отзывов: {reviews_count}. Для стабильного social proof карточке нужен более уверенный объём отзывов.",
            })

        if unanswered_reviews_count > 0:
            findings.append({
                "code": "unanswered_reviews_backlog",
                "severity": "high" if unanswered_reviews_count >= 3 else "medium",
                "title": "Есть отзывы без ответа",
                "description": f"Без ответа остаётся {unanswered_reviews_count} отзыв(ов). Это снижает доверие и конверсию.",
            })

        if photos_state == "missing":
            findings.append({
                "code": "photos_missing_or_unknown",
                "severity": "medium",
                "title": "Не хватает фото",
                "description": "В карточке нет фото или они не были получены. Визуальное доверие карточки проседает.",
            })

        if not has_recent_activity:
            findings.append({
                "code": "low_recent_activity",
                "severity": "medium",
                "title": "Карточка выглядит неактивной",
                "description": "Нет свежих обновлений. Карточка выглядит менее живой и хуже продаёт.",
            })

        revenue_potential = estimate_card_revenue_gap(
            rating=rating_value,
            services_count=services_count,
            priced_services_count=priced_services_count,
            unanswered_reviews_count=unanswered_reviews_count,
            reviews_count=reviews_count,
            photos_count=photos_count,
            news_count=news_count,
            average_check=average_check,
            current_revenue=current_revenue,
            business_type=business.get("business_type"),
        )

        recommended_actions: List[Dict[str, Any]] = []
        if services_count < 5:
            recommended_actions.append({
                "priority": "high",
                "title": "Доработать услуги",
                "description": "Добавьте 5–10 ключевых услуг и приведите названия к понятной коммерческой структуре.",
            })
        if services_count > 0 and priced_services_count <= 0:
            recommended_actions.append({
                "priority": "high",
                "title": "Добавить цены к основным услугам",
                "description": "Добавьте цены хотя бы для ключевых услуг, чтобы карточка выглядела понятнее и быстрее вела к обращению.",
            })
        if unanswered_reviews_count > 0:
            recommended_actions.append({
                "priority": "high",
                "title": "Закрыть отзывы без ответа",
                "description": f"Сначала ответьте на {unanswered_reviews_count} отзыв(ов), чтобы восстановить доверие.",
            })
        if photos_count < 5:
            recommended_actions.append({
                "priority": "medium",
                "title": "Обновить визуальный блок",
                "description": "Добавьте актуальные фото работ, интерьера или продукции.",
            })
        if not has_recent_activity:
            recommended_actions.append({
                "priority": "medium",
                "title": "Показать активность",
                "description": "Подготовьте 2–3 новости или обновления, чтобы карточка выглядела живой.",
            })
        if rating_value is not None and rating_value < 4.7:
            recommended_actions.append({
                "priority": "low",
                "title": "Работать над рейтингом",
                "description": "Соберите свежие отзывы и быстрее отвечайте на негатив, чтобы вернуть карточку в сильную зону доверия.",
            })

        severity_rank = {"high": 0, "medium": 1, "low": 2}
        findings.sort(key=lambda item: severity_rank.get(item.get("severity"), 9))

        top_driver = max(
            [
                ("рейтинга", revenue_potential["rating_gap"]["max"]),
                ("неполной карточки", revenue_potential["content_gap"]["max"]),
                ("структуры услуг", revenue_potential["service_gap"]["max"]),
            ],
            key=lambda item: item[1],
        )[0]
        summary_text = (
            f"{health_label}. "
            f"Ориентировочный недобор из-за карточки: {revenue_potential['total_min']:,}–{revenue_potential['total_max']:,} ₽ в месяц. "
            f"Главная зона потерь сейчас — из-за {top_driver}."
        ).replace(",", " ")

        no_new_services_found = bool(
            latest_parse.get("status") in ("completed", "success")
            and active_yandex_services == 0
            and services_count > 0
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "business": {
                "id": business.get("id"),
                "name": business.get("name"),
                "business_type": business.get("business_type"),
                "city": business.get("city"),
            },
            "parse_context": {
                "last_parse_at": latest_parse.get("updated_at"),
                "last_parse_status": latest_parse.get("status"),
                "no_new_services_found": no_new_services_found,
            },
            "summary_score": summary_score,
            "health_level": health_level,
            "health_label": health_label,
            "summary_text": summary_text,
            "findings": findings[:5],
            "subscores": {
                "profile": profile_score,
                "reputation": reputation_score,
                "services": service_score,
                "activity": activity_score,
            },
            "revenue_potential": revenue_potential,
            "recommended_actions": recommended_actions[:5],
            "current_state": {
                "rating": rating_value,
                "reviews_count": reviews_count,
                "unanswered_reviews_count": unanswered_reviews_count,
                "services_count": services_count,
                "services_with_price_count": priced_services_count,
                "has_website": has_website,
                "has_recent_activity": has_recent_activity,
                "photos_state": photos_state,
            },
        }
    finally:
        db.close()
