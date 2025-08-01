#!/usr/bin/env python3
"""
Поиск лучших моделей Hugging Face для SEO анализа
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def find_best_seo_models():
    """Ищет лучшие модели для SEO анализа"""
    
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Расширенные поисковые запросы для SEO анализа
    search_queries = [
        "text-generation",
        "text2text-generation", 
        "causal-lm",
        "russian language",
        "multilingual",
        "business analysis",
        "SEO optimization",
        "recommendation system",
        "text analysis",
        "content generation",
        "instruction following",
        "chat model",
        "instruct model",
        "llama",
        "mistral",
        "gemma",
        "qwen",
        "yi",
        "deepseek",
        "codellama",
        "phi",
        "falcon",
        "mpt",
        "redpajama",
        "openllama",
        "vicuna",
        "alpaca",
        "dolly",
        "stablelm",
        "neural-chat",
        "orca",
        "wizardlm",
        "baichuan",
        "chatglm",
        "internlm",
        "aquila",
        "skywork",
        "zephyr",
        "solar",
        "mixtral",
        "llama2",
        "llama3",
        "gpt4all",
        "nomic",
        "openhermes",
        "tigerbot",
        "qwen2",
        "deepseek-coder",
        "codellama-instruct",
        "phi-2",
        "phi-3",
        "gemma2",
        "mistral-7b",
        "mixtral-8x7b",
        "llama-3-8b",
        "llama-3-70b"
    ]
    
    print("🔍 Поиск лучших моделей для SEO анализа...")
    print("=" * 80)
    
    found_models = []
    
    for query in search_queries:
        print(f"\n📝 Поиск: {query}")
        
        try:
            response = requests.get(
                "https://huggingface.co/api/models",
                headers=headers,
                params={
                    "search": query,
                    "sort": "downloads",
                    "direction": "-1",
                    "limit": 20
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
                    if downloads > 10000 and any(tag in ['text-generation', 'text2text-generation', 'causal-lm', 'russian', 'multilingual', 'instruct', 'chat'] for tag in tags):
                        
                        # Проверяем размер модели
                        card_data = model.get('cardData', {})
                        model_size = "Unknown"
                        if 'model-index' in card_data:
                            try:
                                model_size = card_data['model-index'].get('results', [{}])[0].get('metrics', {}).get('parameters', 'Unknown')
                            except:
                                pass
                        
                        found_models.append({
                            'id': model_id,
                            'downloads': downloads,
                            'likes': likes,
                            'tags': tags,
                            'query': query,
                            'size': model_size
                        })
                        
                        print(f"  ✅ {model_id}")
                        print(f"     📥 Downloads: {downloads:,}")
                        print(f"     ❤️  Likes: {likes}")
                        print(f"     📊 Size: {model_size}")
                        print(f"     🏷️  Tags: {', '.join(tags[:5])}")
                        
                        # Проверяем поддержку русского языка
                        if any(tag in ['russian', 'multilingual'] for tag in tags):
                            print(f"     🌍 Поддерживает русский язык")
                        
                        # Проверяем современные модели
                        if any(tag in ['instruct', 'chat', 'llama3', 'mistral', 'gemma', 'qwen2'] for tag in tags):
                            print(f"     🚀 Современная модель")
            else:
                print(f"  ❌ Ошибка API: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Ошибка запроса: {e}")
    
    # Сортируем по популярности
    found_models.sort(key=lambda x: x['downloads'], reverse=True)
    
    print("\n" + "=" * 80)
    print("🏆 ТОП-20 ЛУЧШИХ МОДЕЛЕЙ ДЛЯ SEO АНАЛИЗА:")
    print("=" * 80)
    
    for i, model in enumerate(found_models[:20], 1):
        print(f"\n{i}. {model['id']}")
        print(f"   📥 Downloads: {model['downloads']:,}")
        print(f"   ❤️  Likes: {model['likes']}")
        print(f"   📊 Size: {model['size']}")
        print(f"   🏷️  Tags: {', '.join(model['tags'][:5])}")
        print(f"   🔍 Found by: {model['query']}")
        
        # Специальные отметки
        if any(tag in ['russian', 'multilingual'] for tag in model['tags']):
            print(f"   🌍 Поддерживает русский язык")
        if any(tag in ['instruct', 'chat'] for tag in model['tags']):
            print(f"   🎯 Инструкционная модель")
        if any(tag in ['llama3', 'mistral', 'gemma', 'qwen2'] for tag in model['tags']):
            print(f"   🚀 Современная архитектура")
    
    # Рекомендации
    print("\n" + "=" * 80)
    print("💡 РЕКОМЕНДАЦИИ ДЛЯ SEO АНАЛИЗА:")
    print("=" * 80)
    
    if found_models:
        # Лучшие модели с поддержкой русского языка
        russian_models = [m for m in found_models if any(tag in ['russian', 'multilingual'] for tag in m['tags'])]
        
        if russian_models:
            best_russian = russian_models[0]
            print(f"\n🌍 ЛУЧШАЯ ДЛЯ РУССКОГО ЯЗЫКА:")
            print(f"   {best_russian['id']} ({best_russian['downloads']:,} загрузок)")
        
        # Лучшие современные модели
        modern_models = [m for m in found_models if any(tag in ['llama3', 'mistral', 'gemma', 'qwen2', 'instruct'] for tag in m['tags'])]
        
        if modern_models:
            best_modern = modern_models[0]
            print(f"\n🚀 ЛУЧШАЯ СОВРЕМЕННАЯ МОДЕЛЬ:")
            print(f"   {best_modern['id']} ({best_modern['downloads']:,} загрузок)")
        
        # Лучшие по популярности
        best_popular = found_models[0]
        print(f"\n📈 САМАЯ ПОПУЛЯРНАЯ:")
        print(f"   {best_popular['id']} ({best_popular['downloads']:,} загрузок)")
        
        print(f"\n⚙️  ОПТИМАЛЬНЫЕ НАСТРОЙКИ ДЛЯ ДЛИННЫХ ПРОМПТОВ:")
        print(f"   - max_length: 4096-8192 (для вашего детального промпта)")
        print(f"   - temperature: 0.3-0.5 (для точных ответов)")
        print(f"   - do_sample: True")
        print(f"   - top_p: 0.9")
        print(f"   - repetition_penalty: 1.1")
        
        print(f"\n📝 ВАШ ПРОМПТ ОЧЕНЬ ДЕТАЛЬНЫЙ:")
        print(f"   ✅ Учитывает требования Яндекс Карт 2025")
        print(f"   ✅ Структурированный анализ по разделам")
        print(f"   ✅ Конкретные рекомендации")
        print(f"   ✅ Фокус на русском рынке")
        print(f"   ⚠️  Нужна модель с большим max_length и поддержкой русского языка")

if __name__ == "__main__":
    find_best_seo_models() 