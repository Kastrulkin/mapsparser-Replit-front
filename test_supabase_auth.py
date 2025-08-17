#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики проблем с аутентификацией Supabase
"""

import os
import sys
from dotenv import load_dotenv
import requests
import json
from datetime import datetime

# Загружаем переменные окружения
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

def test_supabase_connection():
    """Тестирует подключение к Supabase"""
    print("🔍 Тестирование подключения к Supabase...")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Ошибка: SUPABASE_URL или SUPABASE_KEY не найдены в .env")
        return False
    
    print(f"✅ Supabase URL: {SUPABASE_URL}")
    print(f"✅ Supabase Key: {SUPABASE_KEY[:20]}...")
    
    # Тестируем API
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Тест базового API
        response = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=headers, timeout=10)
        print(f"✅ API доступен: {response.status_code}")
        
        # Тест auth API
        auth_response = requests.get(f"{SUPABASE_URL}/auth/v1/", headers=headers, timeout=10)
        print(f"✅ Auth API доступен: {auth_response.status_code}")
        
        return True
        
    except requests.exceptions.Timeout:
        print("❌ Таймаут при подключении к Supabase")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка подключения: {e}")
        return False

def test_password_reset(email="test@example.com"):
    """Тестирует функцию сброса пароля"""
    print(f"\n🔍 Тестирование сброса пароля для {email}...")
    
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'email': email,
        'redirect_to': 'https://beautybot.pro/set-password'
    }
    
    try:
        response = requests.post(
            f"{SUPABASE_URL}/auth/v1/recover",
            headers=headers,
            json=data,
            timeout=30  # Увеличиваем таймаут
        )
        
        print(f"📊 Статус ответа: {response.status_code}")
        print(f"📊 Заголовки: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ Запрос сброса пароля успешен")
            return True
        elif response.status_code == 504:
            print("❌ 504 Gateway Timeout - проблема с email-сервисом")
            return False
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(f"📄 Ответ: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Таймаут при запросе сброса пароля")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def check_supabase_settings():
    """Проверяет настройки Supabase"""
    print("\n🔍 Проверка настроек Supabase...")
    
    # Проверяем, есть ли настройки email
    print("ℹ️  Для решения проблемы 504 нужно проверить:")
    print("   1. Настройки SMTP в Supabase Dashboard")
    print("   2. Конфигурацию email-сервиса")
    print("   3. Лимиты отправки email")
    print("   4. Статус email-сервиса Supabase")

def main():
    print("🚀 Диагностика проблем с аутентификацией Supabase")
    print("=" * 50)
    
    # Тест подключения
    if not test_supabase_connection():
        print("\n❌ Не удалось подключиться к Supabase")
        return
    
    # Тест сброса пароля
    test_email = input("\n📧 Введите email для тестирования (или нажмите Enter для пропуска): ").strip()
    if test_email:
        test_password_reset(test_email)
    
    # Проверка настроек
    check_supabase_settings()
    
    print("\n" + "=" * 50)
    print("📋 Рекомендации по решению проблемы 504:")
    print("1. Проверьте настройки SMTP в Supabase Dashboard")
    print("2. Убедитесь, что email-сервис настроен правильно")
    print("3. Проверьте лимиты отправки email")
    print("4. Попробуйте использовать другой email-сервис")
    print("5. Обратитесь в поддержку Supabase")

if __name__ == "__main__":
    main() 