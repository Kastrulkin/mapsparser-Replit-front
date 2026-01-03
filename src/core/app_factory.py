"""
Фабрика для создания Flask приложения
"""
import os
from flask import Flask
from flask_cors import CORS

# Rate limiting для защиты от brute force и DDoS
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    print('⚠️ flask-limiter не установлен. Rate limiting отключен. Установите: pip install flask-limiter')

def create_app():
    """Создать и настроить Flask приложение"""
    app = Flask(__name__)
    
    # Настройка CORS для продакшена и разработки
    # В .env укажите: ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
    allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
    allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]
    CORS(app, supports_credentials=True, origins=allowed_origins)
    
    # Настройка rate limiting
    if RATE_LIMITER_AVAILABLE:
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"],
            storage_uri="memory://"  # Для продакшена лучше использовать Redis
        )
        print("✅ Rate limiting включен")
    else:
        limiter = None
    
    # Регистрируем Blueprint'ы
    from chatgpt_api import chatgpt_bp
    from chatgpt_search_api import chatgpt_search_bp
    from stripe_integration import stripe_bp
    from admin_moderation import admin_moderation_bp
    from bookings_api import bookings_bp
    from ai_agent_webhooks import ai_webhooks_bp
    from ai_agents_api import ai_agents_api_bp
    from chats_api import chats_bp
    
    app.register_blueprint(chatgpt_bp)
    app.register_blueprint(chatgpt_search_bp)
    app.register_blueprint(stripe_bp)
    app.register_blueprint(admin_moderation_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(ai_webhooks_bp)
    app.register_blueprint(ai_agents_api_bp)
    app.register_blueprint(chats_bp)
    
    return app, limiter

def rate_limit_if_available(limiter, limit_str):
    """Декоратор для применения rate limiting, если limiter доступен"""
    def decorator(f):
        if limiter:
            return limiter.limit(limit_str)(f)
        return f
    return decorator

