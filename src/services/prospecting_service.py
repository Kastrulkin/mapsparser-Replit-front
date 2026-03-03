import os
from decimal import Decimal
import requests
from urllib.parse import quote
try:
    from apify_client import ApifyClient
    APIFY_AVAILABLE = True
except ImportError:
    ApifyClient = None
    APIFY_AVAILABLE = False
    print("Warning: apify_client not installed. Prospecting features disabled.")
from typing import List, Dict, Any, Optional
import datetime


APIFY_SEARCH_TIMEOUT_SEC = int(os.environ.get("APIFY_SEARCH_TIMEOUT_SEC", "180"))
APIFY_SEARCH_MAX_CHARGE_USD = Decimal(os.environ.get("APIFY_SEARCH_MAX_CHARGE_USD", "1.0"))

class ProspectingService:
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.environ.get('APIFY_TOKEN')
        self.actor_id = (
            os.environ.get('APIFY_YANDEX_ACTOR_ID')
            or os.environ.get('APIFY_ACTOR_ID')
            or 'PSCXgHmlrrRaoXgRx'
        )
        if not APIFY_AVAILABLE:
            print("Warning: apify_client not available. Prospecting service disabled.")
            self.client = None
        elif not self.api_token:
            print("Warning: APIFY_TOKEN is not set. Prospecting service will not work.")
            self.client = None
        else:
            self.client = ApifyClient(self.api_token)

    def _actor_path_id(self) -> str:
        """
        Apify REST path accepts actor username/name in `owner~actor` form, while
        older local config may still store `owner/actor`. Normalize it here so
        server .env does not have to be perfectly formatted.
        """
        raw_actor_id = str(self.actor_id or "").strip()
        if not raw_actor_id:
            return ""
        if "/" in raw_actor_id and "~" not in raw_actor_id:
            raw_actor_id = raw_actor_id.replace("/", "~", 1)
        return quote(raw_actor_id, safe="~")

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

    def _build_run_input(self, query: str, location: str, limit: int) -> Dict[str, Any]:
        full_query = f"{query.strip()} in {location.strip()}".strip()
        return {
            "query": full_query,
            "maxItems": limit,
            "language": "RU",
            "maxPhotos": 1,
            "proxyConfig": {"useApifyProxy": True},
            "mapsDomain": "auto",
            "enableGlobalDataset": False,
        }

    def start_search_run(self, query: str, location: str, limit: int = 50) -> Dict[str, Any]:
        if not self.api_token:
            raise ValueError("APIFY_TOKEN is not set")

        run_input = self._build_run_input(query, location, limit)
        # Use raw REST start instead of apify_client.start() because the client
        # library uses a shorter default HTTP timeout and can still block before
        # returning a run id on slow API responses.
        actor_path_id = self._actor_path_id()
        if not actor_path_id:
            raise ValueError("APIFY actor id is not set")
        response = requests.post(
            f"https://api.apify.com/v2/acts/{actor_path_id}/runs",
            params={"token": self.api_token, "waitForFinish": 0},
            json=run_input,
            timeout=(10, 120),
        )
        response.raise_for_status()
        payload = response.json().get("data") or {}
        if not payload.get("id"):
            raise RuntimeError("Apify run did not return an id")
        return {
            "run_id": payload.get("id"),
            "dataset_id": payload.get("defaultDatasetId"),
            "status": payload.get("status"),
            "run_input": run_input,
        }

    def get_run(self, run_id: str) -> Dict[str, Any]:
        if not self.api_token:
            raise ValueError("APIFY_TOKEN is not set")
        response = requests.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            params={"token": self.api_token},
            timeout=(10, 45),
        )
        response.raise_for_status()
        return response.json().get("data") or {}

    def fetch_dataset_items(self, dataset_id: str) -> List[Dict[str, Any]]:
        if not self.api_token:
            raise ValueError("APIFY_TOKEN is not set")
        if not dataset_id:
            return []
        response = requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={"token": self.api_token, "format": "json", "clean": "1"},
            timeout=(10, 90),
        )
        response.raise_for_status()
        items = response.json()
        if not isinstance(items, list):
            return []
        return [self._normalize_result(item) for item in items if isinstance(item, dict)]

    def search_businesses(self, query: str, location: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search for businesses using Apify Yandex Maps scraper.
        """
        if not self.client:
            raise ValueError("APIFY_TOKEN is not set")

        try:
            run = self.client.actor(self.actor_id).call(
                run_input=self._build_run_input(query, location, limit),
                timeout_secs=APIFY_SEARCH_TIMEOUT_SEC,
                wait_secs=APIFY_SEARCH_TIMEOUT_SEC,
                max_items=limit,
                max_total_charge_usd=APIFY_SEARCH_MAX_CHARGE_USD,
            )
        except Exception as e:
            print(f"Error running Apify actor: {e}")
            raise

        if not run:
            raise TimeoutError(f"Apify actor did not finish within {APIFY_SEARCH_TIMEOUT_SEC} seconds")

        results = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(self._normalize_result(item))
        
        return results
