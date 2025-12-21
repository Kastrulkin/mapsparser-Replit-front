#!/usr/bin/env python3
"""
Утилиты для определения часового пояса по адресу через Google Maps API
"""
import os
import googlemaps
from datetime import datetime
import pytz

# Загружаем переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')

def get_timezone_from_address(address: str, city: str = None) -> dict:
    """
    Определяет часовой пояс по адресу через Google Maps API
    
    Args:
        address: Адрес бизнеса
        city: Город (опционально, для более точного поиска)
    
    Returns:
        dict с ключами:
            - timezone: часовой пояс (например, 'America/Los_Angeles')
            - latitude: широта
            - longitude: долгота
            - formatted_address: отформатированный адрес
            - error: сообщение об ошибке (если есть)
    """
    if not GOOGLE_MAPS_API_KEY:
        return {
            'error': 'GOOGLE_MAPS_API_KEY не установлен в .env',
            'timezone': 'UTC',
            'latitude': None,
            'longitude': None
        }
    
    try:
        # Формируем полный адрес для поиска
        full_address = f"{address}, {city}" if city else address
        
        # Инициализируем клиент Google Maps
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
        
        # Геокодируем адрес
        geocode_result = gmaps.geocode(full_address)
        
        if not geocode_result:
            return {
                'error': f'Адрес не найден: {full_address}',
                'timezone': 'UTC',
                'latitude': None,
                'longitude': None
            }
        
        # Извлекаем координаты
        location = geocode_result[0]['geometry']['location']
        lat = location['lat']
        lng = location['lng']
        
        # Получаем часовой пояс по координатам
        timezone_result = gmaps.timezone((lat, lng), datetime.now())
        
        if 'timeZoneId' not in timezone_result:
            return {
                'error': 'Не удалось определить часовой пояс',
                'timezone': 'UTC',
                'latitude': lat,
                'longitude': lng,
                'formatted_address': geocode_result[0].get('formatted_address', full_address)
            }
        
        timezone_id = timezone_result['timeZoneId']
        
        return {
            'timezone': timezone_id,
            'latitude': lat,
            'longitude': lng,
            'formatted_address': geocode_result[0].get('formatted_address', full_address),
            'error': None
        }
        
    except Exception as e:
        print(f"⚠️ Ошибка при определении часового пояса: {e}")
        return {
            'error': str(e),
            'timezone': 'UTC',
            'latitude': None,
            'longitude': None
        }

def convert_to_local_time(utc_time: datetime, timezone_id: str) -> datetime:
    """
    Конвертирует UTC время в локальное время по часовому поясу
    
    Args:
        utc_time: Время в UTC
        timezone_id: ID часового пояса (например, 'America/Los_Angeles')
    
    Returns:
        datetime в локальном времени
    """
    try:
        tz = pytz.timezone(timezone_id)
        if utc_time.tzinfo is None:
            # Если время без timezone, считаем его UTC
            utc_time = pytz.UTC.localize(utc_time)
        local_time = utc_time.astimezone(tz)
        return local_time
    except Exception as e:
        print(f"⚠️ Ошибка конвертации времени: {e}")
        return utc_time

if __name__ == "__main__":
    # Тестирование
    test_address = "123 Main St, Los Angeles, CA"
    result = get_timezone_from_address(test_address, "Los Angeles")
    print(f"Результат: {result}")

