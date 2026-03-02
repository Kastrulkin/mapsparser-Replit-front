import os
try:
    from apify_client import ApifyClient
    APIFY_AVAILABLE = True
except ImportError:
    ApifyClient = None
    APIFY_AVAILABLE = False
    print("Warning: apify_client not installed. Prospecting features disabled.")
from typing import List, Dict, Any, Optional
import datetime

class ProspectingService:
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.environ.get('APIFY_TOKEN')
        self.actor_id = os.environ.get('APIFY_YANDEX_ACTOR_ID', 'm_mamaev/yandex-maps-places-scraper')
        if not APIFY_AVAILABLE:
            print("Warning: apify_client not available. Prospecting service disabled.")
            self.client = None
        elif not self.api_token:
            print("Warning: APIFY_TOKEN is not set. Prospecting service will not work.")
            self.client = None
        else:
            self.client = ApifyClient(self.api_token)

    @staticmethod
    def _pick(item: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in item and item.get(key) not in (None, ""):
                return item.get(key)
        return None

    def _normalize_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        messenger_links = self._pick(item, "messengerLinks", "messengers", "socialLinks") or []
        if isinstance(messenger_links, dict):
            messenger_links = [messenger_links]
        if not isinstance(messenger_links, list):
            messenger_links = [messenger_links]

        telegram_url = self._pick(item, "telegram", "telegram_url", "telegramUrl")
        whatsapp_url = self._pick(item, "whatsapp", "whatsapp_url", "whatsappUrl")

        return {
            "source": "apify_yandex",
            "name": self._pick(item, "title", "name", "companyName"),
            "address": self._pick(item, "address", "fullAddress"),
            "phone": self._pick(item, "phone", "phoneNumber"),
            "website": self._pick(item, "website", "site", "siteUrl"),
            "email": self._pick(item, "email"),
            "rating": self._pick(item, "rating", "totalScore"),
            "reviews_count": self._pick(item, "reviewsCount", "reviews_count", "reviews"),
            "source_url": self._pick(item, "url", "placeUrl", "mapsUrl"),
            "source_external_id": self._pick(item, "id", "placeId", "oid", "organizationId"),
            "google_id": self._pick(item, "placeId", "id", "oid"),
            "category": self._pick(item, "category", "categoryName", "rubric"),
            "location": self._pick(item, "location", "coordinates"),
            "city": self._pick(item, "city", "locality"),
            "telegram_url": telegram_url,
            "whatsapp_url": whatsapp_url,
            "messenger_links": messenger_links,
        }

    def search_businesses(self, query: str, location: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search for businesses using Apify Yandex Maps scraper.
        """
        if not self.client:
            raise ValueError("APIFY_TOKEN is not set")

        run_input = {
            "search": query,
            "query": query,
            "searchString": query,
            "searchStringsArray": [query],
            "location": location,
            "locationQuery": location,
            "city": location,
            "maxItems": limit,
            "maxCrawledPlaces": limit,
            "maxCrawledPlacesPerSearch": limit,
            "language": "ru",
        }

        try:
            run = self.client.actor(self.actor_id).call(run_input=run_input)
        except Exception as e:
            print(f"Error running Apify actor: {e}")
            raise

        results = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(self._normalize_result(item))
        
        return results
