from flask import Blueprint, jsonify, request
from database_manager import DatabaseManager
from core.auth_helpers import require_auth_from_request, verify_business_access
from progress_calculator import calculate_business_progress
import uuid
import json
from datetime import datetime

stage_progress_bp = Blueprint('stage_progress_api', __name__)


@stage_progress_bp.route('/api/business/<business_id>/stage-progress', methods=['GET'])
def get_stage_progress(business_id):
    """Получить прогресс пользователя по всем этапам"""
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
            
        # --- AUTO-CALCULATION START ---
        # Рассчитываем прогресс на основе реальных данных
        try:
            calc_results = calculate_business_progress(business_id)
            
            # Маппинг технических проверок на номера задач (1-based)
            # Stage ID -> { Task Number -> [Check Keys] }
            mapping = {
                1: { # Фундамент
                    1: ['profile_completed', 'yandex_maps_profile'], # Заполнить профиль
                    2: ['google_maps_profile'],                    # Создать карточки Google
                    3: ['photos_uploaded'],                        # Загрузить фото
                    4: ['reviews_collected'],                      # Собрать отзывы
                    5: ['social_links']                            # Соцсети
                },
                2: { # Оптимизация
                    1: ['pricelist_added'],                        # Прайс-лист
                    2: ['booking_widget'],                         # Виджет
                    3: ['auto_reviews']                            # Автосбор отзывов
                },
                3: { # Автоматизация
                    1: ['crm_implemented'],                        # CRM
                    2: ['database_filled']                         # База
                },
                4: { # Боты
                    1: ['bots_connected'],                         # Боты
                    3: ['crm_integration']                         # Интеграция
                }
            }
            
            now = datetime.now().isoformat()
            
            # Получаем ID этапов для этого типа бизнеса
            cursor.execute("SELECT business_type FROM Businesses WHERE id = ?", (business_id,))
            b_type_key = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = ?", (b_type_key,))
            b_type_id_row = cursor.fetchone()
            
            if b_type_id_row:
                b_type_id = b_type_id_row[0]
                # Получаем stages: id, stage_number, tasks_count
                cursor.execute("SELECT id, stage_number, tasks FROM GrowthStages WHERE business_type_id = ?", (b_type_id,))
                db_stages = cursor.fetchall()
                
                for stage_row in db_stages:
                    stage_id = stage_row[0]
                    stage_num = stage_row[1]
                    tasks_json = stage_row[2]
                    total_tasks_count = 0
                    if tasks_json:
                        try:
                            total_tasks_count = len(json.loads(tasks_json))
                        except:
                            pass
                    
                    # Проверяем, есть ли расчеты для этого этапа
                    calc_stage = calc_results.get(f'stage_{stage_num}')
                    if calc_stage and stage_num in mapping:
                        # Получаем текущий прогресс из БД
                        cursor.execute("""
                            SELECT id, completed_tasks, is_unlocked FROM UserStageProgress 
                            WHERE business_id = ? AND user_id = ? AND stage_id = ?
                        """, (business_id, user_data['user_id'], stage_id))
                        prog_row = cursor.fetchone()
                        
                        existing_tasks = []
                        is_unlocked = False
                        if prog_row:
                            if prog_row[1]:
                                try:
                                    existing_tasks = json.loads(prog_row[1])
                                except:
                                    pass
                            is_unlocked = bool(prog_row[2])
                        
                        # Вычисляем новые выполненные задачи
                        new_tasks = set(existing_tasks)
                        details = calc_stage['details']
                        
                        task_map = mapping[stage_num]
                        for task_num, check_keys in task_map.items():
                            # Если любой из ключей проверки True -> задача выполнена?
                            # Или ВСЕ? Обычно "или" для профиля, "и" для сложносоставных.
                            # Здесь считаем: если ключ completed=True, то OK.
                            # Если task 1 зависит от profile OR yandex -> any()
                            # Но логика Task 1: "Заполнить на Яндекс..." -> yandex check.
                            # Давайте используем ANY для Task 1, и конкретные для остальных.
                            is_done = False
                            for key in check_keys:
                                if details.get(key, {}).get('completed'):
                                    is_done = True
                                    break
                            
                            if is_done:
                                new_tasks.add(task_num)
                        
                        # Если изменилось - обновляем
                        if len(new_tasks) != len(existing_tasks):
                            final_tasks_list = list(new_tasks)
                            final_percentage = round((len(final_tasks_list) / total_tasks_count) * 100) if total_tasks_count > 0 else 0
                            completed_at = now if final_percentage >= 100 else None
                            
                            # Если прогресс > 0, разблокируем этап автоматически
                            should_unlock = is_unlocked or (final_percentage > 0)
                            # Также можно разблокировать следующий этап, если этот 100%
                            
                            if prog_row:
                                cursor.execute("""
                                    UPDATE UserStageProgress
                                    SET completed_tasks = ?, progress_percentage = ?, completed_at = ?, is_unlocked = ?
                                    WHERE id = ?
                                """, (json.dumps(final_tasks_list), final_percentage, completed_at, 1 if should_unlock else 0, prog_row[0]))
                            else:
                                prog_id = str(uuid.uuid4())
                                cursor.execute("""
                                    INSERT INTO UserStageProgress (
                                        id, user_id, business_id, stage_id, is_unlocked, 
                                        completed_tasks, progress_percentage, unlocked_at, completed_at
                                    )
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (prog_id, user_data['user_id'], business_id, stage_id, 
                                      1 if should_unlock else 0, json.dumps(final_tasks_list), 
                                      final_percentage, now if should_unlock else None, completed_at))
            
            db.conn.commit()
            
        except Exception as e:
            print(f"⚠️ Ошибка авто-расчета прогресса: {e}")
            # Не падаем, отдаем старые данные
        # --- AUTO-CALCULATION END ---

        # Получаем тип бизнеса для загрузки этапов
        cursor.execute("SELECT business_type FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()

        cursor.execute("""
            SELECT id FROM BusinessTypes WHERE type_key = ?
        """, (business[0],))  # FIX: business[0] вместо business[1]
        business_type_row = cursor.fetchone()
        
        if not business_type_row:
            db.close()
            return jsonify({"error": "Тип бизнеса не найден"}), 404
        
        business_type_id = business_type_row[0]
        
        # Загружаем все этапы для типа бизнеса
        cursor.execute("""
            SELECT id, stage_number, title, description, goal, 
                   expected_result, duration, tasks
            FROM GrowthStages
            WHERE business_type_id = ?
            ORDER BY stage_number ASC
        """, (business_type_id,))
        
        stages = []
        for row in cursor.fetchall():
            stage_id = row[0]
            
            # Загружаем прогресс пользователя для этого этапа
            cursor.execute("""
                SELECT is_unlocked, progress_percentage, completed_tasks, 
                       unlocked_at, completed_at
                FROM UserStageProgress
                WHERE business_id = ? AND user_id = ? AND stage_id = ?
            """, (business_id, user_data['user_id'], stage_id))
            
            progress_row = cursor.fetchone()
            
            # Парсим задачи
            tasks = []
            if row[7]:
                try:
                    tasks_raw = json.loads(row[7])
                    tasks = [{"number": idx + 1, "text": t} for idx, t in enumerate(tasks_raw)]
                except:
                    pass
            
            # Парсим завершенные задачи
            completed_tasks = []
            if progress_row and progress_row[2]:
                try:
                    completed_tasks = json.loads(progress_row[2])
                except:
                    pass
            
            stage_data = {
                "id": stage_id,
                "stage_number": row[1],
                "title": row[2],
                "description": row[3],
                "goal": row[4],
                "expected_result": row[5],
                "duration": row[6],
                "tasks": tasks,
                "is_unlocked": bool(progress_row[0]) if progress_row else False,
                "progress_percentage": progress_row[1] if progress_row else 0,
                "completed_tasks": completed_tasks,
                "unlocked_at": progress_row[3] if progress_row else None,
                "completed_at": progress_row[4] if progress_row else None
            }
            stages.append(stage_data)
        
        db.close()
        
        return jsonify({"success": True, "stages": stages})
        
    except Exception as e:
        print(f"❌ Ошибка получения прогресса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@stage_progress_bp.route('/api/business/<business_id>/stage-progress/<stage_id>/unlock', methods=['POST'])
def unlock_stage(business_id, stage_id):
    """Разблокировать этап досрочно"""
    try:
        user_data = require_auth_from_request()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            db.close()
            return jsonify({"error": "Нет доступа" if owner_id else "Бизнес не найден"}), 403 if owner_id else 404
        
        # Проверяем, есть ли уже запись прогресса
        cursor.execute("""
            SELECT id, is_unlocked FROM UserStageProgress
            WHERE business_id = ? AND user_id = ? AND stage_id = ?
        """, (business_id, user_data['user_id'], stage_id))
        
        existing = cursor.fetchone()
        
        if existing and existing[1]:
            db.close()
            return jsonify({"success": True, "message": "Этап уже разблокирован"})
        
        now = datetime.now().isoformat()
        
        if existing:
            # Обновляем существующую запись
            cursor.execute("""
                UPDATE UserStageProgress
                SET is_unlocked = 1, unlocked_at = ?
                WHERE id = ?
            """, (now, existing[0]))
        else:
            # Создаем новую запись
            progress_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO UserStageProgress (
                    id, user_id, business_id, stage_id, is_unlocked, unlocked_at
                )
                VALUES (?, ?, ?, ?, 1, ?)
            """, (progress_id, user_data['user_id'], business_id, stage_id, now))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "message": "Этап разблокирован"})
        
    except Exception as e:
        print(f"❌ Ошибка разблокировки этапа: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@stage_progress_bp.route('/api/business/<business_id>/stage-progress/<stage_id>/complete-task', methods=['POST'])
def complete_task(business_id, stage_id):
    """Отметить задачу как выполненную"""
    try:
        user_data = require_auth_from_request()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        data = request.json
        task_number = data.get('task_number')
        
        if task_number is None:
            return jsonify({"error": "Не указан номер задачи"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ
        has_access, owner_id = verify_business_access(cursor, business_id, user_data)
        if not has_access:
            db.close()
            return jsonify({"error": "Нет доступа" if owner_id else "Бизнес не найден"}), 403 if owner_id else 404
        
        # Получаем текущий прогресс
        cursor.execute("""
            SELECT id, completed_tasks FROM UserStageProgress
            WHERE business_id = ? AND user_id = ? AND stage_id = ?
        """, (business_id, user_data['user_id'], stage_id))
        
        progress_row = cursor.fetchone()
        
        # Парсим завершенные задачи
        completed_tasks = []
        if progress_row and progress_row[1]:
            try:
                completed_tasks = json.loads(progress_row[1])
            except:
                pass
        
        # Добавляем/удаляем задачу (toggle)
        if task_number in completed_tasks:
            completed_tasks.remove(task_number)
        else:
            completed_tasks.append(task_number)
        
        # Получаем общее количество задач
        cursor.execute("SELECT tasks FROM GrowthStages WHERE id = ?", (stage_id,))
        tasks_row = cursor.fetchone()
        total_tasks = 0
        if tasks_row and tasks_row[0]:
            try:
                total_tasks = len(json.loads(tasks_row[0]))
            except:
                pass
        
        # Рассчитываем процент выполнения
        progress_percentage = round((len(completed_tasks) / total_tasks) * 100) if total_tasks > 0 else 0
        
        completed_tasks_json = json.dumps(completed_tasks)
        now = datetime.now().isoformat()
        completed_at = now if progress_percentage >= 100 else None
        
        if progress_row:
            # Обновляем
            cursor.execute("""
                UPDATE UserStageProgress
                SET completed_tasks = ?, progress_percentage = ?, completed_at = ?
                WHERE id = ?
            """, (completed_tasks_json, progress_percentage, completed_at, progress_row[0]))
        else:
            # Создаем новую запись
            progress_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO UserStageProgress (
                    id, user_id, business_id, stage_id, is_unlocked, 
                    completed_tasks, progress_percentage, unlocked_at, completed_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
            """, (progress_id, user_data['user_id'], business_id, stage_id, 
                  completed_tasks_json, progress_percentage, now, completed_at))
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "progress_percentage": progress_percentage,
            "completed_tasks": completed_tasks
        })
        
    except Exception as e:
        print(f"❌ Ошибка обновления задачи: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
