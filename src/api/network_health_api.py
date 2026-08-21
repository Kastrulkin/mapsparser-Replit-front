#!/usr/bin/env python3
"""
Network Health API
Provides endpoints for monitoring the health of all locations in a user's network.
"""

from flask import Blueprint, jsonify, request
from functools import wraps
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

network_health_bp = Blueprint('network_health', __name__)


from auth_system import verify_session
from database_manager import DatabaseManager
from core.growth_schema import ensure_growth_schema
from progress_calculator import _get_map_metrics


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS exists_flag", (f"public.{table_name}",))
    row = cursor.fetchone() or {}
    return bool(row.get("exists_flag")) if isinstance(row, dict) else bool(row[0])

def _table_has_column(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND lower(table_name) = lower(%s)
              AND lower(column_name) = lower(%s)
        ) AS has_column
        """,
        (table_name, column_name),
    )
    row = cursor.fetchone() or {}
    return bool(row.get("has_column")) if isinstance(row, dict) else bool(row[0])


def _network_attention_rows(cursor, where_sql: str, params: list[Any]) -> list[dict[str, Any]]:
    """Return one current, user-facing health row per location."""
    has_reviews = _table_exists(cursor, "externalbusinessreviews")
    reviews_sql = """
        LEFT JOIN LATERAL (
            SELECT COUNT(*) FILTER (
                WHERE COALESCE(NULLIF(TRIM(review.response_text), ''), '') IN ('', '—')
                  AND COALESCE(review.is_current, TRUE) IS TRUE
            ) AS unanswered_reviews
            FROM externalbusinessreviews review
            WHERE review.business_id = b.id
        ) reviews ON TRUE
    """ if has_reviews else "LEFT JOIN LATERAL (SELECT 0::bigint AS unanswered_reviews) reviews ON TRUE"

    cursor.execute(
        f"""
        SELECT
            b.id AS business_id,
            b.name AS business_name,
            b.address,
            b.business_type,
            b.yandex_url,
            COALESCE(latest_card.rating, b.rating, 0) AS rating,
            COALESCE(latest_card.reviews_count, b.reviews_count, 0) AS reviews_count,
            COALESCE(
                NULLIF(b.external_ids->>'yandex_news_count', '')::integer,
                jsonb_array_length(
                CASE
                    WHEN jsonb_typeof(COALESCE(latest_card.news::jsonb, '[]'::jsonb)) = 'array'
                    THEN COALESCE(latest_card.news::jsonb, '[]'::jsonb)
                    ELSE '[]'::jsonb
                END
                ),
                0
            ) AS news_count,
            COALESCE(reviews.unanswered_reviews, 0) AS unanswered_reviews_count
        FROM businesses b
        LEFT JOIN LATERAL (
            SELECT card.rating, card.reviews_count, card.news
            FROM cards card
            WHERE card.business_id = b.id
            ORDER BY card.is_latest DESC NULLS LAST, card.created_at DESC
            LIMIT 1
        ) latest_card ON TRUE
        {reviews_sql}
        WHERE {where_sql}
        ORDER BY b.address, b.name
        """,
        params,
    )
    return [dict(row) for row in (cursor.fetchall() or [])]


def require_auth(f):
    """Decorator to require authentication for API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Unauthorized"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        
        if not user_data:
            return jsonify({"error": "Unauthorized"}), 401
            
        # Compatibility adapter: existing code expects 'id', verify_session returns 'user_id'
        user = {
            'id': user_data['user_id'],
            'email': user_data.get('email'),
            'name': user_data.get('name'),
            'is_superadmin': user_data.get('is_superadmin', False)
        }
            
        return f(user, *args, **kwargs)
    return decorated_function


