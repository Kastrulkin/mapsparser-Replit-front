#!/usr/bin/env python3
"""
Упрощенный скрипт для получения OAuth токена Яндекс.Вордстат
"""

import webbrowser
import requests
import sys
import os

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__))))

from wordstat_config import config

def show_auth_instructions():
    """Показывает инструкции по получению токена"""
    
    print("🔐 Получение OAuth токена для API Яндекс.Вордстат")
    print("=" * 60)
    
    auth_url = config.get_auth_url()
    print(f"1️⃣ Откройте эту ссылку в браузере:")
    print(f"   {auth_url}")
    print()
    
    # Пытаемся открыть браузер
    try:
        webbrowser.open(auth_url)
        print("🌐 Браузер открыт автоматически")
    except Exception:
        print("⚠️  Не удалось открыть браузер автоматически")
    
    print("2️⃣ Войдите в свой Яндекс аккаунт")
    print("3️⃣ Разрешите доступ приложению")
    print("4️⃣ Вы будете перенаправлены на страницу с кодом")
    print("5️⃣ Скопируйте код из URL (параметр 'code')")
    print()
    print("📋 Пример URL с кодом:")
    print("   https://oauth.yandex.ru/verification_code?code=AQAAAAA...")
    print("   Код: AQAAAAA...")
    print()
    
    return auth_url

def exchange_code_for_token(auth_code):
    """Обмен кода на токен"""
    
    print("🔄 Обмен кода на токен...")
    
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
            print("❌ Не удалось получить токен из ответа")
            return None
        
        print("✅ Токен успешно получен!")
        print(f"⏰ Срок действия: {expires_in} секунд")
        
        print("🔐 Токен не сохраняется в исходниках и не выводится в терминал.")
        print("Храните YANDEX_WORDSTAT_OAUTH_TOKEN только в secret storage окружения.")
        
        return access_token
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при получении токена: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Ответ сервера: {e.response.text}")
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
    
    # Показываем инструкции
    auth_url = show_auth_instructions()
    
    print("📝 После получения кода запустите:")
    print("   python3 wordstat_auth.py <код_авторизации>")
    print()
    print("🔗 Или откройте ссылку вручную:")
    print(f"   {auth_url}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Если передан код как аргумент
        auth_code = sys.argv[1]
        token = exchange_code_for_token(auth_code)
        
        if token:
            if test_token(token):
                print("\n🎉 Настройка завершена успешно!")
                print("📝 Теперь вы можете использовать API Яндекс.Вордстат")
            else:
                print("\n💥 Токен получен, но не работает. Проверьте настройки.")
        else:
            print("\n💥 Не удалось получить токен")
    else:
        # Показываем инструкции
        main()
