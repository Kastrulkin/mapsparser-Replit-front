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
import json

chats_bp = Blueprint('chats', __name__)

def require_auth():
    """Проверка авторизации"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    return user_data

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
        
        if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Получаем конфигурацию агентов (новый формат)
        cursor.execute("""
            SELECT ai_agents_config 
            FROM Businesses 
            WHERE id = %s
        """, (business_id,))
        business_data = cursor.fetchone()
        
        agents = []
        
        # Пытаемся загрузить из нового формата
        if business_data and business_data[0]:
            try:
                agents_config = json.loads(business_data[0])
                
                # Для каждого включенного агента получаем его данные
                for agent_key, config in agents_config.items():
                    if config.get('enabled'):
                        # Определяем тип агента из ключа (booking_agent -> booking)
                        agent_type = agent_key.replace('_agent', '')
                        
                        # Если указан конкретный agent_id, загружаем его
                        if config.get('agent_id'):
                            cursor.execute("""
                                SELECT id, name, type, description
                                FROM AIAgents
                                WHERE id = %s
                            """, (config['agent_id'],))
                            agent = cursor.fetchone()
                            
                            if agent:
                                agents.append({
                                    'id': agent[0],
                                    'name': agent[1],
                                    'type': agent[2],
                                    'description': agent[3]
                                })
                        else:
                            # Используем дефолтного агента для типа
                            cursor.execute("""
                                SELECT id, name, type, description
                                FROM AIAgents
                                WHERE type = %s AND is_active = 1
                                ORDER BY id
                                LIMIT 1
                            """, (agent_type,))
                            agent = cursor.fetchone()
                            
                            if agent:
                                agents.append({
                                    'id': agent[0],
                                    'name': agent[1],
                                    'type': agent[2],
                                    'description': agent[3]
                                })
            except (json.JSONDecodeError, TypeError) as e:
                print(f"⚠️ Ошибка парсинга ai_agents_config: {e}")
        
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
        
        if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Получаем чаты для этого бизнеса и агента
        cursor.execute("""
            SELECT 
                c.id,
                c.client_phone,
                c.client_name,
                c.current_state,
                c.last_message_at,
                COALESCE(c.is_agent_paused, 0) as is_agent_paused,
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
                'id': row[0],
                'client_phone': row[1],
                'client_name': row[2],
                'current_state': row[3],
                'last_message_at': row[4],
                'is_agent_paused': row[5],
                'unread_count': row[6] or 0
            })
        
        db.close()
        return jsonify({"success": True, "conversations": conversations})
        
    except Exception as e:
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
        
        if conv[1] != user_data['user_id'] and not user_data.get('is_superadmin'):
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
                'id': row[0],
                'content': row[1],
                'sender': row[2],
                'message_type': row[3],
                'created_at': row[4]
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
        
        if conv[3] != user_data['user_id'] and not user_data.get('is_superadmin'):
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
        business_id = conv[0]
        client_phone = conv[1]
        
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
            whatsapp_phone_id = business_settings[0]
            whatsapp_token = business_settings[1]
            telegram_token = business_settings[2]
            telegram_chat_id = business_settings[3]
            
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
        
        if conv[1] != user_data['user_id'] and not user_data.get('is_superadmin'):
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
        
        if not message:
            return jsonify({"error": "Сообщение не может быть пустым"}), 400
        
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
            "state": default_state
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
        
        if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Проверяем, что агент принадлежит бизнесу или доступен
        cursor.execute("""
            SELECT ai_agent_id FROM Businesses WHERE id = %s
        """, (business_id,))
        business_agent = cursor.fetchone()
        
        if business_agent and business_agent[0] != agent_id:
            db.close()
            return jsonify({"error": "Агент не принадлежит этому бизнесу"}), 403
        
        data = request.get_json()
        message = data.get('message', '').strip()
        conversation_history = data.get('conversation_history', [])  # История для песочницы
        
        if not message:
            return jsonify({"error": "Сообщение не может быть пустым"}), 400
        
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
        workflow_data = agent_row[3]
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
            'task': agent_row[4] or '',
            'identity': agent_row[5] or '',
            'speech_style': agent_row[6] or '',
            'restrictions': json.loads(agent_row[7]) if agent_row[7] else {},
            'variables': json.loads(agent_row[8]) if agent_row[8] else {}
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
        
        task_type = 'ai_agent_marketing' if agent_row[1] == 'marketing' else 'ai_agent_booking'
        
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
            "state": default_state
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

