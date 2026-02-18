from flask import Blueprint, jsonify, request
from database_manager import DatabaseManager
from core.auth_helpers import require_auth_from_request, verify_business_access
import uuid
import json
from datetime import datetime

metrics_history_bp = Blueprint('metrics_history_api', __name__)

@metrics_history_bp.route('/api/business/<business_id>/metrics-history', methods=['GET'])
def get_metrics_history(business_id):
    """Получить историю метрик бизнеса"""
    try:
        user_data = require_auth_from_request()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ к бизнесу
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            db.close()
            return jsonify({"error": "Нет доступа" if owner_id else "Бизнес не найден"}), 403 if owner_id else 404

        def _as_dict(row):
            if row is None:
                return None
            if isinstance(row, dict):
                return row
            cols = [d[0] for d in cursor.description] if cursor.description else []
            return dict(zip(cols, row)) if cols else {}

        def _parse_json(value):
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

        def _count_unanswered_from_reviews(reviews_obj):
            if not isinstance(reviews_obj, list):
                return 0
            cnt = 0
            for r in reviews_obj:
                if not isinstance(r, dict):
                    continue
                resp = (r.get("org_reply") or r.get("response_text") or "").strip()
                if not resp:
                    cnt += 1
            return cnt

        history_by_date = {}

        # 1) История из cards (даёт фото/новости/unanswered).
        # В ряде инсталляций колонки cards.reviews нет — учитываем это динамически.
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'cards'
              AND column_name = 'reviews'
            LIMIT 1
            """
        )
        has_cards_reviews = cursor.fetchone() is not None
        cards_select = "id, created_at, rating, reviews_count, overview, photos, news"
        if has_cards_reviews:
            cards_select += ", reviews"
        cursor.execute(
            f"""
            SELECT {cards_select}
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 365
            """,
            (business_id,),
        )
        for row in cursor.fetchall():
            rd = _as_dict(row) or {}
            created_at = rd.get("created_at")
            if not created_at:
                continue
            date_key = created_at.date().isoformat() if hasattr(created_at, "date") else str(created_at)[:10]
            overview = _parse_json(rd.get("overview")) or {}
            photos = _parse_json(rd.get("photos"))
            news = _parse_json(rd.get("news"))
            reviews = _parse_json(rd.get("reviews")) if has_cards_reviews else None
            photos_count = max(
                len(photos) if isinstance(photos, list) else 0,
                int(overview.get("photos_count") or 0),
            )
            news_count = max(
                len(news) if isinstance(news, list) else 0,
                int(overview.get("news_count") or 0),
            )
            item = {
                "id": rd.get("id"),
                "date": date_key,
                "rating": float(rd["rating"]) if rd.get("rating") not in (None, "") else None,
                "reviews_count": int(rd.get("reviews_count") or 0),
                "photos_count": int(photos_count or 0),
                "news_count": int(news_count or 0),
                "unanswered_reviews_count": _count_unanswered_from_reviews(reviews),
                "source": "parsing",
                "created_at": created_at,
            }
            if date_key not in history_by_date or (history_by_date[date_key].get("created_at") or created_at) < created_at:
                history_by_date[date_key] = item

        # 2) История из externalbusinessstats (подмешиваем rating/reviews)
        cursor.execute(
            """
            SELECT source, date, rating, reviews_total, created_at
            FROM externalbusinessstats
            WHERE business_id = %s
              AND source IN ('yandex_business', 'yandex_maps')
              AND (rating IS NOT NULL OR reviews_total IS NOT NULL)
            ORDER BY created_at DESC
            LIMIT 365
            """,
            (business_id,),
        )
        for row in cursor.fetchall():
            rd = _as_dict(row) or {}
            date_raw = str(rd.get("date") or "").strip()
            if not date_raw:
                continue
            date_key = date_raw[:10]
            current = history_by_date.get(date_key) or {
                "id": None,
                "date": date_key,
                "rating": None,
                "reviews_count": 0,
                "photos_count": 0,
                "news_count": 0,
                "unanswered_reviews_count": 0,
                "source": rd.get("source") or "external",
                "created_at": rd.get("created_at"),
            }
            if rd.get("rating") not in (None, ""):
                current["rating"] = float(rd.get("rating"))
            if rd.get("reviews_total") not in (None, ""):
                current["reviews_count"] = int(rd.get("reviews_total") or 0)
            if not current.get("source"):
                current["source"] = rd.get("source") or "external"
            history_by_date[date_key] = current

        # 3) Текущее количество неотвеченных отзывов — в последнюю дату
        unanswered_now = 0
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM externalbusinessreviews
            WHERE business_id = %s
              AND source IN ('yandex_business', 'yandex_maps')
              AND (response_text IS NULL OR TRIM(COALESCE(response_text, '')) = '')
            """,
            (business_id,),
        )
        cnt_row = _as_dict(cursor.fetchone()) or {}
        unanswered_now = int(cnt_row.get("cnt") or 0)

        history = list(history_by_date.values())
        history.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
        if history and (history[0].get("unanswered_reviews_count") or 0) == 0:
            history[0]["unanswered_reviews_count"] = unanswered_now
        history = history[:100]

        db.close()
        
        return jsonify({"success": True, "history": history})
        
    except Exception as e:
        print(f"❌ Ошибка получения истории метрик: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@metrics_history_bp.route('/api/business/<business_id>/metrics-history', methods=['POST'])
def add_manual_metric(business_id):
    """Добавить метрику вручную"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        data = request.json
        metric_date = data.get('date')
        rating = data.get('rating')
        reviews_count = data.get('reviews_count')
        photos_count = data.get('photos_count')
        news_count = data.get('news_count')
        
        if not metric_date:
            return jsonify({"error": "Не указана дата"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ
        cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business or (business[0] != user_data['user_id'] and not user_data.get('is_superadmin')):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
        
        # Проверяем, есть ли уже запись за эту дату
        cursor.execute("""
            SELECT id FROM businessmetricshistory
            WHERE business_id = %s AND metric_date = %s AND source = 'manual'
        """, (business_id, metric_date))
        
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующую
            cursor.execute("""
                UPDATE businessmetricshistory
                SET rating = %s, reviews_count = %s, photos_count = %s, news_count = %s
                WHERE id = %s
            """, (rating, reviews_count, photos_count, news_count, existing[0]))
            message = "Метрика обновлена"
        else:
            # Создаем новую
            metric_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO businessmetricshistory (
                    id, business_id, metric_date, rating, reviews_count,
                    photos_count, news_count, source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'manual')
            """, (metric_id, business_id, metric_date, rating, reviews_count, 
                  photos_count, news_count))
            message = "Метрика добавлена"
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "message": message})
        
    except Exception as e:
        print(f"❌ Ошибка добавления метрики: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@metrics_history_bp.route('/api/business/<business_id>/metrics-history/<metric_id>', methods=['DELETE'])
def delete_manual_metric(business_id, metric_id):
    """Удалить метрику (только ручные)"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ
        cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business or (business[0] != user_data['user_id'] and not user_data.get('is_superadmin')):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
        
        # Удаляем только ручные записи
        cursor.execute("""
            DELETE FROM businessmetricshistory
            WHERE id = %s AND business_id = %s AND source = 'manual'
        """, (metric_id, business_id))
        
        if cursor.rowcount == 0:
            db.close()
            return jsonify({"error": "Метрика не найдена или не может быть удалена"}), 404
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "message": "Метрика удалена"})
        
    except Exception as e:
        print(f"❌ Ошибка удаления метрики: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
