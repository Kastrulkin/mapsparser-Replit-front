#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к Hugging Face API
"""
import os
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def test_huggingface_connection():
    """Тестирует подключение к Hugging Face API"""
    
    # Получаем токен
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден в переменных окружения")
        return False
    
    print(f"✅ Токен найден: {hf_token[:10]}...")
    
    # Тестируем простую модель
    model_name = "facebook/bart-base"
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Простой тестовый запрос
    payload = {
        "inputs": "Hello, how are you?",
        "parameters": {
            "max_length": 50,
            "temperature": 0.7,
            "do_sample": True
        }
    }
    
    try:
        print(f"🔄 Тестируем модель: {model_name}")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"📊 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Подключение успешно!")
            print(f"📝 Результат: {result}")
            return True
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            print(f"📝 Ответ: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Таймаут запроса")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка запроса: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def test_seo_analysis():
    """Тестирует SEO-анализ с помощью Hugging Face"""
    
    from src.model_config import get_model_config, get_prompt
    
    # Тестовые данные карточки
    test_card_data = {
        "title": "Кафе 'Уютное место'",
        "address": "ул. Ленина, 123, Москва",
        "rating": 4.2,
        "reviews_count": 45,
        "overview": {
            "description": "Уютное кафе с домашней кухней и приятной атмосферой"
        },
        "categories": ["Кафе", "Рестораны"]
    }
    
    # Подготавливаем данные для анализа
    analysis_text = f"""
    Название: {test_card_data['title']}
    Адрес: {test_card_data['address']}
    Рейтинг: {test_card_data['rating']}
    Количество отзывов: {test_card_data['reviews_count']}
    Описание: {test_card_data['overview']['description']}
    Категории: {', '.join(test_card_data['categories'])}
    """
    
    # Получаем промпт
    prompt = get_prompt("seo_analysis", analysis_text)
    print(f"📝 Промпт для анализа:\n{prompt}")
    
    # Получаем конфигурацию модели
    model_config = get_model_config()
    print(f"🤖 Модель: {model_config['name']}")
    
    # Тестируем запрос
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_length": model_config["max_length"],
            "temperature": model_config["temperature"],
            "do_sample": model_config["do_sample"],
            "top_p": model_config["top_p"]
        }
    }
    
    try:
        print("🔄 Отправляем запрос на SEO-анализ...")
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model_config['name']}",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        print(f"📊 Статус: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SEO-анализ успешен!")
            print(f"📝 Результат: {result}")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(f"📝 Ответ: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при SEO-анализе: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование подключения к Hugging Face API")
    print("=" * 50)
    
    # Тест 1: Базовое подключение
    print("\n1️⃣ Тест базового подключения:")
    basic_test = test_huggingface_connection()
    
    # Тест 2: SEO-анализ
    print("\n2️⃣ Тест SEO-анализа:")
    seo_test = test_seo_analysis()
    
    # Итоги
    print("\n" + "=" * 50)
    print("📋 ИТОГИ ТЕСТИРОВАНИЯ:")
    print(f"Базовое подключение: {'✅ УСПЕХ' if basic_test else '❌ ОШИБКА'}")
    print(f"SEO-анализ: {'✅ УСПЕХ' if seo_test else '❌ ОШИБКА'}")
    
    if basic_test and seo_test:
        print("\n🎉 Все тесты пройдены! Hugging Face API работает корректно.")
    else:
        print("\n⚠️ Есть проблемы с подключением к Hugging Face API.") 