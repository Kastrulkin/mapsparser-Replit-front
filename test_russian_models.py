#!/usr/bin/env python3
"""
Тест известных русскоязычных моделей генерации
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_model(model_name):
    """Тестируем модель"""
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return False
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Тест генерации
    payload = {
        "inputs": "Анализ SEO для бизнеса:",
        "parameters": {
            "max_length": 100,
            "temperature": 0.7,
            "do_sample": True
        }
    }
    
    try:
        print(f"🤖 Тестируем: {model_name}")
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model_name}",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {model_name} - РАБОТАЕТ!")
            if isinstance(result, list) and len(result) > 0:
                generated = result[0].get('generated_text', '')
                print(f"   Пример: {generated[:100]}...")
            return True
        else:
            print(f"❌ {model_name} - Ошибка {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ {model_name} - Исключение: {e}")
        return False

def main():
    """Тестируем русскоязычные модели"""
    print("🔍 Тест русскоязычных моделей генерации")
    print("=" * 50)
    
    # Известные русскоязычные модели
    models = [
        "sberbank-ai/rugpt3small_based_on_gpt2",
        "ai-forever/rugpt3.5-13b",
        "ai-forever/rugpt3.5-1.3b",
        "sberbank-ai/rugpt3.5-13b",
        "DeepPavlov/rubert-base-cased",
        "cointegrated/rubert-tiny2",
        "ai-forever/mGPT",
        "microsoft/DialoGPT-medium"
    ]
    
    working_models = []
    
    for model in models:
        if test_model(model):
            working_models.append(model)
        print()
    
    print("📊 Результаты:")
    print("=" * 30)
    if working_models:
        print("✅ Работающие модели:")
        for model in working_models:
            print(f"  - {model}")
    else:
        print("❌ Ни одна модель не работает")
    
    return working_models

if __name__ == "__main__":
    working_models = main() 