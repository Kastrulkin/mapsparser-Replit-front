#!/usr/bin/env python3
"""
Скрипт для получения OAuth токена для API Яндекс.Вордстат
"""

import webbrowser
import requests
import json
import sys
import os

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__))))

from wordstat_config import config

def get_oauth_token():
    """Получение OAuth токена через браузер"""
    
    print("🔐 Получение OAuth токена для API Яндекс.Вордстат")
    print("=" * 60)
    
    # Шаг 1: Получаем код авторизации
    auth_url = config.get_auth_url()
    print(f"1️⃣ Откройте ссылку в браузере:")
    print(f"   {auth_url}")
    print()
    
    # Пытаемся открыть браузер автоматически
    try:
        webbrowser.open(auth_url)
        print("🌐 Браузер открыт автоматически")
    except Exception:
        print("⚠️  Не удалось открыть браузер автоматически")
    
    print("2️⃣ После авторизации вы будете перенаправлены на страницу с кодом")
    print("3️⃣ Скопируйте код из URL (параметр 'code') и вставьте его ниже")
    print()
    
    # Получаем код от пользователя
    auth_code = input("📋 Введите код авторизации: ").strip()
    
    if not auth_code:
        print("❌ Код не введен")
        return None
    
    # Шаг 2: Обмениваем код на токен
    print("\n🔄 Обмен кода на токен...")
    
    token_url = "https://oauth.yandex.ru/token"
    token_data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'client_id': config.client_id,
        'client_secret': config.client_secret
    }
    
    try:
        response = requests.post(token_url, data=token_data, timeout=30)
        response.raise_for_status()
        
        token_info = response.json()
        access_token = token_info.get('access_token')
        expires_in = token_info.get('expires_in', 3600)
        
        if not access_token:
            print("❌ Не удалось получить токен")
            return None
        
        print("✅ Токен успешно получен!")
        print(f"⏰ Срок действия: {expires_in} секунд")
        
        # Сохраняем токен в файл
        token_file = os.path.join(os.path.dirname(__file__), 'wordstat_token.json')
        with open(token_file, 'w', encoding='utf-8') as f:
            json.dump({
                'access_token': access_token,
                'expires_in': expires_in,
                'created_at': time.time()
            }, f, indent=2)
        
        print(f"💾 Токен сохранен в {token_file}")
        
        # Устанавливаем переменную окружения
        print("\n🔧 Установите переменную окружения:")
        print(f"export YANDEX_WORDSTAT_OAUTH_TOKEN={access_token}")
        
        return access_token
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при получении токена: {e}")
        return None
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return None

def test_token(token):
    """Тестирование токена"""
    print("\n🧪 Тестирование токена...")
    
    try:
        from wordstat_client import WordstatClient
        
        client = WordstatClient(config.client_id, config.client_secret)
        client.set_access_token(token)
        
        # Тестовый запрос
        test_data = client.get_popular_queries(["стрижка"], 225)
        
        if test_data:
            print("✅ Токен работает корректно!")
            return True
        else:
            print("❌ Токен не работает")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

def main():
    """Основная функция"""
    print("🚀 Настройка API Яндекс.Вордстат для BeautyBot")
    print("=" * 60)
    
    # Проверяем существующий токен
    token_file = os.path.join(os.path.dirname(__file__), 'wordstat_token.json')
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            
            print(f"📁 Найден существующий токен (создан: {token_data.get('created_at', 'неизвестно')})")
            
            use_existing = input("🔄 Использовать существующий токен? (y/n): ").lower().strip()
            if use_existing == 'y':
                token = token_data.get('access_token')
                if token and test_token(token):
                    print("✅ Существующий токен работает!")
                    return token
                else:
                    print("❌ Существующий токен не работает")
        except Exception as e:
            print(f"⚠️  Ошибка чтения файла токена: {e}")
    
    # Получаем новый токен
    token = get_oauth_token()
    
    if token:
        if test_token(token):
            print("\n🎉 Настройка завершена успешно!")
            print("📝 Теперь вы можете использовать API Яндекс.Вордстат")
        else:
            print("\n💥 Токен получен, но не работает. Проверьте настройки.")
    else:
        print("\n💥 Не удалось получить токен")
    
    return token

if __name__ == "__main__":
    import time
    main()
