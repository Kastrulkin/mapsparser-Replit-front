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
        cursor.execute("SELECT to_regclass('public.cards') IS NOT NULL AS exists_flag")
        cards_exists_row = cursor.fetchone() or {}
        has_cards_table = bool(cards_exists_row.get("exists_flag")) if isinstance(cards_exists_row, dict) else bool(cards_exists_row[0])
        if has_cards_table:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'cards'
                """
            )
            cards_cols = {
                (r.get("column_name") if isinstance(r, dict) else r[0])
                for r in (cursor.fetchall() or [])
            }
            required_cols = {"id", "created_at"}
            has_required = required_cols.issubset(cards_cols)
            if has_required:
                cards_select = ["id", "created_at"]
                for col in ("rating", "reviews_count", "overview", "photos", "news", "reviews"):
                    if col in cards_cols:
                        cards_select.append(col)

                cursor.execute(
                    f"""
                    SELECT {", ".join(cards_select)}
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
                    reviews = _parse_json(rd.get("reviews")) if "reviews" in cards_cols else None
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

        # 2.1) История из businessmetricshistory (ручные/исторические записи)
        cursor.execute("SELECT to_regclass('public.businessmetricshistory') IS NOT NULL AS exists_flag")
        bm_exists_row = cursor.fetchone() or {}
        has_business_metrics_history = bool(
            bm_exists_row.get("exists_flag") if isinstance(bm_exists_row, dict) else bm_exists_row[0]
        )
        if has_business_metrics_history:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'businessmetricshistory'
                """
            )
            bm_cols = {
                (r.get("column_name") if isinstance(r, dict) else r[0])
                for r in (cursor.fetchall() or [])
            }
            if "metric_date" in bm_cols:
                select_cols = [
                    "id",
                    "metric_date",
                    "rating",
                    "reviews_count",
                    "photos_count",
                    "news_count",
                    "source",
                    "created_at",
                ]
                if "unanswered_reviews_count" in bm_cols:
                    select_cols.insert(6, "unanswered_reviews_count")

                cursor.execute(
                    f"""
                    SELECT {", ".join(select_cols)}
                    FROM businessmetricshistory
                    WHERE business_id = %s
                    ORDER BY metric_date DESC, created_at DESC
                    LIMIT 365
                    """,
                    (business_id,),
                )
                for row in cursor.fetchall():
                    rd = _as_dict(row) or {}
                    date_raw = str(rd.get("metric_date") or "").strip()
                    if not date_raw:
                        continue
                    date_key = date_raw[:10]
                    current = history_by_date.get(date_key) or {
                        "id": rd.get("id"),
                        "date": date_key,
                        "rating": None,
                        "reviews_count": 0,
                        "photos_count": 0,
                        "news_count": 0,
                        "unanswered_reviews_count": 0,
                        "source": rd.get("source") or "manual",
                        "created_at": rd.get("created_at"),
                    }

                    if rd.get("rating") not in (None, "") and current.get("rating") in (None, ""):
                        current["rating"] = float(rd.get("rating"))
                    if rd.get("reviews_count") not in (None, ""):
                        current["reviews_count"] = max(int(current.get("reviews_count") or 0), int(rd.get("reviews_count") or 0))
                    if rd.get("photos_count") not in (None, ""):
                        current["photos_count"] = max(int(current.get("photos_count") or 0), int(rd.get("photos_count") or 0))
                    if rd.get("news_count") not in (None, ""):
                        current["news_count"] = max(int(current.get("news_count") or 0), int(rd.get("news_count") or 0))
                    if "unanswered_reviews_count" in bm_cols and rd.get("unanswered_reviews_count") not in (None, ""):
                        current["unanswered_reviews_count"] = max(
                            int(current.get("unanswered_reviews_count") or 0),
                            int(rd.get("unanswered_reviews_count") or 0),
                        )
                    if not current.get("source"):
                        current["source"] = rd.get("source") or "manual"
                    history_by_date[date_key] = current

        # 2.2) Fallback: MapParseResults (если есть, а в истории мало данных)
        cursor.execute("SELECT to_regclass('public.mapparseresults') IS NOT NULL AS exists_flag")
        mpr_exists_row = cursor.fetchone() or {}
        has_map_parse_results = bool(
            mpr_exists_row.get("exists_flag") if isinstance(mpr_exists_row, dict) else mpr_exists_row[0]
        )
        if has_map_parse_results and len(history_by_date) < 3:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'mapparseresults'
                """
            )
            mpr_cols = {
                (r.get("column_name") if isinstance(r, dict) else r[0])
                for r in (cursor.fetchall() or [])
            }
            select_cols = ["id", "created_at", "rating", "reviews_count"]
            if "photos_count" in mpr_cols:
                select_cols.append("photos_count")
            if "news_count" in mpr_cols:
                select_cols.append("news_count")
            if "unanswered_reviews_count" in mpr_cols:
                select_cols.append("unanswered_reviews_count")
            cursor.execute(
                f"""
                SELECT {", ".join(select_cols)}
                FROM mapparseresults
                WHERE business_id = %s
                ORDER BY created_at DESC
                LIMIT 180
                """,
                (business_id,),
            )
            for row in cursor.fetchall():
                rd = _as_dict(row) or {}
                created_at = rd.get("created_at")
                if not created_at:
                    continue
                date_key = created_at.date().isoformat() if hasattr(created_at, "date") else str(created_at)[:10]
                current = history_by_date.get(date_key) or {
                    "id": rd.get("id"),
                    "date": date_key,
                    "rating": None,
                    "reviews_count": 0,
                    "photos_count": 0,
                    "news_count": 0,
                    "unanswered_reviews_count": 0,
                    "source": "parsing",
                    "created_at": created_at,
                }
                if rd.get("rating") not in (None, "") and current.get("rating") in (None, ""):
                    current["rating"] = float(rd.get("rating"))
                if rd.get("reviews_count") not in (None, ""):
                    current["reviews_count"] = max(int(current.get("reviews_count") or 0), int(rd.get("reviews_count") or 0))
                if "photos_count" in mpr_cols and rd.get("photos_count") not in (None, ""):
                    current["photos_count"] = max(int(current.get("photos_count") or 0), int(rd.get("photos_count") or 0))
                if "news_count" in mpr_cols and rd.get("news_count") not in (None, ""):
                    current["news_count"] = max(int(current.get("news_count") or 0), int(rd.get("news_count") or 0))
                if "unanswered_reviews_count" in mpr_cols and rd.get("unanswered_reviews_count") not in (None, ""):
                    current["unanswered_reviews_count"] = max(
                        int(current.get("unanswered_reviews_count") or 0),
                        int(rd.get("unanswered_reviews_count") or 0),
                    )
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

        # 4) Последний fallback: текущие поля из businesses
        if not history:
            cursor.execute(
                """
                SELECT id, rating, reviews_count, updated_at, created_at
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (business_id,),
            )
            b_row = _as_dict(cursor.fetchone()) or {}
            if b_row:
                dt = b_row.get("updated_at") or b_row.get("created_at") or datetime.utcnow()
                date_key = dt.date().isoformat() if hasattr(dt, "date") else str(dt)[:10]
                history.append(
                    {
                        "id": b_row.get("id"),
                        "date": date_key,
                        "rating": float(b_row.get("rating")) if b_row.get("rating") not in (None, "") else None,
                        "reviews_count": int(b_row.get("reviews_count") or 0),
                        "photos_count": 0,
                        "news_count": 0,
                        "unanswered_reviews_count": unanswered_now,
                        "source": "businesses",
                        "created_at": dt,
                    }
                )

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
