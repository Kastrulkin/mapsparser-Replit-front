#!/usr/bin/env python3
"""
API для управления пользователями
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from auth_system import *
from datetime import datetime
import time

# Простой in-memory rate limiting (для dev)
_rate_buckets = {}

def _rate_key(ip: str, endpoint: str) -> str:
    return f"{ip}:{endpoint}"

def rate_limited(limit: int = 10, window_sec: int = 60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            ip = request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'
            key = _rate_key(ip, request.endpoint or func.__name__)
            now = time.time()
            window_start = now - window_sec
            timestamps = _rate_buckets.get(key, [])
            # чистим старые
            timestamps = [t for t in timestamps if t > window_start]
            if len(timestamps) >= limit:
                return jsonify({"error": "Слишком много запросов. Попробуйте позже."}), 429
            timestamps.append(now)
            _rate_buckets[key] = timestamps
            return func(*args, **kwargs)
        # сохраняем метаданные
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

app = Flask(__name__)
CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000'])

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/public/request-report', methods=['POST'])
@rate_limited(limit=5, window_sec=60)
def public_request_report():
    """Публичная заявка на отчёт без авторизации.
    Принимает email и url, создаёт пользователя при необходимости и добавляет URL в ParseQueue.
    """
    try:
        data = request.get_json() or {}
        email = data.get('email')
        url = data.get('url')

        if not email or not url:
            return jsonify({"error": "Email и URL обязательны"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Ищем пользователя по email
        cursor.execute("SELECT id FROM Users WHERE email = ?", (email,))
        user_row = cursor.fetchone()

        if user_row:
            user_id = user_row['id']
        else:
            # Создаём пользователя без пароля
            from auth_system import create_user as create_user_func
            create_result = create_user_func(email)
            if 'error' in create_result:
                conn.close()
                return jsonify(create_result), 400
            user_id = create_result['id']

        # Добавляем заявку в очередь
        from add_to_queue import add_to_queue as add_to_queue_func
        queue_id = add_to_queue_func(url, user_id)

        conn.close()

        return jsonify({
            "queue_id": queue_id,
            "message": "Заявка принята. Мы свяжемся с вами в ближайшее время."
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/register', methods=['POST'])
@rate_limited(limit=5, window_sec=60)
def register():
    """Регистрация нового пользователя"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        phone = data.get('phone')
        
        if not email:
            return jsonify({"error": "Email обязателен"}), 400
        
        # Если пароль пустой, создаем пользователя без пароля
        if not password:
            password = None
        
        result = create_user(email, password, name, phone)
        
        if 'error' in result:
            return jsonify(result), 400
        
        # Создаем сессию
        token = create_session(result['id'], 
                             request.environ.get('REMOTE_ADDR'),
                             request.headers.get('User-Agent'))
        
        if token:
            result['token'] = token
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
@rate_limited(limit=10, window_sec=60)
def login():
    """Вход пользователя"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email:
            return jsonify({"error": "Email обязателен"}), 400
        
        # Если пароль пустой, проверяем, есть ли у пользователя пароль
        if not password:
            # Проверяем, есть ли у пользователя пароль в базе
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM Users WHERE email = ?", (email,))
            user = cursor.fetchone()
            conn.close()
            
            if not user:
                return jsonify({"error": "Пользователь не найден"}), 401
            
            if user['password_hash']:
                return jsonify({"error": "Пароль обязателен"}), 400
            else:
                # У пользователя нет пароля, возвращаем NEED_PASSWORD
                return jsonify({"error": "NEED_PASSWORD", "message": "Необходимо установить пароль"}), 400
        
        result = authenticate_user(email, password)
        
        if 'error' in result:
            return jsonify(result), 401
        
        # Создаем сессию
        token = create_session(result['id'],
                             request.environ.get('REMOTE_ADDR'),
                             request.headers.get('User-Agent'))
        
        if token:
            result['token'] = token
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Выход пользователя"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Токен не предоставлен"}), 401
        
        success = logout_session(token)
        
        if success:
            return jsonify({"message": "Выход выполнен успешно"}), 200
        else:
            return jsonify({"error": "Недействительный токен"}), 401
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """Получить текущего пользователя"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Токен не предоставлен"}), 401
        
        user = verify_session(token)
        
        if not user:
            return jsonify({"error": "Недействительный токен"}), 401
        
        return jsonify(user), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/profile', methods=['PUT'])
