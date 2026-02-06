import os
import requests
from typing import Optional, Dict, List, Any

class TwoGISClient:
    """
    Клиент для работы с 2GIS Places API (Free Tier/Demo).
    Документация: https://docs.2gis.com/en/api/search/places/reference/3.0/items
    """
    
    BASE_URL = "https://catalog.api.2gis.com/3.0"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("TWOGIS_API_KEY")
        if not self.api_key:
            raise ValueError("2GIS API Key is not set")
            
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполняет запрос к API."""
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params['key'] = self.api_key
        
        # Free tier limitation: fields are limited. 
        # items.reviews is NOT available in free tier usually, need to check specific permissions.
        # But we can try to get as much as possible.
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Check for API-level errors
            meta = data.get('meta', {})
            if meta.get('code') != 200:
                error = meta.get('error', {})
                raise Exception(f"2GIS API Error: {error.get('message')} (Code: {meta.get('code')})")
                
            return data
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 2GIS Request Failed: {e}")
            if e.response:
                print(f"   Response: {e.response.text}")
            raise

    def search_organization_by_id(self, org_id: str) -> Optional[Dict[str, Any]]:
        """
        Поиск организации по ID.
        endpoint: /items/byid
        """
        try:
            # fields: items.reviews, items.rating - might require paid key or specific fields
            fields = "items.point,items.address,items.name,items.org,items.adm_div,items.reviews,items.rating,items.schedule,items.contact_groups,items.attributes"
            data = self._make_request("items/byid", {"id": org_id, "fields": fields})
            items = data.get('result', {}).get('items', [])
            return items[0] if items else None
        except Exception as e:
            print(f"⚠️ Error searching org by ID {org_id}: {e}")
            return None

    def search_organization_by_text(self, query: str, city_id: str = None) -> List[Dict[str, Any]]:
        """
        Поиск организации по тексту (названию, адресу).
        endpoint: /items
        """
        params = {
            "q": query,
            "fields": "items.point,items.address,items.name,items.rating,items.reviews,items.schedule",
            "page_size": 5 
        }
        if city_id:
            params["city_id"] = city_id
            
        try:
            data = self._make_request("items", params)
            return data.get('result', {}).get('items', [])
        except Exception as e:
            print(f"⚠️ Error searching org by text '{query}': {e}")
            return []

    def get_reviews(self, org_id: str) -> List[Dict[str, Any]]:
        """
        Получение отзывов.
        ВНИМАНИЕ: Public API 2GIS (Places) часто НЕ отдаёт текст отзывов в бесплатной версии,
        только рейтинг и кол-во. 
        Если API не отдает отзывы, возвращаем пустой список.
        """
        # В документации 3.0 items/reviews endpoint может отсутствовать или требовать доп прав.
        # Пробуем через items/byid с полем items.reviews -- если там нет деталей, значит API ограничен.
        
        # Для демо ключа функционал отзывов часто ограничен.
        # Попробуем вернуть то, что есть в 'items/byid' в поле reviews (если придет).
        # Отдельного эндпоинта /reviews в публичном Places API 3.0 нет (есть в картах 2.0, но он deprecated).
        
        info = self.search_organization_by_id(org_id)
        if not info:
            return []
            
        # 2GIS API structure handling
        # Usually user ratings/reviews are not fully exposed in free tier via API details.
        # We might need to rely on scraping/html parsing for reviews if API fails.
        # But this client implements API Access only.
        
        # Check if 'reviews' field has detailed items
        reviews_data = info.get('reviews', {})
        # Note: often 'reviews' just contains 'general_rating', 'general_review_count'.
        
        return [] # Placeholder as 2GIS Places API typically doesn't return list of reviews text
