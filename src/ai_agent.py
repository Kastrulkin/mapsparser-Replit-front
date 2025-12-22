"""
ИИ агент для автоматического консультирования клиентов
Использует захардкоженные стейты разговора и настраиваемые промпты
"""
import os
import json
import re
import uuid
from datetime import datetime
from database_manager import DatabaseManager
from services.gigachat_client import get_gigachat_client

def get_agent_config(business_id: str) -> dict:
    """Получить конфигурацию агента для бизнеса"""
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        # Получаем тип агента и ID агента из бизнеса
        cursor.execute("""
            SELECT ai_agent_type, ai_agent_id, ai_agent_tone, ai_agent_restrictions, ai_agent_language
            FROM Businesses
            WHERE id = ?
        """, (business_id,))
        row = cursor.fetchone()
        
        if not row:
            return {}
        
        agent_type = row[0] or 'booking'
        agent_id = row[1]
        tone = row[2] or 'professional'
        restrictions_raw = row[3] or '{}'
        language = row[4] or 'ru'  # По умолчанию русский
        try:
            business_restrictions = json.loads(restrictions_raw) if restrictions_raw else {}
        except Exception:
            business_restrictions = {}
        
        # Если указан конкретный агент, получаем его конфигурацию
        if agent_id:
            cursor.execute("""
                SELECT workflow_json, task, identity, speech_style, restrictions_json
                FROM AIAgents
                WHERE id = ? AND is_active = 1
            """, (agent_id,))
            agent_row = cursor.fetchone()
            
            if agent_row:
                agent_restrictions = json.loads(agent_row[4]) if agent_row[4] else {}
                merged_restrictions = {**agent_restrictions, **business_restrictions}
                
                # Пытаемся определить, это JSON или текст
                workflow_raw = agent_row[0] or ''
                workflow_value = workflow_raw
                if workflow_raw:
                    try:
                        # Если это валидный JSON массив, парсим его
                        parsed = json.loads(workflow_raw)
                        if isinstance(parsed, list):
                            workflow_value = parsed
                        else:
                            workflow_value = workflow_raw  # Оставляем как текст
                    except:
                        workflow_value = workflow_raw  # Оставляем как текст
                
                return {
                    'workflow': workflow_value,
                    'task': agent_row[1] or '',
                    'identity': agent_row[2] or '',
                    'speech_style': agent_row[3] or '',
                    'restrictions': merged_restrictions,
                    'tone': tone,
                    'language': language
                }
        
        # Иначе получаем дефолтного агента по типу
        cursor.execute("""
            SELECT workflow_json, task, identity, speech_style, restrictions_json
            FROM AIAgents
            WHERE type = ? AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        """, (agent_type,))
        agent_row = cursor.fetchone()
        
        if agent_row:
            agent_restrictions = json.loads(agent_row[4]) if agent_row[4] else {}
            merged_restrictions = {**agent_restrictions, **business_restrictions}
            
            # Пытаемся определить, это JSON или текст
            workflow_raw = agent_row[0] or ''
            workflow_value = workflow_raw
            if workflow_raw:
                try:
                    # Если это валидный JSON массив, парсим его
                    parsed = json.loads(workflow_raw)
                    if isinstance(parsed, list):
                        workflow_value = parsed
                    else:
                        workflow_value = workflow_raw  # Оставляем как текст
                except:
                    workflow_value = workflow_raw  # Оставляем как текст
            
            return {
                'workflow': workflow_value,
                'task': agent_row[1] or '',
                'identity': agent_row[2] or '',
                'speech_style': agent_row[3] or '',
                'restrictions': merged_restrictions,
                'tone': tone,
                'language': language
            }
        
        # Если агент не найден, возвращаем конфигурацию только с бизнес-ограничениями
        return {
            'workflow': [],
            'task': '',
            'identity': '',
            'speech_style': '',
            'restrictions': business_restrictions,
            'tone': tone,
            'language': language
        }
    finally:
        db.close()

