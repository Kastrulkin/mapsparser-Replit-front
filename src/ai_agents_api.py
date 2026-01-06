"""
API endpoints для управления ИИ агентами (только для суперадмина)
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from auth_system import verify_session
import uuid
import json

ai_agents_api_bp = Blueprint('ai_agents_api', __name__)

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
        cursor = db.conn.cursor()
        
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='AIAgents'")
        if not cursor.fetchone():
            db.close()
            return jsonify({"error": "Таблица AIAgents не найдена. Выполните миграцию: python migrations/migrate_ai_agents_table.py"}), 500
        
        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(AIAgents)")
        columns = {row[1] for row in cursor.fetchall()}
        
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
            # Определяем индексы в зависимости от наличия колонок
            idx = 0
            workflow_raw = row[idx + 5] if "workflow" in columns else ''
            task_value = row[idx + 6] if "task" in columns else ''
            identity_value = row[idx + 7] if "identity" in columns else ''
            speech_style_value = row[idx + 8] if "speech_style" in columns else ''
            
            # Всегда возвращаем workflow как строку (YAML текст), чтобы сохранить форматирование
            workflow_value = workflow_raw or ''
            
            agents.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'description': row[3] or '',
                'personality': row[4] or '',
                'workflow': workflow_value,  # Всегда строка (YAML)
                'task': task_value or '',
                'identity': identity_value or '',
                'speech_style': speech_style_value or '',
                'restrictions': json.loads(row[9]) if row[9] else {},
                'variables': json.loads(row[10]) if row[10] else {},
                'is_active': row[11] == 1 if len(row) > 11 else True,
                'created_at': row[12] if len(row) > 12 else None,
                'updated_at': row[13] if len(row) > 13 else None
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
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO AIAgents 
            (id, name, type, description, personality, workflow, task, identity, speech_style, restrictions_json, variables_json, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        cursor = db.conn.cursor()
        
        # Проверяем существование агента
        cursor.execute("SELECT id FROM AIAgents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            db.close()
            return jsonify({"error": "Агент не найден"}), 404
        
        # Обновляем поля
        update_fields = []
        update_values = []
        
        if 'name' in data:
            update_fields.append('name = ?')
            update_values.append(data['name'])
        
        if 'description' in data:
            update_fields.append('description = ?')
            update_values.append(data['description'])
        
        if 'personality' in data:
            update_fields.append('personality = ?')
            update_values.append(data['personality'])
        
        if 'workflow' in data:
            update_fields.append('workflow = ?')
            # Workflow всегда сохраняем как строку (YAML текст)
            if isinstance(data['workflow'], str):
                update_values.append(data['workflow'])
            else:
                # Если это объект, конвертируем в JSON строку (для обратной совместимости)
                update_values.append(json.dumps(data['workflow'], ensure_ascii=False))
        
        if 'task' in data:
            update_fields.append('task = ?')
            update_values.append(data['task'])
        
        if 'identity' in data:
            update_fields.append('identity = ?')
            update_values.append(data['identity'])
        
        if 'speech_style' in data:
            update_fields.append('speech_style = ?')
            update_values.append(data['speech_style'])
        
        if 'restrictions' in data:
            update_fields.append('restrictions_json = ?')
            update_values.append(json.dumps(data['restrictions'], ensure_ascii=False))
        
        if 'variables' in data:
            update_fields.append('variables_json = ?')
            update_values.append(json.dumps(data['variables'], ensure_ascii=False))
        
        if 'is_active' in data:
            update_fields.append('is_active = ?')
            update_values.append(1 if data['is_active'] else 0)
        
        update_fields.append('updated_at = CURRENT_TIMESTAMP')
        update_values.append(agent_id)
        
        if len(update_fields) > 1:  # Больше чем только updated_at
            cursor.execute(f"""
                UPDATE AIAgents 
                SET {', '.join(update_fields)}
                WHERE id = ?
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
        cursor = db.conn.cursor()
        
        # Проверяем, используется ли агент
        cursor.execute("SELECT COUNT(*) FROM Businesses WHERE ai_agent_id = ?", (agent_id,))
        usage_count = cursor.fetchone()[0]
        
        if usage_count > 0:
            db.close()
            return jsonify({
                "error": f"Агент используется {usage_count} бизнесами. Сначала отвяжите агента от бизнесов."
            }), 400
        
        cursor.execute("DELETE FROM AIAgents WHERE id = ?", (agent_id,))
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
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id, name, type, description, personality, workflow, task, identity, speech_style,
                   restrictions_json, variables_json, is_active, created_at, updated_at
            FROM AIAgents
            WHERE id = ?
        """, (agent_id,))
        
        row = cursor.fetchone()
        db.close()
        
        if not row:
            return jsonify({"error": "Агент не найден"}), 404
        
        # Workflow всегда возвращаем как строку (YAML), чтобы сохранить форматирование
        workflow_raw = row[5] or ''
        
        return jsonify({
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'description': row[3],
            'personality': row[4] or '',
            'workflow': workflow_raw,  # Всегда строка (YAML), не парсим JSON
            'task': row[6] or '',
            'identity': row[7] or '',
            'speech_style': row[8] or '',
            'restrictions': json.loads(row[9]) if row[9] else {},
            'variables': json.loads(row[10]) if row[10] else {},
            'is_active': row[11] == 1,
            'created_at': row[12],
            'updated_at': row[13]
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка получения агента: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

