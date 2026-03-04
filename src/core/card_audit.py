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
                SELECT COUNT(*) AS cnt
                FROM externalbusinessreviews
                WHERE business_id = %s
                  AND (response_text IS NULL OR TRIM(COALESCE(response_text, '')) = '')
                """,
                (business_id,),
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
        services_count = int(services_row.get("active_services") or 0)
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

        summary_text = (
            f"{health_label}. "
            f"Ориентировочный недобор из-за карточки: {revenue_potential['total_min']:,}–{revenue_potential['total_max']:,} ₽ в месяц."
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
