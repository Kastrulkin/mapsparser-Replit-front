#!/usr/bin/env python3
"""
Тест только AI анализа без Supabase
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Добавляем src в путь
sys.path.append('src')

from model_config import get_model_config, get_prompt

load_dotenv()

def call_huggingface_analysis(text: str) -> dict:
    """Вызывает Hugging Face модель для анализа"""
    try:
        model_config = get_model_config()
        model_name = model_config["name"]
        
        # Получаем токен из переменных окружения
        hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
        if not hf_token:
            return {"error": "HUGGINGFACE_API_TOKEN не найден"}
        
        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json"
        }
        
        prompt = get_prompt("seo_analysis", text)
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_length": model_config["max_length"],
                "temperature": model_config["temperature"],
                "do_sample": model_config["do_sample"],
                "top_p": model_config["top_p"]
            }
        }
        
        # Добавляем repetition_penalty если есть
        if "repetition_penalty" in model_config:
            payload["parameters"]["repetition_penalty"] = model_config["repetition_penalty"]
        
        print(f"🤖 Отправляем запрос к модели {model_name}...")
        print(f"📏 Максимальная длина: {model_config['max_length']}")
        print(f"🌡️ Температура: {model_config['temperature']}")
        
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model_name}",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Ответ получен успешно!")
            return result
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            print(f"📄 Ответ: {response.text}")
            return {"error": f"API error {response.status_code}", "details": response.text}
            
    except Exception as e:
        print(f"❌ Ошибка при вызове Hugging Face: {e}")
        return {"error": str(e)}

def test_ai_analysis():
    """Тестируем AI анализ"""
    
    print("🔍 Тестируем AI анализ Яндекс Карт")
    print("=" * 50)
    
    # Тестовые данные карточки бизнеса
    test_data = {
        "title": "Салон красоты Елена у метро Парк Победы",
        "address": "Москва, ул. Кутузовский проспект, 15",
        "phone": "+7 (495) 123-45-67",
        "website": "https://salon-elena.ru",
        "description": "Салон красоты предлагает стрижки, окрашивание, маникюр",
        "services": [
            "Стрижка женская",
            "Окрашивание волос", 
            "Маникюр",
            "Педикюр"
        ],
        "working_hours": "Пн-Пт 9:00-20:00, Сб-Вс 10:00-18:00",
        "rating": 4.2,
        "reviews_count": 15,
        "photos_count": 8,
        "categories": ["Парикмахерская", "Салон красоты"]
    }
    
    print(f"\n📋 Тестовые данные:")
    print(f"Название: {test_data['title']}")
    print(f"Адрес: {test_data['address']}")
    print(f"Услуги: {', '.join(test_data['services'])}")
    print(f"Рейтинг: {test_data['rating']}/5 ({test_data['reviews_count']} отзывов)")
    print(f"Фото: {test_data['photos_count']} шт.")
    
    # Формируем текст для анализа
    text_for_analysis = f"""
    Название: {test_data['title']}
    Адрес: {test_data['address']}
    Телефон: {test_data['phone']}
    Сайт: {test_data['website']}
    Описание: {test_data['description']}
    Услуги: {', '.join(test_data['services'])}
    Часы работы: {test_data['working_hours']}
    Рейтинг: {test_data['rating']}/5 ({test_data['reviews_count']} отзывов)
    Количество фото: {test_data['photos_count']}
    Категории: {', '.join(test_data['categories'])}
    """
    
    try:
        # Выполняем анализ
        print(f"\n🤖 Выполняем ИИ-анализ...")
        result = call_huggingface_analysis(text_for_analysis)
        
        if "error" in result:
            print(f"❌ Ошибка: {result['error']}")
            return False
        
        print(f"\n✅ Анализ завершен!")
        print(f"\n📝 Результат анализа:")
        print("-" * 50)
        
        # Выводим результат в зависимости от формата ответа
        if isinstance(result, list) and len(result) > 0:
            # Стандартный формат Hugging Face
            generated_text = result[0].get('generated_text', '')
            print(generated_text)
        elif isinstance(result, dict) and 'generated_text' in result:
            # Альтернативный формат
            print(result['generated_text'])
        else:
            # Выводим весь результат для отладки
            print("Неожиданный формат ответа:")
            print(result)
            
    except Exception as e:
        print(f"❌ Ошибка при анализе: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_ai_analysis()
    if success:
        print(f"\n🎉 Тест прошел успешно! AI анализ работает с новым промптом и моделью.")
    else:
        print(f"\n💥 Тест не прошел. Нужно исправить ошибки.") 