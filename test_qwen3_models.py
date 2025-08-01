#!/usr/bin/env python3
"""
Тест моделей Qwen 3 для генерации текста
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def search_qwen_models():
    """Поиск моделей Qwen 3 на Hugging Face"""
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return []
    
    headers = {
        "Authorization": f"Bearer {hf_token}"
    }
    
    # Поиск моделей Qwen 3
    search_queries = [
        "Qwen2.5",
        "Qwen2.5-7B",
        "Qwen2.5-14B", 
        "Qwen2.5-32B",
        "Qwen2.5-72B",
        "Qwen2.5-Instruct",
        "Qwen2.5-Chat"
    ]
    
    found_models = []
    
    for query in search_queries:
        try:
            print(f"🔍 Поиск: {query}")
            response = requests.get(
                "https://huggingface.co/api/models",
                headers=headers,
                params={
                    "search": query,
                    "limit": 10,
                    "sort": "downloads",
                    "direction": "-1"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                models = response.json()
                for model in models:
                    model_id = model.get('id', '')
                    downloads = model.get('downloads', 0)
                    likes = model.get('likes', 0)
                    
                    if downloads > 1000:
                        print(f"  📊 {model_id} (загрузок: {downloads}, лайков: {likes})")
                        found_models.append({
                            'id': model_id,
                            'downloads': downloads,
                            'likes': likes,
                            'query': query
                        })
            else:
                print(f"  ❌ Ошибка API: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Ошибка поиска: {e}")
    
    return found_models

def test_qwen_model(model_name):
    """Тестируем модель Qwen"""
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        return False
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Тест генерации с Qwen
    payload = {
        "inputs": "Анализ SEO для бизнеса в Яндекс.Картах. Дай 3 рекомендации:",
        "parameters": {
            "max_length": 200,
            "temperature": 0.7,
            "do_sample": True,
            "top_p": 0.9
        }
    }
    
    try:
        print(f"🤖 Тестируем: {model_name}")
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model_name}",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {model_name} - РАБОТАЕТ!")
            if isinstance(result, list) and len(result) > 0:
                generated = result[0].get('generated_text', '')
                print(f"   Пример: {generated[:150]}...")
            return True
        else:
            print(f"❌ {model_name} - Ошибка {response.status_code}")
            if response.status_code == 503:
                print("   ⏳ Модель загружается...")
            return False
            
    except Exception as e:
        print(f"❌ {model_name} - Исключение: {e}")
        return False

def main():
    """Основная функция"""
    print("🔍 Поиск и тест моделей Qwen 3")
    print("=" * 50)
    
    # Поиск моделей
    print("📋 Поиск моделей Qwen 3...")
    models = search_qwen_models()
    
    if not models:
        print("❌ Модели Qwen 3 не найдены")
        return
    
    # Сортируем по популярности
    models.sort(key=lambda x: x['downloads'], reverse=True)
    
    print(f"\n📊 Найдено {len(models)} моделей Qwen 3:")
    for i, model in enumerate(models[:5], 1):
        print(f"{i}. {model['id']} (загрузок: {model['downloads']})")
    
    # Тестируем топ модели
    print(f"\n🧪 Тестируем топ модели...")
    working_models = []
    
    for model in models[:3]:
        if test_qwen_model(model['id']):
            working_models.append(model)
        print()
    
    print("📊 Результаты:")
    print("=" * 30)
    if working_models:
        print("✅ Работающие модели Qwen 3:")
        for model in working_models:
            print(f"  - {model['id']}")
        
        # Рекомендуем лучшую модель
        best_model = working_models[0]
        print(f"\n🎯 Рекомендуемая модель: {best_model['id']}")
        
        # Обновляем конфигурацию
        update_model_config(best_model['id'])
        
    else:
        print("❌ Ни одна модель Qwen 3 не работает")

def update_model_config(model_name):
    """Обновляем конфигурацию модели"""
    print(f"\n⚙️ Обновляем конфигурацию для {model_name}...")
    
    # Обновляем model_config.py
    config_content = f'''# Конфигурация моделей Hugging Face для ИИ-анализа

# Доступные модели для анализа
AVAILABLE_MODELS = {{
    "{model_name}": {{
        "name": "{model_name}",
        "description": "Мощная модель Qwen 3 для генерации текста",
        "max_length": 2048,
        "temperature": 0.6,
        "do_sample": True,
        "top_p": 0.9,
        "repetition_penalty": 1.1
    }},
    "gpt2": {{
        "name": "gpt2",
        "description": "Базовая модель для генерации текста",
        "max_length": 200,
        "temperature": 0.8,
        "do_sample": True,
        "top_p": 0.9,
        "repetition_penalty": 1.1
    }},
    "facebook/bart-base": {{
        "name": "facebook/bart-base",
        "description": "Модель для понимания текста",
        "max_length": 1024,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.9
    }}
}}

# Промпты для разных типов анализа
PROMPTS = {{
    "seo_analysis": """Проанализируй карточку бизнеса для SEO в Яндекс.Картах. Данные: {{text}}

Инструкция: Дай 5 конкретных рекомендаций по улучшению позиций в Яндекс.Картах. Учитывай требования 2025 года:

1. НАЗВАНИЕ КОМПАНИИ: Только официальное название без ключевых слов
2. УСЛУГИ: Добавляй ключевые слова и геолокацию (метро, район)
3. АДРЕС: Полный адрес с метро/остановками
4. КОНТЕНТ: Минимум 10 фото, актуальная информация
5. АКТИВНОСТЬ: Регулярные посты, ответы на отзывы

Формат ответа:
1) Название: [рекомендация]
2) Услуги: [рекомендация] 
3) Контакты: [рекомендация]
4) Контент: [рекомендация]
5) Активность: [рекомендация]

Не советуй Google Pay/Apple Pay - они не работают в России.""",
    "rating_analysis": "Анализ рейтинга и отзывов. Данные: {text}. Оцени качество и дай 2-3 совета по улучшению.",
    "general_analysis": "Общий анализ бизнеса. Данные: {text}. Дай 3-4 рекомендации по развитию."
}}

# Текущая активная модель
CURRENT_MODEL = "{model_name}"

def get_model_config(model_name=None):
    """Получить конфигурацию модели"""
    if model_name is None:
        model_name = CURRENT_MODEL
    
    return AVAILABLE_MODELS.get(model_name, AVAILABLE_MODELS["{model_name}"])

def get_prompt(prompt_type="seo_analysis", text=""):
    """Получить промпт для анализа"""
    return PROMPTS.get(prompt_type, PROMPTS["seo_analysis"]).format(text=text)
'''
    
    try:
        with open('src/model_config.py', 'w', encoding='utf-8') as f:
            f.write(config_content)
        print(f"✅ Конфигурация обновлена для {model_name}")
    except Exception as e:
        print(f"❌ Ошибка обновления конфигурации: {e}")

if __name__ == "__main__":
    main() 