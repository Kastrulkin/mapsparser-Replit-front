import json
import re
from typing import Any, Dict, List, Optional

from database_manager import DatabaseManager


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
) -> Dict[str, Any]:
    baseline_revenue = current_revenue or 0.0
    if baseline_revenue <= 0 and average_check and average_check > 0:
        estimated_purchases = max(20, services_count * 8, min(reviews_count, 80))
        baseline_revenue = average_check * estimated_purchases
    if baseline_revenue <= 0:
        baseline_revenue = 60000.0

    rating_min = rating_max = 0.0
    if rating is not None:
        rating_gap = max(0.0, 4.7 - float(rating))
        rating_penalty_min = min(0.22, rating_gap * 0.05)
        rating_penalty_max = min(0.38, rating_gap * 0.09)
        rating_min = baseline_revenue * rating_penalty_min
        rating_max = baseline_revenue * rating_penalty_max

    content_penalty_min = 0.0
    content_penalty_max = 0.0
    if photos_count <= 0:
        content_penalty_min += 0.04
        content_penalty_max += 0.09
    elif photos_count < 5:
        content_penalty_min += 0.02
        content_penalty_max += 0.05
    if news_count <= 0:
        content_penalty_min += 0.02
        content_penalty_max += 0.04
    if unanswered_reviews_count > 0:
        content_penalty_min += min(0.06, unanswered_reviews_count * 0.01)
        content_penalty_max += min(0.12, unanswered_reviews_count * 0.02)
    content_min = baseline_revenue * content_penalty_min
    content_max = baseline_revenue * content_penalty_max

    service_penalty_min = 0.0
    service_penalty_max = 0.0
    if services_count <= 0:
        service_penalty_min += 0.08
        service_penalty_max += 0.18
    elif services_count < 5:
        service_penalty_min += 0.04
        service_penalty_max += 0.10
    if priced_services_count <= 0 and services_count > 0:
        service_penalty_min += 0.03
        service_penalty_max += 0.07
    service_min = baseline_revenue * service_penalty_min
    service_max = baseline_revenue * service_penalty_max

    total_min = round(rating_min + content_min + service_min)
    total_max = round(rating_max + content_max + service_max)

    return {
        "baseline_revenue": round(baseline_revenue),
        "rating_gap": {
            "min": round(rating_min),
            "max": round(rating_max),
        },
        "content_gap": {
            "min": round(content_min),
            "max": round(content_max),
        },
        "service_gap": {
            "min": round(service_min),
            "max": round(service_max),
        },
        "total_min": total_min,
        "total_max": total_max,
        "currency": "RUB",
        "model": "deterministic_v1",
    }


