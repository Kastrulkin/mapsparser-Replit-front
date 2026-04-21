"""
Webhook endpoints для получения сообщений от WABA и Telegram
и обработки их через ИИ агента
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
import os
import requests
import json
from ai_agent import process_message, get_business_info
from core.telegram_token_store import decode_telegram_bot_token
from core.telegram_network import build_requests_proxy_kwargs

ai_webhooks_bp = Blueprint('ai_webhooks', __name__)

def send_whatsapp_message(phone_id: str, access_token: str, to: str, message: str) -> bool:
    """Отправить сообщение через WhatsApp Business API"""
    try:
        url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        payload = {
            'messaging_product': 'whatsapp',
            'to': to.replace('+', '').replace(' ', '').replace('-', ''),
            'type': 'text',
            'text': {
                'body': message
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print(f"✅ WhatsApp сообщение отправлено на {to}")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки WhatsApp сообщения: {e}")
        return False

def send_telegram_message(bot_token: str, chat_id: str, message: str) -> bool:
    """Отправить сообщение через Telegram Bot API"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, json=payload, timeout=10, **build_requests_proxy_kwargs())
        response.raise_for_status()
        print(f"✅ Telegram сообщение отправлено в чат {chat_id}")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки Telegram сообщения: {e}")
        return False

def find_business_by_waba_phone_id(phone_id: str) -> dict:
    """Найти бизнес по WABA Phone ID"""
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id, waba_phone_id, waba_access_token, ai_agent_enabled
            FROM Businesses
            WHERE waba_phone_id = %s
            AND ai_agent_enabled = 1
            LIMIT 1
        """, (phone_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'waba_phone_id': row[1],
                'waba_access_token': row[2],
                'ai_agent_enabled': row[3] == 1
            }
        return None
    finally:
        db.close()


def find_business_by_telegram_token(bot_token: str) -> dict | None:
    token = str(bot_token or "").strip()
    if not token:
        return None
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT id, telegram_bot_token, ai_agent_enabled
            FROM Businesses
            WHERE ai_agent_enabled = 1
              AND telegram_bot_token IS NOT NULL
              AND NULLIF(TRIM(telegram_bot_token), '') IS NOT NULL
            """
        )
        for row in cursor.fetchall() or []:
            row_dict = dict(row) if hasattr(row, "keys") else {
                "id": row[0] if len(row) > 0 else None,
                "telegram_bot_token": row[1] if len(row) > 1 else None,
                "ai_agent_enabled": row[2] if len(row) > 2 else None,
            }
            candidate = decode_telegram_bot_token(row_dict.get("telegram_bot_token"))
            if candidate and candidate == token:
                return row_dict
        return None
    finally:
        db.close()

