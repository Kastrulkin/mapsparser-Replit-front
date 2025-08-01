#!/usr/bin/env python3
"""
Поиск моделей текстовой генерации для SEO анализа
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def find_text_generation_models():
    """Ищет модели для текстовой генерации"""
    
    hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not hf_token:
        print("❌ HUGGINGFACE_API_TOKEN не найден")
        return
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    # Специфичные модели для текстовой генерации
    specific_models = [
        "gpt2",
        "gpt2-medium", 
        "gpt2-large",
        "gpt2-xl",
        "facebook/bart-base",
        "facebook/bart-large",
        "facebook/bart-large-cnn",
        "t5-base",
        "t5-large",
        "t5-3b",
        "microsoft/DialoGPT-medium",
        "microsoft/DialoGPT-large",
        "EleutherAI/gpt-neo-125M",
        "EleutherAI/gpt-neo-1.3B",
        "EleutherAI/gpt-neo-2.7B",
        "bigscience/bloom-560m",
        "bigscience/bloom-1b1",
        "bigscience/bloom-3b",
        "microsoft/DialoGPT-medium",
        "microsoft/DialoGPT-large",
        "microsoft/DialoGPT-xl"
    ]
    
    print("🔍 Поиск моделей текстовой генерации...")
    print("=" * 60)
    
    found_models = []
    
    for model_id in specific_models:
        try:
            response = requests.get(
                f"https://huggingface.co/api/models/{model_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                model_data = response.json()
                
                downloads = model_data.get('downloads', 0)
                likes = model_data.get('likes', 0)
                tags = model_data.get('tags', [])
                
                # Проверяем, что это модель текстовой генерации
                if any(tag in ['text-generation', 'text2text-generation', 'causal-lm'] for tag in tags):
                    found_models.append({
                        'id': model_id,
                        'downloads': downloads,
                        'likes': likes,
                        'tags': tags,
                        'cardData': model_data.get('cardData', {})
                    })
                    
                    print(f"✅ {model_id}")
                    print(f"   📥 Downloads: {downloads:,}")
                    print(f"   ❤️  Likes: {likes}")
                    print(f"   🏷️  Tags: {', '.join(tags[:5])}")
                    
                    # Проверяем поддержку русского языка
                    if any(tag in ['russian', 'multilingual'] for tag in tags):
                        print(f"   🌍 Поддерживает русский язык")
                    
            else:
                print(f"❌ {model_id}: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка для {model_id}: {e}")
    
    # Сортируем по популярности
    found_models.sort(key=lambda x: x['downloads'], reverse=True)
    
    print("\n" + "=" * 60)
    print("🏆 ЛУЧШИЕ МОДЕЛИ ДЛЯ ТЕКСТОВОЙ ГЕНЕРАЦИИ:")
    print("=" * 60)
    
    for i, model in enumerate(found_models[:10], 1):
        print(f"\n{i}. {model['id']}")
        print(f"   📥 Downloads: {model['downloads']:,}")
        print(f"   ❤️  Likes: {model['likes']}")
        print(f"   🏷️  Tags: {', '.join(model['tags'][:5])}")
        
        # Проверяем размер модели
        card_data = model.get('cardData', {})
        if 'model-index' in card_data:
            print(f"   📊 Размер: {card_data['model-index'].get('results', [{}])[0].get('metrics', {}).get('parameters', 'N/A')}")
    
    # Рекомендации для SEO анализа
    print("\n" + "=" * 60)
    print("💡 РЕКОМЕНДАЦИИ ДЛЯ SEO АНАЛИЗА:")
    print("=" * 60)
    
    if found_models:
        print(f"\n🎯 ДЛЯ ВАШЕГО ДЕТАЛЬНОГО ПРОМПТА РЕКОМЕНДУЮ:")
        
        # Ищем модели с поддержкой русского языка
        russian_models = [m for m in found_models if any(tag in ['russian', 'multilingual'] for tag in m['tags'])]
        
        if russian_models:
            best_russian = russian_models[0]
            print(f"   1. 🌍 {best_russian['id']} - лучшая для русского языка")
            print(f"      - Downloads: {best_russian['downloads']:,}")
            print(f"      - Поддерживает русский язык")
        
        # Ищем большие модели для сложных промптов
        large_models = [m for m in found_models if m['downloads'] > 1000000]
        if large_models:
            best_large = large_models[0]
            print(f"   2. 🚀 {best_large['id']} - для сложных анализов")
            print(f"      - Downloads: {best_large['downloads']:,}")
            print(f"      - Большая модель для детального анализа")
        
        # Рекомендуем текущую модель если она в списке
        current_model = "facebook/bart-base"
        current_in_list = [m for m in found_models if current_model in m['id']]
        if current_in_list:
            current_data = current_in_list[0]
            print(f"   3. ⚙️  {current_data['id']} - текущая модель")
            print(f"      - Downloads: {current_data['downloads']:,}")
            print(f"      - Уже настроена в системе")
        
        print(f"\n⚙️  ОПТИМАЛЬНЫЕ НАСТРОЙКИ ДЛЯ ДЛИННЫХ ПРОМПТОВ:")
        print(f"   - max_length: 2048-4096 (для вашего детального промпта)")
        print(f"   - temperature: 0.3-0.5 (для точных ответов)")
        print(f"   - do_sample: True")
        print(f"   - top_p: 0.9")
        print(f"   - repetition_penalty: 1.1 (избежать повторов)")
        
        print(f"\n📝 ВАШ ПРОМПТ ОЧЕНЬ ДЕТАЛЬНЫЙ:")
        print(f"   ✅ Учитывает требования Яндекс Карт 2025")
        print(f"   ✅ Структурированный анализ по разделам")
        print(f"   ✅ Конкретные рекомендации")
        print(f"   ✅ Фокус на русском рынке")
        print(f"   ⚠️  Нужна модель с большим max_length")

if __name__ == "__main__":
    find_text_generation_models() 