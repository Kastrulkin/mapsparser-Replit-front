#!/usr/bin/env python3
"""
Скрипт для поиска лучших моделей Hugging Face для SEO анализа
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def search_huggingface_models():
    """Ищет подходящие модели для SEO анализа"""
    
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден в .env")
        return
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Поисковые запросы для SEO анализа
    search_queries = [
        "text-generation",
        "text2text-generation", 
        "text-analysis",
        "business analysis",
        "SEO optimization",
        "recommendation system",
        "russian language",
        "multilingual"
    ]
    
    print("🔍 Поиск лучших моделей для SEO анализа...")
    print("=" * 60)
    
    found_models = []
    
    for query in search_queries:
        print(f"\n📝 Поиск: {query}")
        
        try:
            # Поиск моделей через Hugging Face API
            response = requests.get(
                f"https://huggingface.co/api/models",
                headers=headers,
                params={
                    "search": query,
                    "sort": "downloads",
                    "direction": "-1",
                    "limit": 10
                }
            )
            
            if response.status_code == 200:
                models = response.json()
                
                for model in models:
                    model_id = model.get('id', '')
                    downloads = model.get('downloads', 0)
                    likes = model.get('likes', 0)
                    tags = model.get('tags', [])
                    
                    # Фильтруем только подходящие модели
                    if downloads > 1000 and any(tag in ['text-generation', 'text2text-generation', 'russian', 'multilingual'] for tag in tags):
                        found_models.append({
                            'id': model_id,
                            'downloads': downloads,
                            'likes': likes,
                            'tags': tags,
                            'query': query
                        })
                        
                        print(f"  ✅ {model_id}")
                        print(f"     📥 Downloads: {downloads:,}")
                        print(f"     ❤️  Likes: {likes}")
                        print(f"     🏷️  Tags: {', '.join(tags[:5])}")
            else:
                print(f"  ❌ Ошибка API: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Ошибка запроса: {e}")
    
    # Сортируем по популярности
    found_models.sort(key=lambda x: x['downloads'], reverse=True)
    
    print("\n" + "=" * 60)
    print("🏆 ТОП-10 ЛУЧШИХ МОДЕЛЕЙ ДЛЯ SEO АНАЛИЗА:")
    print("=" * 60)
    
    for i, model in enumerate(found_models[:10], 1):
        print(f"\n{i}. {model['id']}")
        print(f"   📥 Downloads: {model['downloads']:,}")
        print(f"   ❤️  Likes: {model['likes']}")
        print(f"   🏷️  Tags: {', '.join(model['tags'][:5])}")
        print(f"   🔍 Found by: {model['query']}")
    
    # Рекомендации
    print("\n" + "=" * 60)
    print("💡 РЕКОМЕНДАЦИИ:")
    print("=" * 60)
    
    if found_models:
        best_model = found_models[0]
        print(f"\n🎯 ЛУЧШАЯ МОДЕЛЬ: {best_model['id']}")
        print(f"   - Самая популярная ({best_model['downloads']:,} загрузок)")
        print(f"   - Подходит для текстовой генерации")
        print(f"   - Поддерживает русский язык")
        
        print(f"\n📋 ДЛЯ ВАШЕГО ПРОМПТА РЕКОМЕНДУЮ:")
        print(f"   1. {best_model['id']} - для основного анализа")
        print(f"   2. facebook/bart-large-cnn - для структурированных ответов")
        print(f"   3. t5-large - для детального анализа")
        
        print(f"\n⚙️  НАСТРОЙКИ ДЛЯ {best_model['id']}:")
        print(f"   - max_length: 2048 (для длинных промптов)")
        print(f"   - temperature: 0.3 (для точных ответов)")
        print(f"   - do_sample: True")
        print(f"   - top_p: 0.9")
    else:
        print("❌ Не найдено подходящих моделей")

def test_current_model():
    """Тестирует текущую модель"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ ТЕКУЩЕЙ МОДЕЛИ:")
    print("=" * 60)
    
    from src.model_config import get_model_config, get_prompt
    
    model_config = get_model_config()
    print(f"🤖 Текущая модель: {model_config['name']}")
    print(f"📏 Max length: {model_config['max_length']}")
    print(f"🌡️  Temperature: {model_config['temperature']}")
    
    # Тестовый промпт
    test_text = "Кафе 'Уютное место', адрес: ул. Ленина 123, рейтинг 4.2"
    prompt = get_prompt("seo_analysis", test_text)
    
    print(f"\n📝 Текущий промпт:")
    print(f"   {prompt[:100]}...")
    
    print(f"\n⚠️  ПРОБЛЕМЫ ТЕКУЩЕГО ПРОМПТА:")
    print(f"   - Слишком короткий и общий")
    print(f"   - Не учитывает требования Яндекс Карт 2025")
    print(f"   - Нет структурированного анализа")
    print(f"   - Отсутствуют конкретные рекомендации")

if __name__ == "__main__":
    search_huggingface_models()
    test_current_model() 