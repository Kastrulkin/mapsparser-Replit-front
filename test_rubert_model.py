#!/usr/bin/env python3
"""
Тест модели rubert-base-cased для анализа SEO
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_rubert_analysis():
    """Тестируем анализ с rubert-base-cased"""
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return False
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Тестовые данные
    test_data = {
        "title": "Салон красоты Елена у метро Парк Победы",
        "address": "Москва, ул. Кутузовский проспект, 15",
        "services": ["Стрижка женская", "Окрашивание волос", "Маникюр"],
        "rating": 4.2,
        "reviews_count": 15,
        "photos_count": 8
    }
    
    text_for_analysis = f"""
    Название: {test_data['title']}
    Адрес: {test_data['address']}
    Услуги: {', '.join(test_data['services'])}
    Рейтинг: {test_data['rating']}/5 ({test_data['reviews_count']} отзывов)
    Фото: {test_data['photos_count']} шт.
    """
    
    print("🔍 Тестируем анализ с rubert-base-cased")
    print("=" * 50)
    print(f"📋 Данные: {text_for_analysis}")
    
    # Пробуем разные подходы с rubert
    approaches = [
        {
            "name": "Классификация настроения",
            "payload": {
                "inputs": text_for_analysis,
                "parameters": {
                    "max_length": 512
                }
            }
        },
        {
            "name": "Анализ тональности", 
            "payload": {
                "inputs": f"Анализ SEO: {text_for_analysis}",
                "parameters": {
                    "max_length": 256
                }
            }
        }
    ]
    
    for approach in approaches:
        try:
            print(f"\n🤖 {approach['name']}...")
            response = requests.post(
                "https://api-inference.huggingface.co/models/DeepPavlov/rubert-base-cased",
                headers=headers,
                json=approach['payload'],
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Ответ получен!")
                print(f"📄 Формат ответа: {type(result)}")
                print(f"📄 Содержимое: {result}")
                
                # Анализируем структуру ответа
                if isinstance(result, list):
                    print(f"📊 Количество элементов: {len(result)}")
                    for i, item in enumerate(result):
                        print(f"  Элемент {i}: {type(item)} - {item}")
                elif isinstance(result, dict):
                    print(f"📊 Ключи: {list(result.keys())}")
                    for key, value in result.items():
                        print(f"  {key}: {value}")
                
                return True
            else:
                print(f"❌ Ошибка {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Исключение: {e}")
    
    return False

if __name__ == "__main__":
    success = test_rubert_analysis()
    if success:
        print(f"\n🎉 Тест прошел успешно!")
    else:
        print(f"\n💥 Тест не прошел.") 