def update_profile():
    """Обновить профиль пользователя"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Токен не предоставлен"}), 401
        
        user = verify_session(token)
        
        if not user:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        success = update_user(user['user_id'], **data)
        
        if success:
            return jsonify({"message": "Профиль обновлен"}), 200
        else:
            return jsonify({"error": "Ошибка при обновлении профиля"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/change-password', methods=['POST'])
def change_password():
    """Изменить пароль"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Токен не предоставлен"}), 401
        
        user = verify_session(token)
        
        if not user:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        if not old_password or not new_password:
            return jsonify({"error": "Старый и новый пароль обязательны"}), 400
        
        result = change_password(user['user_id'], old_password, new_password)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/set-password', methods=['POST'])
@rate_limited(limit=5, window_sec=60)
def set_password():
    """Установить пароль для нового пользователя"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"error": "Email и пароль обязательны"}), 400
        
        # Находим пользователя по email
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM Users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404
        
        # Устанавливаем пароль
        from auth_system import set_password as set_password_func
        result = set_password_func(user['id'], password)
        
        if 'error' in result:
            return jsonify(result), 400
        
        # Создаем сессию
        token = create_session(user['id'], 
                             request.environ.get('REMOTE_ADDR'),
                             request.headers.get('User-Agent'))
        
        if token:
            result['token'] = token
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/users/queue', methods=['GET'])
def get_user_queue():
    """Получить очередь пользователя"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Токен не предоставлен"}), 401
        
        user = verify_session(token)
        
        if not user:
            return jsonify({"error": "Недействительный токен"}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, url, status, created_at 
            FROM ParseQueue 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        """, (user['user_id'],))
        
        queue_items = []
        for row in cursor.fetchall():
            queue_items.append({
                "id": row['id'],
                "url": row['url'],
                "status": row['status'],
                "created_at": row['created_at']
            })
        
        conn.close()
        
        return jsonify({"queue": queue_items}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/reports', methods=['GET'])
def get_user_reports():
    """Получить отчёты пользователя"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Токен не предоставлен"}), 401
        
        user = verify_session(token)
        
        if not user:
            return jsonify({"error": "Недействительный токен"}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем отчёты пользователя из Cards таблицы
        cursor.execute("""
            SELECT id, url, report_path, ai_analysis, seo_score, created_at
            FROM Cards 
            WHERE user_id = ? AND report_path IS NOT NULL
            ORDER BY created_at DESC
        """, (user['user_id'],))
        
        reports = []
        for row in cursor.fetchall():
            reports.append({
                "id": row['id'],
                "url": row['url'],
                "report_path": row['report_path'],
                "ai_analysis": row['ai_analysis'],
                "seo_score": row['seo_score'],
                "created_at": row['created_at'],
                "has_report": True
            })
        
        conn.close()
        
        return jsonify({"reports": reports}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/add-to-queue', methods=['POST'])
def add_to_queue():
    """Добавить URL в очередь парсинга"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Токен не предоставлен"}), 401
        
        user = verify_session(token)
        
        if not user:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({"error": "URL обязателен"}), 400
        
        # Добавляем в очередь
        from add_to_queue import add_to_queue
        queue_id = add_to_queue(url, user['user_id'])
        
        return jsonify({"queue_id": queue_id, "message": "URL добавлен в очередь"}), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/invite', methods=['POST'])
def create_invite():
    """Создать приглашение"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Токен не предоставлен"}), 401
        
        user = verify_session(token)
        
        if not user:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({"error": "Email обязателен"}), 400
        
        result = create_invite(user['user_id'], email)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/verify-invite/<token>', methods=['GET'])
