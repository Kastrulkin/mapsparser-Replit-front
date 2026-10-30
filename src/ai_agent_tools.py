"""
Модуль с реальными tools для ИИ агента
Эти функции вызываются, когда агент использует соответствующие инструменты
"""
import json
import uuid
from datetime import datetime, timedelta
from database_manager import DatabaseManager
from ai_agent_webhooks import send_whatsapp_message, send_telegram_message
import requests
import os

def notify_operator(business_id: str, message: str, conversation_id: str = None, client_phone: str = None, client_name: str = None) -> dict:
    """Place an existing dialogue in the real LocalOS staff inbox and pause AI."""
    if not conversation_id:
        return {'success': False, 'error': 'Для передачи нужен существующий диалог.'}
    from services.client_chat_handoff import request_handoff
    return request_handoff(business_id, conversation_id, message)


def create_booking(business_id: str, client_phone: str, client_name: str, service_id: str = None, 
                   service_name: str = None, booking_date: str = None, booking_time: str = None,
                   notes: str = None, conversation_id: str = None) -> dict:
    """
    Создать бронирование/заказ
    
    Args:
        business_id: ID бизнеса
        client_phone: Телефон клиента
        client_name: Имя клиента
        service_id: ID услуги (опционально)
        service_name: Название услуги (опционально)
        booking_date: Дата бронирования (YYYY-MM-DD)
        booking_time: Время бронирования (HH:MM)
        notes: Дополнительные заметки
        conversation_id: ID разговора (опционально)
    
    Returns:
        dict с результатом создания бронирования
    """
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, подключена ли CRM
        cursor.execute("""
            SELECT crm_type, crm_api_key, crm_api_url
            FROM CRMIntegrations
            WHERE business_id = %s AND is_active = 1
            LIMIT 1
        """, (business_id,))
        crm_row = cursor.fetchone()
        
        booking_id = str(uuid.uuid4())
        
        # Создаём бронирование в нашей БД
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Bookings (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                client_phone TEXT NOT NULL,
                client_name TEXT,
                service_id TEXT,
                service_name TEXT,
                booking_date DATE,
                booking_time TIME,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                conversation_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE,
                FOREIGN KEY (service_id) REFERENCES UserServices(id) ON DELETE SET NULL
            )
        """)
        
        cursor.execute("""
            INSERT INTO Bookings 
            (id, business_id, client_phone, client_name, service_id, service_name, booking_date, booking_time, notes, conversation_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (booking_id, business_id, client_phone, client_name, service_id, service_name, booking_date, booking_time, notes, conversation_id))
        
        # Если подключена CRM, отправляем туда
        if crm_row:
            crm_type = crm_row[0]
            crm_api_key = crm_row[1]
            crm_api_url = crm_row[2]
            
            # TODO: Реализовать интеграцию с различными CRM
            # HubSpot, Zoho, Pipedrive, BlissCRM
            print(f"📝 Отправка бронирования в CRM {crm_type} (TODO: реализовать)")
        
        # Если подключен Google Calendar, создаём событие
        # TODO: Реализовать интеграцию с Google Calendar
        
        db.conn.commit()
        db.close()
        
        return {
            'success': True,
            'booking_id': booking_id,
            'message': 'Бронирование создано'
        }
        
    except Exception as e:
        print(f"❌ Ошибка создания бронирования: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

def send_message_to_client(business_id: str, client_phone: str, message: str, channel: str = 'whatsapp') -> dict:
    """
    Отправить сообщение клиенту через WhatsApp или Telegram
    
    Args:
        business_id: ID бизнеса
        client_phone: Телефон клиента
        message: Текст сообщения
        channel: Канал отправки ('whatsapp' или 'telegram')
    
    Returns:
        dict с результатом отправки
    """
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Получаем credentials для отправки
        cursor.execute("""
            SELECT waba_phone_id, waba_access_token, telegram_bot_token
            FROM Businesses
            WHERE id = %s
        """, (business_id,))
        business_row = cursor.fetchone()
        
        if not business_row:
            db.close()
            return {'success': False, 'error': 'Бизнес не найден'}
        
        waba_phone_id = business_row[0]
        waba_access_token = business_row[1]
        telegram_bot_token = business_row[2]
        
        if channel == 'whatsapp':
            if not waba_phone_id or not waba_access_token:
                return {'success': False, 'error': 'WhatsApp не настроен для этого бизнеса'}
            
            success = send_whatsapp_message(
                phone_id=waba_phone_id,
                access_token=waba_access_token,
                to=client_phone,
                message=message
            )
            
            if success:
                return {'success': True, 'message': 'Сообщение отправлено через WhatsApp'}
            else:
                return {'success': False, 'error': 'Ошибка отправки через WhatsApp'}
            
        elif channel == 'telegram':
            if not telegram_bot_token:
                return {'success': False, 'error': 'Telegram бот не настроен для этого бизнеса'}
            
            # TODO: Реализовать отправку через пользовательский Telegram бот
            # Нужно получить telegram_id клиента по телефону или другим способом
            return {'success': False, 'error': 'Отправка через Telegram пока не реализована'}
        
        else:
            return {'success': False, 'error': f'Неизвестный канал: {channel}'}
            
    except Exception as e:
        print(f"❌ Ошибка отправки сообщения клиенту: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

def get_client_info(business_id: str, client_phone: str) -> dict:
    """
    Получить информацию о клиенте (история, предпочтения)
    
    Args:
        business_id: ID бизнеса
        client_phone: Телефон клиента
    
    Returns:
        dict с информацией о клиенте
    """
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Получаем историю разговоров
        cursor.execute("""
            SELECT id, current_state, last_message_at, created_at
            FROM AIAgentConversations
            WHERE business_id = %s AND client_phone = %s
            ORDER BY last_message_at DESC
            LIMIT 5
        """, (business_id, client_phone))
        conversations = cursor.fetchall()
        
        # Получаем историю бронирований
        cursor.execute("""
            SELECT id, service_name, booking_date, booking_time, status, created_at
            FROM Bookings
            WHERE business_id = %s AND client_phone = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (business_id, client_phone))
        bookings = cursor.fetchall()
        
        db.close()
        
        return {
            'success': True,
            'client_phone': client_phone,
            'conversations_count': len(conversations),
            'bookings_count': len(bookings),
            'recent_bookings': [
                {
                    'service': b[2],
                    'date': b[3],
                    'time': b[4],
                    'status': b[5]
                } for b in bookings
            ] if bookings else []
        }
        
    except Exception as e:
        print(f"❌ Ошибка получения информации о клиенте: {e}")
        return {'success': False, 'error': str(e)}

def get_services(business_id: str) -> dict:
    """
    Получить список услуг бизнеса
    
    Args:
        business_id: ID бизнеса
    
    Returns:
        dict со списком услуг
    """
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description, price, duration
            FROM UserServices
            WHERE business_id = %s
            ORDER BY name
        """, (business_id,))
        services = cursor.fetchall()
        
        db.close()
        
        return {
            'success': True,
            'services': [
                {
                    'id': s[0],
                    'name': s[1],
                    'description': s[2],
                    'price': s[3] / 100 if s[3] else None,  # Конвертируем из центов
                    'duration': s[4]
                } for s in services
            ]
        }
        
    except Exception as e:
        print(f"❌ Ошибка получения услуг: {e}")
        return {'success': False, 'error': str(e)}

def check_availability(business_id: str, date: str, service_duration: int = None) -> dict:
    """
    Проверить доступное время для записи
    
    Args:
        business_id: ID бизнеса
        date: Дата для проверки (YYYY-MM-DD)
        service_duration: Длительность услуги в минутах (опционально)
    
    Returns:
        dict с доступными временными слотами
    """
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Получаем существующие бронирования на эту дату
        cursor.execute("""
            SELECT booking_time, service_id
            FROM Bookings
            WHERE business_id = %s AND booking_date = %s AND status IN ('pending', 'confirmed')
        """, (business_id, date))
        existing_bookings = cursor.fetchall()
        
        # Простая логика: рабочие часы 9:00 - 18:00, слоты по 30 минут
        # TODO: Получить реальные рабочие часы из настроек бизнеса
        work_start = 9  # 9:00
        work_end = 18   # 18:00
        slot_duration = service_duration or 30  # Длительность слота в минутах
        
        booked_times = [b[0] for b in existing_bookings if b[0]]
        
        available_slots = []
        current_hour = work_start
        while current_hour < work_end:
            time_str = f"{current_hour:02d}:00"
            if time_str not in booked_times:
                available_slots.append(time_str)
            current_hour += 1
        
        db.close()
        
        return {
            'success': True,
            'date': date,
            'available_slots': available_slots[:3],  # Возвращаем первые 3 доступных слота
            'total_available': len(available_slots)
        }
        
    except Exception as e:
        print(f"❌ Ошибка проверки доступности: {e}")
        return {'success': False, 'error': str(e)}

# Маппинг названий tools на функции
TOOLS_MAP = {
    'notify_operator': notify_operator,
    'create_booking': create_booking,
    'send_message': send_message_to_client,
    'get_client_info': get_client_info,
    'get_services': get_services,
    'check_availability': check_availability,
}

def execute_tool(tool_name: str, business_id: str, **kwargs) -> dict:
    """
    Выполнить tool по имени
    
    Args:
        tool_name: Название tool
        business_id: ID бизнеса
        **kwargs: Параметры для tool
    
    Returns:
        dict с результатом выполнения
    """
    if tool_name not in TOOLS_MAP:
        return {'success': False, 'error': f'Неизвестный tool: {tool_name}'}
    
    tool_func = TOOLS_MAP[tool_name]
    try:
        return tool_func(business_id=business_id, **kwargs)
    except Exception as e:
        print(f"❌ Ошибка выполнения tool {tool_name}: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

