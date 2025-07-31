"""
Простой ИИ-анализатор без внешних API
"""
import re
from typing import Dict, Any, List

def analyze_business_data(card_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Анализирует данные бизнеса с помощью простых правил
    """
    
    # Подготавливаем данные для анализа
    analysis_text = prepare_data_for_analysis(card_data)
    
    # Анализируем с помощью простых правил
    analysis_result = simple_analysis(analysis_text, card_data)
    
    # Формируем рекомендации
    recommendations = generate_recommendations(analysis_result, card_data)
    
    return {
        'analysis': analysis_result,
        'recommendations': recommendations,
        'score': calculate_seo_score(analysis_result, card_data)
    }

def prepare_data_for_analysis(card_data: Dict[str, Any]) -> str:
    """
    Подготавливает данные для анализа
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
            text_parts.append(f"Категории: {str(categories)}")
    
    return "\n".join(text_parts)

def simple_analysis(text: str, card_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Простой анализ на основе правил
    """
    analysis = {
        'generated_text': '',
        'strengths': [],
        'weaknesses': [],
        'suggestions': []
    }
    
    # Анализируем рейтинг
    rating = card_data.get('rating')
    if rating:
        try:
            rating_float = float(rating)
            if rating_float >= 4.5:
                analysis['strengths'].append('Высокий рейтинг')
                analysis['generated_text'] += 'Отличный рейтинг показывает высокое качество услуг. '
            elif rating_float >= 4.0:
                analysis['strengths'].append('Хороший рейтинг')
                analysis['generated_text'] += 'Хороший рейтинг, есть потенциал для роста. '
            else:
                analysis['weaknesses'].append('Низкий рейтинг')
                analysis['generated_text'] += 'Рейтинг требует улучшения. '
        except:
            pass
    
    # Анализируем количество отзывов
    reviews_count = card_data.get('reviews_count')
    if reviews_count:
        try:
            reviews_int = int(reviews_count)
            if reviews_int >= 100:
                analysis['strengths'].append('Много отзывов')
                analysis['generated_text'] += 'Большое количество отзывов повышает доверие. '
            elif reviews_int >= 20:
                analysis['strengths'].append('Достаточно отзывов')
                analysis['generated_text'] += 'Умеренное количество отзывов. '
            else:
                analysis['weaknesses'].append('Мало отзывов')
                analysis['generated_text'] += 'Недостаточно отзывов для полной оценки. '
        except:
            pass
    
    # Анализируем наличие сайта
    site = card_data.get('site')
    if site:
        analysis['strengths'].append('Есть сайт')
        analysis['generated_text'] += 'Наличие сайта улучшает SEO. '
    else:
        analysis['weaknesses'].append('Нет сайта')
        analysis['generated_text'] += 'Отсутствие сайта снижает видимость в поиске. '
    
    # Анализируем телефон
    phone = card_data.get('phone')
    if phone:
        analysis['strengths'].append('Есть телефон')
        analysis['generated_text'] += 'Контактный телефон облегчает связь с клиентами. '
    else:
        analysis['weaknesses'].append('Нет телефона')
        analysis['generated_text'] += 'Отсутствие телефона затрудняет связь. '
    
    # Анализируем адрес
    address = card_data.get('address')
    if address:
        analysis['strengths'].append('Есть адрес')
        analysis['generated_text'] += 'Указанный адрес помогает клиентам найти вас. '
    else:
        analysis['weaknesses'].append('Нет адреса')
        analysis['generated_text'] += 'Отсутствие адреса затрудняет поиск. '
    
    # Анализируем часы работы
    hours = card_data.get('hours')
    if hours:
        analysis['strengths'].append('Указаны часы работы')
        analysis['generated_text'] += 'Информация о часах работы удобна для клиентов. '
    else:
        analysis['weaknesses'].append('Не указаны часы работы')
        analysis['generated_text'] += 'Отсутствие информации о часах работы может отпугнуть клиентов. '
    
    # Анализируем фото
    photos = card_data.get('photos')
    if photos and len(photos) > 0:
        analysis['strengths'].append('Есть фото')
        analysis['generated_text'] += 'Фотографии помогают клиентам лучше понять ваши услуги. '
    else:
        analysis['weaknesses'].append('Нет фото')
        analysis['generated_text'] += 'Отсутствие фотографий снижает привлекательность карточки. '
    
    return analysis

def generate_recommendations(analysis_result: Dict[str, Any], card_data: Dict[str, Any]) -> List[str]:
    """
    Генерирует рекомендации на основе анализа
    """
    recommendations = []
    
    # Базовые рекомендации
    if not card_data.get('site'):
        recommendations.append('Создайте официальный сайт для повышения видимости')
    
    if not card_data.get('phone'):
        recommendations.append('Добавьте контактный телефон для связи с клиентами')
    
    if not card_data.get('hours'):
        recommendations.append('Укажите часы работы для удобства клиентов')
    
    if not card_data.get('photos') or len(card_data.get('photos', [])) == 0:
        recommendations.append('Добавьте качественные фотографии ваших услуг')
    
    # Рекомендации по рейтингу
    rating = card_data.get('rating')
    if rating:
        try:
            rating_float = float(rating)
            if rating_float < 4.0:
                recommendations.append('Работайте над улучшением качества услуг для повышения рейтинга')
        except:
            pass
    
    # Рекомендации по отзывам
    reviews_count = card_data.get('reviews_count')
    if reviews_count:
        try:
            reviews_int = int(reviews_count)
            if reviews_int < 20:
                recommendations.append('Попросите клиентов оставлять отзывы для повышения доверия')
        except:
            pass
    
    # Если нет рекомендаций, добавляем общие
    if not recommendations:
        recommendations.extend([
            'Регулярно обновляйте информацию в карточке',
            'Отвечайте на отзывы клиентов',
            'Добавляйте актуальные фотографии'
        ])
    
    return recommendations

def calculate_seo_score(analysis_result: Dict[str, Any], card_data: Dict[str, Any]) -> int:
    """
    Рассчитывает SEO-оценку
    """
    score = 50  # Базовая оценка
    
    # Бонусы за сильные стороны
    score += len(analysis_result.get('strengths', [])) * 5
    
    # Штрафы за слабости
    score -= len(analysis_result.get('weaknesses', [])) * 3
    
    # Дополнительные бонусы
    if card_data.get('site'):
        score += 10
    
    if card_data.get('phone'):
        score += 5
    
    if card_data.get('address'):
        score += 5
    
    if card_data.get('hours'):
        score += 5
    
    if card_data.get('photos') and len(card_data.get('photos', [])) > 0:
        score += 10
    
    # Ограничиваем оценку
    score = max(0, min(100, score))
    
    return score 