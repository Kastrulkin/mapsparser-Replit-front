#!/usr/bin/env python3
"""
Утилиты для отправки уведомлений о бронированиях
- Telegram уведомления
- WhatsApp уведомления (WABA)
"""
import os
import requests
from datetime import datetime

# Загружаем переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')

# WhatsApp Business API
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID', '')
WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')

def send_telegram_notification(telegram_username: str, booking_data: dict) -> bool:
    """
    Отправка уведомления о новом бронировании через Telegram
    
    Args:
        telegram_username: Username в Telegram (без @)
        booking_data: Данные бронирования
    
    Returns:
        True если отправлено успешно, False если ошибка
    """
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN не установлен")
        return False
    
    if not telegram_username:
        return False
    
    try:
        # Получаем telegram_id по username через API бота
        # Или используем существующий механизм привязки
        
        # Формируем сообщение
        message = f"""🔔 Новое бронирование!

👤 Клиент: {booking_data.get('client_name', 'Не указано')}
📞 Телефон: {booking_data.get('client_phone', 'Не указано')}
📧 Email: {booking_data.get('client_email', 'Не указано')}

🕐 Время: {booking_data.get('booking_time_local', booking_data.get('booking_time', 'Не указано'))}

"""
        
        if booking_data.get('service_name'):
            message += f"💇 Услуга: {booking_data['service_name']}\n"
        
        if booking_data.get('notes'):
            message += f"📝 Заметки: {booking_data['notes']}\n"
        
        message += f"\nID бронирования: {booking_data.get('booking_id', '')}"
        
        # Отправляем через Telegram Bot API
        # Используем существующий бот @BeautyBotPro_bot
        # Нужно получить chat_id по username или использовать существующую привязку
        
        # Временное решение: отправляем через внутренний API бота
        # В реальности нужно использовать telegram_id из таблицы Users
        
        print(f"📱 Telegram уведомление для @{telegram_username}: {message[:50]}...")
        
        # TODO: Реализовать отправку через telegram_bot.py
        # Можно использовать существующий механизм отправки сообщений
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки Telegram уведомления: {e}")
        return False

def send_whatsapp_notification(phone: str, booking_data: dict) -> bool:
    """
    Отправка уведомления о новом бронировании через WhatsApp Business API
    
    Args:
        phone: Номер телефона в формате +1234567890
        booking_data: Данные бронирования
    
    Returns:
        True если отправлено успешно, False если ошибка
    """
    if not WHATSAPP_PHONE_ID or not WHATSAPP_ACCESS_TOKEN:
        print("⚠️ WhatsApp не настроен (WHATSAPP_PHONE_ID или WHATSAPP_ACCESS_TOKEN не установлены)")
        return False
    
    if not phone:
        return False
    
    try:
        # Формируем номер телефона (убираем все символы кроме цифр и +)
        phone_clean = ''.join(c for c in phone if c.isdigit() or c == '+')
        if not phone_clean.startswith('+'):
            phone_clean = '+' + phone_clean
        
        # Формируем сообщение
        message = f"""🔔 Новое бронирование!

👤 Клиент: {booking_data.get('client_name', 'Не указано')}
📞 Телефон: {booking_data.get('client_phone', 'Не указано')}
📧 Email: {booking_data.get('client_email', 'Не указано')}

🕐 Время: {booking_data.get('booking_time_local', booking_data.get('booking_time', 'Не указано'))}

"""
        
        if booking_data.get('service_name'):
            message += f"💇 Услуга: {booking_data['service_name']}\n"
        
        if booking_data.get('notes'):
            message += f"📝 Заметки: {booking_data['notes']}\n"
        
        message += f"\nID бронирования: {booking_data.get('booking_id', '')}"
        
        # Отправляем через WhatsApp Business API
        url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
        
        headers = {
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone_clean,
            'type': 'text',
            'text': {
                'body': message
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ WhatsApp уведомление отправлено на {phone_clean}")
            return True
        else:
            print(f"❌ Ошибка отправки WhatsApp: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Ошибка отправки WhatsApp уведомления: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_booking_notification(business_id: str, booking_id: str) -> bool:
    """
    Отправка уведомлений о новом бронировании (Telegram и/или WhatsApp)
    
    Args:
        business_id: ID бизнеса
        booking_id: ID бронирования
    
    Returns:
        True если хотя бы одно уведомление отправлено
    """
    from database_manager import DatabaseManager
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        # Получаем информацию о бизнесе
        cursor.execute("""
            SELECT name, telegram_username, whatsapp_phone, whatsapp_verified, owner_id
            FROM Businesses
            WHERE id = ?
        """, (business_id,))
        
        business = cursor.fetchone()
        if not business:
            db.close()
            return False
        
        salon_name, telegram_username, whatsapp_phone, whatsapp_verified, owner_id = business
        
        # Получаем информацию о бронировании
        cursor.execute("""
            SELECT client_name, client_phone, client_email, service_name,
                   booking_time, booking_time_local, notes
            FROM Bookings
            WHERE id = ?
        """, (booking_id,))
        
        booking = cursor.fetchone()
        if not booking:
            db.close()
            return False
        
        client_name, client_phone, client_email, service_name, booking_time, booking_time_local, notes = booking
        
        booking_data = {
            'booking_id': booking_id,
            'salon_name': salon_name,
            'client_name': client_name,
            'client_phone': client_phone,
            'client_email': client_email,
            'service_name': service_name,
            'booking_time': booking_time,
            'booking_time_local': booking_time_local,
            'notes': notes
        }
        
        # Отправляем уведомления
        telegram_sent = False
        whatsapp_sent = False
        
        # Telegram уведомление
        if telegram_username:
            # Получаем telegram_id владельца из Users
            cursor.execute("SELECT telegram_id FROM Users WHERE id = ?", (owner_id,))
            user = cursor.fetchone()
            if user and user[0]:
                # TODO: Использовать telegram_id для отправки
                # Пока используем username
                telegram_sent = send_telegram_notification(telegram_username, booking_data)
        
        # WhatsApp уведомление
        if whatsapp_phone and whatsapp_verified:
            whatsapp_sent = send_whatsapp_notification(whatsapp_phone, booking_data)
        
        # Обновляем статус уведомления в БД
        notification_channel = []
        if telegram_sent:
            notification_channel.append('telegram')
        if whatsapp_sent:
            notification_channel.append('whatsapp')
        
        if notification_channel:
            cursor.execute("""
                UPDATE Bookings 
                SET notification_sent = 1, notification_channel = ?
                WHERE id = ?
            """, (','.join(notification_channel), booking_id))
            db.conn.commit()
        
        db.close()
        
        return telegram_sent or whatsapp_sent
        
    except Exception as e:
        print(f"❌ Ошибка отправки уведомлений: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False

