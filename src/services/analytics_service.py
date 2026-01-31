"""
analytics_service.py — Сервис для анализа данных бизнеса и расчета метрик.
Используется как воркером (после парсинга), так и API (при ручном обновлении).
"""

import json
from typing import Dict, Any, Union

def calculate_profile_completeness(business_data: Dict[str, Any]) -> int:
    """
    Рассчитывает процент заполненности профиля (0-100).
    Безопасно обрабатывает типы данных.
    
    Args:
        business_data: Словарь с данными бизнеса. Ожидаемые ключи:
            - phone (str)
            - website (str)
            - schedule (list/json) / working_hours
            - photos_count (int/str)
            - services_count (int/str)
            - description (str)
            - messengers (list)
            - is_verified (bool/int)
            
    Returns:
        int: Score from 0 to 100
    """
    try:
        completeness = 0
        
        # Извлекаем и нормализуем данные
        phone = business_data.get('phone')
        website = business_data.get('website') or business_data.get('site')
        
        # Часы могут быть в разных форматах
        schedule = business_data.get('schedule') or business_data.get('working_hours') or business_data.get('hours_json')
        
        description = business_data.get('description')
        messengers = business_data.get('messengers')
        is_verified = business_data.get('is_verified')
        
        # Безопасное приведение чисел
        try:
            photos_count = int(business_data.get('photos_count', 0) or 0)
        except (ValueError, TypeError):
            photos_count = 0
            
        try:
            services_count = int(business_data.get('services_count', 0) or 0)
        except (ValueError, TypeError):
            services_count = 0

        # === ЛОГИКА ОЦЕНКИ ===
        
        # 1. Телефон (+15%)
        if phone and len(str(phone)) > 5:
            completeness += 15
            
        # 2. Сайт (+15%)
        if website and len(str(website)) > 3:
            completeness += 15
            
        # 3. График работы (+10%)
        if schedule:
            if isinstance(schedule, str) and len(schedule) > 5 and schedule != 'null':
                 completeness += 10
            elif isinstance(schedule, (list, dict)) and schedule:
                 completeness += 10
                 
        # 4. Фото (3+ фото = +15%)
        if photos_count >= 3:
            completeness += 15
        elif photos_count > 0:
            completeness += 5 # Частичный балл
            
        # 5. Услуги (5+ услуг = +15%)
        if services_count >= 5:
            completeness += 15
        elif services_count > 0:
            completeness += 5
            
        # 6. Описание (+10%)
        if description and len(str(description)) > 10:
            completeness += 10
            
        # 7. Мессенджеры (+10%)
        if messengers:
            if isinstance(messengers, str) and len(messengers) > 5 and messengers != 'null':
                completeness += 10
            elif isinstance(messengers, list) and messengers:
                completeness += 10
                
        # 8. Верификация/Синяя галочка (+10%)
        if is_verified:
            completeness += 10
            
        return min(completeness, 100)
        
    except Exception as e:
        print(f"⚠️ Ошибка в calculate_profile_completeness: {e}")
        return 0

def generate_seo_recommendations(business_data: Dict[str, Any]) -> Dict[str, Any]:
    """Генерирует простые рекомендации на основе пропусков"""
    recommendations = []
    
    score = calculate_profile_completeness(business_data)
    
    if not business_data.get('phone'):
        recommendations.append({"type": "critical", "text": "Добавьте номер телефона"})
        
    if not business_data.get('website'):
        recommendations.append({"type": "important", "text": "Добавьте веб-сайт"})
        
    photos = 0
    try: photos = int(business_data.get('photos_count', 0) or 0)
    except: pass
    
    if photos < 3:
        recommendations.append({"type": "warning", "text": f"Загружено мало фото ({photos}). Добавьте минимум 3."})
        
    return {
        "score": score,
        "items": recommendations
    }
