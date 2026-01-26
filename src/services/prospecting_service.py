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
        if not APIFY_AVAILABLE:
            print("Warning: apify_client not available. Prospecting service disabled.")
            self.client = None
        elif not self.api_token:
            print("Warning: APIFY_TOKEN is not set. Prospecting service will not work.")
            self.client = None
        else:
            self.client = ApifyClient(self.api_token)

    def search_businesses(self, query: str, location: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search for businesses using Apify Google Maps Scraper.
        """
        if not self.client:
            raise ValueError("APIFY_TOKEN is not set")

        # Prepare the actor input
        run_input = {
            "searchStringsArray": [query],
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": limit,
            "language": "en",
        }

        # Run the actor and wait for it to finish
        # Actor ID for google-maps-scraper: compass/crawler-google-places or equivalent
        # Using 'compass/crawler-google-places' as it's a popular one, or 'apify/google-maps-scraper'
        # Let's use 'compass/crawler-google-places' which is often used for this.
        # Actually, user said "apify actor (likely google-maps-scraper)", so let's stick to a standard one if possible.
        # 'compass/crawler-google-places' is very standard.
        
        try:
            run = self.client.actor("compass/crawler-google-places").call(run_input=run_input)
        except Exception as e:
            print(f"Error running Apify actor: {e}")
            raise

        # Fetch results
        results = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append({
                "name": item.get("title"),
                "address": item.get("address"),
                "phone": item.get("phone"),
                "website": item.get("website"),
                "rating": item.get("totalScore"),
                "reviews_count": item.get("reviewsCount"),
                "source_url": item.get("url"),
                "google_id": item.get("placeId"),
                "category": item.get("categoryName"),
                "location": item.get("location"), # lat/lng
            })
        
        return results
