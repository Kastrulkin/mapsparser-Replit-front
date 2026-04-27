from __future__ import annotations

import json
from typing import Any

from database_manager import get_db_connection


def _row_to_dict(cursor, row) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
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


def _json_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return 0
        return len(parsed) if isinstance(parsed, list) else 0
    return 0


def _load_card_snapshot_by_url(normalized_url: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT
                url,
                title,
                rating,
                reviews_count,
                overview,
                products,
                news,
                photos,
                created_at
            FROM cards
            WHERE url = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (normalized_url,),
        )
        row = _row_to_dict(cursor, cursor.fetchone())
    finally:
        conn.close()
    if not row:
        return None
    overview = row.get("overview")
    if isinstance(overview, str):
        try:
            row["overview"] = json.loads(overview)
        except Exception:
            row["overview"] = {}
    elif not isinstance(overview, dict):
        row["overview"] = {}
    row["products_count"] = _json_count(row.get("products"))
    row["news_count"] = _json_count(row.get("news"))
    row["photos_count"] = _json_count(row.get("photos"))
    return row


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def build_guest_compare_result(
    own_url: str,
    competitor_url: str,
    own_report_url: str,
    competitor_report_url: str,
) -> str:
    own = _load_card_snapshot_by_url(own_url)
    competitor = _load_card_snapshot_by_url(competitor_url)

    if not own and not competitor:
        return (
            "Сравнение с конкурентом\n\n"
            "Я запустил аудит для обеих карточек. Как только данные соберутся, можно будет открыть оба аудита и сравнить их уже по фактам.\n\n"
            f"Ваша карточка:\n{own_report_url}\n\n"
            f"Конкурент:\n{competitor_report_url}\n\n"
            "Главный смысл сравнения — понять, где конкурент может забирать ваш спрос, и что можно исправить первым.\n\n"
            "Следующий шаг: открыть свой аудит и начать исправлять карточку в LocalOS."
        )

    own_title = str((own or {}).get("title") or "Ваша карточка").strip()
    competitor_title = str((competitor or {}).get("title") or "Конкурент").strip()

    own_rating = _safe_float((own or {}).get("rating"))
    competitor_rating = _safe_float((competitor or {}).get("rating"))
    own_reviews = _safe_int((own or {}).get("reviews_count"))
    competitor_reviews = _safe_int((competitor or {}).get("reviews_count"))
    own_products = _safe_int((own or {}).get("products_count"))
    competitor_products = _safe_int((competitor or {}).get("products_count"))
    own_news = _safe_int((own or {}).get("news_count"))
    competitor_news = _safe_int((competitor or {}).get("news_count"))
    own_photos = _safe_int((own or {}).get("photos_count"))
    competitor_photos = _safe_int((competitor or {}).get("photos_count"))

    strengths: list[str] = []
    gaps: list[str] = []

    if own_rating >= competitor_rating and own_rating > 0:
        strengths.append("по рейтингу ваша карточка сейчас выглядит не слабее конкурента")
    elif competitor_rating > own_rating:
        gaps.append("у конкурента сильнее рейтинг, это влияет на доверие и клики")

    if own_reviews >= competitor_reviews and own_reviews > 0:
        strengths.append("по количеству отзывов вы не уступаете или уже впереди")
    elif competitor_reviews > own_reviews:
        gaps.append("по отзывам конкурент выглядит убедительнее")

    if own_products >= competitor_products and own_products > 0:
        strengths.append("структура услуг у вас уже не слабее конкурента")
    elif competitor_products > own_products:
        gaps.append("у конкурента шире или заметнее оформлены услуги")

    if own_news >= competitor_news and own_news > 0:
        strengths.append("по свежести активности вы держитесь не хуже")
    elif competitor_news > own_news:
        gaps.append("конкурент выглядит живее за счёт новостей и обновлений")

    if own_photos >= competitor_photos and own_photos > 0:
        strengths.append("визуально карточка у вас не выглядит пустее")
    elif competitor_photos > own_photos:
        gaps.append("у конкурента сильнее визуальное заполнение карточки")

    if not strengths:
        strengths.append("после полного аудита можно будет точнее увидеть ваши сильные стороны")
    if not gaps:
        gaps.append("критичного разрыва по быстрым метрикам сейчас не видно")

    own_score = 0
    competitor_score = 0
    if own_rating > competitor_rating:
        own_score += 1
    elif competitor_rating > own_rating:
        competitor_score += 1
    if own_reviews > competitor_reviews:
        own_score += 1
    elif competitor_reviews > own_reviews:
        competitor_score += 1
    if own_products > competitor_products:
        own_score += 1
    elif competitor_products > own_products:
        competitor_score += 1
    if own_news > competitor_news:
        own_score += 1
    elif competitor_news > own_news:
        competitor_score += 1
    if own_photos > competitor_photos:
        own_score += 1
    elif competitor_photos > own_photos:
        competitor_score += 1

    if own_score > competitor_score:
        headline = "По быстрому срезу ваша карточка выглядит сильнее."
        closing = "Следующий шаг: закрепить преимущество через отзывы, новости и регулярную активность в LocalOS."
    elif competitor_score > own_score:
        headline = "По быстрому срезу конкурент выглядит сильнее."
        closing = "Следующий шаг: добить 2–3 самых видимых разрыва в LocalOS и вернуть часть спроса себе."
    else:
        headline = "По быстрому срезу разрыв между карточками пока небольшой."
        closing = "Следующий шаг: открыть обе страницы аудита и выбрать, где можно быстрее забрать спрос на своей стороне."

    return "\n".join(
        [
            "Сравнение с конкурентом",
            "",
            f"Вы: {own_title}",
            f"Конкурент: {competitor_title}",
            "",
            "Быстрый срез",
            f"• Рейтинг: {own_rating or '—'} vs {competitor_rating or '—'}",
            f"• Отзывы: {own_reviews} vs {competitor_reviews}",
            f"• Услуги: {own_products} vs {competitor_products}",
            f"• Новости: {own_news} vs {competitor_news}",
            f"• Фото: {own_photos} vs {competitor_photos}",
            "",
            headline,
            "",
            "Где вы уже держитесь",
            *[f"• {item}" for item in strengths[:2]],
            "",
            "Где стоит догонять в первую очередь",
            *[f"• {item}" for item in gaps[:3]],
            "",
            closing,
            "",
            f"Аудит вашей карточки:\n{own_report_url}",
            "",
            f"Аудит конкурента:\n{competitor_report_url}",
        ]
    )
