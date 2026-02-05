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
        cursor.execute("SELECT owner_id, business_type FROM businesses WHERE id = %s", (business_id,))
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
        cursor.execute("SELECT id FROM businesstypes WHERE type_key = %s OR id = %s", (business_type_key, business_type_key))
        bt_row = cursor.fetchone()
        
        if not bt_row:
            cursor.execute("SELECT id FROM businesstypes WHERE type_key = 'other'")
            bt_row = cursor.fetchone()
             
        business_type_id = bt_row.get('id') if isinstance(bt_row, dict) else (bt_row[0] if bt_row else None)
        
        if not business_type_id:
            db.close()
            return jsonify({"success": True, "stages": []})
            
        # Получаем текущий шаг визарда
        cursor.execute("SELECT step FROM businessoptimizationwizard WHERE business_id = %s", (business_id,))
        wiz_row = cursor.fetchone()
        current_step = wiz_row.get('step') if isinstance(wiz_row, dict) else (wiz_row[0] if wiz_row else 1)
        
        # --- Фетчим метрики для проверки условий ---
        metrics = {
            "rating": 0.0,
            "reviews_count": 0,
            "photos_count": 0,
            "services_count": 0,
            "has_phone": False,
            "has_address": False,
            "has_website": False,
            "yandex_url": None
        }
        
        # 1. MapParseResults (Rating, Reviews, Photos)
        cursor.execute("""
            SELECT rating, reviews_count, photos_count 
            FROM mapparseresults 
            WHERE business_id = %s 
            ORDER BY created_at DESC LIMIT 1
        """, (business_id,))
        map_row = cursor.fetchone()
        if map_row:
            try:
                if isinstance(map_row, dict):
                    metrics["rating"] = float(map_row.get('rating', 0) or 0)
                    metrics["reviews_count"] = int(map_row.get('reviews_count', 0) or 0)
                    metrics["photos_count"] = int(map_row.get('photos_count', 0) or 0)
                else:
                metrics["rating"] = float(map_row[0]) if map_row[0] else 0.0
                metrics["reviews_count"] = int(map_row[1]) if map_row[1] else 0
                metrics["photos_count"] = int(map_row[2]) if map_row[2] else 0
            except:
                pass

        # 2. UserServices (Services Added)
        cursor.execute("SELECT COUNT(*) FROM userservices WHERE business_id = %s", (business_id,))
        svc_row = cursor.fetchone()
        metrics["services_count"] = svc_row.get('count') if isinstance(svc_row, dict) else (svc_row[0] if svc_row else 0)
        
        # 3. Business Profile (Contacts)
        cursor.execute("SELECT phone, address, website, yandex_url FROM businesses WHERE id = %s", (business_id,))
        biz_info = cursor.fetchone()
        if biz_info:
            if isinstance(biz_info, dict):
                metrics["has_phone"] = bool(biz_info.get('phone'))
                metrics["has_address"] = bool(biz_info.get('address'))
                metrics["has_website"] = bool(biz_info.get('website'))
                metrics["yandex_url"] = biz_info.get('yandex_url')
            else:
            metrics["has_phone"] = bool(biz_info[0])
            metrics["has_address"] = bool(biz_info[1])
            metrics["has_website"] = bool(biz_info[2])
            metrics["yandex_url"] = biz_info[3]

        def check_task_status(logic_code, metrics):
            """Проверяет выполнение задачи на основе метрик"""
            if not logic_code:
                return False
                
            if logic_code == 'reviews_count_5':
                return metrics["reviews_count"] >= 5
            elif logic_code == 'reviews_count_15':
                return metrics["reviews_count"] >= 15
            elif logic_code == 'rating_4_5':
                return metrics["rating"] >= 4.5
            elif logic_code == 'photos_count_3':
                return metrics["photos_count"] >= 3
            elif logic_code == 'profile_contacts_full':
                return metrics["has_phone"] and metrics["has_address"]
            elif logic_code == 'services_added':
                return metrics["services_count"] > 0
            elif logic_code == 'profile_verified':
                # Простая эвристика: если есть ссылка на профиль, считаем что базово подтвержден
                return bool(metrics["yandex_url"])
            elif logic_code == 'reply_rate_100':
                 # Пока заглушка или можно проверить reviews without reply
                return False 
            
            return False

        # Получаем этапы
        cursor.execute("""
            SELECT id, stage_number, title, description, goal, expected_result, duration
            FROM growthstages
            WHERE business_type_id = %s
            ORDER BY stage_number
        """, (business_type_id,))
        stages_rows = cursor.fetchall()
        
        stages = []
        for stage_row in stages_rows:
            if isinstance(stage_row, dict):
                stage_id = stage_row.get('id')
                stage_number = stage_row.get('stage_number')
            else:
            stage_id = stage_row[0]
            stage_number = stage_row[1]
            
            # Получаем задачи для этапа
            cursor.execute("""
                SELECT id, task_number, task_text, check_logic, reward_value, reward_type, tooltip, link_url, link_text, is_auto_verifiable
                FROM growthtasks
                WHERE stage_id = %s
                ORDER BY task_number
            """, (stage_id,))
            tasks_rows = cursor.fetchall()
            
            tasks = []
            completed_tasks_count = 0
            
            for tr in tasks_rows:
                if isinstance(tr, dict):
                    check_logic = tr.get('check_logic')
                    tasks.append({
                        'id': tr.get('id'),
                        'task_number': tr.get('task_number'),
                        'text': tr.get('task_text'),
                        'check_logic': check_logic,
                        'reward_value': tr.get('reward_value'),
                        'reward_type': tr.get('reward_type'),
                        'tooltip': tr.get('tooltip'),
                        'link_url': tr.get('link_url'),
                        'link_text': tr.get('link_text'),
                        'is_auto_verifiable': bool(tr.get('is_auto_verifiable')),
                        'is_completed': check_task_status(check_logic, metrics)
                    })
                else:
                check_logic = tr[3]
                is_completed = check_task_status(check_logic, metrics)
                if is_completed:
                    completed_tasks_count += 1
                tasks.append({
                    'id': tr[0],
                    'task_number': tr[1],
                    'text': tr[2],
                    'check_logic': check_logic,
                    'reward_value': tr[4],
                    'reward_type': tr[5],
                    'tooltip': tr[6],
                    'link_url': tr[7],
                    'link_text': tr[8],
                    'is_auto_verifiable': bool(tr[9]),
                        'is_completed': is_completed
                })
                    if is_completed:
                        completed_tasks_count += 1

            # Определяем статус этапа (динамически, если задачи выполнены)
            # Или используем wizard step как hard constraint
            if stage_number < current_step:
                status = 'completed'
                progress_percentage = 100
            elif stage_number == current_step:
                status = 'active'
                # Считаем прогресс по задачам
                progress_percentage = 0
                if len(tasks) > 0:
                    completed = sum(1 for t in tasks if t.get('is_completed'))
                    progress_percentage = int((completed / len(tasks)) * 100)
            else:
                status = 'locked' 
                progress_percentage = 0

            if isinstance(stage_row, dict):
                stages.append({
                    'id': stage_row.get('id'),
                    'stage_number': stage_number,
                    'title': stage_row.get('title'),
                    'stage_description': stage_row.get('description'),
                    'status': status,
                    'progress_percentage': progress_percentage,
                    'duration': stage_row.get('duration'),
                    'goal': stage_row.get('goal'),
                    'expected_result': stage_row.get('expected_result'),
                    'tasks': tasks
                })
            else:
            stages.append({
                'id': stage_row[0],
                'stage_number': stage_number,
                'title': stage_row[2],
                'stage_description': stage_row[3],
                'status': status,
                'progress_percentage': progress_percentage,
                'duration': stage_row[6],
                'goal': stage_row[4],
                'expected_result': stage_row[5],
                'tasks': tasks
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
