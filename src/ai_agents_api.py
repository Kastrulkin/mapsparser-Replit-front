"""
API endpoints для управления ИИ агентами (только для суперадмина)
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from auth_system import verify_session
import uuid
import json

ai_agents_api_bp = Blueprint('ai_agents_api', __name__)


def _row_get(row, key, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return default


def _json_loads_safe(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def _bool_safe(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ("1", "true", "t", "yes", "y")


def _get_table_columns(cursor, table_name: str):
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return {row["column_name"] for row in cursor.fetchall()}


def _ensure_ai_agents_schema(db: DatabaseManager) -> None:
    cursor = db.conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS AIAgents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            personality TEXT,
            states_json TEXT,
            workflow TEXT,
            task TEXT,
            identity TEXT,
            speech_style TEXT,
            restrictions_json TEXT,
            variables_json TEXT,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("ALTER TABLE AIAgents ADD COLUMN IF NOT EXISTS workflow TEXT")
    cursor.execute("ALTER TABLE AIAgents ADD COLUMN IF NOT EXISTS task TEXT")
    cursor.execute("ALTER TABLE AIAgents ADD COLUMN IF NOT EXISTS identity TEXT")
    cursor.execute("ALTER TABLE AIAgents ADD COLUMN IF NOT EXISTS speech_style TEXT")
    cursor.execute("ALTER TABLE AIAgents ADD COLUMN IF NOT EXISTS restrictions_json TEXT")
    cursor.execute("ALTER TABLE AIAgents ADD COLUMN IF NOT EXISTS variables_json TEXT")
    cursor.execute("ALTER TABLE AIAgents ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1")
    cursor.execute("ALTER TABLE AIAgents ADD COLUMN IF NOT EXISTS created_by TEXT")
    cursor.execute("ALTER TABLE AIAgents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    cursor.execute(
        """
        INSERT INTO AIAgents (id, name, type, description, personality, is_active)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            "booking_agent_default",
            "Booking Agent",
            "booking",
            "Агент для записи клиентов",
            "Вежливый, пунктуальный администратор. Твоя задача - записать клиента на услугу.",
            1,
        ),
    )
    db.conn.commit()

