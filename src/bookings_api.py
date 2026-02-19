"""
API endpoints для управления бронированиями
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from auth_system import verify_session
import uuid
from datetime import datetime

bookings_bp = Blueprint('bookings', __name__)

def require_auth():
    """Проверка авторизации"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_data = verify_session(token)
    if not user_data:
        return None
    return user_data

@bookings_bp.route('/api/bookings', methods=['GET'])
def get_bookings():
    """Получить список бронирований для бизнеса"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        business_id = request.args.get('business_id')
        status = request.args.get('status', 'all')
        
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        # Проверяем доступ к бизнесу
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Получаем бронирования
        query = """
            SELECT id, client_name, client_phone, client_email, service_name, 
                   booking_time, booking_time_local, source, status, notes, created_at
            FROM Bookings
            WHERE business_id = %s
        """
        params = [business_id]
        
        if status != 'all':
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY booking_time DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        bookings = []
        for row in rows:
            bookings.append({
                'id': row[0],
                'client_name': row[1],
                'client_phone': row[2],
                'client_email': row[3],
                'service_name': row[4],
                'booking_time': row[5],
                'booking_time_local': row[6],
                'source': row[7],
                'status': row[8],
                'notes': row[9],
                'created_at': row[10]
            })
        
        db.close()
        return jsonify({"bookings": bookings}), 200
        
    except Exception as e:
        print(f"❌ Ошибка получения бронирований: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@bookings_bp.route('/api/bookings/<booking_id>', methods=['PATCH'])
def update_booking(booking_id):
    """Обновить статус бронирования"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({"error": "status обязателен"}), 400
        
        # Проверяем доступ к бронированию
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT business_id FROM Bookings WHERE id = %s", (booking_id,))
        booking = cursor.fetchone()
        
        if not booking:
            db.close()
            return jsonify({"error": "Бронирование не найдено"}), 404
        
        business_id = booking[0]
        
        # Проверяем доступ к бизнесу
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бронированию"}), 403
        
        # Обновляем статус
        cursor.execute("""
            UPDATE Bookings 
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_status, booking_id))
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "message": "Статус бронирования обновлён"
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка обновления бронирования: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

