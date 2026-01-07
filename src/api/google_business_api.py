#!/usr/bin/env python3
"""
API эндпоинты для Google Business Profile интеграции
"""
import os
import json
import uuid
from flask import Blueprint, request, jsonify, redirect
from database_manager import DatabaseManager
from auth_system import verify_session
from google_business_auth import GoogleBusinessAuth
from google_business_sync_worker import GoogleBusinessSyncWorker
from auth_encryption import encrypt_auth_data, decrypt_auth_data
from core.helpers import get_business_owner_id

google_business_bp = Blueprint('google_business', __name__)

def _verify_auth_and_access(business_id: str) -> tuple[dict, DatabaseManager] | tuple[None, None]:
    """Проверить авторизацию и доступ к бизнесу. Возвращает (user_data, db) или (None, None)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, None
    
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return None, None
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    owner_id = get_business_owner_id(cursor, business_id)
    
    if not owner_id:
        db.close()
        return None, None
    
    if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
        db.close()
        return None, None
    
    return user_data, db

def _get_google_account(cursor, business_id: str, account_id: str = None) -> dict | None:
    """Получить Google аккаунт для бизнеса"""
    if account_id:
        cursor.execute("""
            SELECT * FROM ExternalBusinessAccounts
            WHERE id = ? AND business_id = ? AND source = 'google_business' AND is_active = 1
        """, (account_id, business_id))
    else:
        cursor.execute("""
            SELECT * FROM ExternalBusinessAccounts
            WHERE business_id = ? AND source = 'google_business' AND is_active = 1
            LIMIT 1
        """, (business_id,))
    
    account_row = cursor.fetchone()
    return dict(account_row) if account_row else None

@google_business_bp.route('/api/google/oauth/authorize', methods=['GET', 'OPTIONS'])
def google_oauth_authorize():
    """
    Начать OAuth авторизацию
    
    Query параметры:
    - business_id: ID бизнеса для подключения Google
    
    Returns:
    - auth_url: URL для редиректа пользователя на авторизацию Google
    """
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        # Проверка авторизации
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        business_id = request.args.get('business_id')
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        # Проверяем доступ к бизнесу
        db = DatabaseManager()
        cursor = db.conn.cursor()
        owner_id = get_business_owner_id(cursor, business_id)
        db.close()
        
        if not owner_id:
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Генерируем state для безопасности (user_id + business_id)
        state = f"{user_data['user_id']}_{business_id}"
        
        auth = GoogleBusinessAuth()
        auth_url = auth.get_authorization_url(state)
        
        return jsonify({
            "success": True,
            "auth_url": auth_url
        })
    except Exception as e:
        print(f"❌ Ошибка OAuth авторизации: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@google_business_bp.route('/api/google/oauth/callback', methods=['GET'])
def google_oauth_callback():
    """
    Обработка OAuth callback от Google
    
    Query параметры:
    - code: Authorization code от Google
    - state: State для проверки (user_id_business_id)
    
    Returns:
    - HTML страница с редиректом на фронтенд или сообщение об успехе
    """
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    
    if error:
        # Пользователь отменил авторизацию
        return redirect(f"{frontend_url}/dashboard/profile?google_auth=error")
    
    if not code or not state:
        return redirect(f"{frontend_url}/dashboard/profile?google_auth=error")
    
    # Парсим state (user_id_business_id)
    try:
        user_id, business_id = state.split('_', 1)
    except ValueError:
        return redirect(f"{frontend_url}/dashboard/profile?google_auth=error")
    
    try:
        auth = GoogleBusinessAuth()
        credentials = auth.get_credentials_from_code(code)
        
        # Преобразуем credentials в словарь
        creds_dict = auth.credentials_to_dict(credentials)
        creds_json = json.dumps(creds_dict)
        
        # Шифруем credentials
        encrypted_creds = encrypt_auth_data(creds_json)
        
        # Сохраняем или обновляем аккаунт в ExternalBusinessAccounts
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, есть ли уже аккаунт для этого бизнеса
        cursor.execute("""
            SELECT id FROM ExternalBusinessAccounts
            WHERE business_id = ? AND source = 'google_business'
        """, (business_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующий аккаунт
            cursor.execute("""
                UPDATE ExternalBusinessAccounts
                SET auth_data = ?, is_active = 1, last_sync_at = CURRENT_TIMESTAMP, last_error = NULL
                WHERE id = ?
            """, (encrypted_creds, existing[0]))
        else:
            # Создаем новый аккаунт
            account_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO ExternalBusinessAccounts
                (id, business_id, source, external_id, display_name, auth_data, is_active, created_at, updated_at)
                VALUES (?, ?, 'google_business', ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (account_id, business_id, None, 'Google Business', encrypted_creds))
        
        db.conn.commit()
        db.close()
        
        # Редиректим на фронтенд с успешным статусом
        return redirect(f"{frontend_url}/dashboard/profile?google_auth=success")
        
    except Exception as e:
        print(f"❌ Ошибка обработки OAuth callback: {e}")
        import traceback
        traceback.print_exc()
        return redirect(f"{frontend_url}/dashboard/profile?google_auth=error")

@google_business_bp.route('/api/business/<business_id>/google/publish-review-reply', methods=['POST', 'OPTIONS'])
def publish_review_reply(business_id):
    """Опубликовать ответ на отзыв в Google"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        # Проверка авторизации и доступа
        user_data, db = _verify_auth_and_access(business_id)
        if not user_data:
            return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401
        
        cursor = db.conn.cursor()
        
        data = request.get_json()
        review_id = data.get('review_id')
        reply_text = data.get('reply_text')
        account_id = data.get('account_id')
        
        if not review_id or not reply_text:
            db.close()
            return jsonify({"error": "review_id и reply_text обязательны"}), 400
        
        # Получаем аккаунт
        account = _get_google_account(cursor, business_id, account_id)
        db.close()
        
        if not account:
            return jsonify({"error": "Google аккаунт не найден или не активен"}), 404
        
        worker = GoogleBusinessSyncWorker()
        success = worker._publish_review_reply(account, review_id, reply_text)
        
        return jsonify({"success": success})
    except Exception as e:
        print(f"❌ Ошибка публикации ответа на отзыв: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@google_business_bp.route('/api/business/<business_id>/google/publish-post', methods=['POST', 'OPTIONS'])
def publish_post(business_id):
    """Опубликовать пост/новость в Google"""
    if request.method == 'OPTIONS':
        return ('', 204)
    
    try:
        # Проверка авторизации и доступа
        user_data, db = _verify_auth_and_access(business_id)
        if not user_data:
            return jsonify({"error": "Требуется авторизация или нет доступа к бизнесу"}), 401
        
        cursor = db.conn.cursor()
        
        data = request.get_json()
        post_data = {
            'summary': data.get('title', ''),
            'callToAction': {
                'actionType': data.get('action_type', 'CALL'),
                'url': data.get('url', '')
            },
            'media': data.get('media', [])
        }
        
        account_id = data.get('account_id')
        
        # Получаем аккаунт
        account = _get_google_account(cursor, business_id, account_id)
        db.close()
        
        if not account:
            return jsonify({"error": "Google аккаунт не найден или не активен"}), 404
        
        worker = GoogleBusinessSyncWorker()
        post_id = worker._publish_post(account, post_data)
        
        if post_id:
            return jsonify({"success": True, "post_id": post_id})
        else:
            return jsonify({"error": "Не удалось опубликовать пост"}), 500
    except Exception as e:
        print(f"❌ Ошибка публикации поста: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