def get_business_services(business_id: str) -> list:
    """Получить список услуг бизнеса"""
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id, name, price, duration, description
            FROM UserServices
            WHERE business_id = ?
            ORDER BY name
        """, (business_id,))
        rows = cursor.fetchall()
        services = []
        for row in rows:
            services.append({
                'id': row[0],
                'name': row[1],
                'price': row[2] / 100 if row[2] else None,  # Конвертируем из центов
                'duration': row[3],
                'description': row[4]
            })
        return services
    finally:
        db.close()

def get_business_info(business_id: str) -> dict:
    """Получить информацию о бизнесе"""
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT name, address, city, phone, email, ai_agent_type, ai_agent_tone, ai_agent_restrictions, ai_agent_language
            FROM Businesses
            WHERE id = ?
        """, (business_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        
        restrictions = {}
        if row[7]:
            try:
                restrictions = json.loads(row[7])
            except:
                restrictions = {'text': row[7]}
        
        return {
            'name': row[0],
            'address': row[1],
            'city': row[2],
            'phone': row[3],
            'email': row[4],
            'ai_agent_type': row[5] or 'booking',
            'tone': row[6] or 'professional',
            'restrictions': restrictions.get('text', ''),
            'language': row[8] or 'ru'  # По умолчанию русский
        }
    finally:
        db.close()

def get_or_create_conversation(business_id: str, client_phone: str, client_name: str = None) -> str:
    """Получить или создать разговор"""
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        
        # Ищем существующий разговор
        cursor.execute("""
            SELECT id, current_state, conversation_history
            FROM AIAgentConversations
            WHERE business_id = ? AND client_phone = ?
            ORDER BY last_message_at DESC
            LIMIT 1
        """, (business_id, client_phone))
        
        row = cursor.fetchone()
        
        if row:
            conversation_id = row[0]
            # Обновляем время последнего сообщения
            cursor.execute("""
                UPDATE AIAgentConversations
                SET last_message_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (conversation_id,))
            db.conn.commit()
            return conversation_id
        else:
            # Создаём новый разговор
            conversation_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO AIAgentConversations 
                (id, business_id, client_phone, client_name, current_state, conversation_history)
                VALUES (?, ?, ?, ?, 'greeting', ?)
            """, (conversation_id, business_id, client_phone, client_name, json.dumps([])))
            db.conn.commit()
            return conversation_id
    finally:
        db.close()

def save_message(conversation_id: str, message_type: str, content: str, sender: str):
    """Сохранить сообщение в историю"""
    db = DatabaseManager()
    try:
        message_id = str(uuid.uuid4())
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO AIAgentMessages 
            (id, conversation_id, message_type, content, sender)
            VALUES (?, ?, ?, ?, ?)
        """, (message_id, conversation_id, message_type, content, sender))
        db.conn.commit()
    finally:
        db.close()

def update_conversation_state(conversation_id: str, new_state: str):
    """Обновить стейт разговора"""
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE AIAgentConversations
            SET current_state = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_state, conversation_id))
        db.conn.commit()
    finally:
        db.close()

def build_prompt(business_info: dict, services: list, current_state: str, message: str, conversation_history: list, agent_config: dict) -> str:
    """Построить промпт для ИИ на основе workflow (текст или структура)"""
    
    # Получаем workflow (может быть строкой или структурой)
    workflow = agent_config.get('workflow', [])
    workflow_text = None
    workflow_structure = None
    
    if isinstance(workflow, str):
        # Workflow как текст - используем напрямую
        workflow_text = workflow
    elif isinstance(workflow, list) and len(workflow) > 0:
        # Workflow как структура - ищем текущий стейт
        workflow_structure = workflow
        current_state_config = None
        for state in workflow:
            if isinstance(state, dict) and state.get('name') == current_state:
                current_state_config = state
                break
        
        # Если стейт не найден, используем первый init_state или первый стейт
        if not current_state_config:
            for state in workflow:
                if isinstance(state, dict) and state.get('init_state'):
                    current_state_config = state
                    current_state = state.get('name', current_state)
                    break
            if not current_state_config and workflow:
                current_state_config = workflow[0] if isinstance(workflow[0], dict) else None
                if current_state_config:
                    current_state = current_state_config.get('name', current_state)
    
    # Строим промпт
    prompt = ""
    
    # Identity (личность агента)
    identity = agent_config.get('identity', '')
    if identity:
        prompt += f"{identity}\n\n"
    
    # Task (задачи агента)
    task = agent_config.get('task', '')
    if task:
        prompt += f"##### **Задачи:**\n{task}\n\n"
    
    # Speech style (стиль речи)
    speech_style = agent_config.get('speech_style', '')
    language = agent_config.get('language', 'ru')
    
    # Маппинг кодов языков на названия
    language_names = {
        'ru': 'Russian',
        'en': 'English',
        'es': 'Spanish',
        'de': 'German',
        'fr': 'French',
        'it': 'Italian',
        'pt': 'Portuguese',
        'zh': 'Chinese'
    }
    language_name = language_names.get(language, 'Russian')
    
    if speech_style:
        # Заменяем упоминания языка в speech_style на выбранный язык
        speech_style_modified = re.sub(
            r'in\s+(Russian|English|Spanish|German|French|Italian|Portuguese|Chinese)',
            f'in {language_name}',
            speech_style,
            flags=re.IGNORECASE
        )
        speech_style_modified = re.sub(
            r'Write\s+your\s+thoughts\s+and\s+actions\s+in\s+(Russian|English|Spanish|German|French|Italian|Portuguese|Chinese)',
            f'Write your thoughts and actions in {language_name}',
            speech_style_modified,
            flags=re.IGNORECASE
        )
        prompt += f"##### **Стиль речи:**\n{speech_style_modified}\n\n"
    
    # Workflow (если это текст, вставляем целиком)
    if workflow_text:
        prompt += f"##### **Workflow:**\n{workflow_text}\n\n"
    elif workflow_structure and current_state_config:
        # Если workflow - структура, используем старую логику
        prompt += f"##### **Текущий стейт:** {current_state_config.get('name', current_state)}\n"
        description = current_state_config.get('description', '')
        if description:
            prompt += f"{description}\n\n"
        
        scenarios = current_state_config.get('state_scenarios', [])
        if scenarios:
            prompt += f"##### **Возможные переходы:**\n"
            for scenario in scenarios:
                prompt += f"- {scenario.get('transition_name', '')}: {scenario.get('description', '')} → {scenario.get('next_state', '')}\n"
            prompt += "\n"
        
        tools = current_state_config.get('available_tools', {})
        if tools:
            prompt += f"##### **Доступные инструменты:**\n"
            for tool_type, tool_list in tools.items():
                prompt += f"- {tool_type}: {', '.join(tool_list)}\n"
            prompt += "\n"
    
    # Информация о бизнесе
    prompt += f"##### **Информация о бизнесе:**\n"
    prompt += f"- Название: {business_info.get('name', 'Не указано')}\n"
    prompt += f"- Адрес: {business_info.get('address', 'Не указано')}, {business_info.get('city', 'Не указано')}\n"
    prompt += f"- Телефон: {business_info.get('phone', 'Не указано')}\n"
    if business_info.get('email'):
        prompt += f"- Email: {business_info.get('email')}\n"
    prompt += "\n"
    
    # Услуги
    if services:
        prompt += f"##### **Доступные услуги:**\n"
        for service in services:
            price_str = f"${service['price']}" if service['price'] else "Цена по запросу"
            duration_str = f"{service['duration']} мин" if service['duration'] else ""
            prompt += f"- {service['name']}: {price_str} {duration_str}\n"
            if service.get('description'):
                prompt += f"  Описание: {service['description']}\n"
        prompt += "\n"
    
    # Ограничения
    restrictions = agent_config.get('restrictions', {})
    if restrictions.get('text'):
        prompt += f"##### **Ограничения:**\n{restrictions['text']}\n\n"
    
    # Доступные tools (всегда добавляем список доступных tools)
    prompt += f"##### **Доступные инструменты (tools):**\n"
    prompt += "- notify_operator: Уведомить оператора о необходимости его участия. Используй, когда нужна помощь человека.\n"
    prompt += "- create_booking: Создать бронирование/заказ. Параметры: service_id, service_name, booking_date, booking_time, notes.\n"
    prompt += "- send_message: Отправить сообщение клиенту через WhatsApp/Telegram. Параметры: message, channel (whatsapp/telegram).\n"
    prompt += "- get_client_info: Получить информацию о клиенте (история, бронирования).\n"
    prompt += "- get_services: Получить список услуг бизнеса.\n"
    prompt += "- check_availability: Проверить доступное время для записи. Параметры: date (YYYY-MM-DD), service_duration (минуты).\n"
    prompt += "\n"
    prompt += "**Важно:** Если тебе нужно использовать tool, укажи это в ответе в формате:\n"
    prompt += "```json\n"
    prompt += "{\"tool\": \"tool_name\", \"params\": {\"param1\": \"value1\", \"param2\": \"value2\"}}\n"
    prompt += "```\n"
    prompt += "После использования tool, продолжай общение с клиентом.\n\n"
    
    # История разговора
    prompt += f"##### **История разговора:**\n"
    if conversation_history:
        for msg in conversation_history[-5:]:  # Последние 5 сообщений
            sender = msg.get('sender', 'unknown')
            content = msg.get('content', '')
            prompt += f"- {sender}: {content}\n"
    else:
        prompt += "Это начало разговора.\n"
    prompt += "\n"
    
    # Сообщение клиента
    prompt += f"##### **Сообщение клиента:**\n{message}\n\n"
    
    # Инструкция
    prompt += "Ответь на сообщение клиента, учитывая workflow, задачи, ограничения и историю разговора.\n"
    prompt += "Следуй стилю речи, указанному выше.\n"
    prompt += "Если нужно использовать tool, укажи это в формате JSON, как описано выше.\n"
    
    return prompt

def process_message(business_id: str, client_phone: str, client_name: str, message: str) -> dict:
    """Обработать сообщение от клиента и сгенерировать ответ"""
    try:
        # Получаем или создаём разговор
        conversation_id = get_or_create_conversation(business_id, client_phone, client_name)
        
        # Получаем информацию о бизнесе и услугах
        business_info = get_business_info(business_id)
        services = get_business_services(business_id)
        
        # Получаем конфигурацию агента
        agent_config = get_agent_config(business_id)
        
        # Получаем текущий стейт и историю
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT current_state, conversation_history
            FROM AIAgentConversations
            WHERE id = ?
        """, (conversation_id,))
        row = cursor.fetchone()
        db.close()
        
        # Определяем начальный стейт из конфигурации агента
        workflow = agent_config.get('workflow', [])
        default_state = 'greeting'  # По умолчанию
        
        # Если workflow - это структура (список), ищем init_state
        if isinstance(workflow, list) and len(workflow) > 0:
            for state in workflow:
                if isinstance(state, dict) and state.get('init_state'):
                    default_state = state.get('name', 'greeting')
                    break
            if default_state == 'greeting' and workflow:
                first_state = workflow[0]
                if isinstance(first_state, dict):
                    default_state = first_state.get('name', 'greeting')
        
        current_state = row[0] if row and row[0] else default_state
        conversation_history = json.loads(row[1]) if row and row[1] else []
        
        # Сохраняем сообщение клиента
        save_message(conversation_id, 'text', message, 'client')
        conversation_history.append({'sender': 'client', 'content': message, 'timestamp': datetime.now().isoformat()})
        
        # Строим промпт
        prompt = build_prompt(business_info, services, current_state, message, conversation_history, agent_config)
        
        # Определяем тип задачи для выбора модели GigaChat
        agent_type = business_info.get('ai_agent_type', 'booking')
        if agent_type == 'marketing':
            task_type = 'ai_agent_marketing'
        elif agent_type == 'booking':
            # Для агента записи используем Pro по умолчанию
            # Можно добавить логику для определения сложности и использования Max
            task_type = 'ai_agent_booking'
        else:
            task_type = 'ai_agent_booking'  # По умолчанию
        
        # Генерируем ответ через GigaChat
        try:
            client = get_gigachat_client()
            response_text = client.analyze_text(prompt, task_type=task_type)
            
            if not response_text:
                response_text = "Извините, произошла ошибка. Пожалуйста, попробуйте позже или свяжитесь с нами по телефону."
        except Exception as e:
            print(f"❌ Ошибка генерации ответа через GigaChat: {e}")
            response_text = "Извините, произошла ошибка. Пожалуйста, попробуйте позже или свяжитесь с нами по телефону."
        
        # Парсим и выполняем tools из ответа
        from ai_agent_tools import execute_tool
        tools_executed = []
        final_response_text = response_text
        
        # Ищем JSON блоки с вызовами tools
        import re
        tool_pattern = r'```json\s*\{\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"params"\s*:\s*(\{[^}]+\})\s*\}\s*```'
        tool_matches = re.finditer(tool_pattern, response_text, re.IGNORECASE | re.DOTALL)
        
        for match in tool_matches:
            tool_name = match.group(1)
            params_json = match.group(2)
            
            try:
                params = json.loads(params_json)
                # Выполняем tool
                tool_result = execute_tool(
                    tool_name=tool_name,
                    business_id=business_id,
                    client_phone=client_phone,
                    client_name=client_name,
                    conversation_id=conversation_id,
                    **params
                )
                
                tools_executed.append({
                    'tool': tool_name,
                    'params': params,
                    'result': tool_result
                })
                
                # Удаляем JSON блок из ответа
                final_response_text = final_response_text.replace(match.group(0), '')
                
                print(f"✅ Tool {tool_name} выполнен: {tool_result}")
                
            except Exception as e:
                print(f"❌ Ошибка выполнения tool {tool_name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Очищаем лишние пробелы и переносы строк
        final_response_text = re.sub(r'\n\s*\n\s*\n', '\n\n', final_response_text).strip()
        
        # Сохраняем ответ агента (без JSON блоков с tools)
        save_message(conversation_id, 'text', final_response_text, 'agent')
        conversation_history.append({'sender': 'agent', 'content': final_response_text, 'timestamp': datetime.now().isoformat()})
        
        # Сохраняем информацию о выполненных tools
        if tools_executed:
            save_message(conversation_id, 'tool', json.dumps(tools_executed, ensure_ascii=False), 'agent')
        
        # Обновляем историю и стейт (простая логика определения следующего стейта)
        # В будущем можно использовать ИИ для определения следующего стейта
        next_state = determine_next_state(current_state, message, response_text, agent_config)
        if next_state != current_state:
            update_conversation_state(conversation_id, next_state)
        
        # Обновляем историю разговора
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE AIAgentConversations
            SET conversation_history = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (json.dumps(conversation_history), conversation_id))
        db.conn.commit()
        db.close()
        
        return {
            'success': True,
            'response': final_response_text,
            'conversation_id': conversation_id,
            'state': next_state,
            'tools_executed': tools_executed
        }
        
    except Exception as e:
        print(f"❌ Ошибка обработки сообщения: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'response': 'Извините, произошла ошибка. Пожалуйста, попробуйте позже.'
        }

