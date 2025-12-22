#!/usr/bin/env python3
"""
API endpoints для ChatGPT интеграции
- Регистрация с созданием бизнеса
- Обновление профиля бизнеса
- Подключение Telegram/WhatsApp
- Определение часового пояса
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager, get_db_connection
from auth_system import verify_session, create_session
from timezone_utils import get_timezone_from_address
import uuid
import json
from datetime import datetime, timedelta

chatgpt_bp = Blueprint('chatgpt', __name__)

def require_auth():
    """Проверка авторизации"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    return user_data

@chatgpt_bp.route('/api/auth/register-with-business', methods=['POST'])
def register_with_business():
    """Регистрация пользователя с автоматическим созданием бизнеса"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        
        # Данные бизнеса
        business_name = data.get('business_name', '').strip()
        business_address = data.get('business_address', '').strip()
        business_city = data.get('business_city', '').strip()
        business_country = data.get('business_country', 'US').strip()
        
        if not email or not password:
            return jsonify({"error": "Email и пароль обязательны"}), 400
        
        if not business_name or not business_address or not business_city:
            return jsonify({"error": "Название бизнеса, адрес и город обязательны"}), 400
        
        # Создаём пользователя
        from auth_system import create_user
        result = create_user(email, password, name, phone)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 400
        
        user_id = result['id']
        
        # Определяем часовой пояс по адресу (асинхронно, не блокируем регистрацию)
        timezone_result = get_timezone_from_address(business_address, business_city)
        
        # Создаём бизнес
        db = DatabaseManager()
        try:
            business_id = db.create_business(
                name=business_name,
                address=business_address,
                city=business_city,
                country=business_country,
                owner_id=user_id,
                moderation_status='pending',
                business_type='beauty_salon'
            )
            
            # Обновляем часовой пояс и координаты, если они определены
            cursor = db.conn.cursor()
            update_fields = []
            update_values = []
            
            if timezone_result.get('timezone') and not timezone_result.get('error'):
                update_fields.append('timezone = ?')
                update_values.append(timezone_result['timezone'])
            
            if timezone_result.get('latitude'):
                update_fields.append('latitude = ?')
                update_values.append(timezone_result['latitude'])
            
            if timezone_result.get('longitude'):
                update_fields.append('longitude = ?')
                update_values.append(timezone_result['longitude'])
            
            if update_fields:
                update_values.append(business_id)
                cursor.execute(f"""
                    UPDATE Businesses 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, update_values)
            
            db.conn.commit()
            db.close()
        except Exception as e:
            db.close()
            return jsonify({"error": f"Ошибка создания бизнеса: {str(e)}"}), 500
        
        # Создаём сессию
        session_token = create_session(user_id)
        if not session_token:
            return jsonify({"error": "Ошибка создания сессии"}), 500
        
        return jsonify({
            "success": True,
            "user": {
                "id": user_id,
                "email": result['email'],
                "name": result['name'],
                "phone": result['phone']
            },
            "business": {
                "id": business_id,
                "name": business_name,
                "moderation_status": "pending"
            },
            "timezone": timezone_result.get('timezone', 'UTC'),
            "token": session_token
        }), 201
        
    except Exception as e:
        print(f"❌ Ошибка регистрации: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@chatgpt_bp.route('/api/business/profile', methods=['PUT'])
def update_business_profile():
    """Обновление профиля бизнеса"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        data = request.get_json()
        business_id = data.get('business_id')
        
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        # Проверяем доступ к бизнесу
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Обновляем поля
        update_fields = []
        update_values = []
        
        if 'address' in data:
            update_fields.append('address = ?')
            update_values.append(data['address'])
        
        if 'city' in data:
            update_fields.append('city = ?')
            update_values.append(data['city'])
        
        if 'country' in data:
            update_fields.append('country = ?')
            update_values.append(data['country'])
        
        if 'working_hours_json' in data:
            # Сохраняем рабочие часы как JSON
            working_hours = json.dumps(data['working_hours_json'])
            update_fields.append('working_hours_json = ?')
            update_values.append(working_hours)
        
        # Если изменился адрес или город, определяем часовой пояс заново
        if 'address' in data or 'city' in data:
            address = data.get('address', '')
            city = data.get('city', '')
            if address and city:
                timezone_result = get_timezone_from_address(address, city)
                if timezone_result.get('timezone'):
                    update_fields.append('timezone = ?')
                    update_values.append(timezone_result['timezone'])
                if timezone_result.get('latitude'):
                    update_fields.append('latitude = ?')
                    update_values.append(timezone_result['latitude'])
                if timezone_result.get('longitude'):
                    update_fields.append('longitude = ?')
                    update_values.append(timezone_result['longitude'])
        
        if 'phone' in data:
            update_fields.append('phone = ?')
            update_values.append(data['phone'])
        
        if 'email' in data:
            update_fields.append('email = ?')
            update_values.append(data['email'])
        
        if 'website' in data:
            update_fields.append('website = ?')
            update_values.append(data['website'])
        
        # WABA credentials
        if 'waba_phone_id' in data:
            update_fields.append('waba_phone_id = ?')
            update_values.append(data['waba_phone_id'])
        
        if 'waba_access_token' in data:
            update_fields.append('waba_access_token = ?')
            update_values.append(data['waba_access_token'])
        
        # Telegram bot token
        if 'telegram_bot_token' in data:
            update_fields.append('telegram_bot_token = ?')
            update_values.append(data['telegram_bot_token'])
        
        # AI Agent settings
        if 'ai_agent_enabled' in data:
            update_fields.append('ai_agent_enabled = ?')
            update_values.append(data['ai_agent_enabled'])
        
        if 'ai_agent_type' in data:
            update_fields.append('ai_agent_type = ?')
            update_values.append(data['ai_agent_type'])
        
        if 'ai_agent_id' in data:
            update_fields.append('ai_agent_id = ?')
            update_values.append(data['ai_agent_id'] if data['ai_agent_id'] else None)
        
        if 'ai_agent_tone' in data:
            update_fields.append('ai_agent_tone = ?')
            update_values.append(data['ai_agent_tone'])
        
        if 'ai_agent_restrictions' in data:
            update_fields.append('ai_agent_restrictions = ?')
            update_values.append(data['ai_agent_restrictions'])
        
        if 'ai_agent_language' in data:
            update_fields.append('ai_agent_language = ?')
            update_values.append(data['ai_agent_language'])
        
        update_fields.append('updated_at = CURRENT_TIMESTAMP')
        update_values.append(business_id)
        
        if len(update_fields) > 1:  # Больше чем только updated_at
            cursor.execute(f"""
                UPDATE Businesses 
                SET {', '.join(update_fields)}
                WHERE id = ?
            """, update_values)
            db.conn.commit()
        
        db.close()
        
        return jsonify({
            "success": True,
            "message": "Профиль бизнеса обновлён"
        })
        
    except Exception as e:
        print(f"❌ Ошибка обновления профиля: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@chatgpt_bp.route('/api/business/telegram/connect', methods=['POST'])
def connect_telegram():
    """Подключение Telegram бота"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        data = request.get_json()
        business_id = data.get('business_id')
        
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        # Проверяем доступ
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if business[0] != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Генерируем токен для подключения (используем существующую систему токенов)
        from auth_system import create_telegram_bind_token
        token = create_telegram_bind_token(user_data['user_id'], business_id)
        
        db.close()
        
        return jsonify({
            "success": True,
            "token": token,
            "instructions": "Используйте этот токен для подключения бота @BeautyBotPro_bot"
        })
        
    except Exception as e:
        print(f"❌ Ошибка подключения Telegram: {e}")
        return jsonify({"error": str(e)}), 500

@chatgpt_bp.route('/api/business/whatsapp/verify', methods=['POST'])
def verify_whatsapp():
    """Верификация WhatsApp номера"""
    try:
        user_data = require_auth()
        if not user_data:
            return jsonify({"error": "Требуется авторизация"}), 401
        
        data = request.get_json()
        business_id = data.get('business_id')
        # Поддерживаем оба варианта для совместимости
        phone = data.get('whatsapp_phone', '').strip() or data.get('phone', '').strip()
        verification_code = data.get('verification_code', '').strip()
        
        if not business_id or not phone:
            return jsonify({"error": "business_id и whatsapp_phone обязательны"}), 400
        
        # Проверяем доступ
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if business[0] != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # TODO: Реализовать отправку и проверку кода через WABA
        # Пока просто сохраняем номер
        if not verification_code:
            # Отправляем код (заглушка)
            # В реальности здесь будет вызов WABA API
            cursor.execute("""
                UPDATE Businesses 
                SET whatsapp_phone = ?, whatsapp_verified = 0
                WHERE id = ?
            """, (phone, business_id))
            db.conn.commit()
            db.close()
            
            return jsonify({
                "success": True,
                "message": "Номер WhatsApp сохранён",
                "verified": False,
                "verification_required": True
            })
        else:
            # Проверяем код (заглушка)
            # В реальности здесь будет проверка кода через WABA
            cursor.execute("""
                UPDATE Businesses 
                SET whatsapp_verified = 1
                WHERE id = ?
            """, (business_id,))
            db.conn.commit()
            db.close()
            
            return jsonify({
                "success": True,
                "message": "WhatsApp номер верифицирован",
                "verified": True
            })
        
    except Exception as e:
        print(f"❌ Ошибка верификации WhatsApp: {e}")
        return jsonify({"error": str(e)}), 500