def verify_invite_endpoint(token):
    """Проверить приглашение"""
    try:
        invite = verify_invite(token)
        
        if not invite:
            return jsonify({"error": "Недействительное или просроченное приглашение"}), 400
        
        return jsonify({"email": invite['email']}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/accept-invite', methods=['POST'])
def accept_invite_endpoint():
    """Принять приглашение"""
    try:
        data = request.get_json()
        token = data.get('token')
        password = data.get('password')
        name = data.get('name')
        
        if not token or not password:
            return jsonify({"error": "Токен и пароль обязательны"}), 400
        
        result = accept_invite(token, password, name)
        
        if 'error' in result:
            return jsonify(result), 400
        
        # Создаем сессию
        session_token = create_session(result['id'],
                                    request.environ.get('REMOTE_ADDR'),
                                    request.headers.get('User-Agent'))
        
        if session_token:
            result['token'] = session_token
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/users/queue/<queue_id>', methods=['DELETE'])
def delete_queue_item(queue_id):
    """Удалить элемент из очереди"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({"error": "Токен не предоставлен"}), 401
        
        user = verify_session(token)
        
        if not user:
            return jsonify({"error": "Недействительный токен"}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем, что элемент принадлежит пользователю
        cursor.execute("SELECT id FROM ParseQueue WHERE id = ? AND user_id = ?", (queue_id, user['user_id']))
        queue_item = cursor.fetchone()
        
        if not queue_item:
            conn.close()
            return jsonify({"error": "Элемент очереди не найден"}), 404
        
        # Удаляем элемент из очереди
        cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (queue_id,))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Элемент очереди удалён"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze-card', methods=['POST'])
@rate_limited(limit=5, window_sec=60)
def analyze_card():
    """Анализ скриншота карточки Яндекс.Карт через GigaChat API"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_id = verify_token(token)
        if not user_id:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем наличие файла
        if 'image' not in request.files:
            return jsonify({"error": "Файл изображения не найден"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        # Проверяем тип файла
        allowed_types = ['image/png', 'image/jpeg', 'image/jpg']
        if file.content_type not in allowed_types:
            return jsonify({"error": "Неподдерживаемый формат файла. Разрешены: PNG, JPG, JPEG"}), 400
        
        # Проверяем размер файла (15 МБ)
        file.seek(0, 2)  # Переходим в конец файла
        file_size = file.tell()
        file.seek(0)  # Возвращаемся в начало
        
        if file_size > 15 * 1024 * 1024:  # 15 МБ
            return jsonify({"error": "Файл слишком большой. Максимальный размер: 15 МБ"}), 400
        
        # Сохраняем временный файл
        import tempfile
        import os
        from card_analyzer import CardAnalyzer
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # Анализируем карточку
            analyzer = CardAnalyzer()
            result = analyzer.analyze_card_screenshot(temp_path)
            
            return jsonify(result)
            
        finally:
            # Удаляем временный файл
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        return jsonify({"error": f"Ошибка анализа карточки: {str(e)}"}), 500

@app.route('/api/optimize-pricelist', methods=['POST'])
@rate_limited(limit=5, window_sec=60)
def optimize_pricelist():
    """SEO оптимизация прайс-листа через GigaChat API"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_id = verify_token(token)
        if not user_id:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем наличие файла
        if 'file' not in request.files:
            return jsonify({"error": "Файл прайс-листа не найден"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        # Проверяем тип файла
        allowed_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        if file.content_type not in allowed_types:
            return jsonify({"error": "Неподдерживаемый формат файла. Разрешены: PDF, DOC, DOCX, XLS, XLSX"}), 400
        
        # Проверяем размер файла (15 МБ)
        file.seek(0, 2)  # Переходим в конец файла
        file_size = file.tell()
        file.seek(0)  # Возвращаемся в начало
        
        if file_size > 15 * 1024 * 1024:  # 15 МБ
            return jsonify({"error": "Файл слишком большой. Максимальный размер: 15 МБ"}), 400
        
        # Сохраняем временный файл
        import tempfile
        import os
        from seo_optimizer import SEOOptimizer
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # Оптимизируем прайс-лист
            optimizer = SEOOptimizer()
            result = optimizer.optimize_pricelist(temp_path)
            
            return jsonify(result)
            
        finally:
            # Удаляем временный файл
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        return jsonify({"error": f"Ошибка оптимизации прайс-листа: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002, debug=True)
