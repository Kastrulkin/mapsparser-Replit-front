#!/usr/bin/env python3
"""
Скрипт для управления конфигурацией GigaChat
"""
import requests
import json
import sys

API_BASE = "http://localhost:8000"

def get_config():
    """Получить текущую конфигурацию"""
    try:
        response = requests.get(f"{API_BASE}/api/gigachat/config")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Ошибка соединения: {e}")
        return None

def set_model(model_name):
    """Установить модель"""
    try:
        response = requests.post(
            f"{API_BASE}/api/gigachat/config",
            json={"model": model_name},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Ошибка соединения: {e}")
        return None

def list_models():
    """Показать доступные модели"""
    config = get_config()
    if not config:
        return
    
    print("📋 Доступные модели GigaChat:")
    print("-" * 50)
    
    for model in config["available_models"]:
        current = "✅" if model == config["current_config"]["model"] else "⚪"
        print(f"{current} {model}")
    
    print(f"\n🎯 Текущая модель: {config['current_config']['model']}")
    print(f"🌡️ Температура: {config['current_config']['temperature']}")
    print(f"📝 Максимум токенов: {config['current_config']['max_tokens']}")

def main():
    if len(sys.argv) < 2:
        print("🔧 Управление конфигурацией GigaChat")
        print("\nИспользование:")
        print("  python manage_gigachat.py list                    - показать доступные модели")
        print("  python manage_gigachat.py set <model_name>        - установить модель")
        print("  python manage_gigachat.py status                   - показать текущую конфигурацию")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_models()
    
    elif command == "set":
        if len(sys.argv) < 3:
            print("❌ Укажите название модели")
            return
        
        model_name = sys.argv[2]
        result = set_model(model_name)
        
        if result and result.get("success"):
            print(f"✅ {result['message']}")
        else:
            print(f"❌ Ошибка установки модели: {result.get('error', 'Неизвестная ошибка')}")
    
    elif command == "status":
        config = get_config()
        if config:
            print("🔧 Текущая конфигурация GigaChat:")
            print(f"   Модель: {config['current_config']['model']}")
            print(f"   Температура: {config['current_config']['temperature']}")
            print(f"   Максимум токенов: {config['current_config']['max_tokens']}")
            print(f"   Таймаут: {config['current_config']['timeout']}с")
            print(f"   Попытки повтора: {config['current_config']['retry_attempts']}")
            
            model_info = config['model_info']
            print(f"\n📋 Информация о модели:")
            print(f"   Описание: {model_info['description']}")
            print(f"   Поддержка изображений: {'Да' if model_info['supports_images'] else 'Нет'}")
            print(f"   Рекомендуется для: {', '.join(model_info['recommended_for'])}")
    
    else:
        print(f"❌ Неизвестная команда: {command}")

if __name__ == "__main__":
    main()
