import os
from decimal import Decimal
import requests
import urllib3
from urllib.parse import quote
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
        if normalized_source not in {"apify_yandex", "apify_2gis"}:
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
        source_actor = twogis_actor if self.source == "apify_2gis" else yandex_actor
        self.actor_id = str(actor_id_override or source_actor or "").strip()
        if not APIFY_AVAILABLE:
            print("Warning: apify_client not available. Prospecting service disabled.")
            self.client = None
        elif not self.api_token:
            print("Warning: APIFY_TOKEN is not set. Prospecting service will not work.")
            self.client = None
        else:
            self.client = ApifyClient(self.api_token)
        self._apify_proxy_strict = str(os.environ.get("APIFY_PROXY_STRICT", "") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._apify_proxy_insecure = str(os.environ.get("APIFY_PROXY_INSECURE", "true") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

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

    @classmethod
    def _extract_photos(cls, item: Dict[str, Any], limit: int = 20) -> List[str]:
        raw_photos = item.get("photos")
        photos: List[str] = []
        if isinstance(raw_photos, list):
            for entry in raw_photos:
                if isinstance(entry, str):
                    value = entry.strip()
                    if value:
                        photos.append(value)
                elif isinstance(entry, dict):
                    for key in ("url", "imageUrl", "src", "originalUrl"):
                        candidate = cls._coerce_scalar_text(entry.get(key))
                        if candidate:
                            photos.append(candidate)
                            break
        main_photo = cls._coerce_scalar_text(item.get("photoUrlTemplate"))
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
        proxy_groups_raw = str(os.environ.get("APIFY_PROXY_GROUPS", "RESIDENTIAL") or "").strip()
        proxy_groups = [grp.strip() for grp in proxy_groups_raw.split(",") if grp.strip()]
        if not proxy_groups:
            proxy_groups = ["RESIDENTIAL"]

        if self.source == "apify_2gis":
            return {
                "query": query_text,
                "city": location_text,
                "maxItems": limit,
                "proxyConfiguration": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": proxy_groups,
                },
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
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": proxy_groups,
            },
        }

    def _load_proxy_from_db(self) -> Optional[Dict[str, Any]]:
        """
        Pick one active/working proxy from ProxyServers for outgoing Apify API calls.
        Safe fallback: return None if DB/table is unavailable.
        """
        try:
            from database_manager import get_db_connection

            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT id, proxy_type, host, port, username, password
                    FROM proxyservers
                    WHERE is_active IS TRUE AND is_working IS TRUE
                    ORDER BY last_used_at ASC NULLS FIRST, RANDOM()
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
                if not row:
                    return None

                if hasattr(row, "get"):
                    proxy_id = str(row.get("id") or "").strip()
                    proxy_type = str(row.get("proxy_type") or "http").strip().lower() or "http"
                    host = str(row.get("host") or "").strip()
                    port = row.get("port")
                    username = str(row.get("username") or "").strip()
                    password = str(row.get("password") or "").strip()
                else:
                    proxy_id, proxy_type, host, port, username, password = row
                    proxy_id = str(proxy_id or "").strip()
                    proxy_type = str(proxy_type or "http").strip().lower() or "http"
                    host = str(host or "").strip()
                    username = str(username or "").strip()
                    password = str(password or "").strip()

                if not host or not port:
                    return None

                cur.execute(
                    """
                    UPDATE proxyservers
                    SET last_used_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (proxy_id,),
                )
                conn.commit()

                scheme = proxy_type if proxy_type in {"http", "https", "socks5"} else "http"
                if username and password:
                    proxy_url = f"{scheme}://{username}:{password}@{host}:{port}"
                else:
                    proxy_url = f"{scheme}://{host}:{port}"
                return {"id": proxy_id, "url": proxy_url}
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
                conn.close()
        except Exception:
            return None

    def _resolve_apify_proxy(self) -> Dict[str, Any]:
        """
        Resolve proxy for Apify HTTP API calls.
        Priority:
        1) APIFY_PROXY_URL / APIFY_HTTP_PROXY / APIFY_HTTPS_PROXY
        2) ProxyServers table (active + working).
        """
        explicit_url = str(os.environ.get("APIFY_PROXY_URL", "") or "").strip()
        if explicit_url:
            return {"id": "env", "url": explicit_url}

        explicit_http = str(os.environ.get("APIFY_HTTP_PROXY", "") or "").strip()
        explicit_https = str(os.environ.get("APIFY_HTTPS_PROXY", "") or "").strip()
        if explicit_http or explicit_https:
            return {"id": "env", "http": explicit_http, "https": explicit_https}

        db_proxy = self._load_proxy_from_db()
        if db_proxy and db_proxy.get("url"):
            return {
                "id": db_proxy.get("id"),
                "http": db_proxy.get("url"),
                "https": db_proxy.get("url"),
            }
        return {}

    def _mark_apify_proxy_result(self, proxy_id: Optional[str], *, success: bool) -> None:
        if not proxy_id or proxy_id == "env":
            return
        try:
            from database_manager import get_db_connection

            conn = get_db_connection()
            cur = conn.cursor()
            try:
                if success:
                    cur.execute(
                        """
                        UPDATE proxyservers
                        SET success_count = COALESCE(success_count, 0) + 1,
                            is_working = TRUE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (proxy_id,),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE proxyservers
                        SET failure_count = COALESCE(failure_count, 0) + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (proxy_id,),
                    )
                conn.commit()
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
                conn.close()
        except Exception:
            return

    def _apify_request(self, method: str, url: str, **kwargs: Any) -> Response:
        proxy_payload = self._resolve_apify_proxy()
        proxy_id = str(proxy_payload.get("id") or "").strip() or None
        proxies = None
        if proxy_payload.get("http") or proxy_payload.get("https"):
            proxies = {
                "http": proxy_payload.get("http") or proxy_payload.get("https"),
                "https": proxy_payload.get("https") or proxy_payload.get("http"),
            }
            print(f"🌐 Apify API via proxy id={proxy_id}", flush=True)
            if self._apify_proxy_insecure and "verify" not in kwargs:
                # Some proxy providers MITM TLS; allow insecure verify only for proxied Apify calls.
                kwargs = dict(kwargs)
                kwargs["verify"] = False
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        try:
            response = requests.request(method=method, url=url, proxies=proxies, **kwargs)
            self._mark_apify_proxy_result(proxy_id, success=True)
            return response
        except requests.RequestException:
            self._mark_apify_proxy_result(proxy_id, success=False)
            if proxies and not self._apify_proxy_strict:
                print("⚠️ Apify proxy request failed, retrying direct", flush=True)
                return requests.request(method=method, url=url, **kwargs)
            raise

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
