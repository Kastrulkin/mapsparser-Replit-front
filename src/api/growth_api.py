from flask import Blueprint, jsonify, request
from database_manager import DatabaseManager
from auth_system import verify_session

growth_bp = Blueprint('growth_api', __name__)

@growth_bp.route('/api/business/<string:business_id>/stages', methods=['GET'])
def get_business_stages(business_id):
    """Получить этапы роста для конкретного бизнеса (для ProgressTracker)"""
    try:
        # Проверка авторизации
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
            
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверка доступа
        cursor.execute("SELECT owner_id, business_type FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
            
        owner_id = business[0]
        business_type_key = business[1]
        
        if hasattr(owner_id, 'keys'): # sqlite3.Row support assumption check
             # If logic assumes tuple
             pass 

        # Handle row factory if needed, but fetchone returns tuple by default in this project setup usually
        # unless configured otherwise. Let's assume tuple access as per existing code patterns.
        
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
            
        # Находим ID типа бизнеса
        cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = ? OR id = ?", (business_type_key, business_type_key))
        bt_row = cursor.fetchone()
        
        if not bt_row:
            cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = 'other'")
            bt_row = cursor.fetchone()
             
        business_type_id = bt_row[0] if bt_row else None
        
        if not business_type_id:
            db.close()
            return jsonify({"success": True, "stages": []})
            
        # Получаем текущий шаг визарда
        cursor.execute("SELECT step FROM BusinessOptimizationWizard WHERE business_id = ?", (business_id,))
        wiz_row = cursor.fetchone()
        current_step = wiz_row[0] if wiz_row else 1
        
        # Получаем этапы
        cursor.execute("""
            SELECT id, stage_number, title, description, goal, expected_result, duration
            FROM GrowthStages
            WHERE business_type_id = ?
            ORDER BY stage_number
        """, (business_type_id,))
        stages_rows = cursor.fetchall()
        
        stages = []
        for stage_row in stages_rows:
            stage_number = stage_row[1]
            
            # Определяем статус
            # Логика: если текущий шаг визарда > номера этапа, то этап пройден
            # Если равен - активен
            # Иначе - ожидается
            if stage_number < current_step:
                status = 'completed'
            elif stage_number == current_step:
                status = 'active'
            else:
                status = 'locked' 
            
            stages.append({
                'id': stage_row[0],
                'stage_number': stage_number,
                'stage_name': stage_row[2],
                'stage_description': stage_row[3],
                'status': status,
                'progress_percentage': 100 if status == 'completed' else (0 if status == 'locked' else 50),
                'duration': stage_row[6],
                'goal': stage_row[4],
                'expected_result': stage_row[5]
            })
            
        db.close()
        
        return jsonify({
            "success": True,
            "stages": stages
        })
        
    except Exception as e:
        print(f"❌ Ошибка /api/business/{business_id}/stages: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
