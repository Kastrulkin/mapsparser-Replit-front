"""
API для управления услугами бизнеса
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from auth_system import verify_session
from core.helpers import get_business_owner_id
import re

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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
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

        # PostgreSQL: список колонок таблицы userservices
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'userservices'
            ORDER BY ordinal_position
        """)
        columns = [row[0] if isinstance(row, (list, tuple)) else row.get('column_name') for row in cursor.fetchall()]
        has_optimized_desc = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns
        has_price_from = 'price_from' in columns

        select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at', 'updated_at']
        if has_optimized_desc:
            select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
        if has_optimized_name:
            select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
        if has_price_from:
            select_fields.append('price_from')
            select_fields.append('price_to')
        # Служебные поля для разделения распарсенных/ручных услуг и дедупликации.
        if business_id:
            if 'source' not in select_fields:
                select_fields.append('source')
            if 'raw' not in select_fields:
                select_fields.append('raw')

        # Если передан business_id — фильтруем по нему и is_active, иначе по user_id
        if business_id:
            owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
            if not owner_id:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            if owner_id != user_id and not user_data.get('is_superadmin'):
                db.close()
                return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

            order_by = "ORDER BY category NULLS LAST, name NULLS LAST"
            if has_price_from:
                order_by += ", price_from NULLS LAST"
            order_by += ", updated_at DESC NULLS LAST"

            select_sql = (
                f"SELECT {', '.join(select_fields)} FROM userservices "
                "WHERE business_id = %s AND (is_active IS TRUE OR is_active IS NULL) "
                f"{order_by}"
            )
            cursor.execute(select_sql, (business_id,))
        else:
            select_sql = (
                f"SELECT {', '.join(select_fields)} FROM userservices "
                "WHERE user_id = %s ORDER BY created_at DESC NULLS LAST"
            )
            cursor.execute(select_sql, (user_id,))

        services_rows = cursor.fetchall()
        col_names = [d[0] for d in cursor.description] if cursor.description else select_fields
        db.close()

        def _parse_price_text(raw_price):
            if raw_price is None:
                return None
            s = str(raw_price).strip()
            if not s:
                return None
            numbers = re.findall(r"\d+", s)
            if not numbers:
                return None
            try:
                if len(numbers) >= 2 and not re.search(r"[-–—]", s) and " до " not in s.lower():
                    return float(int("".join(numbers[:2])))
                return float(int(numbers[0]))
            except (TypeError, ValueError):
                return None

        services = []
        for service in services_rows:
            if hasattr(service, 'keys'):
                service_dict = dict(service)
            else:
                service_dict = dict(zip(col_names, service)) if col_names else {}
            # Нормализация NULL
            for k in list(service_dict.keys()):
                if service_dict[k] is None and k in ('description', 'category', 'name', 'price', 'keywords'):
                    service_dict[k] = '' if k != 'keywords' else []
            raw_kw = service_dict.get('keywords')
            parsed_kw = []
            if raw_kw:
                try:
                    import json
                    parsed_kw = json.loads(raw_kw) if isinstance(raw_kw, str) else raw_kw
                    if not isinstance(parsed_kw, list):
                        parsed_kw = []
                except Exception:
                    parsed_kw = [k.strip() for k in str(raw_kw).split(',') if k.strip()]
            service_dict['keywords'] = parsed_kw
            services.append(service_dict)

        # Для business_id отдаём в приоритете распарсенные услуги.
        # Это скрывает устаревшие ручные строки с предыдущих дат, если для них уже есть свежий парсинг.
        if business_id:
            def _price_norm(svc: dict) -> str:
                pf = svc.get('price_from')
                pt = svc.get('price_to')
                if pf is not None or pt is not None:
                    return f"{pf or ''}-{pt or ''}"
                return str(svc.get('price') or '').strip()

            def _svc_key(svc: dict):
                return (
                    str(svc.get('name') or '').strip().lower(),
                    str(svc.get('category') or '').strip().lower(),
                    _price_norm(svc).lower(),
                )

            parsed_services = []
            manual_services = []
            for svc in services:
                source = str(svc.get('source') or '').strip().lower()
                is_parsed = source in ('yandex_maps', 'yandex_business') or svc.get('raw') is not None
                if is_parsed:
                    raw_obj = svc.get('raw')
                    if isinstance(raw_obj, str):
                        try:
                            import json
                            raw_obj = json.loads(raw_obj)
                        except Exception:
                            raw_obj = None
                    if isinstance(raw_obj, dict):
                        parsed_price = _parse_price_text(raw_obj.get('price'))
                        if parsed_price is not None:
                            svc['price'] = parsed_price
                            if svc.get('price_from') is None:
                                svc['price_from'] = parsed_price
                            if svc.get('price_to') is None:
                                svc['price_to'] = parsed_price
                if is_parsed:
                    parsed_services.append(svc)
                else:
                    manual_services.append(svc)

            if parsed_services:
                # Берём только последний снапшот парсинга по updated_at.
                parsed_services = sorted(
                    parsed_services,
                    key=lambda s: str(s.get('updated_at') or ''),
                    reverse=True,
                )
                latest_ts = str(parsed_services[0].get('updated_at') or '')
                parsed_services = [s for s in parsed_services if str(s.get('updated_at') or '') == latest_ts]

                # Дедуп распарсенных: один ключ -> одна запись, приоритет более полному описанию.
                parsed_by_key = {}
                for svc in parsed_services:
                    key = _svc_key(svc)
                    prev = parsed_by_key.get(key)
                    if not prev:
                        parsed_by_key[key] = svc
                        continue
                    prev_desc_len = len((prev.get('description') or '').strip())
                    cur_desc_len = len((svc.get('description') or '').strip())
                    if cur_desc_len > prev_desc_len:
                        parsed_by_key[key] = svc
                    elif cur_desc_len == prev_desc_len:
                        prev_upd = str(prev.get('updated_at') or '')
                        cur_upd = str(svc.get('updated_at') or '')
                        if cur_upd > prev_upd:
                            parsed_by_key[key] = svc

                # Если есть распарсенные услуги, в UI отдаём только их:
                # это гарантирует замену устаревшего ручного списка актуальными данными парсинга.
                services = list(parsed_by_key.values())

            # Убираем служебные поля из ответа API
            for svc in services:
                svc.pop('source', None)
                svc.pop('raw', None)

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
        cursor.execute("SELECT user_id, business_id FROM UserServices WHERE id = %s", (service_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Услуга не найдена"}), 404
        
        service_user_id = row.get('user_id') if isinstance(row, dict) else row[0]
        service_business_id = row.get('business_id') if isinstance(row, dict) else row[1]
        
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
        
        # Проверяем, есть ли поля optimized_description и optimized_name (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'userservices'
        """)
        columns = [c.get('column_name') if isinstance(c, dict) else c[0] for c in cursor.fetchall()]
        has_optimized_description = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns
        
        optimized_description = data.get('optimized_description', '')
        optimized_name = data.get('optimized_name', '')
        
        print(f"🔍 DEBUG services_api.update_service: has_optimized_description = {has_optimized_description}, has_optimized_name = {has_optimized_name}", flush=True)
        print(f"🔍 DEBUG services_api.update_service: optimized_name = '{optimized_name}' (length: {len(optimized_name) if optimized_name else 0})", flush=True)
        print(f"🔍 DEBUG services_api.update_service: optimized_description = '{optimized_description[:50] if optimized_description else ''}...' (length: {len(optimized_description) if optimized_description else 0})", flush=True)
        
        # Обновляем услугу с учетом наличия полей
        if has_optimized_description and has_optimized_name:
            print(f"🔍 DEBUG services_api.update_service: Обновление с optimized_description и optimized_name", flush=True)
            cursor.execute("""
                UPDATE UserServices 
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
            cursor.execute("SELECT optimized_name, optimized_description FROM UserServices WHERE id = %s", (service_id,))
            check_row = cursor.fetchone()
            if check_row:
                print(f"✅ DEBUG services_api.update_service: Проверка после UPDATE - optimized_name = '{check_row[0]}', optimized_description = '{check_row[1][:50] if check_row[1] else ''}...'", flush=True)
            else:
                print(f"❌ DEBUG services_api.update_service: Услуга не найдена после UPDATE!", flush=True)
        elif has_optimized_description:
            cursor.execute("""
                UPDATE UserServices 
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
                UPDATE UserServices 
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
                UPDATE UserServices 
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
        return jsonify({"success": True})
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
        cursor.execute("SELECT user_id FROM UserServices WHERE id = %s", (service_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Услуга не найдена"}), 404
        
        service_user_id = row.get('user_id') if isinstance(row, dict) else row[0]
        if service_user_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этой услуге"}), 403
        
        # Удаляем услугу
        cursor.execute("DELETE FROM UserServices WHERE id = %s", (service_id,))
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"❌ Ошибка удаления услуги: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
