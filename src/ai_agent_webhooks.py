"""
Webhook endpoints для получения сообщений от WABA и Telegram
и обработки их через ИИ агента
"""
from flask import Blueprint, request, jsonify
from database_manager import DatabaseManager
import hashlib
import hmac
import os
import requests
import json
import uuid
from ai_agent import process_message, get_business_info
from core.telegram_token_store import decode_telegram_bot_token
from core.telegram_webhook_auth import (
    TELEGRAM_WEBHOOK_SECRET_HEADER,
    has_valid_telegram_webhook_secret,
)
from core.telegram_network import build_requests_proxy_kwargs
from core.telegram_agent_transport import (
    evaluate_and_record_telegram_agent_transport,
)
from services.agent_legacy_migration import business_agent_enabled_for_channel
from services.agent_trigger_runtime import dispatch_telegram_message_to_agent_blueprints

ai_webhooks_bp = Blueprint('ai_webhooks', __name__)


def _has_valid_whatsapp_signature(raw_body: bytes) -> bool:
    """Validate Meta's request HMAC before touching webhook payload data."""
    app_secret = str(os.getenv("WHATSAPP_APP_SECRET") or "").strip()
    header = str(request.headers.get("X-Hub-Signature-256") or "").strip()
    prefix = "sha256="

    if not app_secret or not header.startswith(prefix):
        return False

    supplied_digest = header[len(prefix):]
    if len(supplied_digest) != 64 or any(
        character not in "0123456789abcdef" for character in supplied_digest
    ):
        return False

    expected_digest = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_digest, supplied_digest)

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
            SELECT id, waba_phone_id, waba_access_token
            FROM Businesses
            WHERE waba_phone_id = %s
            LIMIT 1
        """, (phone_id,))
        
        row = cursor.fetchone()
        if row:
            row_dict = dict(row)
            runtime_gate = business_agent_enabled_for_channel(cursor, str(row_dict.get("id") or ""))
            return {
                'id': row_dict.get("id"),
                'waba_phone_id': row_dict.get("waba_phone_id"),
                'waba_access_token': row_dict.get("waba_access_token"),
                'ai_agent_enabled': bool(runtime_gate.get("enabled")),
                'agent_runtime_source': runtime_gate.get("source"),
                'legacy_field_status': runtime_gate.get("legacy_field_status"),
            }
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
            verify_token = str(os.getenv('WHATSAPP_VERIFY_TOKEN') or '').strip()

            if (
                verify_token
                and mode == 'subscribe'
                and token is not None
                and hmac.compare_digest(verify_token.encode("utf-8"), token.encode("utf-8"))
            ):
                if challenge is None:
                    return jsonify({"error": "Verification challenge required"}), 400
                print("✅ WhatsApp webhook верифицирован")
                return challenge, 200

            print("❌ WhatsApp webhook верификация не удалась")
            return jsonify({"error": "Verification failed"}), 403

        raw_body = request.get_data(cache=True)
        if not str(os.getenv("WHATSAPP_APP_SECRET") or "").strip():
            return jsonify({"error": "Webhook signing is not configured"}), 503
        if not _has_valid_whatsapp_signature(raw_body):
            return jsonify({"error": "Invalid webhook signature"}), 403

        # Parse only an authenticated request. Silent parsing avoids a 500 on malformed JSON.
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "No data"}), 400

        # Обрабатываем структуру WABA webhook
        entry = data.get('entry', [])
        if not isinstance(entry, list):
            return jsonify({"error": "Invalid webhook payload"}), 400
        if not entry:
            return jsonify({"status": "ok"}), 200

        for entry_item in entry:
            if not isinstance(entry_item, dict):
                continue
            changes = entry_item.get('changes', [])
            if not isinstance(changes, list):
                continue
            for change in changes:
                if not isinstance(change, dict):
                    continue
                value = change.get('value', {})
                if not isinstance(value, dict):
                    continue
                messages = value.get('messages', [])
                if not isinstance(messages, list):
                    continue
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    from_number = message.get('from', '')
                    message_text_data = message.get('text', {})
                    message_text = (
                        message_text_data.get('body', '')
                        if isinstance(message_text_data, dict)
                        else ''
                    )
                    message_id = message.get('id', '')
                    
                    if not message_text or not from_number:
                        continue
                    
                    print(f"📱 Получено WhatsApp сообщение от {from_number}: {message_text}")
                    
                    # Находим бизнес по phone_id из webhook
                    # В WABA webhook phone_number_id указывает на бизнес, который получил сообщение
                    metadata = value.get('metadata', {})
                    phone_id = (
                        metadata.get('phone_number_id', '')
                        if isinstance(metadata, dict)
                        else ''
                    )
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
    """Handle a business-scoped Telegram callback after authenticating it."""
    raw_business_id = str(request.args.get("business_id") or "").strip()
    supplied_secret = str(request.headers.get(TELEGRAM_WEBHOOK_SECRET_HEADER) or "")
    secret_is_malformed = len(supplied_secret) != 64 or any(
        character not in "0123456789abcdef" for character in supplied_secret
    )
    if request.headers.get("X-Bot-Token") or request.args.get("bot_token") or secret_is_malformed:
        return jsonify({"error": "Webhook authentication failed"}), 403
    try:
        business_id = str(uuid.UUID(raw_business_id))
    except (TypeError, ValueError, AttributeError):
        return jsonify({"error": "Webhook authentication failed"}), 403

    database = DatabaseManager()
    try:
        cursor = database.conn.cursor()
        cursor.execute(
            "SELECT id, telegram_bot_token FROM Businesses WHERE id = %s LIMIT 1",
            (business_id,),
        )
        row = cursor.fetchone()
        row_dict = dict(row) if row else {}
        stored_bot_token = decode_telegram_bot_token(row_dict.get("telegram_bot_token"))
        if not stored_bot_token or not has_valid_telegram_webhook_secret(
            supplied_secret, stored_bot_token, business_id
        ):
            return jsonify({"error": "Webhook authentication failed"}), 403

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid webhook payload"}), 400
        if "bot_token" in data:
            return jsonify({"error": "Invalid webhook payload"}), 400

        message = data.get("message")
        if message is None:
            return jsonify({"status": "ok"}), 200
        if not isinstance(message, dict):
            return jsonify({"error": "Invalid webhook payload"}), 400
        chat = message.get("chat")
        from_user = message.get("from")
        if not isinstance(chat, dict) or not isinstance(from_user, dict):
            return jsonify({"error": "Invalid webhook payload"}), 400

        chat_id = str(chat.get("id") or "")
        user_id = str(from_user.get("id") or "")
        username = str(from_user.get("username") or "")
        first_name = str(from_user.get("first_name") or "")
        message_text = message.get("text")
        if not isinstance(message_text, str) or not message_text or not chat_id:
            return jsonify({"status": "ok"}), 200

        runtime_gate = business_agent_enabled_for_channel(cursor, business_id)
        if not bool(runtime_gate.get("enabled")):
            return jsonify({"status": "ok"}), 200

        agent_transport_decision = {"allow_normal_routing": True, "code": "HUMAN_SENDER"}
        if bool(from_user.get("is_bot")):
            agent_transport_decision = evaluate_and_record_telegram_agent_transport(
                cursor,
                data,
                local_bot_username=os.getenv("TELEGRAM_BOT_USERNAME", ""),
                ip=request.headers.get("X-Forwarded-For", request.remote_addr or ""),
                user_agent=request.headers.get("User-Agent", ""),
            )
            database.conn.commit()
        if not agent_transport_decision.get("allow_normal_routing"):
            return jsonify({"status": "ignored", "reason": agent_transport_decision.get("code")}), 200

        trigger_result = dispatch_telegram_message_to_agent_blueprints(
            cursor,
            business_id,
            {
                "message_text": message_text,
                "telegram_user_id": user_id,
                "telegram_username": username,
                "telegram_first_name": first_name,
                "chat_id": chat_id,
                "message_id": str(message.get("message_id") or ""),
            },
        )
        database.conn.commit()
        if trigger_result.get("matched_count"):
            return jsonify(
                {
                    "status": "ok",
                    "agent_workflow": {
                        "trigger_event_id": trigger_result.get("trigger_event_id"),
                        "started_runs": trigger_result.get("started_runs"),
                    },
                }
            ), 200

        result = process_message(
            business_id=business_id,
            client_phone=f"tg_{user_id}",
            client_name=first_name or username or None,
            message=message_text,
        )
        if result.get("success") and result.get("response"):
            send_telegram_message(
                bot_token=stored_bot_token,
                chat_id=chat_id,
                message=result["response"],
            )
        return jsonify({"status": "ok"}), 200
    except Exception:
        database.conn.rollback()
        print("❌ Ошибка обработки Telegram webhook")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Webhook processing failed"}), 500
    finally:
        database.close()


@ai_webhooks_bp.route('/api/webhooks/telegram/<bot_token>', methods=['POST'])
def telegram_webhook_with_token(bot_token: str):
    """Deny the retired raw-token URL without inspecting its value or payload."""
    return jsonify({"error": "Webhook endpoint retired; rebind required"}), 410
