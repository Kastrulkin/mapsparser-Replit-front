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
    Анализирует данные с помощью модели ainize/bart-base-cnn
    """
    try:
        from model_config import get_model_config, get_prompt
        
        # Получаем конфигурацию модели
        model_config = get_model_config("ainize/bart-base-cnn")
        
        # Получаем промпт
        prompt = get_prompt("seo_analysis", text)
        
        # Вызываем Hugging Face API
        import requests
        import os
        
        hf_token = os.getenv('HUGGINGFACE_API_TOKEN')
        if not hf_token:
            return {"error": "HUGGINGFACE_API_TOKEN не найден"}
        
        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_length": model_config.get("max_length", 1024),
                "temperature": model_config.get("temperature", 0.7),
                "do_sample": model_config.get("do_sample", True),
                "top_p": model_config.get("top_p", 0.9),
                "repetition_penalty": model_config.get("repetition_penalty", 1.1)
            }
        }
        
        response = requests.post(
            f"https://api-inference.huggingface.co/models/ainize/bart-base-cnn",
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
                
                return {
                    "generated_text": generated_text,
                    "analysis_type": "ai_model",
                    "model_used": "ainize/bart-base-cnn"
                }
            else:
                return {"error": "Неожиданный формат ответа от модели"}
        else:
            return {"error": f"Ошибка API {response.status_code}: {response.text}"}
            
    except Exception as e:
        print(f"Ошибка при анализе: {e}")
        return {"error": str(e)}

def analyze_with_rules(text: str) -> str:
    """
    Анализирует данные на основе правил SEO для Яндекс.Карт
    """
    text_lower = text.lower()
    recommendations = []
    
    # 1. Анализ названия
    if "метро" in text_lower or "район" in text_lower:
        recommendations.append("1) Название: Уберите из названия ключевые слова и геометки. Оставьте только официальное название компании")
    
    # 2. Анализ услуг
    if "услуги" in text_lower or "стрижка" in text_lower or "маникюр" in text_lower:
        recommendations.append("2) Услуги: Добавьте к названиям услуг ключевые слова и геолокацию (например, 'Стрижка у метро Парк Победы')")
    
    # 3. Анализ адреса
    if "адрес" in text_lower:
        if "метро" not in text_lower and "остановка" not in text_lower:
            recommendations.append("3) Контакты: Добавьте информацию о ближайшем метро или остановке в адрес")
    
    # 4. Анализ контента
    if "фото" in text_lower:
        if "8" in text or "10" in text:
            recommendations.append("4) Контент: Добавьте больше фотографий (минимум 10): фасад, интерьер, процесс работы, результаты")
    
    # 5. Анализ активности
    if "отзыв" in text_lower:
        recommendations.append("5) Активность: Регулярно отвечайте на отзывы и публикуйте новости в разделе 'Посты'")
    
    # Если рекомендаций мало, добавляем базовые
    if len(recommendations) < 3:
        recommendations.extend([
            "Добавьте полную информацию о способах оплаты (наличные, карты, СБП)",
            "Укажите точные часы работы",
            "Добавьте ссылки на социальные сети"
        ])
    
    return ". ".join(recommendations[:5]) + "."

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