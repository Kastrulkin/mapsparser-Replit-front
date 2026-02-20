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
        
        if business_id:
            # Phase 0.1: Security & Validation
            cursor.execute("SELECT owner_id, network_id FROM Businesses WHERE id = %s", (business_id,))
            biz_row = cursor.fetchone()
            
            if not biz_row:
                db.close()
                return jsonify({"error": "Business not found"}), 404
            
            owner_id = biz_row.get('owner_id') if isinstance(biz_row, dict) else biz_row[0]
            biz_network_id = biz_row.get('network_id') if isinstance(biz_row, dict) else biz_row[1]
            
            # 403 Forbidden
            if owner_id != user_id and not current_user.get('is_superadmin'):
                return jsonify({"error": "Access denied"}), 403
                
            if biz_network_id:
                # Backward-compatible behavior for old frontend:
                # if member business_id is passed, return network aggregate instead of 400.
                network_id = network_id or biz_network_id
                business_id = None
                where_clauses.append("b.network_id = %s")
                params.append(network_id)
            else:
                where_clauses.append("b.id = %s")
                params.append(business_id)
        
        where_sql = " AND ".join(where_clauses)
        has_map_parse_results = _table_exists(cursor, "mapparseresults")

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
            # Агрегат по нескольким бизнесам — MapParseResults (последняя запись на бизнес)
            if has_map_parse_results:
                cursor.execute(f"""
                    SELECT 
                        COUNT(DISTINCT b.id) as locations_count,
                        AVG(CAST(mpr.rating AS REAL)) as avg_rating,
                        SUM(mpr.reviews_count) as total_reviews
                    FROM Businesses b
                    LEFT JOIN LATERAL (
                        SELECT rating, reviews_count FROM MapParseResults
                        WHERE business_id = b.id ORDER BY created_at DESC LIMIT 1
                    ) mpr ON true
                    WHERE {where_sql}
                """, params)
                row = cursor.fetchone()
                locations_count = (row.get('locations_count') if isinstance(row, dict) else row[0]) or 0
                avg_rating = round((row.get('avg_rating') if isinstance(row, dict) else row[1]) or 0, 1)
                total_reviews = (row.get('total_reviews') if isinstance(row, dict) else row[2]) or 0
            else:
                cursor.execute(f"SELECT COUNT(DISTINCT b.id) AS locations_count FROM Businesses b WHERE {where_sql}", params)
                row = cursor.fetchone() or {}
                locations_count = (row.get('locations_count') if isinstance(row, dict) else row[0]) or 0
                avg_rating = 0
                total_reviews = 0
            unanswered_reviews_count = 0
        
        # Count locations with alerts (placeholder for now)
        locations_with_alerts = 0
        alerts_breakdown = {
            "stale_news": 0,
            "stale_photos": 0,
            "unanswered_reviews": 0,
            "low_rating": 0
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

        if business_id:
            # Phase 0.1: Security & Validation
            cursor.execute("SELECT owner_id, network_id FROM Businesses WHERE id = %s", (business_id,))
            biz_row = cursor.fetchone()
            
            if not biz_row:
                db.close()
                return jsonify({"error": "Business not found"}), 404
            
            owner_id = biz_row.get('owner_id') if isinstance(biz_row, dict) else biz_row[0]
            biz_network_id = biz_row.get('network_id') if isinstance(biz_row, dict) else biz_row[1]
            
            if owner_id != user_id and not current_user.get('is_superadmin'):
                return jsonify({"error": "Access denied"}), 403
            
            if biz_network_id:
                # Backward-compatible behavior for old frontend:
                # if member business_id is passed, return alerts for whole network.
                network_id = network_id or biz_network_id
                where_clauses.append("b.network_id = %s")
                params.append(network_id)
            else:
                where_clauses.append("b.id = %s")
                params.append(business_id)
        
        where_sql = " AND ".join(where_clauses)
        has_map_parse_results = _table_exists(cursor, "mapparseresults")
        
        # Get all businesses with their thresholds and latest activity
        if has_map_parse_results:
            cursor.execute(f"""
                SELECT 
                    b.id as business_id,
                    b.name as business_name,
                    b.business_type,
                    bt.alert_threshold_news_days,
                    bt.alert_threshold_photos_days,
                    bt.alert_threshold_reviews_days,
                    mpr.rating,
                    mpr.reviews_count,
                    mpr.photos_count,
                    mpr.created_at as last_parse
                FROM Businesses b
                LEFT JOIN BusinessTypes bt ON b.business_type = bt.type_key
                LEFT JOIN MapParseResults mpr ON b.id = mpr.business_id
                WHERE {where_sql}
                ORDER BY b.name
            """, params)
        else:
            cursor.execute(f"""
                SELECT 
                    b.id as business_id,
                    b.name as business_name,
                    b.business_type,
                    bt.alert_threshold_news_days,
                    bt.alert_threshold_photos_days,
                    bt.alert_threshold_reviews_days,
                    NULL::float AS rating,
                    NULL::int AS reviews_count,
                    NULL::int AS photos_count,
                    NULL::timestamp AS last_parse
                FROM Businesses b
                LEFT JOIN BusinessTypes bt ON b.business_type = bt.type_key
                WHERE {where_sql}
                ORDER BY b.name
            """, params)
        
        businesses = cursor.fetchall()
        locations_with_alerts = []
        
        for biz in businesses:
            business_id = biz['business_id']
            business_name = biz['business_name'] or f"Бизнес {business_id[:8]}"
            business_type = biz['business_type']
            rating = float(biz['rating']) if biz['rating'] else None
            
            # Get thresholds (with defaults if not configured)
            threshold_news = biz['alert_threshold_news_days'] or 30
            threshold_photos = biz['alert_threshold_photos_days'] or 90
            threshold_reviews = biz['alert_threshold_reviews_days'] or 7
            
            alerts = []
            
            # Check for stale news
            cursor.execute("""
                SELECT MAX(created_at) as last_news
                FROM UserNews
                WHERE business_id = %s
            """, (business_id,))
            news_row = cursor.fetchone()
            
            if news_row and news_row['last_news']:
                last_news = datetime.fromisoformat(news_row['last_news'])
                days_since_news = (datetime.now() - last_news).days
                
                if days_since_news > threshold_news:
                    if not alert_type or alert_type == 'stale_news':
                        alerts.append({
                            "type": "stale_news",
                            "severity": "warning",
                            "days_since": days_since_news,
                            "threshold": threshold_news,
                            "message": f"Новости не обновлялись {days_since_news} дней (порог: {threshold_news})"
                        })
            else:
                # No news at all
                if not alert_type or alert_type == 'stale_news':
                    alerts.append({
                        "type": "stale_news",
                        "severity": "warning",
                        "days_since": None,
                        "threshold": threshold_news,
                        "message": f"Нет новостей"
                    })
            
            # Check for stale photos (placeholder - need to implement photo tracking)
            # For now, skip
            
            # Check for low rating (below average)
            if rating and rating < 4.0:  # Hardcoded threshold for now
                if not alert_type or alert_type == 'low_rating':
                    alerts.append({
                        "type": "low_rating",
                        "severity": "info",
                        "rating": rating,
                        "message": f"Рейтинг {rating} ниже среднего"
                    })
            
            # Add unanswered reviews check (placeholder)
            # TODO: Implement when external review sync is available
            
            if alerts:
                locations_with_alerts.append({
                    "business_id": business_id,
                    "business_name": business_name,
                    "business_type": business_type,
                    "rating": rating,
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