def determine_next_state(current_state: str, client_message: str, agent_response: str, agent_config: dict) -> str:
    """Определить следующий стейт разговора на основе workflow scenarios"""
    workflow = agent_config.get('workflow', [])
    
    # Находим текущий стейт в workflow
    current_state_config = None
    for state in workflow:
        if state.get('name') == current_state:
            current_state_config = state
            break
    
    if not current_state_config:
        return current_state
    
    # Получаем scenarios для текущего стейта
    scenarios = current_state_config.get('state_scenarios', [])
    
    # Если нет scenarios, остаёмся в текущем стейте
    if not scenarios:
        return current_state
    
    message_lower = client_message.lower()
    
    # Простая логика определения следующего стейта на основе ключевых слов
    # В будущем можно использовать ИИ для более точного определения
    if current_state == 'greeting' or not current_state:
        if any(word in message_lower for word in ['услуг', 'что', 'какие', 'предлага']):
            return 'service_inquiry'
        elif any(word in message_lower for word in ['запис', 'хочу', 'можно']):
            return 'booking'
        elif any(word in message_lower for word in ['цена', 'стоимость', 'сколько']):
            return 'pricing'
    
    elif current_state == 'service_inquiry':
        if any(word in message_lower for word in ['запис', 'хочу', 'можно', 'давай']):
            return 'booking'
        elif any(word in message_lower for word in ['цена', 'стоимость', 'сколько']):
            return 'pricing'
        elif any(word in message_lower for word in ['спасибо', 'до свидания', 'пока']):
            return 'goodbye'
    
    elif current_state == 'booking':
        if any(word in message_lower for word in ['подтвержд', 'да', 'соглас', 'ок']):
            return 'confirmation'
        elif any(word in message_lower for word in ['цена', 'стоимость', 'сколько']):
            return 'pricing'
    
    elif current_state == 'confirmation':
        return 'goodbye'
    
    elif current_state in ['pricing', 'service_inquiry']:
        if any(word in message_lower for word in ['спасибо', 'до свидания', 'пока', 'всё']):
            return 'goodbye'
    
    return current_state  # Остаёмся в текущем стейте, если не определили переход

