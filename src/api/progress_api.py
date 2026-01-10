from flask import Blueprint, jsonify, request
from database_manager import DatabaseManager
from auth_system import verify_session
from progress_calculator import calculate_business_progress

progress_bp = Blueprint('progress_api', __name__)

def require_auth():
    """Проверка авторизации"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    return verify_session(token)

@progress_bp.route('/api/business/<business_id>/progress', methods=['GET'])
def get_business_progress(business_id):
    """Получить прогресс выполнения этапов роста для бизнеса"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ к бизнесу
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        # Проверяем права доступа
        if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        db.close()
        
        # Рассчитываем прогресс
        progress_data = calculate_business_progress(business_id)
        
        return jsonify({
            "success": True,
            "progress": progress_data
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения прогресса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
