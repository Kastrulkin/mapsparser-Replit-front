#!/usr/bin/env python3
"""
API endpoints для работы с чатами ИИ агента
- Получение списка агентов бизнеса
- Получение списка чатов агента
- Получение сообщений чата
- Отправка сообщения оператором
- Остановка/возобновление агента
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from auth_system import verify_session
from core.telegram_token_store import decode_telegram_bot_token
import json
import os
import requests

chats_bp = Blueprint('chats', __name__)

def _row_get(row, key, idx=0, default=None):
    if row is None:
        return default
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        return row[idx]
    except Exception:
        return default

def require_auth():
    """Проверка авторизации"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    return user_data


def _call_openclaw_sandbox_bridge(
    *,
    business_id: str,
    agent_id: str,
    message: str,
    conversation_history: list | None,
    user_data: dict | None,
):
    endpoint = str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_URL", "") or "").strip()
    if not endpoint:
        return None
    token = (
        str(os.getenv("OPENCLAW_SANDBOX_BRIDGE_TOKEN", "") or "").strip()
        or str(os.getenv("OPENCLAW_LOCALOS_TOKEN", "") or "").strip()
    )
    if not token:
        return {
            "success": False,
            "error": "OPENCLAW_SANDBOX_BRIDGE_TOKEN is not configured",
            "runtime": "openclaw_bridge",
        }

    payload = {
        "business_id": business_id,
        "agent_id": agent_id,
        "message": message,
        "conversation_history": conversation_history or [],
        "dry_run": True,
        "actor": {
            "user_id": str((user_data or {}).get("user_id") or ""),
            "role": "sandbox_operator",
        },
    }
    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=35,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"OpenClaw sandbox bridge request failed: {exc}",
            "runtime": "openclaw_bridge",
        }

    try:
        data = response.json() if response.content else {}
    except Exception:
        data = {}

    if response.status_code >= 400:
        return {
            "success": False,
            "error": f"OpenClaw sandbox bridge HTTP {response.status_code}: {data or response.text}",
            "runtime": "openclaw_bridge",
        }

    return {
        "success": bool(data.get("success", True)),
        "response": str(data.get("response") or data.get("message") or "").strip(),
        "usage": data.get("usage") or {},
        "state": str(data.get("state") or data.get("decision") or "runtime_bridge").strip(),
        "runtime": "openclaw_bridge",
        "dry_run": True,
        "decision_trace": data.get("decision_trace") or data.get("trace") or {},
        "tool_calls": data.get("tool_calls") or [],
        "error": str(data.get("error") or "").strip() or None,
    }