def build_card_audit_snapshot(business_id: str) -> Dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, name, business_type, city
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
                MAX(updated_at) AS last_service_update
            FROM userservices
            WHERE business_id = %s
            """,
            (business_id,),
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
        products = _safe_json(latest_card.get("products"))

        if isinstance(products, list):
            products_count = len(products)
        elif isinstance(products, dict):
            products_count = len(products)
        else:
            products_count = 0

        if isinstance(photos, list):
            photos_count = len(photos)
        else:
            photos_count = int(overview.get("photos_count") or 0)

        if isinstance(news, list):
            news_count = len(news)
        elif isinstance(news, dict):
            news_count = len(news)
        else:
            news_count = 0

        rating = latest_card.get("rating")
        reviews_count = int(latest_card.get("reviews_count") or 0)
        services_count = int(services_row.get("active_services") or 0)
        priced_services_count = int(services_row.get("priced_services") or 0)

        average_check = _extract_numeric(wizard_data.get("average_check"))
        current_revenue = _extract_numeric(wizard_data.get("revenue"))

        profile_score = 100
        if services_count <= 0:
            profile_score -= 35
        elif services_count < 5:
            profile_score -= 18
        if photos_count <= 0:
            profile_score -= 18
        elif photos_count < 5:
            profile_score -= 8
        if not overview:
            profile_score -= 10
        profile_score = max(0, min(100, profile_score))

        reputation_score = 100
        if rating is None:
            reputation_score -= 30
        else:
            rating_gap = max(0.0, 4.7 - float(rating))
            reputation_score -= min(45, int(round(rating_gap * 30)))
        if unanswered_reviews_count > 0:
            reputation_score -= min(25, unanswered_reviews_count * 3)
        if reviews_count < 20:
            reputation_score -= 10
        reputation_score = max(0, min(100, reputation_score))

        service_score = 100
        if services_count <= 0:
            service_score -= 45
        elif services_count < 5:
            service_score -= 22
        if priced_services_count <= 0 and services_count > 0:
            service_score -= 12
        if products_count <= 0:
            service_score -= 8
        service_score = max(0, min(100, service_score))

        activity_score = 100
        if news_count <= 0:
            activity_score -= 20
        if latest_parse.get("status") not in ("completed", "success"):
            activity_score -= 10
        activity_score = max(0, min(100, activity_score))

        summary_score = int(round(
            profile_score * 0.28
            + reputation_score * 0.32
            + service_score * 0.25
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
                "key": "services_missing",
                "severity": "critical",
                "title": "Услуги не заполнены",
                "detail": "В карточке нет активного списка услуг. Это снижает понятность предложения и конверсию.",
            })
        elif services_count < 5:
            findings.append({
                "key": "services_thin",
                "severity": "high",
                "title": "Список услуг слишком короткий",
                "detail": f"Сейчас активных услуг: {services_count}. Карточка выглядит неполной и теряет коммерческие запросы.",
            })

        if rating is not None and float(rating) < 4.4:
            findings.append({
                "key": "rating_low",
                "severity": "critical",
                "title": "Рейтинг ниже зоны доверия",
                "detail": f"Текущий рейтинг {float(rating):.1f}. При таком уровне падает доверие и видимость карточки.",
            })
        elif rating is not None and float(rating) < 4.7:
            findings.append({
                "key": "rating_gap",
                "severity": "high",
                "title": "Рейтинг можно усилить",
                "detail": f"Текущий рейтинг {float(rating):.1f}. До сильной зоны не хватает примерно {4.7 - float(rating):.1f} звезды.",
            })

        if unanswered_reviews_count > 0:
            findings.append({
                "key": "reviews_unanswered",
                "severity": "high" if unanswered_reviews_count >= 3 else "medium",
                "title": "Есть отзывы без ответа",
                "detail": f"Без ответа остаётся {unanswered_reviews_count} отзыв(ов). Это снижает доверие и конверсию.",
            })

        if photos_count <= 0:
            findings.append({
                "key": "photos_missing",
                "severity": "medium",
                "title": "Не хватает фото",
                "detail": "В карточке нет фото или они не были получены. Визуальное доверие карточки проседает.",
            })

        if news_count <= 0:
            findings.append({
                "key": "activity_low",
                "severity": "medium",
                "title": "Карточка выглядит неактивной",
                "detail": "Нет свежих новостей или обновлений. Карточка выглядит менее живой и хуже продаёт.",
            })

        revenue_potential = estimate_card_revenue_gap(
            rating=float(rating) if rating is not None else None,
            services_count=services_count,
            priced_services_count=priced_services_count,
            unanswered_reviews_count=unanswered_reviews_count,
            reviews_count=reviews_count,
            photos_count=photos_count,
            news_count=news_count,
            average_check=average_check,
            current_revenue=current_revenue,
        )

        recommended_actions: List[Dict[str, Any]] = []
        if services_count < 5:
            recommended_actions.append({
                "priority": "high",
                "title": "Доработать услуги",
                "detail": "Добавить ключевые услуги и привести названия к понятной коммерческой структуре.",
            })
        if unanswered_reviews_count > 0:
            recommended_actions.append({
                "priority": "high",
                "title": "Закрыть отзывы без ответа",
                "detail": f"Сначала ответить на {unanswered_reviews_count} отзыв(ов), чтобы восстановить доверие.",
            })
        if photos_count < 5:
            recommended_actions.append({
                "priority": "medium",
                "title": "Обновить визуальный блок",
                "detail": "Добавить актуальные фото работ, интерьера или продукции.",
            })
        if news_count <= 0:
            recommended_actions.append({
                "priority": "medium",
                "title": "Показать активность",
                "detail": "Подготовить 2–3 новости или обновления для карточки, чтобы она выглядела живой.",
            })
        if rating is not None and float(rating) < 4.7:
            recommended_actions.append({
                "priority": "high",
                "title": "Работать над рейтингом",
                "detail": "Собрать свежие отзывы и быстрее отвечать на негатив, чтобы вернуть карточку в сильную зону доверия.",
            })

        summary_text = (
            f"{health_label}. "
            f"Ориентировочный недобор из-за карточки: {revenue_potential['total_min']:,}–{revenue_potential['total_max']:,} ₽ в месяц."
        ).replace(",", " ")

        return {
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
                "rating": float(rating) if rating is not None else None,
                "reviews_count": reviews_count,
                "unanswered_reviews_count": unanswered_reviews_count,
                "services_count": services_count,
                "priced_services_count": priced_services_count,
                "photos_count": photos_count,
                "news_count": news_count,
                "last_parse_date": latest_parse.get("updated_at"),
                "last_parse_status": latest_parse.get("status"),
                "last_card_update": latest_card.get("updated_at"),
                "last_service_update": services_row.get("last_service_update"),
            },
            "business": {
                "id": business.get("id"),
                "name": business.get("name"),
                "business_type": business.get("business_type"),
                "city": business.get("city"),
            },
        }
    finally:
        db.close()