@ai_webhooks_bp.route('/api/webhooks/whatsapp', methods=['POST', 'GET'])
def whatsapp_webhook():
    """Webhook для получения сообщений от WhatsApp Business API"""
    try:
        # GET запрос - верификация webhook
        if request.method == 'GET':
            mode = request.args.get('hub.mode')
            token = request.args.get('hub.verify_token')
            challenge = request.args.get('hub.challenge')
            
            verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'local_verify_token')
            
            if mode == 'subscribe' and token == verify_token:
                print("✅ WhatsApp webhook верифицирован")
                return challenge, 200
            else:
                print("❌ WhatsApp webhook верификация не удалась")
                return jsonify({"error": "Verification failed"}), 403
        
        # POST запрос - получение сообщения
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data"}), 400
        
        # Обрабатываем структуру WABA webhook
        entry = data.get('entry', [])
        if not entry:
            return jsonify({"status": "ok"}), 200
        
        for entry_item in entry:
            changes = entry_item.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                messages = value.get('messages', [])
                
                for message in messages:
                    from_number = message.get('from', '')
                    message_text = message.get('text', {}).get('body', '')
                    message_id = message.get('id', '')
                    
                    if not message_text or not from_number:
                        continue
                    
                    print(f"📱 Получено WhatsApp сообщение от {from_number}: {message_text}")
                    
                    # Находим бизнес по phone_id из webhook
                    # В WABA webhook phone_number_id указывает на бизнес, который получил сообщение
                    phone_id = value.get('metadata', {}).get('phone_number_id', '')
                    if not phone_id:
                        # Пробуем получить из другого места в структуре
                        phone_id = entry_item.get('id', '')
                    
                    business = None
                    if phone_id:
                        business = find_business_by_waba_phone_id(phone_id)
                    
                    if not business or not business['ai_agent_enabled']:
                        print(f"⚠️ Бизнес не найден или ИИ агент отключен для номера {from_number}")
                        continue
                    
                    # Обрабатываем сообщение через ИИ агента
                    result = process_message(
                        business_id=business['id'],
                        client_phone=from_number,
                        client_name=None,  # WABA не всегда предоставляет имя
                        message=message_text
                    )
                    
                    if result.get('success') and result.get('response'):
                        # Отправляем ответ через WABA
                        send_whatsapp_message(
                            phone_id=business['waba_phone_id'],
                            access_token=business['waba_access_token'],
                            to=from_number,
                            message=result['response']
                        )
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print(f"❌ Ошибка обработки WhatsApp webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@ai_webhooks_bp.route('/api/webhooks/telegram', methods=['POST'])
def telegram_webhook():
    """Webhook для получения сообщений от Telegram ботов пользователей"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data"}), 400
        
        # Telegram webhook структура
        message = data.get('message', {})
        if not message:
            return jsonify({"status": "ok"}), 200
        
        chat_id = str(message.get('chat', {}).get('id', ''))
        from_user = message.get('from', {})
        user_id = str(from_user.get('id', ''))
        username = from_user.get('username', '')
        first_name = from_user.get('first_name', '')
        message_text = message.get('text', '')
        
        # Получаем bot_token из заголовка или параметров запроса
        bot_token = request.headers.get('X-Bot-Token') or request.args.get('bot_token') or data.get('bot_token')
        
        if not message_text or not chat_id:
            return jsonify({"status": "ok"}), 200
        
        print(f"📱 Получено Telegram сообщение от {user_id} ({username}): {message_text}")
        
        # Находим бизнес по токену бота
        if not bot_token:
            return jsonify({"error": "bot_token required"}), 400
        
        row = find_business_by_telegram_token(bot_token)
        
        if not row:
            print(f"⚠️ Бизнес не найден для токена бота")
            return jsonify({"status": "ok"}), 200
        
        business_id = row.get("id") if isinstance(row, dict) else row[0]
        raw_enabled = row.get("ai_agent_enabled") if isinstance(row, dict) else row[2]
        ai_agent_enabled = bool(raw_enabled in (1, True, "1", "t", "true", "TRUE"))
        
        if not ai_agent_enabled:
            print(f"⚠️ ИИ агент отключен для бизнеса {business_id}")
            return jsonify({"status": "ok"}), 200
        
        # Обрабатываем сообщение через ИИ агента
        client_phone = f"tg_{user_id}"  # Используем формат tg_ для Telegram
        client_name = first_name or username or None
        
        result = process_message(
            business_id=business_id,
            client_phone=client_phone,
            client_name=client_name,
            message=message_text
        )
        
        if result.get('success') and result.get('response'):
            # Отправляем ответ через Telegram
            send_telegram_message(
                bot_token=bot_token,
                chat_id=chat_id,
                message=result['response']
            )
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print(f"❌ Ошибка обработки Telegram webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@ai_webhooks_bp.route('/api/webhooks/telegram/<bot_token>', methods=['POST'])
def telegram_webhook_with_token(bot_token: str):
    """Webhook для Telegram с токеном в URL (альтернативный вариант)"""
    try:
        data = request.get_json()
        if data:
            data['bot_token'] = bot_token
        else:
            data = {'bot_token': bot_token}
        
        # Перенаправляем на основной обработчик
        request._cached_json = data
        return telegram_webhook()
    except Exception as e:
        print(f"❌ Ошибка обработки Telegram webhook с токеном: {e}")
        return jsonify({"error": str(e)}), 500