@chats_bp.route('/api/business/<business_id>/ai-agents', methods=['GET'])
def get_business_ai_agents(business_id):
    """Получить список ИИ агентов бизнеса"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ к бизнесу
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        owner_id = _row_get(business, 'owner_id', 0)
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Получаем конфигурацию агентов (новый формат + fallback на legacy поля)
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'businesses'
        """)
        business_cols = {str(_row_get(r, 'column_name', 0, '') or '').lower() for r in (cursor.fetchall() or [])}
        has_ai_agents_config = 'ai_agents_config' in business_cols
        select_fields = [
            ("ai_agents_config" if has_ai_agents_config else "NULL AS ai_agents_config"),
            ("ai_agent_enabled" if "ai_agent_enabled" in business_cols else "NULL AS ai_agent_enabled"),
            ("ai_agent_type" if "ai_agent_type" in business_cols else "NULL AS ai_agent_type"),
            ("ai_agent_id" if "ai_agent_id" in business_cols else "NULL AS ai_agent_id"),
        ]
        cursor.execute(f"""
            SELECT {", ".join(select_fields)}
            FROM Businesses
            WHERE id = %s
        """, (business_id,))
        business_data = cursor.fetchone()
        
        agents = []
        
        # Пытаемся загрузить из нового формата
        ai_agents_config_raw = _row_get(business_data, 'ai_agents_config', 0)
        added_agent_ids = set()

        def _append_agent_row(agent_row):
            if not agent_row:
                return
            agent_id = _row_get(agent_row, 'id', 0)
            if not agent_id or agent_id in added_agent_ids:
                return
            added_agent_ids.add(agent_id)
            agents.append({
                'id': agent_id,
                'name': _row_get(agent_row, 'name', 1),
                'type': _row_get(agent_row, 'type', 2),
                'description': _row_get(agent_row, 'description', 3)
            })

        def _resolve_default_agent(agent_type_raw: str):
            normalized = str(agent_type_raw or '').strip().lower()
            if not normalized:
                normalized = 'booking'
            if 'book' in normalized or 'запис' in normalized:
                normalized = 'booking'
            elif 'mark' in normalized or 'маркет' in normalized:
                normalized = 'marketing'
            cursor.execute("""
                SELECT id, name, type, description
                FROM AIAgents
                WHERE type = %s
                  AND COALESCE(is_active::text, '1') IN ('1', 'true', 't')
                ORDER BY id
                LIMIT 1
            """, (normalized,))
            return cursor.fetchone()

        if ai_agents_config_raw:
            try:
                agents_config = json.loads(ai_agents_config_raw) if isinstance(ai_agents_config_raw, str) else ai_agents_config_raw
                if not isinstance(agents_config, dict):
                    agents_config = {}
                
                # Для каждого включенного агента получаем его данные
                for agent_key, config in agents_config.items():
                    if isinstance(config, dict) and config.get('enabled'):
                        # Определяем тип агента из ключа (booking_agent -> booking)
                        agent_type = agent_key.replace('_agent', '')
                        
                        # Если указан конкретный agent_id, загружаем его
                        if config.get('agent_id'):
                            cursor.execute("""
                                SELECT id, name, type, description
                                FROM AIAgents
                                WHERE id = %s
                            """, (config['agent_id'],))
                            _append_agent_row(cursor.fetchone())
                        else:
                            # Используем дефолтного агента для типа
                            _append_agent_row(_resolve_default_agent(agent_type))
            except (json.JSONDecodeError, TypeError) as e:
                print(f"⚠️ Ошибка парсинга ai_agents_config: {e}")

        # Legacy fallback (если новый формат не заполнен)
        if not agents and _row_get(business_data, 'ai_agent_enabled', 1):
            legacy_agent_id = _row_get(business_data, 'ai_agent_id', 3)
            if legacy_agent_id:
                cursor.execute("""
                    SELECT id, name, type, description
                    FROM AIAgents
                    WHERE id = %s
                """, (legacy_agent_id,))
                _append_agent_row(cursor.fetchone())
            else:
                _append_agent_row(_resolve_default_agent(_row_get(business_data, 'ai_agent_type', 2) or 'booking'))

        # Дополняем список активными агентами, чтобы новый пользовательский агент
        # был доступен в чатах даже до явной привязки в ai_agents_config.
        cursor.execute("""
            SELECT id, name, type, description
            FROM AIAgents
            WHERE COALESCE(is_active::text, '1') IN ('1', 'true', 't')
              AND (
                    created_by = %s
                    OR created_by IS NULL
                    OR created_by = ''
                    OR id IN ('booking_agent_default', 'marketing_agent_default')
                  )
            ORDER BY
              CASE WHEN created_by = %s THEN 0 ELSE 1 END,
              created_at DESC NULLS LAST,
              id
        """, (user_data['user_id'], user_data['user_id']))
        for agent_row in cursor.fetchall() or []:
            _append_agent_row(agent_row)
        
        db.close()
        return jsonify({"success": True, "agents": agents})
        
    except Exception as e:
        print(f"❌ Ошибка получения агентов: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@chats_bp.route('/api/business/<business_id>/conversations', methods=['GET'])
def get_business_conversations(business_id):
    """Получить список чатов бизнеса для конкретного агента"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        agent_id = request.args.get('agent_id')
        if not agent_id:
            return jsonify({"error": "agent_id обязателен"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ к бизнесу
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        owner_id = _row_get(business, 'owner_id', 0)
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Получаем схему таблицы чатов для совместимости с разными миграциями
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'aiagentconversations'
        """)
        conv_cols = {str(_row_get(r, 'column_name', 0, '') or '').lower() for r in (cursor.fetchall() or [])}
        if not conv_cols:
            db.close()
            return jsonify({"success": True, "conversations": []})
        is_agent_paused_expr = "COALESCE(c.is_agent_paused, 0)" if 'is_agent_paused' in conv_cols else "0"

        # Получаем чаты для этого бизнеса и агента
        cursor.execute(f"""
            SELECT 
                c.id,
                c.client_phone,
                c.client_name,
                c.current_state,
                c.last_message_at,
                {is_agent_paused_expr} as is_agent_paused,
                (SELECT COUNT(*) 
                 FROM AIAgentMessages m 
                 WHERE m.conversation_id = c.id 
                 AND m.sender = 'client' 
                 AND m.created_at > (
                     SELECT MAX(created_at) 
                     FROM AIAgentMessages 
                     WHERE conversation_id = c.id 
                     AND sender IN ('agent', 'operator')
                 )
                ) as unread_count
            FROM AIAgentConversations c
            WHERE c.business_id = %s
            ORDER BY c.last_message_at DESC
        """, (business_id,))
        
        rows = cursor.fetchall()
        conversations = []
        
        for row in rows:
            conversations.append({
                'id': _row_get(row, 'id', 0),
                'client_phone': _row_get(row, 'client_phone', 1),
                'client_name': _row_get(row, 'client_name', 2),
                'current_state': _row_get(row, 'current_state', 3),
                'last_message_at': _row_get(row, 'last_message_at', 4),
                'is_agent_paused': _row_get(row, 'is_agent_paused', 5),
                'unread_count': _row_get(row, 'unread_count', 6) or 0
            })
        
        db.close()
        return jsonify({"success": True, "conversations": conversations})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@chats_bp.route('/api/conversations/<conversation_id>/messages', methods=['GET'])
