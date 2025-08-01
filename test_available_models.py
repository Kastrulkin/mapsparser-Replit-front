#!/usr/bin/env python3
"""
Тест доступных моделей через Hugging Face API
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
    
    # Простой тест
    payload = {
        "inputs": "Hello, how are you?",
        "parameters": {
            "max_length": 50,
            "temperature": 0.7,
            "do_sample": True
        }
    }
    
    try:
        print(f"🤖 Тестируем модель: {model_name}")
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model_name}",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ {model_name} - РАБОТАЕТ!")
            return True
        else:
            print(f"❌ {model_name} - Ошибка {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ {model_name} - Исключение: {e}")
        return False

def main():
    """Тестируем разные модели"""
    print("🔍 Тестируем доступные модели Hugging Face")
    print("=" * 50)
    
    models_to_test = [
        "gpt2",
        "distilgpt2", 
        "facebook/bart-base",
        "t5-base",
        "microsoft/DialoGPT-small",
        "EleutherAI/gpt-neo-125M"
    ]
    
    working_models = []
    
    for model in models_to_test:
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