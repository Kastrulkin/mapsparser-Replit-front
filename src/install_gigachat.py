#!/usr/bin/env python3
"""
Скрипт для установки зависимостей GigaChat
"""
import subprocess
import sys
import os

def install_requirements():
    """Установить необходимые пакеты"""
    packages = [
        "requests>=2.31.0",
        "python-dotenv>=1.0.0"
    ]
    
    for package in packages:
        try:
            print(f"📦 Устанавливаем {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} установлен успешно")
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка установки {package}: {e}")

def create_env_file():
    """Создать файл .env если его нет"""
    env_path = ".env"
    if not os.path.exists(env_path):
        print("📝 Создаем файл .env...")
        with open(env_path, "w") as f:
            f.write("# GigaChat API Configuration\n")
            f.write("GIGACHAT_CLIENT_ID=your_client_id_here\n")
            f.write("GIGACHAT_CLIENT_SECRET=your_client_secret_here\n")
        print("✅ Файл .env создан")
        print("⚠️ Не забудьте добавить ваши ключи GigaChat в файл .env")
    else:
        print("✅ Файл .env уже существует")

def test_gigachat():
    """Тестировать GigaChat"""
    print("🧪 Тестируем GigaChat...")
    try:
        from gigachat_analyzer import analyze_business_data
        
        test_data = {
            'title': 'Тестовый бизнес',
            'address': 'Тестовый адрес',
            'phone': '+7 (999) 123-45-67',
            'rating': '4.5',
            'reviews_count': '25'
        }
        
        result = analyze_business_data(test_data)
        print("✅ GigaChat тест прошел успешно")
        print(f"📊 Результат: {result.get('score', 'N/A')} баллов")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка теста GigaChat: {e}")
        print("🔄 Система будет использовать простой анализ")
        return False

if __name__ == "__main__":
    print("🚀 Настройка GigaChat...")
    
    # Устанавливаем зависимости
    install_requirements()
    
    # Создаем .env файл
    create_env_file()
    
    # Тестируем
    test_success = test_gigachat()
    
    if test_success:
        print("\n✅ GigaChat настроен успешно!")
        print("Теперь система будет использовать GigaChat для анализа")
    else:
        print("\n⚠️ GigaChat недоступен, используется простой анализ")
        print("Добавьте ключи в .env файл для активации GigaChat")