def get_conversation_messages(conversation_id):
    """Получить сообщения чата"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ к чату
        cursor.execute("""
            SELECT c.business_id, b.owner_id
            FROM AIAgentConversations c
            JOIN Businesses b ON c.business_id = b.id
            WHERE c.id = %s
        """, (conversation_id,))
        
        conv = cursor.fetchone()
        if not conv:
            db.close()
            return jsonify({"error": "Чат не найден"}), 404
        
        conv_owner_id = _row_get(conv, 'owner_id', 1)
        if conv_owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому чату"}), 403
        
        # Получаем сообщения
        cursor.execute("""
            SELECT id, content, sender, message_type, created_at
            FROM AIAgentMessages
            WHERE conversation_id = %s
            ORDER BY created_at ASC
        """, (conversation_id,))
        
        rows = cursor.fetchall()
        messages = []
        
        for row in rows:
            messages.append({
                'id': _row_get(row, 'id', 0),
                'content': _row_get(row, 'content', 1),
                'sender': _row_get(row, 'sender', 2),
                'message_type': _row_get(row, 'message_type', 3),
                'created_at': _row_get(row, 'created_at', 4)
            })
        
        db.close()
        return jsonify({"success": True, "messages": messages})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chats_bp.route('/api/conversations/<conversation_id>/send-message', methods=['POST'])
def send_operator_message(conversation_id):
    """Отправить сообщение от оператора"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        data = request.get_json()
        message = data.get('message', '').strip()
        sender = data.get('sender', 'operator')
        
        if not message:
            return jsonify({"error": "Сообщение не может быть пустым"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ к чату
        cursor.execute("""
            SELECT c.business_id, c.client_phone, c.client_name, b.owner_id
            FROM AIAgentConversations c
            JOIN Businesses b ON c.business_id = b.id
            WHERE c.id = %s
        """, (conversation_id,))
        
        conv = cursor.fetchone()
        if not conv:
            db.close()
            return jsonify({"error": "Чат не найден"}), 404
        
        conv_owner_id = _row_get(conv, 'owner_id', 3)
        if conv_owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому чату"}), 403
        
        # Сохраняем сообщение
        import uuid
        message_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO AIAgentMessages 
            (id, conversation_id, message_type, content, sender)
            VALUES (%s, %s, 'text', %s, %s)
        """, (message_id, conversation_id, message, sender))
        
        # Обновляем время последнего сообщения
        cursor.execute("""
            UPDATE AIAgentConversations
            SET last_message_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (conversation_id,))
        
        # Отправляем сообщение клиенту через WhatsApp или Telegram
        business_id = _row_get(conv, 'business_id', 0)
        client_phone = _row_get(conv, 'client_phone', 1)
        
        # Получаем настройки бизнеса для отправки
        cursor.execute("""
            SELECT whatsapp_phone_id, whatsapp_access_token, 
                   telegram_bot_token, telegram_chat_id
            FROM Businesses
            WHERE id = %s
        """, (business_id,))
        
        business_settings = cursor.fetchone()
        
        db.conn.commit()
        db.close()
        
        # Отправляем сообщение (если настроены каналы)
        if business_settings:
            whatsapp_phone_id = _row_get(business_settings, 'whatsapp_phone_id', 0)
            whatsapp_token = _row_get(business_settings, 'whatsapp_access_token', 1)
            telegram_token = decode_telegram_bot_token(_row_get(business_settings, 'telegram_bot_token', 2))
            telegram_chat_id = _row_get(business_settings, 'telegram_chat_id', 3)
            
            # Пытаемся отправить через WhatsApp
            if whatsapp_phone_id and whatsapp_token:
                try:
                    from ai_agent_webhooks import send_whatsapp_message
                    send_whatsapp_message(whatsapp_phone_id, whatsapp_token, client_phone, message)
                except Exception as e:
                    print(f"Ошибка отправки WhatsApp: {e}")
            
            # Пытаемся отправить через Telegram
            if telegram_token and telegram_chat_id:
                try:
                    from ai_agent_webhooks import send_telegram_message
                    send_telegram_message(telegram_token, telegram_chat_id, message)
                except Exception as e:
                    print(f"Ошибка отправки Telegram: {e}")
        
        return jsonify({"success": True, "message_id": message_id})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chats_bp.route('/api/conversations/<conversation_id>/toggle-agent', methods=['POST'])
def toggle_agent(conversation_id):
    """Остановить или возобновить работу агента в чате"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        data = request.get_json()
        pause = data.get('pause', True)
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ к чату
        cursor.execute("""
            SELECT c.business_id, b.owner_id
            FROM AIAgentConversations c
            JOIN Businesses b ON c.business_id = b.id
            WHERE c.id = %s
        """, (conversation_id,))
        
        conv = cursor.fetchone()
        if not conv:
            db.close()
            return jsonify({"error": "Чат не найден"}), 404
        
        conv_owner_id = _row_get(conv, 'owner_id', 1)
        if conv_owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому чату"}), 403
        
        # Обновляем статус агента
        cursor.execute("""
            UPDATE AIAgentConversations
            SET is_agent_paused = %s
            WHERE id = %s
        """, (1 if pause else 0, conversation_id))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "is_agent_paused": 1 if pause else 0})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@chats_bp.route('/api/admin/ai-agents/<agent_id>/test', methods=['POST'])
def test_ai_agent(agent_id):
    """Тестирование агента в песочнице (для админа)"""
    try:
        user_data = require_auth()
        if not user_data or not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуется права суперадмина"}), 403
        
        data = request.get_json()
        message = data.get('message', '').strip()
        business_id = data.get('business_id')  # Опционально, для тестирования с реальным бизнесом
        dry_run = bool(data.get('dry_run', True))
        
        if not message:
            return jsonify({"error": "Сообщение не может быть пустым"}), 400
        if not dry_run:
            return jsonify({"error": "Песочница работает только в dry-run режиме (без реальной отправки)"}), 400
        
        bridge_result = _call_openclaw_sandbox_bridge(
            business_id=str(business_id or ""),
            agent_id=str(agent_id or ""),
            message=message,
            conversation_history=[],
            user_data=user_data,
        )
        if bridge_result and bridge_result.get("success") and bridge_result.get("response"):
            return jsonify(bridge_result)

        # Импортируем функции для работы с агентом
        from ai_agent import build_prompt, get_business_info, get_business_services
        from services.gigachat_client import GigaChatClient
        from ai_agent_functions import get_ai_agent_functions
        import json
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Получаем конфигурацию агента
        cursor.execute("""
            SELECT name, type, description, workflow, task, identity, speech_style, restrictions_json, variables_json
            FROM AIAgents
            WHERE id = %s
        """, (agent_id,))
        
        agent_row = cursor.fetchone()
        if not agent_row:
            db.close()
            return jsonify({"error": "Агент не найден"}), 404
        
        # Если указан business_id, используем его данные, иначе создаём тестовые
        if business_id:
            cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
            business_check = cursor.fetchone()
            if not business_check:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            
            business_info = get_business_info(business_id)
            services = get_business_services(business_id)
        else:
            # Тестовые данные
            business_info = {
                'id': 'test_business',
                'name': 'Тестовый салон',
                'address': 'Тестовый адрес',
                'phone': '+79999999999',
                'owner_id': user_data['user_id'],
                'ai_agent_type': agent_row[1]
            }
            services = [
                {'name': 'Стрижка', 'price': 1000, 'duration': 60},
                {'name': 'Окрашивание', 'price': 3000, 'duration': 120}
            ]
        
        # Формируем конфигурацию агента
        workflow_data = agent_row[3]
        # Workflow может быть строкой (YAML) или JSON
        # Если это валидный JSON массив, парсим его, иначе оставляем как строку
        workflow = workflow_data if workflow_data else ''
        if isinstance(workflow_data, str) and workflow_data.strip():
            try:
                # Пытаемся распарсить как JSON
                parsed = json.loads(workflow_data)
                if isinstance(parsed, list):
                    workflow = parsed  # Это JSON массив
                # Иначе оставляем как строку (YAML)
            except:
                # Не валидный JSON - оставляем как строку (YAML)
                pass
        
        agent_config = {
            'workflow': workflow,
            'task': agent_row[4] or '',
            'identity': agent_row[5] or '',
            'speech_style': agent_row[6] or '',
            'restrictions': json.loads(agent_row[7]) if agent_row[7] else {},
            'variables': json.loads(agent_row[8]) if agent_row[8] else {}
        }
        
        # Тестовая история разговора
        conversation_history = []
        
        # Определяем начальный стейт
        default_state = 'greeting'
        # Если workflow это строка (YAML), используем дефолтный стейт
        # Если это список, ищем init_state
        if isinstance(workflow, list) and len(workflow) > 0:
            for state in workflow:
                if isinstance(state, dict) and state.get('init_state'):
                    default_state = state.get('name', 'greeting')
                    break
        elif isinstance(workflow, str) and workflow.strip():
            # Если workflow это YAML текст, пытаемся найти init_state в тексте
            # Или просто используем дефолтный 'greeting'
            if 'init_state: true' in workflow or 'init_state: True' in workflow:
                # Пытаемся извлечь имя стейта с init_state
                import re
                match = re.search(r'- name:\s*(\w+).*?init_state:\s*true', workflow, re.DOTALL | re.IGNORECASE)
                if match:
                    default_state = match.group(1)
        
        # Строим промпт
        prompt = build_prompt(
            business_info,
            services,
            default_state,
            message,
            conversation_history,
            agent_config
        )
        
        # Генерируем ответ через GigaChat
        client = GigaChatClient()
        functions = get_ai_agent_functions()
        
        task_type = 'ai_agent_marketing' if agent_row[1] == 'marketing' else 'ai_agent_booking'
        
        response_text, usage_info = client.analyze_text(
            prompt=prompt,
            task_type=task_type,
            functions=functions,
            business_id=business_info.get('id'),
            user_id=business_info.get('owner_id')
        )
        
        if not response_text:
            response_text = "Извините, произошла ошибка при генерации ответа."
        
        db.close()
        
        return jsonify({
            "success": True,
            "response": response_text,
            "usage": usage_info,
            "state": default_state,
            "dry_run": True,
            "runtime": "local",
            "decision_trace": {},
            "tool_calls": [],
            "bridge_error": bridge_result.get("error") if bridge_result and bridge_result.get("error") else None,
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@chats_bp.route('/api/business/<business_id>/ai-agents/<agent_id>/test', methods=['POST'])
def test_business_ai_agent(business_id, agent_id):
    """Тестирование агента в песочнице (для пользователя)"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        # Проверяем доступ к бизнесу
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        owner_id = _row_get(business, 'owner_id', 0)
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Проверяем, что агент принадлежит бизнесу или доступен (legacy-safe)
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'businesses'
        """)
        business_cols = {str(_row_get(r, 'column_name', 0, '') or '').lower() for r in (cursor.fetchall() or [])}
        ai_agent_id_expr = "ai_agent_id" if 'ai_agent_id' in business_cols else "NULL AS ai_agent_id"
        cursor.execute(f"""
            SELECT {ai_agent_id_expr} FROM Businesses WHERE id = %s
        """, (business_id,))
        business_agent = cursor.fetchone()
        
        business_agent_id = _row_get(business_agent, 'ai_agent_id', 0) if business_agent else None
        if business_agent_id and business_agent_id != agent_id:
            db.close()
            return jsonify({"error": "Агент не принадлежит этому бизнесу"}), 403
        
        data = request.get_json()
        message = data.get('message', '').strip()
        conversation_history = data.get('conversation_history', [])  # История для песочницы
        dry_run = bool(data.get('dry_run', True))
        
        if not message:
            return jsonify({"error": "Сообщение не может быть пустым"}), 400
        if not dry_run:
            return jsonify({"error": "Песочница работает только в dry-run режиме (без реальной отправки)"}), 400
        
        bridge_result = _call_openclaw_sandbox_bridge(
            business_id=str(business_id or ""),
            agent_id=str(agent_id or ""),
            message=message,
            conversation_history=conversation_history,
            user_data=user_data,
        )
        if bridge_result and bridge_result.get("success") and bridge_result.get("response"):
            db.close()
            return jsonify(bridge_result)

        # Импортируем функции для работы с агентом
        from ai_agent import build_prompt, get_business_info, get_business_services
        from services.gigachat_client import GigaChatClient
        from ai_agent_functions import get_ai_agent_functions
        import json
        
        # Получаем конфигурацию агента
        cursor.execute("""
            SELECT name, type, description, workflow, task, identity, speech_style, restrictions_json, variables_json
            FROM AIAgents
            WHERE id = %s
        """, (agent_id,))
        
        agent_row = cursor.fetchone()
        if not agent_row:
            db.close()
            return jsonify({"error": "Агент не найден"}), 404
        
        # Используем данные бизнеса
        business_info = get_business_info(business_id)
        services = get_business_services(business_id)
        
        # Формируем конфигурацию агента
        workflow_data = _row_get(agent_row, 'workflow', 3)
        workflow = workflow_data if workflow_data else ''
        if isinstance(workflow_data, str) and workflow_data.strip():
            try:
                parsed = json.loads(workflow_data)
                if isinstance(parsed, list):
                    workflow = parsed
            except:
                pass
        
        agent_config = {
            'workflow': workflow,
            'task': _row_get(agent_row, 'task', 4) or '',
            'identity': _row_get(agent_row, 'identity', 5) or '',
            'speech_style': _row_get(agent_row, 'speech_style', 6) or '',
            'restrictions': json.loads(_row_get(agent_row, 'restrictions_json', 7)) if _row_get(agent_row, 'restrictions_json', 7) else {},
            'variables': json.loads(_row_get(agent_row, 'variables_json', 8)) if _row_get(agent_row, 'variables_json', 8) else {}
        }
        
        # Определяем начальный стейт
        default_state = 'greeting'
        if isinstance(workflow, list) and len(workflow) > 0:
            for state in workflow:
                if isinstance(state, dict) and state.get('init_state'):
                    default_state = state.get('name', 'greeting')
                    break
        elif isinstance(workflow, str) and workflow.strip():
            if 'init_state: true' in workflow or 'init_state: True' in workflow:
                import re
                match = re.search(r'- name:\s*(\w+).*?init_state:\s*true', workflow, re.DOTALL | re.IGNORECASE)
                if match:
                    default_state = match.group(1)
        
        # Строим промпт
        prompt = build_prompt(
            business_info,
            services,
            default_state,
            message,
            conversation_history,
            agent_config
        )
        
        # Генерируем ответ через GigaChat
        client = GigaChatClient()
        functions = get_ai_agent_functions()
        
        task_type = 'ai_agent_marketing' if _row_get(agent_row, 'type', 1) == 'marketing' else 'ai_agent_booking'
        
        response_text, usage_info = client.analyze_text(
            prompt=prompt,
            task_type=task_type,
            functions=functions,
            business_id=business_id,
            user_id=user_data['user_id']
        )
        
        if not response_text:
            response_text = "Извините, произошла ошибка при генерации ответа."
        
        db.close()
        
        return jsonify({
            "success": True,
            "response": response_text,
            "usage": usage_info,
            "state": default_state,
            "dry_run": True,
            "runtime": "local",
            "decision_trace": {},
            "tool_calls": [],
            "bridge_error": bridge_result.get("error") if bridge_result and bridge_result.get("error") else None,
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