def require_superadmin():
    """Проверка, что пользователь - суперадмин"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_data = verify_session(token)
    if not user_data or not user_data.get('is_superadmin'):
        return None
    return user_data

@ai_agents_api_bp.route('/api/admin/ai-agents', methods=['GET'])
def get_ai_agents():
    """Получить список всех агентов"""
    try:
        user_data = require_superadmin()
        if not user_data:
            return jsonify({"error": "Требуются права суперадмина"}), 403
        
        db = DatabaseManager()
        _ensure_ai_agents_schema(db)
        cursor = db.conn.cursor()
        columns = _get_table_columns(cursor, "aiagents")
        
        # Формируем SELECT в зависимости от наличия колонок
        select_fields = ["id", "name", "type", "description", "personality"]
        
        # Добавляем новые поля, если они есть
        if "workflow" in columns:
            select_fields.append("workflow")
        else:
            select_fields.append("NULL as workflow")
            
        if "task" in columns:
            select_fields.append("task")
        else:
            select_fields.append("NULL as task")
            
        if "identity" in columns:
            select_fields.append("identity")
        else:
            select_fields.append("NULL as identity")
            
        if "speech_style" in columns:
            select_fields.append("speech_style")
        else:
            select_fields.append("NULL as speech_style")
        
        select_fields.extend(["restrictions_json", "variables_json", "is_active", "created_at", "updated_at"])
        
        cursor.execute(f"""
            SELECT {', '.join(select_fields)}
            FROM AIAgents
            ORDER BY type, name
        """)
        
        rows = cursor.fetchall()
        agents = []
        for row in rows:
            workflow_value = (_row_get(row, "workflow", "") if "workflow" in columns else "") or ""
            task_value = (_row_get(row, "task", "") if "task" in columns else "") or ""
            identity_value = (_row_get(row, "identity", "") if "identity" in columns else "") or ""
            speech_style_value = (_row_get(row, "speech_style", "") if "speech_style" in columns else "") or ""

            agents.append({
                'id': _row_get(row, "id"),
                'name': _row_get(row, "name"),
                'type': _row_get(row, "type"),
                'description': _row_get(row, "description", "") or '',
                'personality': _row_get(row, "personality", "") or '',
                'workflow': workflow_value,  # Всегда строка (YAML)
                'task': task_value or '',
                'identity': identity_value or '',
                'speech_style': speech_style_value or '',
                'restrictions': _json_loads_safe(_row_get(row, "restrictions_json")),
                'variables': _json_loads_safe(_row_get(row, "variables_json")),
                'is_active': _bool_safe(_row_get(row, "is_active"), default=True),
                'created_at': _row_get(row, "created_at"),
                'updated_at': _row_get(row, "updated_at")
            })
        
        db.close()
        return jsonify({"agents": agents}), 200
        
    except Exception as e:
        print(f"❌ Ошибка получения агентов: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@ai_agents_api_bp.route('/api/admin/ai-agents', methods=['POST'])
def create_ai_agent():
    """Создать нового агента"""
    try:
        user_data = require_superadmin()
        if not user_data:
            return jsonify({"error": "Требуются права суперадмина"}), 403
        
        data = request.get_json()
        name = data.get('name', '').strip()
        agent_type = data.get('type', '').strip()
        description = data.get('description', '').strip()
        personality = data.get('personality', '').strip()
        workflow = data.get('workflow', '')
        # Workflow всегда сохраняем как строку (YAML текст)
        if isinstance(workflow, str):
            workflow_value = workflow
        else:
            # Если это объект, конвертируем в JSON строку (для обратной совместимости)
            workflow_value = json.dumps(workflow, ensure_ascii=False) if workflow else ''
        
        task = data.get('task', '').strip()
        identity = data.get('identity', '').strip()
        speech_style = data.get('speech_style', '').strip()
        restrictions = data.get('restrictions', {})
        variables = data.get('variables', {})
        
        if not name or not agent_type:
            return jsonify({"error": "name и type обязательны"}), 400
        
        agent_id = str(uuid.uuid4())
        
        db = DatabaseManager()
        _ensure_ai_agents_schema(db)
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO AIAgents 
            (id, name, type, description, personality, workflow, task, identity, speech_style, restrictions_json, variables_json, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            agent_id,
            name,
            agent_type,
            description,
            personality,
            workflow_value,
            task,
            identity,
            speech_style,
            json.dumps(restrictions, ensure_ascii=False),
            json.dumps(variables, ensure_ascii=False),
            user_data['user_id']
        ))
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "agent_id": agent_id,
            "message": "Агент создан"
        }), 201
        
    except Exception as e:
        print(f"❌ Ошибка создания агента: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@ai_agents_api_bp.route('/api/admin/ai-agents/<agent_id>', methods=['PUT'])
def update_ai_agent(agent_id: str):
    """Обновить агента"""
    try:
        user_data = require_superadmin()
        if not user_data:
            return jsonify({"error": "Требуются права суперадмина"}), 403
        
        data = request.get_json()
        
        db = DatabaseManager()
        _ensure_ai_agents_schema(db)
        cursor = db.conn.cursor()
        
        # Проверяем существование агента
        cursor.execute("SELECT id FROM AIAgents WHERE id = %s", (agent_id,))
        if not cursor.fetchone():
            db.close()
            return jsonify({"error": "Агент не найден"}), 404
        
        # Обновляем поля
        update_fields = []
        update_values = []
        
        if 'name' in data:
            update_fields.append('name = %s')
            update_values.append(data['name'])
        
        if 'description' in data:
            update_fields.append('description = %s')
            update_values.append(data['description'])
        
        if 'personality' in data:
            update_fields.append('personality = %s')
            update_values.append(data['personality'])
        
        if 'workflow' in data:
            update_fields.append('workflow = %s')
            # Workflow всегда сохраняем как строку (YAML текст)
            if isinstance(data['workflow'], str):
                update_values.append(data['workflow'])
            else:
                # Если это объект, конвертируем в JSON строку (для обратной совместимости)
                update_values.append(json.dumps(data['workflow'], ensure_ascii=False))
        
        if 'task' in data:
            update_fields.append('task = %s')
            update_values.append(data['task'])
        
        if 'identity' in data:
            update_fields.append('identity = %s')
            update_values.append(data['identity'])
        
        if 'speech_style' in data:
            update_fields.append('speech_style = %s')
            update_values.append(data['speech_style'])
        
        if 'restrictions' in data:
            update_fields.append('restrictions_json = %s')
            update_values.append(json.dumps(data['restrictions'], ensure_ascii=False))
        
        if 'variables' in data:
            update_fields.append('variables_json = %s')
            update_values.append(json.dumps(data['variables'], ensure_ascii=False))
        
        if 'is_active' in data:
            update_fields.append('is_active = %s')
            update_values.append(1 if data['is_active'] else 0)
        
        update_fields.append('updated_at = CURRENT_TIMESTAMP')
        update_values.append(agent_id)
        
        if len(update_fields) > 1:  # Больше чем только updated_at
            cursor.execute(f"""
                UPDATE AIAgents 
                SET {', '.join(update_fields)}
                WHERE id = %s
            """, update_values)
            db.conn.commit()
        
        db.close()
        
        return jsonify({
            "success": True,
            "message": "Агент обновлён"
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка обновления агента: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@ai_agents_api_bp.route('/api/admin/ai-agents/<agent_id>', methods=['DELETE'])
def delete_ai_agent(agent_id: str):
    """Удалить агента"""
    try:
        user_data = require_superadmin()
        if not user_data:
            return jsonify({"error": "Требуются права суперадмина"}), 403
        
        db = DatabaseManager()
        _ensure_ai_agents_schema(db)
        cursor = db.conn.cursor()
        
        # Проверяем, используется ли агент
        cursor.execute("SELECT COUNT(*) AS usage_count FROM Businesses WHERE ai_agent_id = %s", (agent_id,))
        usage_row = cursor.fetchone() or {}
        usage_count = int(_row_get(usage_row, "usage_count", 0) or 0)
        
        if usage_count > 0:
            db.close()
            return jsonify({
                "error": f"Агент используется {usage_count} бизнесами. Сначала отвяжите агента от бизнесов."
            }), 400
        
        cursor.execute("DELETE FROM AIAgents WHERE id = %s", (agent_id,))
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "message": "Агент удалён"
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка удаления агента: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@ai_agents_api_bp.route('/api/admin/ai-agents/<agent_id>', methods=['GET'])
def get_ai_agent(agent_id: str):
    """Получить информацию об агенте"""
    try:
        user_data = require_superadmin()
        if not user_data:
            return jsonify({"error": "Требуются права суперадмина"}), 403
        
        db = DatabaseManager()
        _ensure_ai_agents_schema(db)
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id, name, type, description, personality, workflow, task, identity, speech_style,
                   restrictions_json, variables_json, is_active, created_at, updated_at
            FROM AIAgents
            WHERE id = %s
        """, (agent_id,))
        
        row = cursor.fetchone()
        db.close()
        
        if not row:
            return jsonify({"error": "Агент не найден"}), 404
        
        # Workflow всегда возвращаем как строку (YAML), чтобы сохранить форматирование
        workflow_raw = _row_get(row, "workflow", "") or ''
        
        return jsonify({
            'id': _row_get(row, "id"),
            'name': _row_get(row, "name"),
            'type': _row_get(row, "type"),
            'description': _row_get(row, "description"),
            'personality': _row_get(row, "personality", "") or '',
            'workflow': workflow_raw,  # Всегда строка (YAML), не парсим JSON
            'task': _row_get(row, "task", "") or '',
            'identity': _row_get(row, "identity", "") or '',
            'speech_style': _row_get(row, "speech_style", "") or '',
            'restrictions': _json_loads_safe(_row_get(row, "restrictions_json")),
            'variables': _json_loads_safe(_row_get(row, "variables_json")),
            'is_active': _bool_safe(_row_get(row, "is_active"), default=True),
            'created_at': _row_get(row, "created_at"),
            'updated_at': _row_get(row, "updated_at")
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка получения агента: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
