from flask import Blueprint, jsonify, request
from database_manager import DatabaseManager
from core.auth_helpers import require_auth_from_request, verify_business_access
import uuid

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
        
        # --- SYNC LEGACY PARSES START ---
                # Проверяем старые парсинги и добавляем их в историю, если их нет
        try:
            # Используем MAX(), чтобы выбрать непустые значения. 
            # SQLite MAX игнорирует NULL, но может выбрать пустую строку, если она считается "больше" NULL.
            # Поэтому явно фильтруем пустые строки
            cursor.execute("""
                SELECT MAX(rating), MAX(reviews_count), MAX(photos_count), MAX(news_count), DATE(created_at) as parse_date
                FROM MapParseResults 
                WHERE business_id = ? 
                GROUP BY parse_date 
            """, (business_id,))
            
            parses = cursor.fetchall()
            for parse in parses:
                parse_date = parse[4]
                if not parse_date: continue
                
                # Проверяем, есть ли запись в истории за эту дату
                cursor.execute("""
                    SELECT id, rating FROM BusinessMetricsHistory 
                    WHERE business_id = ? AND metric_date = ? AND source = 'parsing'
                """, (business_id, parse_date))
                
                existing = cursor.fetchone()
                
                if not existing:
                    # Создаем запись
                    metric_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO BusinessMetricsHistory (
                            id, business_id, metric_date, rating, reviews_count, 
                            photos_count, news_count, source
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'parsing')
                    """, (
                        metric_id, business_id, parse_date,
                        parse[0], parse[1], parse[2], parse[3]
                    ))
                # Обновляем, если в базе пусто (None или ''), а у нас есть данные
                elif (existing[1] is None or existing[1] == '') and parse[0]:
                     cursor.execute("""
                        UPDATE BusinessMetricsHistory
                        SET rating = ?, reviews_count = ?, photos_count = ?, news_count = ?
                        WHERE id = ?
                    """, (parse[0], parse[1], parse[2], parse[3], existing[0]))
                    
            db.conn.commit()
        except Exception as e:
            db.conn.commit()
        except Exception as e:
            print(f"⚠️ Ошибка синхронизации истории метрик из MapParseResults: {e}")

        # --- SYNC EXTERNAL STATS START ---
        try:
            # Синхронизируем исторические данные из ExternalBusinessStats (если они есть)
            # Синхронизируем исторические данные из ExternalBusinessStats (если они есть)
            cursor.execute("""
                SELECT source, date, rating, reviews_total, unanswered_reviews_count
                FROM ExternalBusinessStats 
                WHERE business_id = ? AND (rating IS NOT NULL OR reviews_total IS NOT NULL)
            """, (business_id,))
            
            stats_rows = cursor.fetchall()
            for row in stats_rows:
                source = row[0]
                metric_date = row[1]
                rating = row[2]
                reviews_count = row[3]
                unanswered = row[4]
                
                # Проверяем, есть ли запись
                cursor.execute("""
                    SELECT id FROM BusinessMetricsHistory 
                    WHERE business_id = ? AND metric_date = ? AND source = ?
                """, (business_id, metric_date, source))
                
                existing = cursor.fetchone()
                
                if not existing:
                    metric_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO BusinessMetricsHistory (
                            id, business_id, metric_date, rating, reviews_count, 
                            photos_count, news_count, unanswered_reviews_count, source
                        )
                        VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?)
                    """, (metric_id, business_id, metric_date, rating, reviews_count, unanswered, source))
                else:
                    # Обновляем
                    cursor.execute("""
                        UPDATE BusinessMetricsHistory
                        SET rating = COALESCE(?, rating), 
                            reviews_count = COALESCE(?, reviews_count),
                            unanswered_reviews_count = COALESCE(?, unanswered_reviews_count)
                        WHERE id = ?
                    """, (rating, reviews_count, unanswered, existing[0]))
            
            db.conn.commit()
        except Exception as e:
            print(f"⚠️ Ошибка синхронизации истории метрик из ExternalBusinessStats: {e}")
        # --- SYNC EXTERNAL STATS END ---

        # Загружаем историю метрик
        cursor.execute("""
            SELECT id, metric_date, rating, reviews_count, 
                   photos_count, news_count, unanswered_reviews_count, source, created_at
            FROM BusinessMetricsHistory
            WHERE business_id = ?
            ORDER BY metric_date DESC
            LIMIT 100
        """, (business_id,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "id": row[0],
                "date": row[1],
                "rating": float(row[2]) if row[2] is not None and row[2] != '' else None,
                "reviews_count": row[3],
                "photos_count": row[4],
                "news_count": row[5],
                "unanswered_reviews_count": row[6],
                "source": row[7],
                "created_at": row[8]
            })
        
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
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        
        if not business or (business[0] != user_data['user_id'] and not user_data.get('is_superadmin')):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
        
        # Проверяем, есть ли уже запись за эту дату
        cursor.execute("""
            SELECT id FROM BusinessMetricsHistory
            WHERE business_id = ? AND metric_date = ? AND source = 'manual'
        """, (business_id, metric_date))
        
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующую
            cursor.execute("""
                UPDATE BusinessMetricsHistory
                SET rating = ?, reviews_count = ?, photos_count = ?, news_count = ?
                WHERE id = ?
            """, (rating, reviews_count, photos_count, news_count, existing[0]))
            message = "Метрика обновлена"
        else:
            # Создаем новую
            metric_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO BusinessMetricsHistory (
                    id, business_id, metric_date, rating, reviews_count,
                    photos_count, news_count, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'manual')
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
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        
        if not business or (business[0] != user_data['user_id'] and not user_data.get('is_superadmin')):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
        
        # Удаляем только ручные записи
        cursor.execute("""
            DELETE FROM BusinessMetricsHistory
            WHERE id = ? AND business_id = ? AND source = 'manual'
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
