"""Admin parsing queue and runtime setting routes."""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

from auth_system import verify_session
from core.parsing_runtime_config import get_use_apify_map_parsing, set_use_apify_map_parsing
from database_manager import DatabaseManager
from parsequeue_status import STATUS_ERROR, normalize_status


parsing_admin_bp = Blueprint("parsing_admin_api", __name__)


def _row_to_dict(cursor, row):
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


@parsing_admin_bp.route('/api/admin/parsing/tasks', methods=['GET'])
def get_parsing_tasks():
    """Получить список задач парсинга для администратора"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403

        # Получаем параметры фильтрации
        status_filter = request.args.get('status')
        task_type_filter = request.args.get('task_type')
        source_filter = request.args.get('source')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Формируем WHERE условия
        where_conditions = []
        params = []

        if status_filter:
            # Фильтр "completed": учитываем и старый статус "done"
            if status_filter == STATUS_COMPLETED:
                where_conditions.append("(status = %s OR status = 'done')")
                params.append(STATUS_COMPLETED)
            else:
                where_conditions.append("status = %s")
                params.append(status_filter)

        if task_type_filter:
            where_conditions.append("task_type = %s")
            params.append(task_type_filter)

        if source_filter:
            where_conditions.append("source = %s")
            params.append(source_filter)

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        cursor.execute(f"""
            SELECT
                pq.id, pq.url, pq.user_id, pq.business_id, pq.task_type, pq.account_id, pq.source,
                pq.status, pq.retry_after, pq.error_message, pq.created_at, pq.updated_at,
                b.name AS business_name
            FROM parsequeue pq
            LEFT JOIN businesses b ON b.id = pq.business_id
            WHERE {where_clause}
            ORDER BY pq.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cursor.fetchall()

        cursor.execute(f"""
            SELECT COUNT(*) AS cnt FROM parsequeue WHERE {where_clause}
        """, params)
        total = _count_from_row(cursor, cursor.fetchone())

        cursor.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM parsequeue
            GROUP BY status
        """)
        status_stats = {}
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd:
                st_canonical = normalize_status(rd.get("status"))
                status_stats[st_canonical] = status_stats.get(st_canonical, 0) + (rd.get("cnt") or 0)

        tasks = []
        for row in rows:
            task_dict = _row_to_dict(cursor, row)
            if not task_dict:
                continue
            task_dict.setdefault("task_type", "parse_card")
            task_dict["status"] = normalize_status(task_dict.get("status"))
            task_dict["business_name"] = (task_dict.get("business_name") or "").strip() or None
            tasks.append(task_dict)

        db.close()

        return jsonify({
            "success": True,
            "tasks": tasks,
            "total": total,
            "stats": status_stats
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        body = {"success": False, "error": str(e), "where": "get_parsing_tasks"}
        if getattr(current_app, "debug", False):
            body["error_type"] = type(e).__name__
            body["traceback"] = traceback.format_exc()
        return jsonify(body), 500

@parsing_admin_bp.route('/api/admin/parsing/tasks/<task_id>/restart', methods=['POST'])
def restart_parsing_task(task_id):
    """Перезапустить задачу парсинга (сбросить статус на pending)"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем, существует ли задача
        cursor.execute("SELECT id, status FROM parsequeue WHERE id = %s", (task_id,))
        task = cursor.fetchone()

        if not task:
            db.close()
            return jsonify({"error": "Задача не найдена"}), 404

        if isinstance(task, dict):
            current_status = task.get('status')
        else:
             # tuple or sqlite3.Row
            current_status = task[1]

        cursor.execute("""
            UPDATE parsequeue
            SET status = 'pending',
                error_message = NULL,
                retry_after = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (task_id,))

        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "message": f"Задача перезапущена (был статус: {current_status})"
        })

    except Exception as e:
        print(f"❌ Ошибка перезапуска задачи: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@parsing_admin_bp.route('/api/admin/parsing/tasks/<task_id>', methods=['DELETE'])
def delete_parsing_task(task_id):
    """Удалить задачу из очереди"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("DELETE FROM parsequeue WHERE id = %s", (task_id,))
        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Задача удалена"})

    except Exception as e:
        print(f"❌ Ошибка удаления задачи: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@parsing_admin_bp.route('/api/admin/parsing/tasks/<task_id>/switch-to-sync', methods=['POST'])
def switch_task_to_sync(task_id):
    """Переключить задачу парсинга на синхронизацию с Яндекс.Бизнес"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("""
            SELECT id, business_id, task_type, status
            FROM parsequeue
            WHERE id = %s
        """, (task_id,))
        raw_task = cursor.fetchone()
        task_dict = _row_to_dict(cursor, raw_task) if raw_task else None

        if not task_dict:
            db.close()
            return jsonify({"error": "Задача не найдена"}), 404

        business_id = task_dict.get('business_id')
        if not business_id:
            db.close()
            return jsonify({"error": "У задачи нет business_id"}), 400

        if task_dict.get('task_type') == 'sync_yandex_business':
            db.close()
            return jsonify({"error": "Задача уже является синхронизацией"}), 400

        cursor.execute("""
            SELECT id
            FROM externalbusinessaccounts
            WHERE business_id = %s AND source = 'yandex_business' AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        raw_account = cursor.fetchone()
        account_row = _row_to_dict(cursor, raw_account) if raw_account else None

        if not account_row:
            db.close()
            return jsonify({
                "success": False,
                "error": "Не найден активный аккаунт Яндекс.Бизнес",
                "message": "Добавьте аккаунт Яндекс.Бизнес в настройках внешних интеграций"
            }), 400

        account_id = account_row.get("id")

        cursor.execute("""
            UPDATE parsequeue
            SET task_type = 'sync_yandex_business',
                account_id = %s,
                source = 'yandex_business',
                status = 'pending',
                error_message = NULL,
                retry_after = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (account_id, task_id))

        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "message": "Задача переключена на синхронизацию с Яндекс.Бизнес"
        })

    except Exception as e:
        print(f"❌ Ошибка переключения задачи на синхронизацию: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@parsing_admin_bp.route('/api/admin/parsing/stats', methods=['GET'])
def get_parsing_stats():
    """Получить общую статистику парсинга"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT COUNT(*) AS cnt FROM parsequeue")
        total_tasks = _count_from_row(cursor, cursor.fetchone())

        cursor.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM parsequeue
            GROUP BY status
        """)
        by_status = {}
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd:
                st_canonical = normalize_status(rd.get("status") or "idle")
                by_status[st_canonical] = by_status.get(st_canonical, 0) + (rd.get("cnt") or 0)

        cursor.execute("""
            SELECT task_type, COUNT(*) AS cnt
            FROM parsequeue
            GROUP BY task_type
        """)
        by_task_type = {}
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd:
                by_task_type[rd.get("task_type") or "parse_card"] = rd.get("cnt") or 0

        cursor.execute("""
            SELECT source, COUNT(*) AS cnt
            FROM parsequeue
            WHERE source IS NOT NULL
            GROUP BY source
        """)
        by_source = {}
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd and rd.get("source") is not None:
                by_source[rd["source"]] = rd.get("cnt") or 0

        cursor.execute("""
            SELECT id, business_id, task_type, created_at, updated_at
            FROM parsequeue
            WHERE status = 'processing'
              AND COALESCE(updated_at, created_at) < NOW() - INTERVAL '30 minutes'
        """)
        stuck_tasks = []
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd:
                stuck_tasks.append({
                    'id': rd.get('id'),
                    'business_id': rd.get('business_id'),
                    'task_type': rd.get('task_type') or 'parse_card',
                    'created_at': rd.get('created_at'),
                    'updated_at': rd.get('updated_at') or rd.get('created_at')
                })

        db.close()

        return jsonify({
            "success": True,
            "stats": {
                "total_tasks": total_tasks,
                "by_status": by_status or {},
                "by_task_type": by_task_type or {},
                "by_source": by_source or {},
                "stuck_tasks_count": len(stuck_tasks),
                "stuck_tasks": stuck_tasks or []
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        body = {"success": False, "error": str(e), "where": "get_parsing_stats"}
        if getattr(current_app, "debug", False):
            body["error_type"] = type(e).__name__
            body["traceback"] = traceback.format_exc()
        return jsonify(body), 500

@parsing_admin_bp.route('/api/admin/parsing/runtime-settings', methods=['GET'])
def get_parsing_runtime_settings():
    """Получить runtime-настройки парсинга (только superadmin)."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403

        conn = get_db_connection()
        try:
            enabled = bool(get_use_apify_map_parsing(conn))
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "settings": {
                "use_apify_map_parsing": enabled
            }
        })
    except Exception as e:
        print(f"❌ Ошибка чтения runtime-настроек парсинга: {e}")
        return jsonify({"error": str(e)}), 500

@parsing_admin_bp.route('/api/admin/parsing/runtime-settings', methods=['POST'])
def update_parsing_runtime_settings():
    """Обновить runtime-настройки парсинга (только superadmin)."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403

        payload = request.get_json(silent=True) or {}
        if "use_apify_map_parsing" not in payload:
            return jsonify({"error": "Поле use_apify_map_parsing обязательно"}), 400
        enabled = bool(payload.get("use_apify_map_parsing"))

        conn = get_db_connection()
        try:
            set_use_apify_map_parsing(conn, enabled)
            current = bool(get_use_apify_map_parsing(conn))
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "settings": {
                "use_apify_map_parsing": current
            }
        })
    except Exception as e:
        print(f"❌ Ошибка обновления runtime-настроек парсинга: {e}")
        return jsonify({"error": str(e)}), 500
