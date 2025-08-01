#!/usr/bin/env python3
"""
Тест найденных рабочих моделей
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_model_detailed(model_name):
    """Детальный тест модели"""
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return False
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Тест с SEO промптом
    payload = {
        "inputs": "Анализ SEO для бизнеса в Яндекс.Картах. Дай 3 рекомендации по улучшению позиций:",
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
            
            # Анализируем формат ответа
            if isinstance(result, list) and len(result) > 0:
                first_result = result[0]
                if 'generated_text' in first_result:
                    generated = first_result['generated_text']
                    print(f"   📝 Генерация: {generated[:200]}...")
                    return True
                elif 'summary_text' in first_result:
                    summary = first_result['summary_text']
                    print(f"   📝 Суммаризация: {summary[:200]}...")
                    return True
                else:
                    print(f"   📝 Формат: {list(first_result.keys())}")
                    return True
            else:
                print(f"   📝 Формат ответа: {type(result)}")
                return True
        elif response.status_code == 503:
            print(f"⏳ {model_name} - Модель загружается...")
            return False
        else:
            print(f"❌ {model_name} - Ошибка {response.status_code}: {response.text[:100]}")
            return False
            
    except Exception as e:
        print(f"❌ {model_name} - Исключение: {e}")
        return False

def main():
    """Тестируем найденные рабочие модели"""
    print("🔍 Тест найденных рабочих моделей")
    print("=" * 50)
    
    # Модели, которые мы нашли работающими
    working_models = [
        "ainize/bart-base-cnn",
        "google-t5/t5-small",
        "facebook/bart-base",
        "facebook/bart-large",
        "DeepPavlov/rubert-base-cased"
    ]
    
    print(f"📋 Тестируем {len(working_models)} найденных моделей...")
    print()
    
    successful_models = []
    
    for model in working_models:
        if test_model_detailed(model):
            successful_models.append(model)
        print()
    
    print("📊 Результаты:")
    print("=" * 30)
    if successful_models:
        print("✅ Успешно работающие модели:")
        for i, model in enumerate(successful_models, 1):
            print(f"{i}. {model}")
        
        # Рекомендуем лучшую модель
        best_model = successful_models[0]
        print(f"\n🎯 Рекомендуемая модель: {best_model}")
        
        # Обновляем конфигурацию
        update_model_config(best_model)
        
    else:
        print("❌ Ни одна модель не работает")

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
                first_result = result[0]
                if 'generated_text' in first_result:
                    generated_text = first_result['generated_text']
                elif 'summary_text' in first_result:
                    generated_text = first_result['summary_text']
                else:
                    generated_text = str(first_result)
                
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