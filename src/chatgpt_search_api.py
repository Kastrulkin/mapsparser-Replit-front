#!/usr/bin/env python3
"""
Публичные API endpoints для ChatGPT
- Поиск салонов по городу и услуге
- Создание бронирований
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from subscription_manager import check_access
from datetime import datetime
import uuid
import json

chatgpt_search_bp = Blueprint('chatgpt_search', __name__)

@chatgpt_search_bp.route('/api/chatgpt/search', methods=['GET'])
def chatgpt_search():
    """
    Поиск салонов для ChatGPT (публичный API)
    
    Параметры:
        - city: город (обязательно)
        - service: услуга (обязательно)
        - budget: бюджет в долларах (опционально)
        - limit: количество результатов (по умолчанию 5)
    """
    try:
        city = request.args.get('city', '').strip()
        service = request.args.get('service', '').strip()
        budget = request.args.get('budget', type=int)
        limit = request.args.get('limit', 5, type=int)
        
        if not city or not service:
            return jsonify({"error": "Параметры city и service обязательны"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Ищем только одобренные бизнесы с включённым ChatGPT
        # и активной подпиской
        query = """
            SELECT DISTINCT b.id, b.name, b.address, b.city, b.phone, b.whatsapp_phone,
                   b.working_hours_json, b.timezone, b.latitude, b.longitude
            FROM Businesses b
            LEFT JOIN UserServices us ON b.id = us.business_id
            WHERE b.moderation_status = 'approved'
            AND b.chatgpt_enabled = 1
            AND b.subscription_status = 'active'
            AND b.city LIKE ?
            AND (us.name LIKE ? OR b.name LIKE ?)
        """
        
        params = [f'%{city}%', f'%{service}%', f'%{service}%']
        
        # Фильтр по бюджету (если указан)
        if budget:
            query += " AND (us.price IS NULL OR us.price <= ?)"
            params.append(budget * 100)  # Конвертируем в центы
        
        query += " LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        businesses = cursor.fetchall()
        
        results = []
        for biz in businesses:
            business_id, name, address, city_name, phone, whatsapp, working_hours_json, timezone, lat, lng = biz
            
            # Получаем услуги для этого бизнеса
            cursor.execute("""
                SELECT id, name, price, duration, description
                FROM UserServices
                WHERE business_id = ?
            """, (business_id,))
            services = cursor.fetchall()
            
            # Фильтруем услуги по бюджету, если указан
            filtered_services = []
            for svc in services:
                svc_id, svc_name, svc_price, svc_duration, svc_desc = svc
                if not budget or svc_price is None or svc_price <= budget * 100:
                    filtered_services.append({
                        'id': svc_id,
                        'name': svc_name,
                        'price': svc_price / 100 if svc_price else None,  # Конвертируем из центов
                        'duration': svc_duration,
                        'description': svc_desc
                    })
            
            # Парсим рабочие часы
            working_hours = None
            if working_hours_json:
                try:
                    working_hours = json.loads(working_hours_json)
                except:
                    pass
            
            results.append({
                'id': business_id,
                'name': name,
                'address': address,
                'city': city_name,
                'phone': phone,
                'whatsapp': whatsapp,
                'timezone': timezone,
                'latitude': lat,
                'longitude': lng,
                'working_hours': working_hours,
                'services': filtered_services
            })
        
        db.close()
        
        return jsonify({
            'success': True,
            'salons': results,
            'count': len(results)
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка поиска салонов: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@chatgpt_search_bp.route('/api/chatgpt/book', methods=['POST'])
def chatgpt_book():
    """
    Создание бронирования через ChatGPT
    
    Body:
        - salonId: ID салона (обязательно)
        - clientName: имя клиента (обязательно)
        - clientPhone: телефон клиента (обязательно)
        - clientEmail: email клиента (опционально)
        - serviceId: ID услуги (опционально)
        - bookingTime: время бронирования в ISO формате (обязательно)
        - notes: дополнительные заметки (опционально)
    """
    try:
        data = request.get_json()
        
        salon_id = data.get('salonId')
        client_name = data.get('clientName', '').strip()
        client_phone = data.get('clientPhone', '').strip()
        client_email = data.get('clientEmail', '').strip()
        service_id = data.get('serviceId')
        booking_time_str = data.get('bookingTime')
        notes = data.get('notes', '').strip()
        
        if not salon_id or not client_name or not client_phone or not booking_time_str:
            return jsonify({"error": "salonId, clientName, clientPhone и bookingTime обязательны"}), 400
        
        # Парсим время бронирования
        try:
            booking_time = datetime.fromisoformat(booking_time_str.replace('Z', '+00:00'))
        except:
            return jsonify({"error": "Неверный формат bookingTime (используйте ISO 8601)"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, что салон существует и активен
        cursor.execute("""
            SELECT id, name, owner_id, timezone, phone, whatsapp_phone, telegram_username
            FROM Businesses
            WHERE id = ? AND moderation_status = 'approved' AND chatgpt_enabled = 1
        """, (salon_id,))
        
        salon = cursor.fetchone()
        if not salon:
            db.close()
            return jsonify({"error": "Салон не найден или не доступен"}), 404
        
        business_id, salon_name, owner_id, timezone, phone, whatsapp, telegram_username = salon
        
        # Получаем название услуги, если указана
        service_name = None
        if service_id:
            cursor.execute("SELECT name FROM UserServices WHERE id = ?", (service_id,))
            service = cursor.fetchone()
            if service:
                service_name = service[0]
        
        # Конвертируем время в локальный часовой пояс салона
        booking_time_local = booking_time_str
        if timezone:
            try:
                from timezone_utils import convert_to_local_time
                local_time = convert_to_local_time(booking_time, timezone)
                booking_time_local = local_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            except:
                pass
        
        # Создаём бронирование
        booking_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO Bookings 
            (id, business_id, client_name, client_phone, client_email, service_id, service_name,
             booking_time, booking_time_local, source, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'chatgpt', 'pending', ?)
        """, (
            booking_id,
            business_id,
            client_name,
            client_phone,
            client_email if client_email else None,
            service_id,
            service_name,
            booking_time.isoformat(),
            booking_time_local,
            notes if notes else None
        ))
        
        db.conn.commit()
        
        # Отправляем уведомления (через Telegram и/или WhatsApp)
        from notifications import send_booking_notification
        notification_sent = send_booking_notification(business_id, booking_id)
        
        db.close()
        
        return jsonify({
            'success': True,
            'bookingId': booking_id,
            'message': 'Бронирование создано! Салон получит уведомление.',
            'salon': {
                'name': salon_name,
                'phone': phone
            }
        }), 201
        
    except Exception as e:
        print(f"❌ Ошибка создания бронирования: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@chatgpt_search_bp.route('/api/chatgpt/salon/<salon_id>', methods=['GET'])
def get_salon_details(salon_id):
    """Получить детальную информацию о салоне"""
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Получаем информацию о салоне
        cursor.execute("""
            SELECT id, name, address, city, phone, whatsapp_phone, email, website,
                   working_hours_json, timezone, latitude, longitude
            FROM Businesses
            WHERE id = ? AND moderation_status = 'approved' AND chatgpt_enabled = 1
        """, (salon_id,))
        
        salon = cursor.fetchone()
        if not salon:
            db.close()
            return jsonify({"error": "Салон не найден"}), 404
        
        # Получаем услуги
        cursor.execute("""
            SELECT id, name, price, duration, description
            FROM UserServices
            WHERE business_id = ?
            ORDER BY name
        """, (salon_id,))
        
        services = cursor.fetchall()
        
        # Парсим рабочие часы
        working_hours = None
        if salon[8]:  # working_hours_json
            try:
                working_hours = json.loads(salon[8])
            except:
                pass
        
        db.close()
        
        return jsonify({
            'success': True,
            'salon': {
                'id': salon[0],
                'name': salon[1],
                'address': salon[2],
                'city': salon[3],
                'phone': salon[4],
                'whatsapp': salon[5],
                'email': salon[6],
                'website': salon[7],
                'working_hours': working_hours,
                'timezone': salon[9],
                'latitude': salon[10],
                'longitude': salon[11],
                'services': [
                    {
                        'id': s[0],
                        'name': s[1],
                        'price': s[2] / 100 if s[2] else None,
                        'duration': s[3],
                        'description': s[4]
                    }
                    for s in services
                ]
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка получения информации о салоне: {e}")
        return jsonify({"error": str(e)}), 500

@chatgpt_search_bp.route('/api/chatgpt/request-support', methods=['POST'])
def request_human_support():
    """
    Запрос на призыв представителя салона в чат ChatGPT
    
    Body:
        - salonId: ID салона (обязательно)
        - reason: причина запроса (обязательно)
        - clientMessage: последнее сообщение клиента (опционально)
        - clientName: имя клиента (опционально)
        - clientPhone: телефон клиента (опционально)
    """
    try:
        data = request.get_json()
        
        salon_id = data.get('salonId')
        reason = data.get('reason', '').strip()
        client_message = data.get('clientMessage', '').strip()
        client_name = data.get('clientName', '').strip()
        client_phone = data.get('clientPhone', '').strip()
        
        if not salon_id or not reason:
            return jsonify({"error": "salonId и reason обязательны"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Получаем информацию о салоне и владельце
        cursor.execute("""
            SELECT id, name, owner_id, phone, whatsapp_phone, telegram_username, email, telegram_bot_token
            FROM Businesses
            WHERE id = ? AND moderation_status = 'approved' AND chatgpt_enabled = 1
        """, (salon_id,))
        
        salon = cursor.fetchone()
        if not salon:
            db.close()
            return jsonify({"error": "Салон не найден или не доступен"}), 404
        
        business_id, salon_name, owner_id, phone, whatsapp, telegram_username, email, telegram_bot_token = salon
        
        # Получаем информацию о владельце
        cursor.execute("""
            SELECT id, email, telegram_id
            FROM Users
            WHERE id = ?
        """, (owner_id,))
        
        owner = cursor.fetchone()
        if not owner:
            db.close()
            return jsonify({"error": "Владелец салона не найден"}), 404
        
        user_id, user_email, telegram_id = owner
        
        # Отправляем уведомления владельцу
        from notifications import send_support_request_notification
        
        notification_sent = send_support_request_notification(
            business_id=business_id,
            salon_name=salon_name,
            reason=reason,
            client_message=client_message,
            client_name=client_name,
            client_phone=client_phone,
            telegram_id=telegram_id,
            email=user_email,
            phone=phone,
            whatsapp=whatsapp,
            telegram_bot_token=telegram_bot_token  # Токен бота конкретного бизнеса
        )
        
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Запрос на поддержку отправлен. Представитель салона получит уведомление и свяжется с вами.',
            'salon': {
                'name': salon_name,
                'phone': phone,
                'whatsapp': whatsapp
            },
            'notification_sent': notification_sent
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка запроса поддержки: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

