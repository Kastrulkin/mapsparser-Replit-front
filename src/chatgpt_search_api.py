#!/usr/bin/env python3
"""
Публичные API endpoints для ChatGPT
- Поиск салонов по городу и услуге
- Создание бронирований
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
from datetime import datetime, timedelta, time as dt_time
import uuid
import json
import math
import time
from chatgpt_monitoring import log_request

chatgpt_search_bp = Blueprint('chatgpt_search', __name__)

@chatgpt_search_bp.route('/api/chatgpt/search', methods=['GET'])
def chatgpt_search():
    """
    Поиск салонов для ChatGPT (публичный API)
    
    Параметры:
        - city: город (обязательно)
        - service: услуга (обязательно)
        - budget: бюджет в долларах (опционально)
        - min_rating: минимальный рейтинг (опционально, 1-5)
        - keywords: ключевые слова для поиска в описании услуг (опционально)
        - available_now: только доступные сейчас (опционально, true/false)
        - limit: количество результатов (по умолчанию 5)
        - latitude, longitude: координаты пользователя для сортировки по расстоянию
    """
    start_time = time.time()
    chatgpt_user_id = request.headers.get('X-ChatGPT-User-ID')
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    try:
        city = request.args.get('city', '').strip()
        service = request.args.get('service', '').strip()
        budget = request.args.get('budget', type=int)
        min_rating = request.args.get('min_rating', type=float)
        keywords = request.args.get('keywords', '').strip()
        available_now = request.args.get('available_now', 'false').lower() == 'true'
        limit = request.args.get('limit', 5, type=int)
        user_latitude = request.args.get('latitude', type=float)
        user_longitude = request.args.get('longitude', type=float)
        
        if not city or not service:
            return jsonify({"error": "Параметры city и service обязательны"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Ищем только одобренные бизнесы с включённым ChatGPT
        # и активной подпиской
        query = """
            SELECT DISTINCT b.id, b.name, b.address, b.city, b.phone, b.whatsapp_phone,
                   b.working_hours_json, b.timezone, b.latitude, b.longitude,
                   b.network_id, n.name as network_name
            FROM Businesses b
            LEFT JOIN UserServices us ON b.id = us.business_id
            LEFT JOIN Networks n ON b.network_id = n.id
            WHERE b.moderation_status = 'approved'
            AND b.chatgpt_enabled = 1
            AND b.subscription_status = 'active'
            AND b.city LIKE ?
            AND (us.name LIKE ? OR b.name LIKE ? OR us.description LIKE ? OR us.keywords LIKE ?)
        """
        
        # Поиск по ключевым словам в описании услуг
        service_pattern = f'%{service}%'
        keywords_pattern = f'%{keywords}%' if keywords else '%'
        
        params = [f'%{city}%', service_pattern, service_pattern, service_pattern, keywords_pattern]
        
        # Фильтр по бюджету (если указан)
        if budget:
            query += " AND (us.price IS NULL OR us.price <= ?)"
            params.append(budget * 100)  # Конвертируем в центы
        
        query += " LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        businesses = cursor.fetchall()
        
        # Группируем результаты по сетям
        networks_dict = {}  # network_id -> {network_name, salons: []}
        standalone_salons = []  # Салоны без сети
        
        for biz in businesses:
            business_id, name, address, city_name, phone, whatsapp, working_hours_json, timezone, lat, lng, network_id, network_name = biz
            
            # Получаем рейтинг для фильтрации
            rating = None
            if min_rating is not None and min_rating > 0:
                cursor.execute("""
                    SELECT rating
                    FROM ExternalBusinessStats
                    WHERE business_id = ? AND source = 'yandex_business'
                    ORDER BY date DESC
                    LIMIT 1
                """, (business_id,))
                rating_row = cursor.fetchone()
                rating = float(rating_row[0]) if rating_row and rating_row[0] else None
                
                # Фильтр по минимальному рейтингу
                if rating is None or rating < min_rating:
                    continue
            
            # Фильтр по доступности (рабочие часы)
            if available_now:
                working_hours = None
                if working_hours_json:
                    try:
                        working_hours = json.loads(working_hours_json)
                    except:
                        pass
                
                if working_hours:
                    current_time = datetime.now()
                    current_day = current_time.strftime('%A').lower()
                    day_hours = working_hours.get(current_day)
                    
                    if day_hours and '-' in day_hours:
                        try:
                            start_str, end_str = day_hours.split('-')
                            start_hour, start_min = map(int, start_str.split(':'))
                            end_hour, end_min = map(int, end_str.split(':'))
                            
                            current_hour = current_time.hour
                            current_min = current_time.minute
                            current_total = current_hour * 60 + current_min
                            start_total = start_hour * 60 + start_min
                            end_total = end_hour * 60 + end_min
                            
                            if not (start_total <= current_total <= end_total):
                                continue  # Салон сейчас не работает
                        except:
                            pass  # Если не удалось распарсить, пропускаем фильтр
                else:
                    continue  # Нет информации о рабочих часах
            
            # Получаем услуги для этого бизнеса
            cursor.execute("""
                SELECT id, name, price, duration, description, 
                       COALESCE(chatgpt_context, '') as chatgpt_context
                FROM UserServices
                WHERE business_id = ?
            """, (business_id,))
            services = cursor.fetchall()
            
            # Фильтруем услуги по бюджету, если указан
            filtered_services = []
            for svc in services:
                svc_id, svc_name, svc_price, svc_duration, svc_desc, svc_context = svc
                if not budget or svc_price is None or svc_price <= budget * 100:
                    filtered_services.append({
                        'id': svc_id,
                        'name': svc_name,
                        'price': svc_price / 100 if svc_price else None,  # Конвертируем из центов
                        'duration': svc_duration,
                        'description': svc_desc,
                        'chatgpt_context': svc_context if svc_context else None
                    })
            
            # Парсим рабочие часы (если еще не распарсили)
            if not available_now:
                working_hours = None
                if working_hours_json:
                    try:
                        working_hours = json.loads(working_hours_json)
                    except:
                        pass
            else:
                # Уже распарсили выше
                pass
            
            # Вычисляем расстояние, если указаны координаты пользователя
            distance = None
            if user_latitude is not None and user_longitude is not None and lat and lng:
                # Используем формулу Haversine для расчета расстояния
                R = 6371  # Радиус Земли в километрах
                lat1_rad = math.radians(user_latitude)
                lat2_rad = math.radians(lat)
                delta_lat = math.radians(lat - user_latitude)
                delta_lng = math.radians(lng - user_longitude)
                
                a = math.sin(delta_lat / 2) ** 2 + \
                    math.cos(lat1_rad) * math.cos(lat2_rad) * \
                    math.sin(delta_lng / 2) ** 2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                distance = round(R * c, 2)
            
            salon_data = {
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
                'services': filtered_services,
                'distance': distance
            }
            
            # Группируем по сетям
            if network_id and network_name:
                if network_id not in networks_dict:
                    networks_dict[network_id] = {
                        'network_id': network_id,
                        'network_name': network_name,
                        'salons': []
                    }
                networks_dict[network_id]['salons'].append(salon_data)
            else:
                standalone_salons.append(salon_data)
        
        # Сортируем салоны внутри сетей по расстоянию
        if user_latitude is not None and user_longitude is not None:
            for network in networks_dict.values():
                network['salons'].sort(key=lambda x: x['distance'] if x['distance'] is not None else float('inf'))
            standalone_salons.sort(key=lambda x: x['distance'] if x['distance'] is not None else float('inf'))
        
        # Формируем финальный ответ
        networks_list = list(networks_dict.values())
        total_count = sum(len(n['salons']) for n in networks_list) + len(standalone_salons)
        
        db.close()
        
        return jsonify({
            'success': True,
            'networks': networks_list,
            'standalone_salons': standalone_salons,
            'count': total_count,
            'networks_count': len(networks_list),
            'standalone_count': len(standalone_salons)
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
    start_time = time.time()
    chatgpt_user_id = request.headers.get('X-ChatGPT-User-ID')
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
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
        
        # Получаем информацию об услуге, если указана
        service_name = None
        service_duration = None
        if service_id:
            cursor.execute("""
                SELECT name, duration, price
                FROM UserServices
                WHERE id = ? AND business_id = ?
            """, (service_id, business_id))
            service = cursor.fetchone()
            if service:
                service_name = service[0]
                service_duration = service[1]
            else:
                db.close()
                return jsonify({"error": "Услуга не найдена или не принадлежит этому салону"}), 400
        
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
        
        # Записываем бронирование в историю (если есть chatgpt_user_id в заголовках)
        if chatgpt_user_id:
            try:
                from chatgpt_personalization import record_booking
                record_booking(chatgpt_user_id, business_id, service_id, booking_id)
            except Exception as e:
                print(f"⚠️ Ошибка записи истории бронирования: {e}")
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Логируем запрос
        try:
            log_request(
                endpoint='/api/chatgpt/book',
                method='POST',
                request_params=data,
                response_status=201,
                response_time_ms=response_time_ms,
                chatgpt_user_id=chatgpt_user_id,
                business_id=business_id,
                service_id=service_id,
                booking_id=booking_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception as e:
            print(f"⚠️ Ошибка логирования: {e}")
        
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
        response_time_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        
        # Логируем ошибку
        try:
            data = request.get_json() or {}
            log_request(
                endpoint='/api/chatgpt/book',
                method='POST',
                request_params=data,
                response_status=500,
                response_time_ms=response_time_ms,
                error_message=error_msg,
                chatgpt_user_id=chatgpt_user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
        except:
            pass
        
        print(f"❌ Ошибка создания бронирования: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500

@chatgpt_search_bp.route('/api/chatgpt/salon/<salon_id>', methods=['GET'])
def get_salon_details(salon_id):
    """Получить детальную информацию о салоне"""
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Получаем информацию о салоне
        cursor.execute("""
            SELECT id, name, address, city, phone, whatsapp_phone, email, website,
                   working_hours_json, timezone, latitude, longitude, 
                   COALESCE(chatgpt_context, '') as chatgpt_context
            FROM Businesses
            WHERE id = ? AND moderation_status = 'approved' AND chatgpt_enabled = 1
        """, (salon_id,))
        
        salon = cursor.fetchone()
        if not salon:
            db.close()
            return jsonify({"error": "Салон не найден"}), 404
        
        # Получаем услуги
        cursor.execute("""
            SELECT id, name, price, duration, description, 
                   COALESCE(chatgpt_context, '') as chatgpt_context
            FROM UserServices
            WHERE business_id = ?
            ORDER BY name
        """, (salon_id,))
        
        services = cursor.fetchall()
        
        # Получаем рейтинг и количество отзывов из ExternalBusinessStats
        cursor.execute("""
            SELECT rating, reviews_total
            FROM ExternalBusinessStats
            WHERE business_id = ? AND source = 'yandex_business'
            ORDER BY date DESC
            LIMIT 1
        """, (salon_id,))
        stats_row = cursor.fetchone()
        rating = float(stats_row[0]) if stats_row and stats_row[0] else None
        reviews_count = int(stats_row[1]) if stats_row and stats_row[1] else None
        
        # Получаем последние 10 отзывов
        cursor.execute("""
            SELECT author_name, rating, text, published_at
            FROM ExternalBusinessReviews
            WHERE business_id = ? AND source = 'yandex_business'
            ORDER BY published_at DESC
            LIMIT 10
        """, (salon_id,))
        reviews_rows = cursor.fetchall()
        
        recent_reviews = []
        for rev in reviews_rows:
            author_name, rev_rating, rev_text, published_at = rev
            recent_reviews.append({
                'author_name': author_name,
                'rating': rev_rating,
                'text': rev_text,
                'date': published_at.isoformat() if published_at else None
            })
        
        # Получаем количество фото из ExternalBusinessPhotos
        cursor.execute("""
            SELECT total_count
            FROM ExternalBusinessPhotos
            WHERE business_id = ? AND source = 'yandex_business'
            ORDER BY last_updated DESC
            LIMIT 1
        """, (salon_id,))
        photos_row = cursor.fetchone()
        photos_count = int(photos_row[0]) if photos_row and photos_row[0] else 0
        
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
                'rating': rating,
                'reviews_count': reviews_count,
                'photos_count': photos_count,
                'services': [
                    {
                        'id': s[0],
                        'name': s[1],
                        'price': s[2] / 100 if s[2] else None,
                        'duration': s[3],
                        'description': s[4],
                        'chatgpt_context': s[5] if len(s) > 5 and s[5] else None
                    }
                    for s in services
                ],
                'chatgpt_context': salon[12] if len(salon) > 12 and salon[12] else None,
                'recent_reviews': recent_reviews
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка получения информации о салоне: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@chatgpt_search_bp.route('/api/chatgpt/salon/<salon_id>/available-slots', methods=['GET'])
def get_available_slots(salon_id):
    """
    Получить доступные слоты для бронирования
    
    Параметры:
        - serviceId: ID услуги (опционально, для учета длительности)
        - date: дата для поиска (опционально, по умолчанию - сегодня)
        - days: количество дней для поиска (по умолчанию 7)
    """
    try:
        service_id = request.args.get('serviceId', type=str)
        date_str = request.args.get('date', type=str)
        days = request.args.get('days', 7, type=int)
        
        if days < 1 or days > 30:
            days = 7
        
        # Определяем начальную дату
        if date_str:
            try:
                start_date = datetime.fromisoformat(date_str).date()
            except:
                start_date = datetime.now().date()
        else:
            start_date = datetime.now().date()
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, что салон существует
        cursor.execute("""
            SELECT id, name, working_hours_json, timezone
            FROM Businesses
            WHERE id = ? AND moderation_status = 'approved' AND chatgpt_enabled = 1
        """, (salon_id,))
        
        salon = cursor.fetchone()
        if not salon:
            db.close()
            return jsonify({"error": "Салон не найден"}), 404
        
        business_id, salon_name, working_hours_json, timezone = salon
        
        # Получаем длительность услуги, если указана
        service_duration = 60  # По умолчанию 60 минут
        if service_id:
            cursor.execute("SELECT duration FROM UserServices WHERE id = ? AND business_id = ?", (service_id, business_id))
            service_row = cursor.fetchone()
            if service_row and service_row[0]:
                service_duration = service_row[0]
        
        # Парсим рабочие часы
        working_hours = {}
        if working_hours_json:
            try:
                working_hours = json.loads(working_hours_json)
            except:
                pass
        
        # Получаем уже забронированные слоты
        cursor.execute("""
            SELECT booking_time, service_id
            FROM Bookings
            WHERE business_id = ? AND status != 'cancelled'
            AND booking_time >= ?
            AND booking_time < ?
        """, (
            business_id,
            start_date.isoformat(),
            (start_date + timedelta(days=days)).isoformat()
        ))
        booked_slots = cursor.fetchall()
        
        # Создаем множество забронированных времен
        booked_times = set()
        for booking_time_str, booked_service_id in booked_slots:
            try:
                booking_time = datetime.fromisoformat(booking_time_str.replace('Z', '+00:00'))
                booked_times.add(booking_time)
            except:
                pass
        
        # Генерируем доступные слоты
        available_slots = []
        slot_interval = 30  # Интервал между слотами в минутах
        
        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            day_name = current_date.strftime('%A').lower()
            
            # Получаем рабочие часы для этого дня
            day_hours = working_hours.get(day_name)
            if not day_hours:
                continue
            
            # Парсим рабочие часы (формат: "09:00-21:00")
            try:
                if '-' in day_hours:
                    start_str, end_str = day_hours.split('-')
                    start_hour, start_min = map(int, start_str.split(':'))
                    end_hour, end_min = map(int, end_str.split(':'))
                    
                    start_time = dt_time(start_hour, start_min)
                    end_time = dt_time(end_hour, end_min)
                    
                    # Генерируем слоты с интервалом
                    current_time = datetime.combine(current_date, start_time)
                    end_datetime = datetime.combine(current_date, end_time)
                    
                    while current_time < end_datetime:
                        # Проверяем, что слот не забронирован
                        slot_end = current_time + timedelta(minutes=service_duration)
                        
                        # Проверяем, что слот не пересекается с забронированными
                        is_available = True
                        for booked_time in booked_times:
                            booked_end = booked_time + timedelta(minutes=60)  # Предполагаем стандартную длительность
                            
                            # Проверяем пересечение
                            if not (slot_end <= booked_time or current_time >= booked_end):
                                is_available = False
                                break
                        
                        if is_available and slot_end <= end_datetime:
                            # Форматируем время в локальном часовом поясе
                            datetime_local_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                            if timezone:
                                datetime_local_str += f' {timezone}'
                            
                            available_slots.append({
                                'datetime': current_time.isoformat() + 'Z',
                                'datetime_local': datetime_local_str,
                                'available': True
                            })
                        
                        current_time += timedelta(minutes=slot_interval)
            except Exception as e:
                print(f"⚠️ Ошибка парсинга рабочих часов для {day_name}: {e}")
                continue
        
        db.close()
        
        return jsonify({
            'success': True,
            'slots': available_slots,
            'count': len(available_slots)
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка получения доступных слотов: {e}")
        import traceback
        traceback.print_exc()
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

@chatgpt_search_bp.route('/api/chatgpt/user/preferences', methods=['GET'])
def get_chatgpt_user_preferences():
    """
    Получить предпочтения пользователя ChatGPT
    
    Заголовки:
        - X-ChatGPT-User-ID: ID пользователя в ChatGPT (обязательно)
    """
    try:
        chatgpt_user_id = request.headers.get('X-ChatGPT-User-ID')
        if not chatgpt_user_id:
            return jsonify({"error": "X-ChatGPT-User-ID заголовок обязателен"}), 400
        
        from chatgpt_personalization import get_user_preferences
        preferences = get_user_preferences(chatgpt_user_id)
        
        return jsonify({
            'success': True,
            'preferences': preferences
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка получения предпочтений: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@chatgpt_search_bp.route('/api/chatgpt/stats', methods=['GET'])
def get_chatgpt_statistics():
    """
    Получить статистику использования ChatGPT API (только для администраторов)
    
    Параметры:
        - days: количество дней для анализа (по умолчанию 30)
        - business_id: фильтр по бизнесу (опционально)
        - endpoint: фильтр по endpoint (опционально)
    """
    try:
        # Проверка авторизации (только для администраторов)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        from auth_system import verify_session
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        
        if not user_data or not user_data.get('is_superadmin'):
            return jsonify({"error": "Доступ запрещен. Требуются права администратора"}), 403
        
        days = request.args.get('days', 30, type=int)
        business_id = request.args.get('business_id', type=str)
        endpoint = request.args.get('endpoint', type=str)
        
        from chatgpt_monitoring import get_statistics, get_top_businesses
        from datetime import datetime, timedelta
        
        start_date = datetime.now() - timedelta(days=days)
        stats = get_statistics(
            start_date=start_date,
            business_id=business_id,
            endpoint=endpoint
        )
        
        # Получаем топ бизнесов
        top_businesses = get_top_businesses(limit=10, days=days) if not business_id else []
        
        return jsonify({
            'success': True,
            'statistics': stats,
            'top_businesses': top_businesses,
            'period_days': days
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

