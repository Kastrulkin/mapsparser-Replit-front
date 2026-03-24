import os
import re
import time
from decimal import Decimal
import requests
from urllib.parse import quote, urlparse, parse_qs
from requests import Response
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
SUPPORTED_APIFY_SOURCES = {"apify_yandex", "apify_2gis", "apify_google", "apify_apple"}

class ProspectingService:
    def __init__(
        self,
        api_token: Optional[str] = None,
        *,
        source: str = "apify_yandex",
        actor_id_override: Optional[str] = None,
    ):
        self.api_token = api_token or os.environ.get('APIFY_TOKEN')
        normalized_source = str(source or "apify_yandex").strip().lower()
        if normalized_source not in SUPPORTED_APIFY_SOURCES:
            normalized_source = "apify_yandex"
        self.source = normalized_source

        yandex_actor = (
            os.environ.get("APIFY_YANDEX_ACTOR_ID")
            or os.environ.get("APIFY_ACTOR_ID")
            or "PSCXgHmlrrRaoXgRx"
        )
        twogis_actor = (
            os.environ.get("APIFY_2GIS_ACTOR_ID")
            or os.environ.get("APIFY_TWOGIS_ACTOR_ID")
            or yandex_actor
        )
        google_actor = (
            os.environ.get("APIFY_GOOGLE_ACTOR_ID")
            or "0SHtjFyh3L6V8fLDT"
        )
        apple_actor = (
            os.environ.get("APIFY_APPLE_ACTOR_ID")
            or "5bSvAQKSK3LPq9OXb"
        )
        source_actor_map = {
            "apify_yandex": yandex_actor,
            "apify_2gis": twogis_actor,
            "apify_google": google_actor,
            "apify_apple": apple_actor,
        }
        source_actor = source_actor_map.get(self.source) or yandex_actor
        self.actor_id = str(actor_id_override or source_actor or "").strip()
        if not APIFY_AVAILABLE:
            print("Warning: apify_client not available. Prospecting service disabled.")
            self.client = None
        elif not self.api_token:
            print("Warning: APIFY_TOKEN is not set. Prospecting service will not work.")
            self.client = None
        else:
            self.client = ApifyClient(self.api_token)

    @staticmethod
    def _apify_actor_proxy_config() -> Dict[str, Any]:
        """
        Apify actor-side proxy config (runs inside Apify platform).
        We do not force residential groups by default to avoid 402 on plans
        without RESIDENTIAL access.
        """
        config: Dict[str, Any] = {"useApifyProxy": True}
        proxy_groups_raw = str(os.environ.get("APIFY_ACTOR_PROXY_GROUPS", "") or "").strip()
        proxy_groups = [grp.strip() for grp in proxy_groups_raw.split(",") if grp.strip()]
        if proxy_groups:
            config["apifyProxyGroups"] = proxy_groups
        country = str(os.environ.get("APIFY_ACTOR_PROXY_COUNTRY", "") or "").strip().upper()
        if country:
            config["apifyProxyCountry"] = country
        return config

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

    @classmethod
    def _strip_none_values(cls, value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: Dict[str, Any] = {}
            for key, nested in value.items():
                if nested is None:
                    continue
                normalized = cls._strip_none_values(nested)
                cleaned[key] = normalized
            return cleaned
        if isinstance(value, list):
            return [cls._strip_none_values(item) for item in value if item is not None]
        return value

    @staticmethod
    def _collect_nested_strings(value: Any) -> List[str]:
        out: List[str] = []
        if isinstance(value, str):
            text = value.strip()
            if text:
                out.append(text)
            return out
        if isinstance(value, dict):
            for nested in value.values():
                out.extend(ProspectingService._collect_nested_strings(nested))
            return out
        if isinstance(value, list):
            for nested in value:
                out.extend(ProspectingService._collect_nested_strings(nested))
            return out
        return out

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @classmethod
    def _coerce_scalar_text(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        if isinstance(value, (int, float, bool)):
            return str(value)
        nested = cls._collect_nested_strings(value)
        if not nested:
            return None
        return nested[0].strip() or None

    @staticmethod
    def _coerce_reviews_count(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            digits = "".join(ch for ch in value if ch.isdigit())
            return int(digits) if digits else None
        if isinstance(value, list):
            return len(value)
        return None

    @staticmethod
    def _normalize_media_url(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        if text.startswith("//"):
            text = f"https:{text}"
        if "{size}" in text:
            text = text.replace("{size}", "XXXL")
        if "/%s" in text:
            text = text.replace("/%s", "/XXXL")
        elif "%s" in text:
            text = text.replace("%s", "XXXL")
        return text

    @classmethod
    def _extract_photos(cls, item: Dict[str, Any], limit: int = 20) -> List[str]:
        raw_photos = item.get("photos")
        photos: List[str] = []
        if isinstance(raw_photos, list):
            for entry in raw_photos:
                if isinstance(entry, str):
                    value = cls._normalize_media_url(entry) or ""
                    if value:
                        photos.append(value)
                elif isinstance(entry, dict):
                    for key in ("url", "imageUrl", "src", "originalUrl"):
                        candidate = cls._normalize_media_url(entry.get(key)) or cls._coerce_scalar_text(entry.get(key))
                        if candidate:
                            photos.append(candidate)
                            break
        main_photo = cls._normalize_media_url(item.get("photoUrlTemplate")) or cls._coerce_scalar_text(item.get("photoUrlTemplate"))
        if main_photo:
            photos.insert(0, main_photo)

        deduped: List[str] = []
        seen: set[str] = set()
        for value in photos:
            key = value.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(value.strip())
            if len(deduped) >= max(1, limit):
                break
        return deduped

    @classmethod
    def _extract_services_preview(cls, item: Dict[str, Any], limit: int = 30) -> List[Dict[str, Any]]:
        services: List[Dict[str, Any]] = []
        menu_payload = item.get("menu")
        menu_items: List[Dict[str, Any]] = []
        if isinstance(menu_payload, list):
            menu_items = [entry for entry in menu_payload if isinstance(entry, dict)]
        elif isinstance(menu_payload, dict):
            items = menu_payload.get("items")
            if isinstance(items, list):
                menu_items = [entry for entry in items if isinstance(entry, dict)]

        for entry in menu_items:
            name = cls._coerce_scalar_text(entry.get("name") or entry.get("title"))
            if not name:
                continue
            category = cls._coerce_scalar_text(
                entry.get("category") or entry.get("group") or entry.get("section")
            )
            description = cls._coerce_scalar_text(entry.get("description"))
            price_value = (
                entry.get("price")
                or entry.get("price_from")
                or entry.get("price_to")
                or entry.get("cost")
            )
            price = cls._coerce_scalar_text(price_value)
            services.append(
                {
                    "name": name,
                    "title": name,
                    "category": category,
                    "description": description,
                    "price": price,
                }
            )
            if len(services) >= max(1, limit):
                return services

        # Fallback: when menu is missing, derive pseudo-services from features blocks.
        features = item.get("features")
        if isinstance(features, dict):
            for feature_name, feature_values in features.items():
                if not isinstance(feature_values, list):
                    continue
                category = cls._coerce_scalar_text(feature_name) or "features"
                for raw_value in feature_values:
                    name = cls._coerce_scalar_text(raw_value)
                    if not name:
                        continue
                    services.append(
                        {
                            "name": name,
                            "title": name,
                            "category": category,
                            "description": None,
                            "price": None,
                        }
                    )
                    if len(services) >= max(1, limit):
                        return services
        return services

    @classmethod
    def _extract_reviews_preview(cls, item: Dict[str, Any], limit: int = 30) -> List[Dict[str, Any]]:
        raw_reviews = item.get("reviews")
        if not isinstance(raw_reviews, list):
            return []

        reviews: List[Dict[str, Any]] = []
        for entry in raw_reviews:
            if not isinstance(entry, dict):
                continue
            text = cls._coerce_scalar_text(entry.get("text") or entry.get("review"))
            if not text:
                continue
            reviews.append(
                {
                    "text": text,
                    "review": text,
                    "rating": entry.get("rating"),
                    "author_name": cls._coerce_scalar_text(entry.get("authorName") or entry.get("author")),
                    "date": cls._coerce_scalar_text(entry.get("date") or entry.get("createdAt")),
                    "business_comment": cls._coerce_scalar_text(
                        entry.get("businessComment") or entry.get("response_text")
                    ),
                }
            )
            if len(reviews) >= max(1, limit):
                break
        return reviews

    @classmethod
    def _is_placeholder_value(cls, value: Any, placeholders: set[str]) -> bool:
        normalized = cls._normalize_text(value).lower()
        return bool(normalized) and normalized in placeholders

    @classmethod
    def _is_meaningful_lead(cls, lead: Dict[str, Any]) -> bool:
        """
        Ignore sample/example rows accidentally imported from UI placeholder JSON.
        """
        placeholder_values = {
            "name",
            "company",
            "company name",
            "title",
            "address",
            "phone",
            "email",
            "website",
            "rating",
            "reviews_count",
            "reviews",
            "status",
            "source",
            "category",
        }
        name = lead.get("name")
        if cls._is_placeholder_value(name, placeholder_values):
            return False
        if not cls._normalize_text(name):
            return False

        meaningful_fields = (
            lead.get("address"),
            lead.get("phone"),
            lead.get("website"),
            lead.get("email"),
            lead.get("source_url"),
            lead.get("source_external_id"),
        )
        if not any(
            cls._normalize_text(value) and not cls._is_placeholder_value(value, placeholder_values)
            for value in meaningful_fields
        ):
            return False
        return True

    def _normalize_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        messenger_links = self._pick(item, "messengerLinks", "messengers", "socialLinks", "socials", "contacts") or []
        if isinstance(messenger_links, dict):
            messenger_links = [messenger_links]
        if not isinstance(messenger_links, list):
            messenger_links = [messenger_links]

        normalized_messenger_links: List[str] = []
        for link in messenger_links:
            if isinstance(link, str) and link.strip():
                normalized_messenger_links.append(link.strip())
            elif isinstance(link, dict):
                for key in ("url", "link", "value"):
                    value = link.get(key)
                    if isinstance(value, str) and value.strip():
                        normalized_messenger_links.append(value.strip())
                        break
        for candidate in self._collect_nested_strings(item.get("contacts")):
            if any(token in candidate.lower() for token in ("t.me/", "telegram", "wa.me/", "whatsapp", "vk.com/", "instagram.com/")):
                normalized_messenger_links.append(candidate.strip())
        normalized_messenger_links = list(dict.fromkeys([link for link in normalized_messenger_links if link]))

        categories_value = self._pick(item, "categories", "category", "categoryName", "rubric")
        category_text = None
        if isinstance(categories_value, list):
            clean_categories = [str(v).strip() for v in categories_value if str(v).strip()]
            if clean_categories:
                category_text = " / ".join(clean_categories[:3])
        elif categories_value not in (None, ""):
            category_text = str(categories_value).strip()

        telegram_url = self._coerce_scalar_text(self._pick(item, "telegram", "telegram_url", "telegramUrl"))
        whatsapp_url = self._coerce_scalar_text(self._pick(item, "whatsapp", "whatsapp_url", "whatsappUrl"))
        if not telegram_url:
            telegram_url = next((link for link in normalized_messenger_links if "t.me/" in link or "telegram.me/" in link), None)
        if not whatsapp_url:
            whatsapp_url = next((link for link in normalized_messenger_links if "wa.me/" in link or "whatsapp" in link.lower()), None)

        email = self._coerce_scalar_text(self._pick(item, "email"))
        if not email:
            nested_values = self._collect_nested_strings(item.get("contacts"))
            email = next((v for v in nested_values if "@" in v and "." in v), None)

        location_value = self._pick(item, "location", "coordinates")
        if isinstance(location_value, (dict, list)):
            location_value = str(location_value)
        location_value = self._coerce_scalar_text(location_value)

        reviews_count = self._coerce_reviews_count(
            self._pick(item, "reviewsCount", "reviews_count", "reviewCount", "ratingsCount", "reviews")
        )
        description = self._coerce_scalar_text(item.get("description"))
        logo_url = self._coerce_scalar_text(item.get("logoUrl") or item.get("logo_url"))
        photos = self._extract_photos(item)
        services_preview = self._extract_services_preview(item)
        reviews_preview = self._extract_reviews_preview(item)
        social_links = self._collect_nested_strings(item.get("socialLinks"))

        search_payload_json = {
            "logo_url": logo_url,
            "description": description,
            "photos": photos,
            "menu_preview": services_preview,
            "reviews_preview": reviews_preview,
            "social_links": social_links,
            "reviews_count": reviews_count,
        }

        return {
            "source": self.source,
            "name": self._coerce_scalar_text(self._pick(item, "title", "name", "companyName")),
            "address": self._coerce_scalar_text(self._pick(item, "address", "fullAddress")),
            "phone": self._coerce_scalar_text(self._pick(item, "phone", "phoneNumber", "phones")),
            "website": self._coerce_scalar_text(self._pick(item, "website", "site", "siteUrl")),
            "email": email,
            "rating": self._pick(item, "rating", "totalScore"),
            "reviews_count": reviews_count,
            "source_url": self._coerce_scalar_text(self._pick(item, "url", "placeUrl", "mapsUrl")),
            "source_external_id": self._coerce_scalar_text(self._pick(item, "businessId", "id", "placeId", "oid", "organizationId")),
            "google_id": self._coerce_scalar_text(self._pick(item, "placeId", "id", "oid", "businessId")),
            "category": category_text,
            "location": location_value,
            "city": self._coerce_scalar_text(self._pick(item, "city", "locality")),
            "telegram_url": telegram_url,
            "whatsapp_url": whatsapp_url,
            "messenger_links": normalized_messenger_links,
            "logo_url": logo_url,
            "description": description,
            "photos_json": photos,
            "services_json": services_preview,
            "reviews_json": reviews_preview,
            "search_payload_json": search_payload_json,
            "raw_payload_json": item,
        }

    def normalize_results(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                normalized_item = self._normalize_result(item)
                if self._is_meaningful_lead(normalized_item):
                    normalized.append(normalized_item)
        return normalized

    def _build_run_input(self, query: str, location: str, limit: int) -> Dict[str, Any]:
        query_text = query.strip()
        location_text = location.strip()
        proxy_configuration = self._apify_actor_proxy_config()

        if self.source == "apify_google":
            return {
                "search_term": query_text,
                "location": location_text,
                "language": str(os.environ.get("APIFY_GOOGLE_LANGUAGE", "English") or "English"),
                "max_results": max(1, int(limit or 1)),
                "reviews": 0,
                "photos": 0,
            }

        if self.source == "apify_apple":
            return {
                "searchQueries": [
                    {
                        "query": query_text,
                        "location": location_text,
                    }
                ],
                "maxResults": max(1, int(limit or 1)),
                "countryCode": str(os.environ.get("APIFY_APPLE_COUNTRY_CODE", "RU") or "RU"),
                "language": str(os.environ.get("APIFY_APPLE_LANGUAGE", "ru-RU") or "ru-RU"),
                "proxyConfiguration": proxy_configuration,
            }

        if self.source == "apify_2gis":
            return {
                "query": [query_text],
                "city": location_text,
                "maxItems": limit,
                "proxyConfiguration": proxy_configuration,
            }

        # fRSgBvgbsRB4o7t30 (zen-studio/yandex-maps-scraper) concrete input schema.
        return {
            "query": [query_text],
            "location": location_text,
            "category": "",
            "maxResults": limit,
            "language": "ru",
            "enrichBusinessData": False,
            "maxPhotos": 0,
            "maxPosts": 0,
            "startUrls": [],
            "businessIds": [],
            "coordinates": "",
            "viewportSpan": "",
            "filterRating": "",
            "filterOpenNow": False,
            "filterOpen24h": False,
            "filterDelivery": False,
            "filterTakeaway": False,
            "filterWifi": False,
            "filterCardPayment": False,
            "filterParking": False,
            "filterPetFriendly": False,
            "filterWheelchairAccess": False,
            "filterGoodPlace": False,
            "filterMichelin": False,
            "filterBusinessLunch": False,
            "filterSummerTerrace": False,
            "filterCuisine": [],
            "filterPriceCategory": [],
            "filterPriceMin": None,
            "filterPriceMax": None,
            "filterCategoryId": [],
            "filterChainId": [],
            "customFilters": [],
            "sortBy": "",
            "sortOrigin": "",
            "proxyConfiguration": proxy_configuration,
        }

    @staticmethod
    def _extract_map_business_id(map_url: str, source: str) -> Optional[str]:
        value = str(map_url or "").strip()
        if not value:
            return None
        if source == "apify_2gis":
            match = re.search(r"/firm/(\d+)", value)
            if match:
                return match.group(1)
            return None
        match = re.search(r"/org/(?:[^/?]+/)?(\d+)", value)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_google_place_id(map_url: str) -> Optional[str]:
        value = str(map_url or "").strip()
        if not value:
            return None
        patterns = [
            r"cid=(\d+)",
            r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, value, flags=re.IGNORECASE)
            if match:
                return str(match.group(1)).strip()
        return None

    @staticmethod
    def _extract_query_from_map_url(map_url: str) -> str:
        value = str(map_url or "").strip()
        if not value:
            return ""
        try:
            parsed = urlparse(value)
            params = parse_qs(parsed.query)
            for key in ("q", "query"):
                values = params.get(key) or []
                if values:
                    text = str(values[0]).replace("+", " ").strip()
                    if text:
                        return text
        except Exception:
            pass
        match = re.search(r"/org/([^/?#]+)/", value)
        if match:
            slug = str(match.group(1)).replace("_", " ").replace("-", " ").strip()
            if slug:
                return slug
        match = re.search(r"/place/([^/?#]+)", value)
        if match:
            slug = str(match.group(1)).replace("+", " ").replace("%20", " ").strip()
            if slug:
                return slug
        return ""

    @staticmethod
    def _extract_2gis_city_hint(map_url: str) -> str:
        value = str(map_url or "").strip()
        if not value:
            return ""
        match = re.search(r"https?://2gis\\.ru/([^/]+)/", value)
        slug = str(match.group(1) if match else "").strip().lower()
        city_map = {
            "spb": "Санкт-Петербург",
            "saint_petersburg": "Санкт-Петербург",
            "moscow": "Москва",
            "kazan": "Казань",
            "novosibirsk": "Новосибирск",
            "ekaterinburg": "Екатеринбург",
        }
        return city_map.get(slug, "")

    def _build_run_input_for_map_url(self, map_url: str, limit: int = 1, city: str = "") -> Dict[str, Any]:
        map_url_text = str(map_url or "").strip()
        if not map_url_text:
            raise ValueError("map_url is required")
        proxy_configuration = self._apify_actor_proxy_config()

        if self.source == "apify_google":
            place_id = self._extract_google_place_id(map_url_text)
            query_text = self._extract_query_from_map_url(map_url_text) or map_url_text
            payload = {
                "search_term": query_text,
                "location": str(city or "").strip(),
                "language": str(os.environ.get("APIFY_GOOGLE_LANGUAGE", "English") or "English"),
                "max_results": max(1, int(limit or 1)),
                "reviews": 30,
                "photos": 20,
                "startUrls": [map_url_text],
            }
            if place_id:
                payload["placeIds"] = [place_id]
            return payload

        if self.source == "apify_apple":
            query_text = self._extract_query_from_map_url(map_url_text)
            city_text = str(city or "").strip()
            search_queries = []
            if query_text:
                search_queries.append({"query": query_text, "location": city_text})
            payload = {
                "searchQueries": search_queries or [{"query": map_url_text, "location": city_text}],
                "placeUrls": [map_url_text],
                "searchUrls": [map_url_text],
                "maxResults": max(1, int(limit or 1)),
                "countryCode": str(os.environ.get("APIFY_APPLE_COUNTRY_CODE", "RU") or "RU"),
                "language": str(os.environ.get("APIFY_APPLE_LANGUAGE", "ru-RU") or "ru-RU"),
                "proxyConfiguration": proxy_configuration,
            }
            return payload

        if self.source == "apify_2gis":
            city_text = str(city or "").strip() or self._extract_2gis_city_hint(map_url_text)
            return {
                "query": [map_url_text],
                "city": city_text,
                "maxItems": max(1, int(limit or 1)),
                "proxyConfiguration": proxy_configuration,
            }

        # Minimal input for map-url runs to avoid actor schema mismatch (400).
        return {
            "startUrls": [{"url": map_url_text}],
            "maxItems": max(1, int(limit or 1)),
            "language": "ru",
            "proxyConfiguration": proxy_configuration,
        }

    def _apify_request(self, method: str, url: str, **kwargs: Any) -> Response:
        # Split proxy policy:
        # - Apify API calls are always direct from LocalOS infra.
        # - Proxying/rotation for target sites is handled inside Apify actor via proxyConfiguration.
        return requests.request(method=method, url=url, **kwargs)

    def start_search_run(self, query: str, location: str, limit: int = 50) -> Dict[str, Any]:
        if not self.api_token:
            raise ValueError("APIFY_TOKEN is not set")

        run_input = self._build_run_input(query, location, limit)
        return self._start_run_with_input(self._strip_none_values(run_input))

    def _start_run_with_input(self, run_input: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_token:
            raise ValueError("APIFY_TOKEN is not set")

        # Use raw REST start instead of apify_client.start() because the client
        # library uses a shorter default HTTP timeout and can still block before
        # returning a run id on slow API responses.
        actor_path_id = self._actor_path_id()
        if not actor_path_id:
            raise ValueError("APIFY actor id is not set")
        last_exc = None
        response = None
        for timeout_seconds in (30, 120):
            try:
                response = self._apify_request(
                    "POST",
                    f"https://api.apify.com/v2/acts/{actor_path_id}/runs",
                    params={"token": self.api_token, "waitForFinish": 0},
                    json=run_input,
                    timeout=timeout_seconds,
                )
                break
            except requests.exceptions.Timeout as exc:
                last_exc = exc
        if response is None:
            if last_exc:
                raise last_exc
            raise RuntimeError("Apify run start request failed without response")
        if response.status_code >= 400:
            try:
                print(
                    f"❌ Apify start error status={response.status_code} body={response.text}",
                    flush=True,
                )
            except Exception:
                pass
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

    def run_business_by_map_url(
        self,
        map_url: str,
        *,
        limit: int = 1,
        timeout_sec: int = 300,
        city: str = "",
    ) -> Dict[str, Any]:
        run_input = self._build_run_input_for_map_url(map_url, limit=limit, city=city)
        run_input_candidates = [self._strip_none_values(run_input)]
        if self.source == "apify_google":
            run_input_candidates.append(
                self._strip_none_values(
                    {
                        "search_term": self._extract_query_from_map_url(map_url) or str(map_url or "").strip(),
                        "location": str(city or "").strip(),
                        "language": str(os.environ.get("APIFY_GOOGLE_LANGUAGE", "English") or "English"),
                        "max_results": max(1, int(limit or 1)),
                        "reviews": 30,
                        "photos": 20,
                    }
                )
            )
        elif self.source == "apify_apple":
            run_input_candidates.append(
                self._strip_none_values(
                    {
                        "searchQueries": [
                            {
                                "query": self._extract_query_from_map_url(map_url) or str(map_url or "").strip(),
                                "location": str(city or "").strip(),
                            }
                        ],
                        "maxResults": max(1, int(limit or 1)),
                        "countryCode": str(os.environ.get("APIFY_APPLE_COUNTRY_CODE", "RU") or "RU"),
                        "language": str(os.environ.get("APIFY_APPLE_LANGUAGE", "ru-RU") or "ru-RU"),
                    }
                )
            )

        run_meta: Dict[str, Any] = {}
        last_error: Optional[Exception] = None
        for candidate in run_input_candidates:
            if not candidate:
                continue
            try:
                run_meta = self._start_run_with_input(candidate)
                run_input = candidate
                break
            except requests.exceptions.HTTPError as exc:
                response = getattr(exc, "response", None)
                if response is not None and int(response.status_code or 0) == 400:
                    last_error = exc
                    continue
                raise
            except Exception as exc:
                last_error = exc
                break
        if not run_meta:
            if last_error:
                raise last_error
            raise RuntimeError("Apify run did not start")
        run_id = str(run_meta.get("run_id") or "").strip()
        if not run_id:
            raise RuntimeError("Apify run did not start")

        started_at = datetime.datetime.utcnow()
        final_status = str(run_meta.get("status") or "").strip().upper() or "RUNNING"
        dataset_id = str(run_meta.get("dataset_id") or "").strip()

        while final_status in {"READY", "RUNNING", "TIMING-OUT", "ABORTING"}:
            elapsed = (datetime.datetime.utcnow() - started_at).total_seconds()
            if elapsed > max(30, int(timeout_sec or 300)):
                raise TimeoutError(f"Apify actor did not finish within {int(timeout_sec or 300)} seconds")
            time.sleep(4)
            run_data = self.get_run(run_id)
            final_status = str(run_data.get("status") or "").strip().upper() or final_status
            dataset_id = str(run_data.get("defaultDatasetId") or dataset_id or "").strip()

        if final_status != "SUCCEEDED":
            raise RuntimeError(f"Apify run finished with status={final_status}")

        items = self.fetch_dataset_items(dataset_id)
        return {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "status": final_status,
            "items": items,
            "run_input": run_input,
        }

    def run_search(
        self,
        query: str,
        location: str,
        *,
        limit: int = 50,
        timeout_sec: int = 300,
    ) -> Dict[str, Any]:
        run_meta = self.start_search_run(query, location, limit)
        run_id = str(run_meta.get("run_id") or "").strip()
        if not run_id:
            raise RuntimeError("Apify search run did not start")

        started_at = datetime.datetime.utcnow()
        final_status = str(run_meta.get("status") or "").strip().upper() or "RUNNING"
        dataset_id = str(run_meta.get("dataset_id") or "").strip()

        while final_status in {"READY", "RUNNING", "TIMING-OUT", "ABORTING"}:
            elapsed = (datetime.datetime.utcnow() - started_at).total_seconds()
            if elapsed > max(30, int(timeout_sec or 300)):
                raise TimeoutError(f"Apify search did not finish within {int(timeout_sec or 300)} seconds")
            time.sleep(4)
            run_data = self.get_run(run_id)
            final_status = str(run_data.get("status") or "").strip().upper() or final_status
            dataset_id = str(run_data.get("defaultDatasetId") or dataset_id or "").strip()

        if final_status != "SUCCEEDED":
            raise RuntimeError(f"Apify run finished with status={final_status}")

        items = self.fetch_dataset_items(dataset_id)
        return {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "status": final_status,
            "items": items,
            "run_input": run_meta.get("run_input") or {},
        }

    def get_run(self, run_id: str) -> Dict[str, Any]:
        if not self.api_token:
            raise ValueError("APIFY_TOKEN is not set")
        response = self._apify_request(
            "GET",
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            params={"token": self.api_token},
            timeout=45,
        )
        response.raise_for_status()
        return response.json().get("data") or {}

    def fetch_dataset_items(self, dataset_id: str) -> List[Dict[str, Any]]:
        if not self.api_token:
            raise ValueError("APIFY_TOKEN is not set")
        if not dataset_id:
            return []
        response = self._apify_request(
            "GET",
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={"token": self.api_token, "format": "json", "clean": "1"},
            timeout=90,
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
