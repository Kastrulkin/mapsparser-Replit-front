#!/usr/bin/env python3
"""
Тест рабочих моделей, доступных через бесплатный Hugging Face API
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
    
    # Простой тест генерации
    payload = {
        "inputs": "Анализ SEO для бизнеса. Дай 2 рекомендации:",
        "parameters": {
            "max_length": 150,
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
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {model_name} - РАБОТАЕТ!")
            if isinstance(result, list) and len(result) > 0:
                generated = result[0].get('generated_text', '')
                print(f"   Пример: {generated[:100]}...")
            return True
        elif response.status_code == 503:
            print(f"⏳ {model_name} - Модель загружается...")
            return False
        else:
            print(f"❌ {model_name} - Ошибка {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ {model_name} - Исключение: {e}")
        return False

def main():
    """Тестируем модели, которые должны работать"""
    print("🔍 Тест рабочих моделей")
    print("=" * 40)
    
    # Модели, которые точно должны работать через бесплатный API
    test_models = [
        # Базовые модели GPT
        "gpt2",
        "gpt2-medium",
        "distilgpt2",
        
        # Модели BART
        "facebook/bart-base",
        "facebook/bart-large",
        
        # Модели T5
        "t5-small",
        "t5-base",
        
        # Модели DialoGPT
        "microsoft/DialoGPT-small",
        "microsoft/DialoGPT-medium",
        
        # Модели BLOOM
        "bigscience/bloom-560m",
        "bigscience/bloom-1b1",
        
        # Модели EleutherAI
        "EleutherAI/gpt-neo-125M",
        "EleutherAI/gpt-neo-1.3B",
        
        # Модели для русского языка
        "DeepPavlov/rubert-base-cased",
        "DeepPavlov/rubert-large-cased",
        
        # Модели для анализа текста
        "cardiffnlp/twitter-roberta-base-sentiment",
        "nlptown/bert-base-multilingual-uncased-sentiment",
        
        # Модели для генерации
        "microsoft/DialoGPT-medium",
        "microsoft/DialoGPT-large",
        
        # Альтернативные модели
        "sshleifer/tiny-gpt2",
        "sshleifer/distilgpt2",
        "microsoft/DialoGPT-small"
    ]
    
    print(f"📋 Тестируем {len(test_models)} моделей...")
    print()
    
    working_models = []
    
    for model in test_models:
        if test_model(model):
            working_models.append(model)
        print()
    
    print("📊 Результаты:")
    print("=" * 30)
    if working_models:
        print("✅ Работающие модели:")
        for i, model in enumerate(working_models, 1):
            print(f"{i}. {model}")
        
        # Рекомендуем лучшую модель
        best_model = working_models[0]
        print(f"\n🎯 Рекомендуемая модель: {best_model}")
        
        # Обновляем конфигурацию
        update_model_config(best_model)
        
    else:
        print("❌ Ни одна модель не работает")
        print("\n💡 Попробуем поиск через API...")
        search_working_models()

def search_working_models():
    """Поиск рабочих моделей через API"""
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return
    
    headers = {
        "Authorization": f"Bearer {hf_token}"
    }
    
    search_queries = [
        "text-generation",
        "gpt2",
        "bart-base",
        "t5-small",
        "dialoGPT"
    ]
    
    print("🔍 Поиск рабочих моделей через API...")
    
    for query in search_queries:
        try:
            print(f"\n📝 Поиск: {query}")
            response = requests.get(
                "https://huggingface.co/api/models",
                headers=headers,
                params={
                    "search": query,
                    "limit": 5,
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
                    print(f"  📊 {model_id} (загрузок: {downloads})")
                    
                    # Тестируем найденную модель
                    if test_model(model_id):
                        print(f"🎯 Найдена работающая модель: {model_id}")
                        update_model_config(model_id)
                        return
            else:
                print(f"  ❌ Ошибка API: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Ошибка поиска: {e}")

def update_model_config(model_name):
    """Обновляем конфигурацию модели"""
    print(f"\n⚙️ Обновляем конфигурацию для {model_name}...")
    
    # Обновляем model_config.py
    config_content = f'''# Конфигурация моделей Hugging Face для ИИ-анализа

# Доступные модели для анализа
AVAILABLE_MODELS = {{
    "{model_name}": {{
        "name": "{model_name}",
        "description": "Рабочая модель для генерации текста",
        "max_length": 1024,
        "temperature": 0.7,
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
    "seo_analysis": """Анализ SEO для Яндекс.Карт. Данные: {{text}}

Дай 5 рекомендаций:
1) Название: убрать ключевые слова
2) Услуги: добавить геолокацию  
3) Контакты: полный адрес
4) Контент: больше фото
5) Активность: регулярные посты

Не советуй Google Pay/Apple Pay - они не работают в России.""",
    "rating_analysis": "Анализ рейтинга и отзывов. Данные: {{text}}. Оцени качество и дай 2-3 совета по улучшению.",
    "general_analysis": "Общий анализ бизнеса. Данные: {{text}}. Дай 3-4 рекомендации по развитию."
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
        
        # Также обновляем ai_analyzer.py для использования реальной модели
        update_ai_analyzer(model_name)
        
    except Exception as e:
        print(f"❌ Ошибка обновления конфигурации: {e}")

def update_ai_analyzer(model_name):
    """Обновляем ai_analyzer.py для использования реальной модели"""
    print(f"🔄 Обновляем ai_analyzer.py для {model_name}...")
    
    try:
        with open('src/ai_analyzer.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Заменяем rule-based анализ на реальный вызов модели
        new_call_function = f'''def call_huggingface_analysis(text: str) -> Dict[str, Any]:
    """
    Анализирует данные с помощью модели {model_name}
    """
    try:
        from model_config import get_model_config, get_prompt
        
        # Получаем конфигурацию модели
        model_config = get_model_config("{model_name}")
        
        # Получаем промпт
        prompt = get_prompt("seo_analysis", text)
        
        # Вызываем Hugging Face API
        import requests
        import os
        
        hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
        if not hf_token:
            return {{"error": "HUGGINGFACE_API_TOKEN не найден"}}
        
        headers = {{
            "Authorization": f"Bearer {{hf_token}}",
            "Content-Type": "application/json"
        }}
        
        payload = {{
            "inputs": prompt,
            "parameters": {{
                "max_length": model_config.get("max_length", 1024),
                "temperature": model_config.get("temperature", 0.7),
                "do_sample": model_config.get("do_sample", True),
                "top_p": model_config.get("top_p", 0.9),
                "repetition_penalty": model_config.get("repetition_penalty", 1.1)
            }}
        }}
        
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{model_name}",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                generated_text = result[0].get('generated_text', '')
                return {{
                    "generated_text": generated_text,
                    "analysis_type": "ai_model",
                    "model_used": "{model_name}"
                }}
            else:
                return {{"error": "Неожиданный формат ответа от модели"}}
        else:
            return {{"error": f"Ошибка API {{response.status_code}}: {{response.text}}"}}
            
    except Exception as e:
        print(f"Ошибка при анализе: {{e}}")
        return {{"error": str(e)}}'''
        
        # Заменяем функцию в файле
        import re
        pattern = r'def call_huggingface_analysis\(text: str\) -> Dict\[str, Any\]:.*?return \{"error": str\(e\)\}'
        new_content = re.sub(pattern, new_call_function, content, flags=re.DOTALL)
        
        with open('src/ai_analyzer.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ ai_analyzer.py обновлен для использования реальной модели")
        
    except Exception as e:
        print(f"❌ Ошибка обновления ai_analyzer.py: {e}")

if __name__ == "__main__":
    main() 