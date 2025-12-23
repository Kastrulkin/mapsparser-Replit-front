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

def send_telegram_notification(telegram_id: str, booking_data: dict) -> bool:
    """
    Отправка уведомления о новом бронировании через Telegram
    
    Args:
        telegram_id: Telegram ID пользователя (не username!)
        booking_data: Данные бронирования
    
    Returns:
        True если отправлено успешно, False если ошибка
    """
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN не установлен")
        return False
    
    if not telegram_id:
        return False
    
    try:
        # Формируем сообщение
        message = f"""🔔 Новое бронирование!

👤 Клиент: {booking_data.get('client_name', 'Не указано')}
📞 Телефон: {booking_data.get('client_phone', 'Не указано')}
📧 Email: {booking_data.get('client_email', 'Не указано') or 'Не указано'}

🕐 Время: {booking_data.get('booking_time_local', booking_data.get('booking_time', 'Не указано'))}

"""
        
        if booking_data.get('service_name'):
            message += f"💇 Услуга: {booking_data['service_name']}\n"
        
        if booking_data.get('notes'):
            message += f"📝 Заметки: {booking_data['notes']}\n"
        
        message += f"\nID бронирования: {booking_data.get('booking_id', '')}"
        
        # Отправляем через Telegram Bot API
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        payload = {
            'chat_id': telegram_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Telegram уведомление отправлено на {telegram_id}")
            return True
        else:
            print(f"❌ Ошибка отправки Telegram: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Ошибка отправки Telegram уведомления: {e}")
        import traceback
        traceback.print_exc()
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
        # Получаем telegram_id владельца из Users
        cursor.execute("SELECT telegram_id FROM Users WHERE id = ?", (owner_id,))
        user = cursor.fetchone()
        if user and user[0]:
            telegram_id = user[0]
            telegram_sent = send_telegram_notification(telegram_id, booking_data)
        
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

def send_support_request_notification(
    business_id: str,
    salon_name: str,
    reason: str,
    client_message: str = '',
    client_name: str = '',
    client_phone: str = '',
    telegram_id: str = None,
    email: str = None,
    phone: str = None,
    whatsapp: str = None,
    telegram_bot_token: str = None
) -> bool:
    """
    Отправка уведомления о запросе поддержки от клиента ChatGPT
    
    Args:
        business_id: ID бизнеса
        salon_name: Название салона
        reason: Причина запроса
        client_message: Последнее сообщение клиента
        client_name: Имя клиента
        client_phone: Телефон клиента
        telegram_id: Telegram ID владельца
        email: Email владельца
        phone: Телефон салона
        whatsapp: WhatsApp номер салона
    
    Returns:
        True если хотя бы одно уведомление отправлено
    """
    telegram_sent = False
    whatsapp_sent = False
    
    # Формируем сообщение
    message = f"""🔔 Запрос на поддержку от клиента ChatGPT!

🏢 Салон: {salon_name}

📋 Причина: {reason}
"""
    
    if client_message:
        message += f"\n💬 Сообщение клиента: {client_message}\n"
    
    if client_name:
        message += f"\n👤 Клиент: {client_name}"
    
    if client_phone:
        message += f"\n📞 Телефон: {client_phone}"
    
    message += "\n\n⚠️ Клиент ожидает ответа от представителя салона!"
    
    # Telegram уведомление
    # Используем токен бота бизнеса, если он есть, иначе глобальный токен
    bot_token_to_use = telegram_bot_token or TELEGRAM_BOT_TOKEN
    
    if telegram_id and bot_token_to_use:
        try:
            url = f"https://api.telegram.org/bot{bot_token_to_use}/sendMessage"
            payload = {
                'chat_id': telegram_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                telegram_sent = True
                bot_type = "бизнеса" if telegram_bot_token else "глобального"
                print(f"✅ Telegram уведомление о поддержке отправлено на {telegram_id} через {bot_type} бота")
            else:
                print(f"❌ Ошибка отправки Telegram: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Ошибка отправки Telegram уведомления о поддержке: {e}")
    
    # WhatsApp уведомление
    if whatsapp and WHATSAPP_PHONE_ID and WHATSAPP_ACCESS_TOKEN:
        try:
            phone_clean = ''.join(c for c in whatsapp if c.isdigit() or c == '+')
            if not phone_clean.startswith('+'):
                phone_clean = '+' + phone_clean
            
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
                whatsapp_sent = True
                print(f"✅ WhatsApp уведомление о поддержке отправлено на {phone_clean}")
        except Exception as e:
            print(f"❌ Ошибка отправки WhatsApp уведомления о поддержке: {e}")
    
    return telegram_sent or whatsapp_sent

