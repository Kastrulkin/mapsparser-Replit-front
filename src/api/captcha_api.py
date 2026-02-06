"""
API endpoints для human-in-the-loop обработки капчи через noVNC.

TODO: Интеграция с noVNC сервером (например, novnc-websockify).
Контракт API:
- GET /tasks/{id}/captcha?token=... -> HTML страница с iframe на /vnc/{session_id}?token=...
- POST /tasks/{id}/captcha/resume?token=... -> ставит resume_requested=true
- /vnc/{session_id}?token=... -> проксирует noVNC (или отдаёт ссылку на уже существующий прокси), проверяя token+TTL
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from safe_db_utils import get_db_connection

captcha_bp = Blueprint('captcha', __name__)

# HTML шаблон для страницы с noVNC
CAPTCHA_PAGE_HTML_WAITING = """
<!DOCTYPE html>
<html>
<head>
    <title>Решение капчи - Задача {{ task_id }}</title>
    <meta charset="utf-8">
    <style>
        body { margin: 0; padding: 20px; font-family: Arial, sans-serif; }
        .header { margin-bottom: 20px; }
        .status-info { padding: 10px; margin-bottom: 10px; border-radius: 4px; }
        .status-waiting { background: #e3f2fd; border: 1px solid #2196F3; }
        .status-expired { background: #fff3e0; border: 1px solid #ff9800; }
        .status-token-expired { background: #ffebee; border: 1px solid #f44336; }
        .vnc-container { width: 100%; height: 80vh; border: 1px solid #ccc; }
        .actions { margin-top: 20px; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; margin-right: 10px; }
        .btn-continue { background: #4CAF50; color: white; border: none; }
        .btn-restart { background: #ff9800; color: white; border: none; }
        .btn-refresh { background: #2196F3; color: white; border: none; }
        .btn-cancel { background: #f44336; color: white; border: none; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Решение капчи</h1>
        <p>Задача: {{ task_id }}</p>
        <div id="status-info" class="status-info status-waiting">
            <p>Решите капчу в окне ниже, затем нажмите "Продолжить"</p>
        </div>
    </div>
    <div class="vnc-container">
        <iframe id="vnc-iframe" src="/vnc/{{ session_id }}?token={{ token }}" width="100%" height="100%" frameborder="0"></iframe>
    </div>
    <div class="actions">
        <button class="btn-continue" onclick="resumeParsing()">Продолжить</button>
        <button class="btn-cancel" onclick="window.close()">Отмена</button>
    </div>
    <script>
        let taskId = '{{ task_id }}';
        let token = '{{ token }}';
        
        // Авто-refresh статуса раз в 5 секунд
        function checkStatus() {
            fetch(`/tasks/${taskId}/captcha/status?token=${token}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'expired') {
                        showExpiredMessage();
                    } else if (data.token_expired) {
                        showTokenExpiredMessage();
                    }
                })
                .catch(error => console.error('Ошибка проверки статуса:', error));
        }
        
        function showExpiredMessage() {
            document.getElementById('status-info').innerHTML = 
                '<p><strong>Сессия истекла.</strong> Нажмите "Перезапустить сессию"</p>';
            document.getElementById('status-info').className = 'status-info status-expired';
            document.querySelector('.btn-continue').style.display = 'none';
            let restartBtn = document.createElement('button');
            restartBtn.className = 'btn-restart';
            restartBtn.textContent = 'Перезапустить сессию';
            restartBtn.onclick = restartSession;
            document.querySelector('.actions').insertBefore(restartBtn, document.querySelector('.btn-cancel'));
        }
        
        function showTokenExpiredMessage() {
            document.getElementById('status-info').innerHTML = 
                '<p><strong>Ссылка истекла.</strong> Нажмите "Обновить ссылку"</p>';
            document.getElementById('status-info').className = 'status-info status-token-expired';
        }
        
        function resumeParsing() {
            fetch(`/tasks/${taskId}/captcha/resume?token=${token}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Парсинг продолжен!');
                    window.close();
                } else {
                    alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                }
            })
            .catch(error => {
                alert('Ошибка: ' + error.message);
            });
        }
        
        function restartSession() {
            fetch(`/tasks/${taskId}/captcha/restart?token=${token}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Сессия перезапущена! Обновите страницу.');
                    window.location.reload();
                } else {
                    alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                }
            })
            .catch(error => {
                alert('Ошибка: ' + error.message);
            });
        }
        
        // Запускаем проверку статуса каждые 5 секунд
        setInterval(checkStatus, 5000);
    </script>
</body>
</html>
"""

CAPTCHA_PAGE_HTML_EXPIRED = """
<!DOCTYPE html>
<html>
<head>
    <title>Сессия истекла - Задача {{ task_id }}</title>
    <meta charset="utf-8">
    <style>
        body { margin: 0; padding: 20px; font-family: Arial, sans-serif; }
        .header { margin-bottom: 20px; }
        .status-expired { background: #fff3e0; border: 1px solid #ff9800; padding: 20px; border-radius: 4px; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; margin-right: 10px; }
        .btn-restart { background: #ff9800; color: white; border: none; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Сессия истекла</h1>
        <p>Задача: {{ task_id }}</p>
        <div class="status-expired">
            <p><strong>Сессия истекла.</strong> Нажмите "Перезапустить сессию"</p>
        </div>
    </div>
    <div class="actions">
        <button class="btn-restart" onclick="restartSession()">Перезапустить сессию</button>
    </div>
    <script>
        function restartSession() {
            fetch('/tasks/{{ task_id }}/captcha/restart?token={{ token }}', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Сессия перезапущена! Обновите страницу.');
                    window.location.reload();
                } else {
                    alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                }
            })
            .catch(error => {
                alert('Ошибка: ' + error.message);
            });
        }
    </script>
</body>
</html>
"""

@captcha_bp.route('/tasks/<task_id>/captcha', methods=['GET'])
def show_captcha_page(task_id: str):
    """
    Отображает страницу с noVNC для решения капчи.
    
    Args:
        task_id: ID задачи в очереди
        token: одноразовый токен (query parameter)
    
    Returns:
        HTML страница с iframe на /vnc/{session_id}?token=...
    """
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Token required"}), 400
    
    # Проверяем токен и получаем session_id
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT captcha_session_id, captcha_token, captcha_started_at, 
                   captcha_token_expires_at, captcha_status
            FROM parsequeue
            WHERE id = %s AND captcha_token = %s
        """, (task_id, token))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Invalid token or task not found"}), 404
        
        session_id = row.get('captcha_session_id') if isinstance(row, dict) else row[0]
        started_at_str = row.get('captcha_started_at') if isinstance(row, dict) else row[2]
        expires_at_str = row.get('captcha_token_expires_at') if isinstance(row, dict) else (row[3] if len(row) > 3 else None)
        captcha_status = row.get('captcha_status') if isinstance(row, dict) else (row[4] if len(row) > 4 else None)
        
        # Проверяем статус задачи
        if captcha_status == 'expired':
            html = CAPTCHA_PAGE_HTML_EXPIRED.replace('{{ task_id }}', task_id)
            html = html.replace('{{ token }}', token)
            return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
        # Проверяем TTL токена (30 минут)
        token_expired = False
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(str(expires_at_str).replace('Z', '+00:00'))
                if isinstance(expires_at, str):
                    from dateutil import parser as date_parser
                    expires_at = date_parser.parse(expires_at)
                
                if expires_at.replace(tzinfo=None) < datetime.now():
                    token_expired = True
            except Exception as e:
                print(f"⚠️ Ошибка проверки TTL: {e}")
                # Fallback на старую логику (15 минут от started_at)
                if started_at_str:
                    try:
                        started_at = datetime.fromisoformat(str(started_at_str).replace('Z', '+00:00'))
                        if isinstance(started_at, str):
                            from dateutil import parser as date_parser
                            started_at = date_parser.parse(started_at)
                        elapsed = (datetime.now() - started_at.replace(tzinfo=None)).total_seconds()
                        if elapsed > 1800:  # 30 минут
                            token_expired = True
                    except:
                        pass
        
        if token_expired:
            return jsonify({"error": "Token expired", "refresh_available": True}), 403
        
        # Рендерим HTML страницу
        html = CAPTCHA_PAGE_HTML_WAITING.replace('{{ task_id }}', task_id)
        html = html.replace('{{ session_id }}', str(session_id))
        html = html.replace('{{ token }}', token)
        
        return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    finally:
        cursor.close()
        conn.close()

@captcha_bp.route('/tasks/<task_id>/captcha/resume', methods=['POST'])
def resume_parsing(task_id: str):
    """
    Устанавливает флаг resume_requested=true для продолжения парсинга.
    
    Args:
        task_id: ID задачи в очереди
        token: одноразовый токен (query parameter)
    
    Returns:
        JSON с результатом операции
    """
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Token required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Проверяем токен и обновляем флаг
        cursor.execute("""
            UPDATE parsequeue 
            SET resume_requested = TRUE,
                captcha_status = 'resume',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND captcha_token = %s
        """, (task_id, token))
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Invalid token or task not found"}), 404
        
        return jsonify({"success": True, "message": "Parsing will resume shortly"}), 200
    finally:
        cursor.close()
        conn.close()

@captcha_bp.route('/tasks/<task_id>/captcha/status', methods=['GET'])
def get_captcha_status(task_id: str):
    """
    Возвращает текущий статус капчи для авто-refresh.
    
    Args:
        task_id: ID задачи
        token: одноразовый токен (query parameter)
    
    Returns:
        JSON с статусом и информацией о токене
    """
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Token required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT captcha_status, captcha_token_expires_at, captcha_started_at
            FROM parsequeue
            WHERE id = %s AND captcha_token = %s
        """, (task_id, token))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Invalid token or task not found"}), 404
        
        captcha_status = row.get('captcha_status') if isinstance(row, dict) else row[0]
        expires_at_str = row.get('captcha_token_expires_at') if isinstance(row, dict) else (row[1] if len(row) > 1 else None)
        started_at_str = row.get('captcha_started_at') if isinstance(row, dict) else (row[2] if len(row) > 2 else None)
        
        token_expired = False
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(str(expires_at_str).replace('Z', '+00:00'))
                if isinstance(expires_at, str):
                    from dateutil import parser as date_parser
                    expires_at = date_parser.parse(expires_at)
                if expires_at.replace(tzinfo=None) < datetime.now():
                    token_expired = True
            except:
                # Fallback на старую логику
                if started_at_str:
                    try:
                        started_at = datetime.fromisoformat(str(started_at_str).replace('Z', '+00:00'))
                        if isinstance(started_at, str):
                            from dateutil import parser as date_parser
                            started_at = date_parser.parse(started_at)
                        elapsed = (datetime.now() - started_at.replace(tzinfo=None)).total_seconds()
                        if elapsed > 1800:  # 30 минут
                            token_expired = True
                    except:
                        pass
        
        return jsonify({
            "status": captcha_status,
            "token_expired": token_expired
        }), 200
    finally:
        cursor.close()
        conn.close()

@captcha_bp.route('/tasks/<task_id>/captcha/restart', methods=['POST'])
def restart_captcha_session(task_id: str):
    """
    Перезапускает сессию капчи (сбрасывает captcha_* поля и запускает новый парсинг).
    
    Args:
        task_id: ID задачи
        token: одноразовый токен (query parameter)
    
    Returns:
        JSON с результатом операции
    """
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Token required"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Проверяем токен и статус
        cursor.execute("""
            SELECT captcha_status, captcha_token
            FROM parsequeue
            WHERE id = %s AND captcha_token = %s
        """, (task_id, token))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Invalid token or task not found"}), 404
        
        captcha_status = row.get('captcha_status') if isinstance(row, dict) else row[0]
        
        # Сбрасываем captcha_* поля и возвращаем задачу в pending
        cursor.execute("""
            UPDATE parsequeue 
            SET status = 'pending',
                captcha_required = FALSE,
                captcha_url = NULL,
                captcha_session_id = NULL,
                captcha_token = NULL,
                captcha_token_expires_at = NULL,
                captcha_vnc_path = NULL,
                captcha_started_at = NULL,
                captcha_status = NULL,
                resume_requested = FALSE,
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (task_id,))
        conn.commit()
        
        return jsonify({
            "success": True, 
            "message": "Session restarted. Task returned to pending queue."
        }), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@captcha_bp.route('/vnc/<session_id>', methods=['GET'])
def vnc_proxy(session_id: str):
    """
    Проксирует noVNC соединение (TODO: интеграция с novnc-websockify).
    
    Args:
        session_id: UUID сессии браузера
        token: одноразовый токен (query parameter)
    
    Returns:
        HTML страницу noVNC или редирект на существующий прокси
    """
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Token required"}), 400
    
    # TODO: Проверка токена и session_id
    # TODO: Интеграция с novnc-websockify для проксирования WebSocket соединения
    # Пока что возвращаем заглушку
    
    return jsonify({
        "error": "VNC proxy not implemented yet",
        "session_id": session_id,
        "note": "This endpoint should proxy WebSocket connection to noVNC server"
    }), 501
