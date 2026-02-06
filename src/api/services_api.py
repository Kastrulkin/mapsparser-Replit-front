"""
API для управления услугами бизнеса
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from auth_system import verify_session
from core.helpers import get_business_owner_id

services_bp = Blueprint('services', __name__)

@services_bp.route('/api/services/add', methods=['POST', 'OPTIONS'])
def add_service():
    """Добавить услугу"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Нет данных"}), 400
        
        business_id = data.get('business_id')
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Добавляем услугу
        import uuid
        service_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO UserServices (id, user_id, business_id, category, name, description, keywords, price, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            service_id,
            user_data["user_id"],
            business_id,
            data.get('category', ''),
            data.get('name', ''),
            data.get('description', ''),
            data.get('keywords', ''),
            data.get('price', 0)
        ))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "service_id": service_id})
    
    except Exception as e:
        print(f"❌ Ошибка добавления услуги: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@services_bp.route('/api/services/list', methods=['GET', 'OPTIONS'])
def get_services():
    """Получить список услуг"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        user_id = user_data['user_id']
        
        # Получаем business_id из query параметров
        business_id = request.args.get('business_id')
        
        # Проверяем, есть ли поля optimized_description и optimized_name
        cursor.execute("PRAGMA table_info(UserServices)")
        columns = [col[1] for col in cursor.fetchall()]
        has_optimized_desc = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns
        
        # Формируем SELECT с учетом наличия полей
        select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at', 'updated_at']
        if has_optimized_desc:
            select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
        if has_optimized_name:
            select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
        
        # Если передан business_id - фильтруем по нему, иначе по user_id
        if business_id:
            # Проверяем доступ к бизнесу
            owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
            if owner_id:
                if owner_id == user_id or user_data.get('is_superadmin'):
                    select_sql = f"SELECT {', '.join(select_fields)} FROM userservices WHERE business_id = %s ORDER BY created_at DESC"
                    cursor.execute(select_sql, (business_id,))
                else:
                    db.close()
                    return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
            else:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
        else:
            # Старая логика: получаем все услуги пользователя
            select_sql = f"SELECT {', '.join(select_fields)} FROM userservices WHERE user_id = %s ORDER BY created_at DESC"
            cursor.execute(select_sql, (user_id,))
        
        services_rows = cursor.fetchall()
        db.close()
        
        # Преобразуем Row в словари
        services = []
        for service in services_rows:
            # Преобразуем Row в словарь через dict() - это гарантирует правильное извлечение всех полей
            if hasattr(service, 'keys'):
                service_dict = dict(service)  # Преобразуем Row в dict
            else:
                # Fallback для tuple/list - создаем словарь по порядку полей
                service_dict = {field_name: service[idx] for idx, field_name in enumerate(select_fields) if idx < len(service)}
            
            # Парсим keywords
            raw_kw = service_dict.get('keywords')
            parsed_kw = []
            if raw_kw:
                try:
                    import json
                    parsed_kw = json.loads(raw_kw)
                    if not isinstance(parsed_kw, list):
                        parsed_kw = []
                except Exception:
                    parsed_kw = [k.strip() for k in str(raw_kw).split(',') if k.strip()]
            service_dict['keywords'] = parsed_kw
            
            services.append(service_dict)
        
        return jsonify({"success": True, "services": services})
    
    except Exception as e:
        print(f"❌ Ошибка получения услуг: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@services_bp.route('/api/services/update/<string:service_id>', methods=['PUT', 'OPTIONS'])
def update_service(service_id):
    """Обновить услугу"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Нет данных"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, что услуга принадлежит пользователю
        cursor.execute("SELECT user_id, business_id FROM userservices WHERE id = %s", (service_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Услуга не найдена"}), 404
        
        service_user_id = row[0]
        service_business_id = row[1]
        
        if service_user_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этой услуге"}), 403
        
        # Преобразуем keywords в строку JSON, если это массив
        import json
        keywords = data.get('keywords', [])
        if isinstance(keywords, list):
            keywords_str = json.dumps(keywords, ensure_ascii=False)
        elif isinstance(keywords, str):
            keywords_str = keywords
        else:
            keywords_str = json.dumps([])
        
        # Проверяем, есть ли поля optimized_description и optimized_name в таблице
        cursor.execute("PRAGMA table_info(UserServices)")
        columns = [col[1] for col in cursor.fetchall()]
        has_optimized_description = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns
        
        optimized_description = data.get('optimized_description', '')
        optimized_name = data.get('optimized_name', '')
        
        print(f"🔍 DEBUG services_api.update_service: has_optimized_description = {has_optimized_description}, has_optimized_name = {has_optimized_name}", flush=True)
        print(f"🔍 DEBUG services_api.update_service: optimized_name = '{optimized_name}' (length: {len(optimized_name) if optimized_name else 0})", flush=True)
        print(f"🔍 DEBUG services_api.update_service: optimized_description = '{optimized_description[:50] if optimized_description else ''}...' (length: {len(optimized_description) if optimized_description else 0})", flush=True)
        
        # Обновляем услугу с учетом наличия полей
        if has_optimized_description and has_optimized_name:
            print("🔍 DEBUG services_api.update_service: Обновление с optimized_description и optimized_name", flush=True)
            cursor.execute("""
                UPDATE userservices 
                SET category = %s, name = %s, optimized_name = %s, description = %s, optimized_description = %s, keywords = %s, price = %s
                WHERE id = %s
            """, (
                data.get('category', ''),
                data.get('name', ''),
                optimized_name,
                data.get('description', ''),
                optimized_description,
                keywords_str,
                data.get('price', 0),
                service_id
            ))
            print(f"✅ DEBUG services_api.update_service: UPDATE выполнен, rowcount = {cursor.rowcount}", flush=True)
            
            # Проверяем, что данные сохранились
            cursor.execute("SELECT optimized_name, optimized_description FROM userservices WHERE id = %s", (service_id,))
            check_row = cursor.fetchone()
            if check_row:
                print(f"✅ DEBUG services_api.update_service: Проверка после UPDATE - optimized_name = '{check_row[0]}', optimized_description = '{check_row[1][:50] if check_row[1] else ''}...'", flush=True)
            else:
                print("❌ DEBUG services_api.update_service: Услуга не найдена после UPDATE!", flush=True)
        elif has_optimized_description:
            cursor.execute("""
                UPDATE userservices 
                SET category = %s, name = %s, description = %s, optimized_description = %s, keywords = %s, price = %s
                WHERE id = %s
            """, (
                data.get('category', ''),
                data.get('name', ''),
                data.get('description', ''),
                optimized_description,
                keywords_str,
                data.get('price', 0),
                service_id
            ))
        elif has_optimized_name:
            cursor.execute("""
                UPDATE userservices 
                SET category = %s, name = %s, optimized_name = %s, description = %s, keywords = %s, price = %s
                WHERE id = %s
            """, (
                data.get('category', ''),
                data.get('name', ''),
                optimized_name,
                data.get('description', ''),
                keywords_str,
                data.get('price', 0),
                service_id
            ))
        else:
            cursor.execute("""
                UPDATE userservices 
                SET category = %s, name = %s, description = %s, keywords = %s, price = %s
                WHERE id = %s
            """, (
                data.get('category', ''),
                data.get('name', ''),
                data.get('description', ''),
                keywords_str,
                data.get('price', 0),
                service_id
            ))
        
        db.conn.commit()
        db.close()
    except Exception as e:
        print(f"❌ Ошибка обновления услуги: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@services_bp.route('/api/services/delete/<string:service_id>', methods=['DELETE', 'OPTIONS'])
def delete_service(service_id):
    """Удалить услугу"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, что услуга принадлежит пользователю
        cursor.execute("SELECT user_id FROM userservices WHERE id = %s", (service_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Услуга не найдена"}), 404
        
        service_user_id = row[0]
        if service_user_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этой услуге"}), 403
        
        # Удаляем услугу
        cursor.execute("DELETE FROM userservices WHERE id = %s", (service_id,))
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"❌ Ошибка удаления услуги: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

