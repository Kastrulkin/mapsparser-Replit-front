#!/usr/bin/env python3
"""
API endpoints для модерации бизнесов (только для суперадмина)
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from auth_system import verify_session

admin_moderation_bp = Blueprint('admin_moderation', __name__)

def require_superadmin():
    """Проверка прав суперадмина"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return None
    
    # Проверяем, является ли пользователь суперадмином
    db = DatabaseManager()
    is_superadmin = db.is_superadmin(user_data['user_id'])
    db.close()
    
    if not is_superadmin:
        return None
    
    return user_data

@admin_moderation_bp.route('/api/admin/businesses/pending', methods=['GET'])
def get_pending_businesses():
    """Получить список бизнесов на модерации"""
    try:
        user_data = require_superadmin()
        if not user_data:
            return jsonify({"error": "Требуются права суперадмина"}), 403
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("""
            SELECT b.id, b.name, b.address, b.city, b.phone, b.email,
                   b.created_at, u.email as owner_email, u.name as owner_name
            FROM Businesses b
            JOIN Users u ON b.owner_id = u.id
            WHERE b.moderation_status = 'pending'
            ORDER BY b.created_at DESC
        """)
        
        businesses = cursor.fetchall()
        db.close()
        
        results = []
        for biz in businesses:
            results.append({
                'id': biz[0],
                'name': biz[1],
                'address': biz[2],
                'city': biz[3],
                'phone': biz[4],
                'email': biz[5],
                'created_at': biz[6],
                'owner_email': biz[7],
                'owner_name': biz[8]
            })
        
        return jsonify({
            'success': True,
            'businesses': results,
            'count': len(results)
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения списка на модерации: {e}")
        return jsonify({"error": str(e)}), 500

@admin_moderation_bp.route('/api/admin/businesses/<business_id>/moderate', methods=['POST'])
def moderate_business(business_id):
    """
    Модерация бизнеса (approve/reject)
    
    Body:
        - action: 'approve' или 'reject'
        - notes: заметки модератора (опционально)
    """
    try:
        user_data = require_superadmin()
        if not user_data:
            return jsonify({"error": "Требуются права суперадмина"}), 403
        
        data = request.get_json()
        action = data.get('action', '').strip().lower()
        notes = data.get('notes', '').strip()
        
        if action not in ['approve', 'reject']:
            return jsonify({"error": "action должен быть 'approve' или 'reject'"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, что бизнес существует
        cursor.execute("SELECT id FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        # Обновляем статус модерации
        moderation_status = 'approved' if action == 'approve' else 'rejected'
        
        cursor.execute("""
            UPDATE Businesses 
            SET moderation_status = %s,
                moderation_notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (moderation_status, notes if notes else None, business_id))
        
        # Если одобрен, активируем ChatGPT (если пользователь уже оплатил)
        if action == 'approve':
            cursor.execute("""
                UPDATE Businesses 
                SET chatgpt_enabled = 1
                WHERE id = %s AND subscription_status = 'active'
            """, (business_id,))
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': f'Бизнес {action}ed',
            'moderation_status': moderation_status
        })
        
    except Exception as e:
        print(f"❌ Ошибка модерации бизнеса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