@network_health_bp.route('/api/network/health', methods=['GET'])
@require_auth
def get_network_health(current_user):
    """
    Get aggregate health metrics for all locations in user's network.
    
    Query params:
        - network_id: Filter by specific network (optional)
        - business_id: Filter by specific business (optional)
    
    Returns:
        {
            "success": true,
            "data": {
                "locations_count": 164,
                "avg_rating": 4.2,
                "total_reviews": 1520,
                "unanswered_reviews_count": 23,
                "locations_with_alerts": 12,
                "alerts_breakdown": {
                    "stale_news": 5,
                    "stale_photos": 3,
                    "unanswered_reviews": 8,
                    "low_rating": 2
                }
            }
        }
    """
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        ensure_growth_schema(db)
        
        user_id = current_user['id']
        network_id = request.args.get('network_id')
        business_id = request.args.get('business_id')
        requested_business_id = business_id
        
        # Build WHERE clause
        where_clauses = ["b.owner_id = %s"]
        params = [user_id]
        
        if network_id:
            where_clauses.append("b.network_id = %s")
            params.append(network_id)
            where_clauses.append("b.id <> %s")
            params.append(network_id)
        
        if business_id:
            # Phase 0.1: Security & Validation
            cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
            biz_row = cursor.fetchone()
            
            if not biz_row:
                db.close()
                return jsonify({"error": "Business not found"}), 404
            
            owner_id = biz_row.get('owner_id') if isinstance(biz_row, dict) else biz_row[0]
            
            # 403 Forbidden
            if owner_id != user_id and not current_user.get('is_superadmin'):
                return jsonify({"error": "Access denied"}), 403

            where_clauses.append("b.id = %s")
            params.append(business_id)
        
        where_sql = " AND ".join(where_clauses)

        # Для одного бизнеса — используем унифицированные метрики (external → cards → MapParseResults)
        if requested_business_id and not network_id:
            metrics = _get_map_metrics(cursor, business_id)
            avg_rating = round(metrics["rating"] or 0, 1)
            total_reviews = metrics["reviews_count"] or 0
            cursor.execute("""
                SELECT COUNT(*) FROM externalbusinessreviews
                WHERE business_id = %s AND source = 'yandex_business'
                  AND (response_text IS NULL OR response_text = '' OR response_text = '—')
            """, (business_id,))
            unr = cursor.fetchone()
            unanswered_reviews_count = (unr[0] if isinstance(unr, (list, tuple)) else unr.get('count', 0)) or 0
            locations_count = 1
        else:
            location_rows = _network_attention_rows(cursor, where_sql, params)
            locations_count = len(location_rows)
            ratings = [float(row.get("rating") or 0) for row in location_rows if float(row.get("rating") or 0) > 0]
            avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
            total_reviews = sum(int(row.get("reviews_count") or 0) for row in location_rows)
            unanswered_reviews_count = sum(int(row.get("unanswered_reviews_count") or 0) for row in location_rows)

        if requested_business_id and not network_id:
            attention_rows = _network_attention_rows(cursor, where_sql, params)
        else:
            attention_rows = location_rows

        locations_with_alerts = sum(
            1
            for row in attention_rows
            if int(row.get("news_count") or 0) == 0
            or int(row.get("unanswered_reviews_count") or 0) > 0
            or (0 < float(row.get("rating") or 0) < 4.5)
        )
        alerts_breakdown = {
            "stale_news": sum(1 for row in attention_rows if int(row.get("news_count") or 0) == 0),
            "stale_photos": 0,
            "unanswered_reviews": sum(1 for row in attention_rows if int(row.get("unanswered_reviews_count") or 0) > 0),
            "low_rating": sum(1 for row in attention_rows if 0 < float(row.get("rating") or 0) < 4.5),
        }
        
        db.close()
        
        return jsonify({
            "success": True,
            "data": {
                "locations_count": locations_count,
                "avg_rating": avg_rating,
                "total_reviews": total_reviews,
                "unanswered_reviews_count": unanswered_reviews_count,
                "locations_with_alerts": locations_with_alerts,
                "alerts_breakdown": alerts_breakdown
            }
        })
        
    except Exception as e:
        print(f"Error in get_network_health: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@network_health_bp.route('/api/network/locations-alerts', methods=['GET'])
@require_auth
def get_location_alerts(current_user):
    """
    Get list of locations requiring attention based on business-type-specific thresholds.
    
    Query params:
        - network_id: Filter by specific network (optional)
        - alert_type: Filter by specific alert type (optional): stale_news, stale_photos, unanswered_reviews, low_rating
    
    Returns:
        {
            "success": true,
            "data": {
                "locations": [
                    {
                        "business_id": "...",
                        "business_name": "Салон красоты Нежность",
                        "business_type": "beauty_salon",
                        "rating": 4.1,
                        "alerts": [
                            {
                                "type": "stale_news",
                                "severity": "warning",
                                "days_since": 45,
                                "threshold": 30,
                                "message": "Новости не обновлялись 45 дней (порог: 30)"
                            },
                            {
                                "type": "unanswered_reviews",
                                "severity": "urgent",
                                "count": 3,
                                "message": "3 неотвеченных отзыва"
                            }
                        ]
                    }
                ]
            }
        }
    """
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        ensure_growth_schema(db)
        
        user_id = current_user['id']
        network_id = request.args.get('network_id')
        business_id = request.args.get('business_id')  # NEW: Support business_id
        alert_type = request.args.get('alert_type')
        
        # Build WHERE clause
        where_clauses = ["b.owner_id = %s"]
        params = [user_id]
        
        if network_id:
            where_clauses.append("b.network_id = %s")
            params.append(network_id)
            where_clauses.append("b.id <> %s")
            params.append(network_id)

        if business_id:
            # Phase 0.1: Security & Validation
            cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
            biz_row = cursor.fetchone()
            
            if not biz_row:
                db.close()
                return jsonify({"error": "Business not found"}), 404
            
            owner_id = biz_row.get('owner_id') if isinstance(biz_row, dict) else biz_row[0]
            
            if owner_id != user_id and not current_user.get('is_superadmin'):
                return jsonify({"error": "Access denied"}), 403

            where_clauses.append("b.id = %s")
            params.append(business_id)
        
        where_sql = " AND ".join(where_clauses)
        businesses = _network_attention_rows(cursor, where_sql, params)
        locations_with_alerts = []
        
        for biz in businesses:
            business_id = biz['business_id']
            business_name = biz['business_name'] or f"Бизнес {business_id[:8]}"
            business_type = biz['business_type']
            rating = float(biz['rating']) if biz['rating'] else None
            
            alerts = []

            news_count = int(biz.get("news_count") or 0)
            unanswered_count = int(biz.get("unanswered_reviews_count") or 0)
            if news_count == 0 and (not alert_type or alert_type == 'stale_news'):
                alerts.append({
                    "type": "stale_news",
                    "severity": "warning",
                    "count": 0,
                    "message": "В карточке нет новостей",
                })

            if unanswered_count > 0 and (not alert_type or alert_type == 'unanswered_reviews'):
                alerts.append({
                    "type": "unanswered_reviews",
                    "severity": "urgent",
                    "count": unanswered_count,
                    "message": f"Отзывов без ответа: {unanswered_count}",
                })

            if rating and rating < 4.5:
                if not alert_type or alert_type == 'low_rating':
                    alerts.append({
                        "type": "low_rating",
                        "severity": "info",
                        "rating": rating,
                        "message": f"Рейтинг {rating:.1f} ниже сильных точек сети"
                    })
            
            if alerts:
                locations_with_alerts.append({
                    "business_id": business_id,
                    "business_name": business_name,
                    "business_type": business_type,
                    "address": biz.get("address"),
                    "yandex_url": biz.get("yandex_url"),
                    "rating": rating,
                    "reviews_count": int(biz.get("reviews_count") or 0),
                    "news_count": news_count,
                    "unanswered_reviews_count": unanswered_count,
                    "alerts": alerts
                })
        
        db.close()
        
        return jsonify({
            "success": True,
            "data": {
                "locations": locations_with_alerts
            }
        })
        
    except Exception as e:
        print(f"Error in get_location_alerts: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
