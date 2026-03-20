import json
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from playwright.sync_api import sync_playwright


_IMAGE_EXT_PATTERN = re.compile(r"\.(jpg|jpeg|png|webp)(\?|$)", re.IGNORECASE)
_LD_JSON_PATTERN = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_META_CONTENT_PATTERN_TEMPLATE = r'<meta[^>]+property=["\']{property_name}["\'][^>]+content=["\'](.*?)["\']'


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        text = str(value).strip().replace(",", ".")
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        digits = re.sub(r"[^\d]", "", text)
        if not digits:
            return None
        return int(digits)
    except Exception:
        return None


def _normalize_url(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_domain(url: str) -> bool:
    value = (url or "").lower()
    return "2gis." in value


def _extract_firm_id(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    match = re.search(r"/firm/(\d+)", text)
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _candidate_2gis_urls(url: str) -> List[str]:
    raw = str(url or "").strip()
    out: List[str] = []
    if raw:
        out.append(raw)
    firm_id = _extract_firm_id(raw)
    if firm_id:
        out.extend(
            [
                f"https://2gis.ru/firm/{firm_id}",
                f"https://2gis.ru/spb/firm/{firm_id}",
                f"https://2gis.com/spb/firm/{firm_id}",
            ]
        )
    return _unique_preserve_order(out)


def _unique_preserve_order(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        normalized = _normalize_url(value)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _extract_json_ld_objects(raw_items: List[str]) -> List[Dict[str, Any]]:
    objects: List[Dict[str, Any]] = []
    for raw in raw_items:
        text = (raw or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    objects.append(item)
            continue
        if isinstance(payload, dict):
            if isinstance(payload.get("@graph"), list):
                for item in payload.get("@graph") or []:
                    if isinstance(item, dict):
                        objects.append(item)
            objects.append(payload)
    return objects


def _pick_local_business_schema(json_ld_objects: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for item in json_ld_objects:
        item_type = item.get("@type")
        if isinstance(item_type, list):
            item_types = [str(x).lower() for x in item_type]
        else:
            item_types = [str(item_type).lower()] if item_type else []
        if any("localbusiness" in value for value in item_types):
            return item
        if any("organization" in value for value in item_types):
            return item
    return None


def _extract_reviews_from_payloads(payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    reviews: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node):
                text_fields = 0
                for item in node:
                    if item.get("text") or item.get("review_text") or item.get("comment"):
                        text_fields += 1
                if text_fields >= 2:
                    for item in node:
                        text = str(
                            item.get("text")
                            or item.get("review_text")
                            or item.get("comment")
                            or ""
                        ).strip()
                        if not text:
                            continue
                        review: Dict[str, Any] = {
                            "id": item.get("id") or item.get("review_id"),
                            "author": item.get("author_name") or item.get("author") or item.get("user_name"),
                            "text": text,
                            "score": _safe_int(item.get("rating") or item.get("stars")),
                            "date": item.get("date") or item.get("created_at") or item.get("published_at"),
                            "org_reply": item.get("reply_text") or item.get("owner_reply"),
                        }
                        reviews.append(review)
            for item in node:
                walk(item)
            return

        if isinstance(node, dict):
            for value in node.values():
                walk(value)

    for payload in payloads:
        walk(payload)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for review in reviews:
        key = (
            str(review.get("author") or "").strip().lower(),
            str(review.get("text") or "").strip().lower(),
        )
        if not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(review)
    return deduped[:120]


def _extract_products_from_payloads(payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Tuple[str, Dict[str, Any]]] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node):
                for item in node:
                    name = str(item.get("name") or item.get("title") or "").strip()
                    if not name:
                        continue
                    lower_name = name.lower()
                    if "отзыв" in lower_name or "review" in lower_name or "новост" in lower_name:
                        continue
                    if len(name) > 180:
                        continue
                    description = str(item.get("description") or item.get("subtitle") or "").strip()
                    if len(description) > 1200:
                        description = description[:1200].rstrip()
                    price_text = (
                        item.get("price")
                        or item.get("price_text")
                        or item.get("cost")
                        or item.get("value")
                    )
                    category = (
                        item.get("category")
                        or item.get("group")
                        or item.get("rubric")
                        or "Общие услуги"
                    )
                    candidate = {
                        "name": name,
                        "description": description,
                        "price": str(price_text).strip() if price_text is not None else "",
                        "category": str(category).strip() or "Общие услуги",
                    }
                    candidates.append((path, candidate))
            for item in node:
                walk(item, path)
            return
        if isinstance(node, dict):
            for key, value in node.items():
                child_path = f"{path}.{key}" if path else str(key)
                walk(value, child_path)

    for payload in payloads:
        walk(payload)

    items: List[Dict[str, Any]] = []
    seen = set()
    for path, candidate in candidates:
        path_lower = path.lower()
        if not any(token in path_lower for token in ("service", "product", "price", "menu", "catalog", "offer")):
            continue
        key = (
            candidate["name"].lower(),
            candidate["category"].lower(),
            candidate["price"],
        )
        if key in seen:
            continue
        seen.add(key)
        items.append(candidate)
    items = items[:250]

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        category = item.get("category") or "Общие услуги"
        grouped.setdefault(category, []).append(item)
    return [{"category": category, "items": rows} for category, rows in grouped.items() if rows]


def _extract_news_from_payloads(payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node):
                for item in node:
                    title = str(item.get("title") or item.get("name") or "").strip()
                    text = str(item.get("text") or item.get("description") or "").strip()
                    date_value = item.get("date") or item.get("published_at") or item.get("created_at")
                    if not title and not text:
                        continue
                    if len(title) > 220:
                        continue
                    if len(text) > 3000:
                        text = text[:3000].rstrip()
                    path_lower = path.lower()
                    if not any(token in path_lower for token in ("news", "post", "publication", "feed", "event")):
                        continue
                    items.append(
                        {
                            "title": title or "Новость",
                            "text": text or title,
                            "date": str(date_value).strip() if date_value else None,
                            "photos": [],
                        }
                    )
            for item in node:
                walk(item, path)
            return
        if isinstance(node, dict):
            for key, value in node.items():
                child_path = f"{path}.{key}" if path else str(key)
                walk(value, child_path)

    for payload in payloads:
        walk(payload)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        key = (
            str(item.get("title") or "").strip().lower(),
            str(item.get("text") or "").strip().lower(),
        )
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:60]


def _extract_photos(dom_images: List[str], payloads: List[Dict[str, Any]]) -> List[str]:
    urls: List[str] = []
    for image_url in dom_images:
        value = _normalize_url(image_url)
        if _IMAGE_EXT_PATTERN.search(value):
            urls.append(value)

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if isinstance(node, dict):
            for key, value in node.items():
                key_lower = str(key).lower()
                if key_lower in ("url", "image", "image_url", "photo", "preview_url", "src"):
                    text = _normalize_url(value)
                    if _IMAGE_EXT_PATTERN.search(text):
                        urls.append(text)
                walk(value)

    for payload in payloads:
        walk(payload)
    return _unique_preserve_order(urls)[:120]


def _extract_categories(schema_obj: Optional[Dict[str, Any]], payloads: List[Dict[str, Any]], dom_categories: List[str]) -> List[str]:
    categories: List[str] = []
    for value in dom_categories:
        normalized = str(value).strip()
        if normalized:
            categories.append(normalized)

    if schema_obj:
        schema_type = schema_obj.get("@type")
        if isinstance(schema_type, list):
            for item in schema_type:
                text = str(item).strip()
                if text and text.lower() not in ("localbusiness", "organization"):
                    categories.append(text)
        elif schema_type:
            text = str(schema_type).strip()
            if text and text.lower() not in ("localbusiness", "organization"):
                categories.append(text)

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, path)
            return
        if isinstance(node, dict):
            for key, value in node.items():
                child_path = f"{path}.{key}" if path else str(key)
                key_lower = str(key).lower()
                if key_lower in ("rubric", "category", "categories", "type", "kind"):
                    if isinstance(value, str):
                        text = value.strip()
                        if text and len(text) <= 80:
                            categories.append(text)
                    elif isinstance(value, dict):
                        for nested_key in ("name", "title", "label"):
                            nested_text = str(value.get(nested_key) or "").strip()
                            if nested_text and len(nested_text) <= 80:
                                categories.append(nested_text)
                walk(value, child_path)

    for payload in payloads:
        walk(payload)
    return _unique_preserve_order(categories)[:20]


def _extract_meta_content(html: str, property_name: str) -> str:
    pattern = _META_CONTENT_PATTERN_TEMPLATE.format(property_name=re.escape(property_name))
    match = re.search(pattern, html or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _looks_like_captcha_text(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    markers = [
        "captcha",
        "2gis captcha",
        "вы не робот",
        "подтвердите, что вы не робот",
        "подтвердите что вы не робот",
    ]
    for marker in markers:
        if marker in text:
            return True
    return False


def _parse_2gis_http_fallback(urls: List[str], timeout_sec: int) -> Dict[str, Any]:
    timeout = max(20, int(timeout_sec or 120))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    last_error = ""

    for target_url in urls:
        try:
            response = requests.get(
                target_url,
                headers=headers,
                timeout=timeout,
                verify=False,
                allow_redirects=True,
            )
            if response.status_code >= 400:
                last_error = f"http_status={response.status_code}"
                continue
            html = response.text or ""
            if not html:
                last_error = "empty_html"
                continue

            ld_json_raw_items = _LD_JSON_PATTERN.findall(html)
            schema_objects = _extract_json_ld_objects(ld_json_raw_items)
            schema = _pick_local_business_schema(schema_objects)

            title = _extract_meta_content(html, "og:title")
            if not title and schema:
                title = str(schema.get("name") or "").strip()
            if _looks_like_captcha_text(title):
                last_error = "captcha_page_detected"
                continue
            address = ""
            if schema:
                schema_address = schema.get("address")
                if isinstance(schema_address, dict):
                    address = str(schema_address.get("streetAddress") or "").strip()
                elif schema_address:
                    address = str(schema_address).strip()
            if not address:
                address = _extract_meta_content(html, "business:contact_data:street_address")
            if not address and title:
                # Формат og:title обычно:
                # "<name>, <type>, <address> — 2ГИС"
                normalized_title = title.replace("— 2ГИС", "").replace("— 2GIS", "").strip()
                title_parts = [part.strip() for part in normalized_title.split(",") if part.strip()]
                if len(title_parts) >= 3:
                    address = ", ".join(title_parts[2:]).strip()

            rating = None
            reviews_count = None
            if schema and isinstance(schema.get("aggregateRating"), dict):
                agg = schema.get("aggregateRating") or {}
                rating = _safe_float(agg.get("ratingValue"))
                reviews_count = _safe_int(agg.get("reviewCount"))

            categories = _extract_categories(schema, [], [])
            if not title and not address and rating is None and not categories:
                last_error = "no_usable_fields_from_html"
                continue

            return {
                "source": "2gis",
                "url": str(response.url or target_url).strip(),
                "title": title,
                "title_or_name": title,
                "name": title,
                "address": address,
                "phone": str(schema.get("telephone") or "").strip() if schema else "",
                "site": str(schema.get("url") or "").strip() if schema else "",
                "rating": rating if rating is not None else 0.0,
                "reviews_count": reviews_count if reviews_count is not None else 0,
                "categories": categories,
                "products": [],
                "news": [],
                "reviews": [],
                "photos": [],
                "overview": {
                    "rating": rating if rating is not None else 0.0,
                    "reviews_count": reviews_count if reviews_count is not None else 0,
                    "photos_count": 0,
                    "news_count": 0,
                    "title": title,
                },
            }
        except Exception as exc:
            last_error = str(exc)
            continue

    return {"error": "2gis_http_fallback_failed", "message": last_error or "unknown_http_fallback_error"}


def parse_2gis_card(url: str, timeout_sec: int = 120, headless: bool = True, proxy: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    if not url:
        return {"error": "empty_url"}
    if not _extract_domain(url):
        return {"error": "unsupported_2gis_url", "url": url}

    payloads: List[Dict[str, Any]] = []
    dom_snapshot: Dict[str, Any] = {}
    final_url = url
    timeout_ms = max(30, int(timeout_sec)) * 1000

    candidate_urls = _candidate_2gis_urls(url)

    http_prefetch = _parse_2gis_http_fallback(candidate_urls, timeout_sec=timeout_sec)
    if not http_prefetch.get("error"):
        return http_prefetch

    try:
        with sync_playwright() as playwright:
            launch_kwargs: Dict[str, Any] = {
                "headless": bool(headless),
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            }
            if proxy and proxy.get("server"):
                launch_kwargs["proxy"] = proxy

            browser = playwright.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                ignore_https_errors=True,
            )
            page = context.new_page()

            def on_response(response) -> None:
                content_type = str(response.headers.get("content-type") or "").lower()
                if "application/json" not in content_type:
                    return
                response_url = str(response.url or "")
                if "2gis" not in response_url and "/api/" not in response_url:
                    return
                try:
                    raw_text = response.text()
                    if not raw_text or len(raw_text) > 2_500_000:
                        return
                    data = json.loads(raw_text)
                    if isinstance(data, dict):
                        payloads.append(data)
                except Exception:
                    return

            page.on("response", on_response)

            nav_success = False
            last_nav_error = ""
            for target_url in candidate_urls:
                try:
                    page.goto(target_url, wait_until="commit", timeout=timeout_ms)
                    page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 45000))
                    try:
                        page.wait_for_load_state("networkidle", timeout=12000)
                    except Exception:
                        pass
                    page.wait_for_timeout(1800)
                    final_url = page.url or target_url
                    nav_success = True
                    break
                except Exception as nav_exc:
                    last_nav_error = str(nav_exc)
                    continue

            if not nav_success:
                context.close()
                browser.close()
                http_result = _parse_2gis_http_fallback(candidate_urls, timeout_sec=timeout_sec)
                if not http_result.get("error"):
                    return http_result
                return {
                    "error": "2gis_parse_failed",
                    "message": f"playwright_nav_failed: {last_nav_error or 'unknown'}",
                    "url": url,
                }

            dom_snapshot = page.evaluate(
                """
                () => {
                  const text = (selector) => {
                    const el = document.querySelector(selector);
                    return el ? (el.textContent || '').trim() : '';
                  };
                  const allText = (selector) => {
                    return Array.from(document.querySelectorAll(selector))
                      .map((el) => (el.textContent || '').trim())
                      .filter(Boolean);
                  };
                  const links = Array.from(document.querySelectorAll('a[href]'))
                    .map((el) => String(el.getAttribute('href') || '').trim())
                    .filter(Boolean);
                  const phones = allText('a[href^="tel:"], [data-testid*="phone"], [class*="phone"]');
                  const imageUrls = Array.from(document.querySelectorAll('img[src]'))
                    .map((el) => String(el.getAttribute('src') || '').trim())
                    .filter(Boolean);
                  const ldJson = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
                    .map((el) => (el.textContent || '').trim())
                    .filter(Boolean);
                  return {
                    title: text('h1'),
                    pageTitle: document.title || '',
                    address: text('[class*="address"], [data-testid*="address"]'),
                    ratingText: text('[class*="rating"], [data-testid*="rating"]'),
                    reviewsCountText: text('[class*="reviews"], [data-testid*="review"]'),
                    siteLink: links.find((url) => /^https?:\\/\\//i.test(url) && !url.includes('2gis')) || '',
                    phoneText: phones[0] || '',
                    hoursText: text('[class*="work"], [class*="schedule"], [data-testid*="schedule"]'),
                    categoryTexts: allText('[class*="rubric"], [class*="category"], [data-testid*="rubric"]'),
                    imageUrls,
                    ldJson,
                  };
                }
                """
            )

            context.close()
            browser.close()
    except Exception as exc:
        http_result = _parse_2gis_http_fallback(candidate_urls, timeout_sec=timeout_sec)
        if not http_result.get("error"):
            return http_result
        return {"error": "2gis_parse_failed", "message": str(exc), "url": url}

    schema_objects = _extract_json_ld_objects(dom_snapshot.get("ldJson") or [])
    local_business_schema = _pick_local_business_schema(schema_objects)

    title = str(dom_snapshot.get("title") or "").strip()
    if not title and local_business_schema:
        title = str(local_business_schema.get("name") or "").strip()
    if not title:
        title = str(dom_snapshot.get("pageTitle") or "").replace(" — 2ГИС", "").strip()

    address = str(dom_snapshot.get("address") or "").strip()
    if not address and local_business_schema:
        if isinstance(local_business_schema.get("address"), dict):
            address = str(local_business_schema.get("address", {}).get("streetAddress") or "").strip()
        elif local_business_schema.get("address"):
            address = str(local_business_schema.get("address") or "").strip()

    site = str(dom_snapshot.get("siteLink") or "").strip()
    if not site and local_business_schema:
        site = str(local_business_schema.get("url") or "").strip()
        if site and "2gis." in site.lower():
            site = ""

    phone = str(dom_snapshot.get("phoneText") or "").strip()
    if not phone and local_business_schema:
        phone = str(local_business_schema.get("telephone") or "").strip()

    rating = None
    reviews_count = None
    if local_business_schema and isinstance(local_business_schema.get("aggregateRating"), dict):
        agg = local_business_schema.get("aggregateRating") or {}
        rating = _safe_float(agg.get("ratingValue"))
        reviews_count = _safe_int(agg.get("reviewCount"))
    if rating is None:
        rating = _safe_float(dom_snapshot.get("ratingText"))
    if reviews_count is None:
        reviews_count = _safe_int(dom_snapshot.get("reviewsCountText"))

    products = _extract_products_from_payloads(payloads)
    news = _extract_news_from_payloads(payloads)
    reviews = _extract_reviews_from_payloads(payloads)
    photos = _extract_photos(dom_snapshot.get("imageUrls") or [], payloads)
    categories = _extract_categories(local_business_schema, payloads, dom_snapshot.get("categoryTexts") or [])

    if reviews_count is None:
        reviews_count = len(reviews)
    if rating is None:
        rating = 0.0

    if _looks_like_captcha_text(title):
        return {"error": "captcha_detected", "message": "2gis_captcha_detected", "url": final_url}

    overview = {
        "rating": rating,
        "reviews_count": reviews_count,
        "photos_count": len(photos),
        "news_count": len(news),
        "title": title,
    }

    return {
        "source": "2gis",
        "url": final_url,
        "title": title,
        "title_or_name": title,
        "name": title,
        "address": address,
        "phone": phone,
        "site": site,
        "rating": rating,
        "reviews_count": reviews_count,
        "categories": categories,
        "overview": overview,
        "products": products,
        "news": news,
        "photos": photos,
        "features_full": {},
        "competitors": [],
        "hours": str(dom_snapshot.get("hoursText") or "").strip(),
        "hours_full": [],
        "reviews": reviews,
    }
