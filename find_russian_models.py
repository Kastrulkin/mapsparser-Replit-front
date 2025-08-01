#!/usr/bin/env python3
"""
Поиск русскоязычных моделей генерации текста на Hugging Face
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def search_models(query, limit=20):
    """Поиск моделей через Hugging Face API"""
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return []
    
    headers = {
        "Authorization": f"Bearer {hf_token}"
    }
    
    try:
        # Поиск моделей
        response = requests.get(
            "https://huggingface.co/api/models",
            headers=headers,
            params={
                "search": query,
                "limit": limit,
                "sort": "downloads",
                "direction": "-1"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Ошибка поиска: {e}")
        return []

def test_model_generation(model_name):
    """Тестируем модель на генерацию текста"""
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        return False
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Простой тест генерации
    payload = {
        "inputs": "Анализ SEO для бизнеса:",
        "parameters": {
            "max_length": 100,
            "temperature": 0.7,
            "do_sample": True
        }
    }
    
    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model_name}",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            # Проверяем, что модель генерирует текст
            if isinstance(result, list) and len(result) > 0:
                if 'generated_text' in result[0]:
                    return True
        return False
        
    except Exception as e:
        return False

def main():
    """Основная функция поиска"""
    print("🔍 Поиск русскоязычных моделей генерации текста")
    print("=" * 60)
    
    # Поисковые запросы для русскоязычных моделей
    search_queries = [
        "russian text generation",
        "russian gpt",
        "russian language model",
        "text2text-generation russian",
        "sberbank-ai russian",
        "ai-forever russian"
    ]
    
    found_models = []
    
    for query in search_queries:
        print(f"\n🔎 Поиск: {query}")
        models = search_models(query, limit=10)
        
        for model in models:
            model_id = model.get('id', '')
            downloads = model.get('downloads', 0)
            likes = model.get('likes', 0)
            
            # Фильтруем по популярности
            if downloads > 1000:
                print(f"  📊 {model_id} (загрузок: {downloads}, лайков: {likes})")
                
                # Тестируем генерацию
                if test_model_generation(model_id):
                    print(f"    ✅ ГЕНЕРАЦИЯ РАБОТАЕТ!")
                    found_models.append({
                        'id': model_id,
                        'downloads': downloads,
                        'likes': likes,
                        'query': query
                    })
                else:
                    print(f"    ❌ Генерация не работает")
    
    print(f"\n📊 Результаты поиска:")
    print("=" * 40)
    
    if found_models:
        # Сортируем по популярности
        found_models.sort(key=lambda x: x['downloads'], reverse=True)
        
        print("✅ Найденные рабочие модели:")
        for i, model in enumerate(found_models[:10], 1):
            print(f"{i}. {model['id']}")
            print(f"   Загрузок: {model['downloads']}, Лайков: {model['likes']}")
            print(f"   Найден через: {model['query']}")
            print()
    else:
        print("❌ Не найдено рабочих моделей генерации")
    
    return found_models

if __name__ == "__main__":
    models = main() 