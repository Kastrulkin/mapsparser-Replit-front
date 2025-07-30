import os
import requests
import json
from typing import Dict, Any, List
from supabase import create_client, Client
from model_config import get_model_config, get_prompt

# Инициализация Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

# Hugging Face API
HF_API_TOKEN = os.getenv('HUGGINGFACE_API_TOKEN')
HF_API_URL = "https://api-inference.huggingface.co/models"

def analyze_business_data(card_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Анализирует данные бизнеса с помощью ИИ
    """
    
    # Подготавливаем данные для анализа
    analysis_text = prepare_data_for_analysis(card_data)
    
    # Анализируем с помощью Hugging Face
    analysis_result = call_huggingface_analysis(analysis_text)
    
    # Формируем рекомендации
    recommendations = generate_recommendations(analysis_result, card_data)
    
    return {
        'analysis': analysis_result,
        'recommendations': recommendations,
        'score': calculate_seo_score(analysis_result)
    }

def prepare_data_for_analysis(card_data: Dict[str, Any]) -> str:
    """
    Подготавливает данные для ИИ-анализа
    """
    text_parts = []
    
    # Основная информация
    if card_data.get('title'):
        text_parts.append(f"Название: {card_data['title']}")
    
    if card_data.get('address'):
        text_parts.append(f"Адрес: {card_data['address']}")
    
    if card_data.get('rating'):
        text_parts.append(f"Рейтинг: {card_data['rating']}")
    
    if card_data.get('reviews_count'):
        text_parts.append(f"Количество отзывов: {card_data['reviews_count']}")
    
    # Описание
    if card_data.get('overview'):
        overview = card_data['overview']
        if isinstance(overview, dict):
            if 'description' in overview:
                text_parts.append(f"Описание: {overview['description']}")
        elif isinstance(overview, str):
            text_parts.append(f"Описание: {overview}")
    
    # Категории
    if card_data.get('categories'):
        categories = card_data['categories']
        if isinstance(categories, list):
            text_parts.append(f"Категории: {', '.join(categories)}")
        elif isinstance(categories, dict):
            text_parts.append(f"Категории: {json.dumps(categories, ensure_ascii=False)}")
    
    # Отзывы
    if card_data.get('reviews'):
        reviews = card_data['reviews']
        if isinstance(reviews, list) and len(reviews) > 0:
            # Берём первые 5 отзывов для анализа
            review_texts = []
            for review in reviews[:5]:
                if isinstance(review, dict) and 'text' in review:
                    review_texts.append(review['text'])
            if review_texts:
                text_parts.append(f"Отзывы: {' '.join(review_texts)}")
    
    return "\n".join(text_parts)

def call_huggingface_analysis(text: str) -> Dict[str, Any]:
    """
    Вызывает Hugging Face модель для анализа
    """
    try:
        # Получаем конфигурацию модели
        model_config = get_model_config()
        model_name = model_config["name"]
        
        headers = {
            "Authorization": f"Bearer {HF_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Получаем промпт для анализа
        prompt = get_prompt("seo_analysis", text)
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_length": model_config["max_length"],
                "temperature": model_config["temperature"],
                "do_sample": model_config["do_sample"],
                "top_p": model_config["top_p"]
            }
        }
        
        response = requests.post(
            f"{HF_API_URL}/{model_name}",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка Hugging Face API: {response.status_code}")
            return {"error": "API error", "status": response.status_code}
            
    except Exception as e:
        print(f"Ошибка при вызове Hugging Face: {e}")
        return {"error": str(e)}

def generate_recommendations(analysis_result: Dict[str, Any], card_data: Dict[str, Any]) -> List[str]:
    """
    Генерирует конкретные рекомендации на основе анализа
    """
    recommendations = []
    
    # Базовые рекомендации на основе данных
    if card_data.get('rating') and card_data['rating'] < 4.0:
        recommendations.append("Улучшите качество услуг для повышения рейтинга")
    
    if card_data.get('reviews_count') and card_data['reviews_count'] < 10:
        recommendations.append("Попросите клиентов оставлять отзывы для повышения доверия")
    
    if not card_data.get('site'):
        recommendations.append("Добавьте ссылку на официальный сайт")
    
    if not card_data.get('phone'):
        recommendations.append("Укажите контактный телефон")
    
    # Добавляем рекомендации из ИИ-анализа
    if 'generated_text' in analysis_result:
        ai_recommendations = analysis_result['generated_text'].split('.')
        recommendations.extend([rec.strip() for rec in ai_recommendations if rec.strip()])
    
    return recommendations[:10]  # Ограничиваем 10 рекомендациями

def calculate_seo_score(analysis_result: Dict[str, Any]) -> int:
    """
    Рассчитывает SEO-оценку (0-100)
    """
    score = 50  # Базовая оценка
    
    # Логика расчёта оценки на основе анализа
    if 'generated_text' in analysis_result:
        text = analysis_result['generated_text'].lower()
        if 'хорошо' in text or 'отлично' in text:
            score += 20
        if 'улучшить' in text or 'рекомендуется' in text:
            score -= 10
    
    return max(0, min(100, score))

def process_pending_analyses():
    """
    Обрабатывает все записи в Cards, которые требуют ИИ-анализа
    """
    try:
        # Получаем записи без анализа
        response = supabase.table('Cards').select('*').is_('ai_analysis', 'null').execute()
        
        if response.data:
            print(f"Найдено {len(response.data)} записей для анализа")
            
            for card in response.data:
                print(f"Анализируем карточку {card['id']}...")
                
                # Выполняем анализ
                analysis_result = analyze_business_data(card)
                
                # Сохраняем результат
                supabase.table('Cards').update({
                    'ai_analysis': analysis_result,
                    'seo_score': analysis_result['score'],
                    'recommendations': analysis_result['recommendations']
                }).eq('id', card['id']).execute()
                
                print(f"Анализ завершён для {card['id']}")
        
        else:
            print("Нет записей для анализа")
            
    except Exception as e:
        print(f"Ошибка при обработке анализов: {e}")

if __name__ == "__main__":
    # Запускаем обработку
    process_pending_analyses() 