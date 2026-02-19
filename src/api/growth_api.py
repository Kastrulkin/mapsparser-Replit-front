from flask import Blueprint, jsonify, request
from database_manager import DatabaseManager
from auth_system import verify_session
from core.growth_schema import ensure_growth_schema
from progress_calculator import _get_map_metrics

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
        ensure_growth_schema(db)
        
        # Проверка доступа
        cursor.execute("SELECT owner_id, business_type FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        # RealDictCursor возвращает dict; tuple — для sqlite
        owner_id = business.get('owner_id') if isinstance(business, dict) else business[0]
        business_type_key = business.get('business_type') if isinstance(business, dict) else business[1]
        
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
            
        # Находим ID типа бизнеса
        cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = %s OR id = %s", (business_type_key, business_type_key))
        bt_row = cursor.fetchone()
        
        if not bt_row:
            cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = 'other'")
            bt_row = cursor.fetchone()
             
        business_type_id = (bt_row.get('id') if isinstance(bt_row, dict) else bt_row[0]) if bt_row else None
        
        if not business_type_id:
            db.close()
            return jsonify({"success": True, "stages": []})
            
        # Получаем текущий шаг визарда
        cursor.execute("SELECT step FROM BusinessOptimizationWizard WHERE business_id = %s", (business_id,))
        wiz_row = cursor.fetchone()
        current_step = (wiz_row.get('step') if isinstance(wiz_row, dict) else wiz_row[0]) if wiz_row else 1
        
        # --- Фетчим метрики: external → cards → MapParseResults ---
        map_metrics = _get_map_metrics(cursor, business_id)
        metrics = {
            "rating": map_metrics["rating"],
            "reviews_count": map_metrics["reviews_count"],
            "photos_count": map_metrics["photos_count"],
            "services_count": 0,
            "has_phone": False,
            "has_address": False,
            "has_website": False,
            "yandex_url": None
        }

        # 2. UserServices (Services Added)
        cursor.execute("SELECT COUNT(*) AS cnt FROM UserServices WHERE business_id = %s", (business_id,))
        svc_row = cursor.fetchone()
        metrics["services_count"] = (svc_row.get('cnt') if isinstance(svc_row, dict) else svc_row[0]) if svc_row else 0

        # 3. Business Profile (Contacts)
        cursor.execute("SELECT phone, address, website, yandex_url FROM Businesses WHERE id = %s", (business_id,))
        biz_info = cursor.fetchone()
        if biz_info:
            ph = biz_info.get('phone') if isinstance(biz_info, dict) else biz_info[0]
            ad = biz_info.get('address') if isinstance(biz_info, dict) else biz_info[1]
            web = biz_info.get('website') if isinstance(biz_info, dict) else biz_info[2]
            yurl = biz_info.get('yandex_url') if isinstance(biz_info, dict) else biz_info[3]
            metrics["has_phone"] = bool(ph)
            metrics["has_address"] = bool(ad)
            metrics["has_website"] = bool(web)
            metrics["yandex_url"] = yurl

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
            FROM GrowthStages
            WHERE business_type_id = %s
            ORDER BY stage_number
        """, (business_type_id,))
        stages_rows = cursor.fetchall()
        
        def _v(row, key_or_idx):
            if row is None:
                return None
            if isinstance(row, dict):
                if isinstance(key_or_idx, str):
                    return row.get(key_or_idx)
                vals = list(row.values())
                return vals[key_or_idx] if isinstance(key_or_idx, int) and 0 <= key_or_idx < len(vals) else None
            return row[key_or_idx] if isinstance(key_or_idx, int) and 0 <= key_or_idx < len(row) else None

        stages = []
        for stage_row in stages_rows:
            stage_id = _v(stage_row, 'id') or _v(stage_row, 0)
            stage_number = _v(stage_row, 'stage_number') or _v(stage_row, 1)

            # Получаем задачи для этапа
            cursor.execute("""
                SELECT id, task_number, task_text, check_logic, reward_value, reward_type, tooltip, link_url, link_text, is_auto_verifiable
                FROM GrowthTasks
                WHERE stage_id = %s
                ORDER BY task_number
            """, (stage_id,))
            tasks_rows = cursor.fetchall()

            tasks = []
            completed_tasks_count = 0

            for tr in tasks_rows:
                check_logic = _v(tr, 'check_logic') or _v(tr, 3)
                is_completed = check_task_status(check_logic, metrics)

                if is_completed:
                    completed_tasks_count += 1

                tasks.append({
                    'id': _v(tr, 'id') or _v(tr, 0),
                    'task_number': _v(tr, 'task_number') or _v(tr, 1),
                    'text': _v(tr, 'task_text') or _v(tr, 2),
                    'check_logic': check_logic,
                    'reward_value': _v(tr, 'reward_value') or _v(tr, 4),
                    'reward_type': _v(tr, 'reward_type') or _v(tr, 5),
                    'tooltip': _v(tr, 'tooltip') or _v(tr, 6),
                    'link_url': _v(tr, 'link_url') or _v(tr, 7),
                    'link_text': _v(tr, 'link_text') or _v(tr, 8),
                    'is_auto_verifiable': bool(_v(tr, 'is_auto_verifiable') if _v(tr, 'is_auto_verifiable') is not None else _v(tr, 9)),
                    'is_completed': is_completed
                })

            # Определяем статус этапа
            if stage_number < current_step:
                status = 'completed'
                progress_percentage = 100
            elif stage_number == current_step:
                status = 'active'
                progress_percentage = int((completed_tasks_count / len(tasks)) * 100) if tasks else 0
            else:
                status = 'locked'
                progress_percentage = 0

            stages.append({
                'id': stage_id,
                'stage_number': stage_number,
                'title': _v(stage_row, 'title') or _v(stage_row, 2),
                'stage_description': _v(stage_row, 'description') or _v(stage_row, 3),
                'status': status,
                'progress_percentage': progress_percentage,
                'duration': _v(stage_row, 'duration') or _v(stage_row, 6),
                'goal': _v(stage_row, 'goal') or _v(stage_row, 4),
                'expected_result': _v(stage_row, 'expected_result') or _v(stage_row, 5),
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
