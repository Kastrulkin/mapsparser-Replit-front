"""
ИИ агент для автоматического консультирования клиентов
Использует захардкоженные стейты разговора и настраиваемые промпты
"""
import os
import json
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
            SELECT ai_agent_type, ai_agent_id, ai_agent_tone, ai_agent_restrictions
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
        try:
            business_restrictions = json.loads(restrictions_raw) if restrictions_raw else {}
        except Exception:
            business_restrictions = {}
        
        # Если указан конкретный агент, получаем его конфигурацию
        if agent_id:
            cursor.execute("""
                SELECT states_json, restrictions_json, personality
                FROM AIAgents
                WHERE id = ? AND is_active = 1
            """, (agent_id,))
            agent_row = cursor.fetchone()
            
            if agent_row:
                agent_restrictions = json.loads(agent_row[1]) if agent_row[1] else {}
                merged_restrictions = {**agent_restrictions, **business_restrictions}
                return {
                    'states': json.loads(agent_row[0]) if agent_row[0] else {},
                    'restrictions': merged_restrictions,
                    'personality': agent_row[2] or '',
                    'tone': tone
                }
        
        # Иначе получаем дефолтного агента по типу
        cursor.execute("""
            SELECT states_json, restrictions_json, personality
            FROM AIAgents
            WHERE type = ? AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        """, (agent_type,))
        agent_row = cursor.fetchone()
        
        if agent_row:
            agent_restrictions = json.loads(agent_row[1]) if agent_row[1] else {}
            merged_restrictions = {**agent_restrictions, **business_restrictions}
            return {
                'states': json.loads(agent_row[0]) if agent_row[0] else {},
                'restrictions': merged_restrictions,
                'personality': agent_row[2] or '',
                'tone': tone
            }
        
        # Если агент не найден, возвращаем конфигурацию только с бизнес-ограничениями
        return {
            'states': {},
            'restrictions': business_restrictions,
            'personality': '',
            'tone': tone
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
            SELECT name, address, city, phone, email, ai_agent_type, ai_agent_tone, ai_agent_restrictions
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
            'tone': row[5] or 'professional',
            'restrictions': restrictions.get('text', '')
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
    """Построить промпт для ИИ на основе workflow структуры"""
    
    # Получаем workflow и текущий стейт
    workflow = agent_config.get('workflow', [])
    current_state_config = None
    for state in workflow:
        if state.get('name') == current_state:
            current_state_config = state
            break
    
    # Если стейт не найден, используем первый init_state или первый стейт
    if not current_state_config:
        for state in workflow:
            if state.get('init_state'):
                current_state_config = state
                current_state = state.get('name', current_state)
                break
        if not current_state_config and workflow:
            current_state_config = workflow[0]
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
    if speech_style:
        prompt += f"##### **Стиль речи:**\n{speech_style}\n\n"
    
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
    
    # Текущий стейт
    if current_state_config:
        prompt += f"##### **Текущий стейт:** {current_state_config.get('name', current_state)}\n"
        description = current_state_config.get('description', '')
        if description:
            prompt += f"{description}\n\n"
        
        # Доступные переходы
        scenarios = current_state_config.get('state_scenarios', [])
        if scenarios:
            prompt += f"##### **Возможные переходы:**\n"
            for scenario in scenarios:
                prompt += f"- {scenario.get('transition_name', '')}: {scenario.get('description', '')} → {scenario.get('next_state', '')}\n"
            prompt += "\n"
        
        # Доступные инструменты
        tools = current_state_config.get('available_tools', {})
        if tools:
            prompt += f"##### **Доступные инструменты:**\n"
            for tool_type, tool_list in tools.items():
                prompt += f"- {tool_type}: {', '.join(tool_list)}\n"
            prompt += "\n"
    
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
    prompt += "Ответь на сообщение клиента, учитывая текущий стейт, задачи, ограничения и историю разговора.\n"
    prompt += "Следуй стилю речи, указанному выше.\n"
    
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
        default_state = None
        for state in workflow:
            if state.get('init_state'):
                default_state = state.get('name')
                break
        if not default_state and workflow:
            default_state = workflow[0].get('name', 'greeting')
        if not default_state:
            default_state = 'greeting'
        
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
        
        # Сохраняем ответ агента
        save_message(conversation_id, 'text', response_text, 'agent')
        conversation_history.append({'sender': 'agent', 'content': response_text, 'timestamp': datetime.now().isoformat()})
        
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
            'response': response_text,
            'conversation_id': conversation_id,
            'state': next_state
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

