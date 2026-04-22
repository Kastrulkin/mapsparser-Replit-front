import json
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from database_manager import DatabaseManager
from core.card_audit_policy import policy_value
from core.map_url_normalizer import normalize_map_url


CATEGORY_BASELINE_REVENUE = {
    "beauty": {"min": 150000.0, "max": 500000.0},
    "beauty salon": {"min": 150000.0, "max": 500000.0},
    "salon": {"min": 150000.0, "max": 500000.0},
    "салон красоты": {"min": 150000.0, "max": 500000.0},
    "салон": {"min": 150000.0, "max": 500000.0},
    "fashion": 220000.0,
    "designer": 220000.0,
    "bridal": 260000.0,
    "barbershop": {"min": 150000.0, "max": 400000.0},
    "барбершоп": {"min": 150000.0, "max": 400000.0},
    "nail": {"min": 100000.0, "max": 250000.0},
    "маникюр": {"min": 100000.0, "max": 250000.0},
    "ногти": {"min": 100000.0, "max": 250000.0},
    "cosmetology": {"min": 200000.0, "max": 800000.0},
    "косметология": {"min": 200000.0, "max": 800000.0},
    "косметолог": {"min": 200000.0, "max": 800000.0},
    "massage": 160000.0,
    "cafe": {"min": 300000.0, "max": 800000.0},
    "кафе": {"min": 300000.0, "max": 800000.0},
    "coffee": {"min": 150000.0, "max": 400000.0},
    "кофейня": {"min": 150000.0, "max": 400000.0},
    "restaurant": {"min": 500000.0, "max": 2000000.0},
    "ресторан": {"min": 500000.0, "max": 2000000.0},
    "school": {"min": 200000.0, "max": 800000.0},
    "education": {"min": 200000.0, "max": 800000.0},
    "школа": {"min": 200000.0, "max": 800000.0},
    "обучение": {"min": 200000.0, "max": 800000.0},
    "fitness": {"min": 300000.0, "max": 1500000.0},
    "gym": {"min": 300000.0, "max": 1500000.0},
    "фитнес": {"min": 300000.0, "max": 1500000.0},
    "зал": {"min": 300000.0, "max": 1500000.0},
    "medical": {"min": 400000.0, "max": 2000000.0},
    "clinic": {"min": 400000.0, "max": 2000000.0},
    "клиника": {"min": 400000.0, "max": 2000000.0},
    "медицин": {"min": 400000.0, "max": 2000000.0},
    "dental": {"min": 500000.0, "max": 3000000.0},
    "dentist": {"min": 500000.0, "max": 3000000.0},
    "стоматология": {"min": 500000.0, "max": 3000000.0},
    "стоматолог": {"min": 500000.0, "max": 3000000.0},
    "зуб": {"min": 500000.0, "max": 3000000.0},
    "auto": {"min": 300000.0, "max": 1000000.0},
    "авто": {"min": 300000.0, "max": 1000000.0},
    "repair": 200000.0,
}


def _normalize_baseline_range(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        min_value = float(value.get("min") or 0)
        max_value = float(value.get("max") or 0)
    else:
        min_value = float(value or 0)
        max_value = float(value or 0)
    if min_value <= 0 and max_value > 0:
        min_value = max_value
    if max_value <= 0 and min_value > 0:
        max_value = min_value
    if max_value < min_value:
        min_value, max_value = max_value, min_value
    midpoint = round((min_value + max_value) / 2) if max_value > 0 else 0
    return {
        "value": midpoint,
        "min": round(min_value),
        "max": round(max_value),
    }

YMAP_SOURCES = ("yandex_maps", "yandex_business_goods", "yandex_business_services")
EDITORIAL_SERVICE_PATTERNS = (
    "хорошее место",
    "где можно",
    "выбрали места",
    "рассказываем про",
    "собрали в одном месте",
    "подборка",
    "салоны красоты на ",
    "салоны красоты в ",
    "салоны красоты около ",
    "салоны красоты у ",
    "салоны красоты с наградой",
    "крафтовые бары",
    "бары для ",
    "бары, в которых ",
    "бары и пабы в ",
    "в районе ",
    "на улице ",
    "рядом с ",
    "музеи",
    "в петербурге",
    "на что обратить внимание",
    "лучшие ",
    "необычные ",
    "где есть ",
    "eat market",
    "день влюбл",
    "в галерее",
    "петергоф",
    "пушкинской карте",
)
REVIEW_PLACEHOLDER_PATTERNS = (
    "текст отзыва",
    "пример отзыва",
    "sample review",
    "demo review",
    "lorem ipsum",
)

SERVICE_EXCLUDED_CATEGORIES = {
    "payment_method",
    "promotions",
}

SERVICE_NOISE_TERMS = {
    "наличными",
    "сбп",
    "оплата картой",
    "qr-код",
    "онлайн",
    "банковским переводом",
    "предоплата",
    "акции",
    "скидки",
    "спецпредложения",
    "подарки",
    "бонусы",
}

SERVICE_POSITIVE_HINTS = (
    "абонемент",
    "тренировк",
    "пилатес",
    "реформер",
    "массаж",
    "лифтинг",
    "эпиля",
    "процедур",
    "консультац",
    "кавитац",
    "ванн",
    "detox",
    "детокс",
    "spa",
    "прессотерап",
    "биоэнерго",
    "rf-",
    "rf ",
)

HOSPITALITY_TYPE_HINTS = (
    "hotel",
    "resort",
    "apartment",
    "apart",
    "guest house",
    "villa",
    "holiday",
    "lodging",
    "inn",
    "spa resort",
)

BOOKING_OFFER_TERMS = (
    "booking.com",
    "agoda",
    "tui",
    "bluepillow",
    "wego",
    "expedia",
    "hotels.com",
    "trip.com",
    "tripadvisor",
    "compare prices",
    "сравнить цены",
    "варианты от партнеров",
    "варианты от партнёров",
    "официальный сайт",
)

HOSPITALITY_POSITIVE_THEMES = {
    "space": ("простор", "spacious", "large apartment", "big apartment", "big room", "big rooms"),
    "quiet": ("тихо", "спокой", "quiet", "peaceful"),
    "pool": ("бассейн", "pool"),
    "parking": ("парков", "parking"),
    "kitchen": ("кухн", "kitchen"),
    "clean": ("чист", "clean"),
    "airport": ("airport", "аэропорт"),
    "family": ("family", "семь", "дет"),
}

HOSPITALITY_NEGATIVE_THEMES = {
    "beach_distance": ("пляж", "beach", "первая линия", "first line", "walk to the beach", "to the beach"),
    "car_dependency": ("машин", "car", "without car", "без машины", "drive"),
    "aircraft_noise": ("самолет", "самол", "airplane", "plane", "airport noise"),
}

HOSPITALITY_INTENT_MODIFIERS = (
    (
        ("sultanahmet", "fatih", "old city", "historic center", "historical peninsula"),
        ("sultanahmet hotel", "hotel in old city", "hotel in fatih"),
    ),
    (
        ("hagia sophia", "ayasofya", "aya sofya"),
        ("hotel near hagia sophia",),
    ),
    (
        ("blue mosque", "sultan ahmet mosque", "sultanahmet mosque"),
        ("hotel near blue mosque",),
    ),
    (
        ("airport", "havaalan", "aeroport", "airport transfer"),
        ("hotel near airport", "airport transfer hotel"),
    ),
    (
        ("beach", "sea", "coast", "shore"),
        ("hotel near beach",),
    ),
)

AUDIT_PROFILE_HINTS = {
    "hospitality": HOSPITALITY_TYPE_HINTS,
    "medical": (
        "medical", "clinic", "doctor", "невролог", "гинек", "терап", "диагност", "медицин", "клиник", "стомат",
        "капельниц", "внутривен", "реабил", "узи", "мрт", "анализ", "приём", "прием", "кардиолог",
        "эндокрин", "травмат", "ортопед", "педиатр", "физиотерап", "процедур", "консультация врача",
    ),
    "beauty": (
        "beauty", "salon", "cosmetology", "barber", "nail", "lashes", "brows", "эпиля", "маник", "космет",
        "салон красоты", "парикмах", "ресниц", "бров", "окрашив", "укладк", "стрижк", "педик",
    ),
    "fashion": (
        "fashion",
        "designer",
        "bridal",
        "dress",
        "dresses",
        "couture",
        "stitching",
        "tailor",
        "tailoring",
        "boutique",
        "custom dress",
        "custom dresses",
        "bridal wear",
        "formal wear",
        "lehenga",
        "gown",
        "fashion designer",
        "bridal designer",
        "wedding dress",
        "clothing",
        "apparel",
        "модельер",
        "дизайнер одежды",
        "пошив",
        "ателье",
        "платье",
        "свадеб",
    ),
    "wellness": ("wellness", "massage", "spa", "detox", "реабил", "оздоров", "массаж", "relax"),
    "food": (
        "cafe", "coffee", "restaurant", "bar", "bakery", "кафе", "ресторан", "пицц", "кофе", "еда",
        "кебаб", "шаверм", "шаурм", "шашлык", "плов", "манты", "бургер", "суши", "ролл", "завтрак", "обед",
    ),
    "fitness": ("fitness", "gym", "pilates", "yoga", "crossfit", "фитнес", "спорт", "пилат", "йога", "тренаж"),
}

AUDIT_PROFILE_LABELS = {
    "default_local_business": "Локальный бизнес",
    "beauty": "Бьюти / сервисные услуги",
    "fashion": "Fashion / designer studio",
    "medical": "Медицина / клиника",
    "wellness": "Wellness / SPA / массаж",
    "food": "HoReCa / еда и напитки",
    "fitness": "Фитнес / студия",
    "hospitality": "Гостеприимство / размещение",
}

STRONG_MEDICAL_SERVICE_HINTS = (
    "узи",
    "мрт",
    "кт ",
    "кт-",
    "рентген",
    "внутривен",
    "капельниц",
    "прием врача",
    "приём врача",
    "консультация врача",
    "эндокрин",
    "кардиолог",
    "невролог",
    "гинеколог",
    "терапевт",
    "педиатр",
    "ортопед",
    "травмат",
)

MEDICAL_IDENTITY_HINTS = (
    "medical",
    "clinic",
    "doctor",
    "hospital",
    "медицин",
    "клиник",
    "врач",
    "доктор",
    "стомат",
    "невролог",
    "гинеколог",
    "кардиолог",
    "эндокрин",
    "терапевт",
    "педиатр",
    "ортопед",
    "травмат",
)


def _has_strong_external_id(value: Any) -> bool:
    raw = str(value or "").strip()
    if len(raw) < 6:
        return False
    if raw.isdigit() and len(raw) < 8:
        return False
    return True


def _safe_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None
    return None


def _to_dict(cursor, row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (f"public.{table_name}",))
    row = _to_dict(cursor, cursor.fetchone())
    return bool((row or {}).get("exists"))


def _extract_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = re.sub(r"[^\d.,-]", "", str(value or "")).replace(",", ".")
    if not raw:
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _extract_int(value: Any) -> int:
    numeric = _extract_numeric(value)
    if numeric is None:
        return 0
    try:
        return int(numeric)
    except Exception:
        return 0


def _normalize_media_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = f"https:{url}"
    if "{size}" in url:
        url = url.replace("{size}", "XXXL")
    if "/%s" in url:
        url = url.replace("/%s", "/XXXL")
    elif "%s" in url:
        url = url.replace("%s", "XXXL")
    return url


def _coerce_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _card_overview_dict(card: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(card, dict):
        return {}
    return _safe_json(card.get("overview")) or {}


def _card_snapshot_type(card: Optional[Dict[str, Any]]) -> str:
    overview = _card_overview_dict(card)
    return str(overview.get("snapshot_type") or "").strip().lower()


def _card_source_name(card: Optional[Dict[str, Any]]) -> str:
    overview = _card_overview_dict(card)
    meta = overview.get("_meta") if isinstance(overview, dict) else {}
    if isinstance(meta, dict):
        return str(meta.get("source") or "").strip().lower()
    return ""


def _card_list_size(value: Any) -> int:
    parsed = _safe_json(value)
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, dict):
        return len(parsed)
    return 0


def _normalize_identity_text(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-z0-9а-я]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _identity_similarity(left: Any, right: Any) -> float:
    left_text = _normalize_identity_text(left)
    right_text = _normalize_identity_text(right)
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _extract_google_place_id_from_url(url: Any) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    patterns = (
        r"cid=(\d+)",
        r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)",
        r"query_place_id=([^&]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return str(match.group(1) or "").strip()
    return ""


def _lead_matches_business_identity(
    lead: Dict[str, Any],
    business: Dict[str, Any],
    *,
    source_url: str,
    source_external_id: str,
) -> bool:
    expected_external_id = str(source_external_id or "").strip()
    business_external_id = str(business.get("yandex_org_id") or "").strip()
    if _has_strong_external_id(expected_external_id) and business_external_id and expected_external_id != business_external_id:
        return False

    lead_city = _normalize_identity_text(lead.get("city") or lead.get("address"))
    business_city = _normalize_identity_text(business.get("city"))
    if (
        lead_city
        and business_city
        and lead_city not in business_city
        and business_city not in lead_city
        and not (_has_strong_external_id(expected_external_id) and business_external_id)
    ):
        return False

    lead_name = str(lead.get("name") or "").strip()
    business_name = str(business.get("name") or "").strip()
    if lead_name and business_name and _identity_similarity(lead_name, business_name) < 0.42:
        return False

    normalized_source_url = normalize_map_url(source_url)
    normalized_business_url = normalize_map_url(str(business.get("yandex_url") or "").strip())
    if normalized_source_url and normalized_business_url and "yandex." in normalized_source_url and "yandex." in normalized_business_url:
        expected_org_id = _extract_yandex_org_id_from_url(normalized_source_url) or ""
        business_org_id = _extract_yandex_org_id_from_url(normalized_business_url) or ""
        if expected_org_id and business_org_id and expected_org_id != business_org_id:
            return False

    return True


BEAUTY_INTENT_MARKERS = (
    (("лазер", "epilation", "laser"), "лазерная эпиляция"),
    (("маник", "nail"), "маникюр"),
    (("педик",), "педикюр"),
    (("космет", "facial", "skin"), "косметология"),
    (("brow", "бров"), "оформление бровей"),
    (("lash", "ресниц"), "ресницы"),
    (("hair", "волос", "окраш", "стриж"), "волосы и окрашивание"),
    (("massage", "массаж"), "массаж"),
)


def _derive_beauty_focus_terms(service_names: List[str], overview_text: str, limit: int = 3) -> List[str]:
    haystack = " ".join([str(item or "") for item in service_names] + [str(overview_text or "")]).lower()
    found: List[str] = []
    for markers, label in BEAUTY_INTENT_MARKERS:
        if any(marker in haystack for marker in markers):
            found.append(label)
    if not found:
        return []
    return _dedupe_text_list(found, limit=limit)


def _card_has_metric_payload(card: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(card, dict):
        return False
    if _extract_numeric(card.get("rating")) is not None:
        return True
    if _extract_int(card.get("reviews_count") or 0) > 0:
        return True
    return False


def _card_richness_score(card: Optional[Dict[str, Any]]) -> int:
    if not isinstance(card, dict):
        return -1
    score = 0
    score += _card_list_size(card.get("products")) * 10
    score += _card_list_size(card.get("photos")) * 3
    score += _card_list_size(card.get("news")) * 2
    overview = _card_overview_dict(card)
    description = str((overview.get("description") if isinstance(overview, dict) else "") or "").strip()
    if description:
        score += 1
    source_name = _card_source_name(card)
    if source_name in {"yandex_business", "yandex_maps"}:
        score += 5
    return score


def _select_preferred_rich_card(cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    best_card: Dict[str, Any] = {}
    best_key = (-1, datetime.min.replace(tzinfo=timezone.utc))
    for card in cards:
        snapshot_type = _card_snapshot_type(card)
        if snapshot_type and snapshot_type != "full":
            continue
        score = _card_richness_score(card)
        created_at = _coerce_dt(card.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)
        key = (score, created_at)
        if key > best_key:
            best_card = card
            best_key = key
    return best_card


def _select_preferred_metrics_card(cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    best_card: Dict[str, Any] = {}
    best_key = (
        -1,
        -1,
        datetime.min.replace(tzinfo=timezone.utc),
    )
    for card in cards:
        if not _card_has_metric_payload(card):
            continue
        reviews_count = _extract_int(card.get("reviews_count") or 0)
        rating_value = _extract_numeric(card.get("rating"))
        rating_score = int(round((rating_value or 0) * 100))
        created_at = _coerce_dt(card.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)
        key = (reviews_count, rating_score, created_at)
        if key > best_key:
            best_card = card
            best_key = key
    return best_card


def _extract_yandex_org_id_from_url(url: Any) -> Optional[str]:
    text = str(url or "").strip()
    if not text:
        return None
    match = re.search(r"/org/(?:[^/]+/)?(\d+)", text)
    if match:
        return match.group(1)
    return None


def _extract_contact_links(value: Any) -> List[str]:
    links: List[str] = []

    def _walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            text = node.strip()
            if text:
                links.append(text)
            return
        if isinstance(node, dict):
            for item in node.values():
                _walk(item)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(value)
    deduped: List[str] = []
    seen = set()
    for item in links:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _extract_telegram_whatsapp_email_from_links(links: List[str]) -> Dict[str, Optional[str]]:
    telegram = None
    whatsapp = None
    email = None
    for raw in links:
        value = str(raw or "").strip()
        low = value.lower()
        if not telegram and ("t.me/" in low or "telegram.me/" in low):
            telegram = value
        if not whatsapp and ("wa.me/" in low or "whatsapp.com/" in low or "api.whatsapp.com/" in low):
            whatsapp = value
        if not email:
            if low.startswith("mailto:"):
                email = value.split(":", 1)[1].strip()
            elif "@" in value and " " not in value and "/" not in value:
                email = value
    return {"telegram_url": telegram, "whatsapp_url": whatsapp, "email": email}


def _is_editorial_service_entry(name: str, description: str | None) -> bool:
    combined = f"{name or ''} {description or ''}".strip().lower()
    if not combined:
        return False
    normalized_name = str(name or "").strip().lower()
    if normalized_name in SERVICE_NOISE_TERMS:
        return True
    if any(pattern in combined for pattern in EDITORIAL_SERVICE_PATTERNS):
        return True
    desc = (description or "").strip().lower()
    if desc.startswith("рассказываем") or desc.startswith("выбрали") or desc.startswith("собрали"):
        return True
    if any(hint in combined for hint in SERVICE_POSITIVE_HINTS):
        return False
    if ":" in (name or ""):
        return True
    if len((name or "").split()) >= 10 and not re.search(r"\d", str(name or "")):
        return True
    return False


def _is_placeholder_review_entry(text: str | None, response: str | None = None) -> bool:
    review_text = str(text or "").strip().lower()
    response_text = str(response or "").strip().lower()
    combined = f"{review_text} {response_text}".strip()
    if not combined:
        return True
    if any(pattern in combined for pattern in REVIEW_PLACEHOLDER_PATTERNS):
        return True
    if review_text in {"клиент", "отзыв", "review"}:
        return True
    return False


def _contains_any_term(text: str, terms: tuple[str, ...]) -> bool:
    haystack = str(text or "").strip().lower()
    if not haystack:
        return False
    return any(term in haystack for term in terms)


def _is_hospitality_business(business_type: Any, business_name: Any, overview: Any) -> bool:
    parts: List[str] = [
        str(business_type or "").strip().lower(),
        str(business_name or "").strip().lower(),
    ]
    if isinstance(overview, dict):
        parts.append(str(overview.get("category") or "").strip().lower())
        categories = overview.get("categories")
        if isinstance(categories, list):
            for item in categories:
                parts.append(str(item or "").strip().lower())
    combined = " ".join([item for item in parts if item]).strip()
    if not combined:
        return False
    return any(token in combined for token in HOSPITALITY_TYPE_HINTS)


def _is_booking_offer_service(name: str, description: Optional[str] = None, category: Optional[str] = None) -> bool:
    combined = " ".join(
        [
            str(name or "").strip().lower(),
            str(description or "").strip().lower(),
            str(category or "").strip().lower(),
        ]
    ).strip()
    if not combined:
        return False
    if any(term in combined for term in BOOKING_OFFER_TERMS):
        return True
    if "₽" in combined or "€" in combined or "$" in combined or "gel" in combined:
        if "booking" in combined or "официальный сайт" in combined:
            return True
    return False


def _extract_hospitality_review_signals(review_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    positives: Dict[str, int] = {key: 0 for key in HOSPITALITY_POSITIVE_THEMES.keys()}
    negatives: Dict[str, int] = {key: 0 for key in HOSPITALITY_NEGATIVE_THEMES.keys()}

    for row in review_rows:
        review_text = str(row.get("review_text") or "").strip().lower()
        if not review_text:
            continue
        for key, terms in HOSPITALITY_POSITIVE_THEMES.items():
            if _contains_any_term(review_text, terms):
                positives[key] += 1
        for key, terms in HOSPITALITY_NEGATIVE_THEMES.items():
            if _contains_any_term(review_text, terms):
                negatives[key] += 1

    top_positive = [key for key, count in sorted(positives.items(), key=lambda item: item[1], reverse=True) if count > 0][:4]
    top_negative = [key for key, count in sorted(negatives.items(), key=lambda item: item[1], reverse=True) if count > 0][:4]

    expectation_mismatch = "beach_distance" in top_negative or "car_dependency" in top_negative

    return {
        "top_positive": top_positive,
        "top_negative": top_negative,
        "expectation_mismatch": expectation_mismatch,
        "positive_counts": positives,
        "negative_counts": negatives,
    }


def _theme_label(theme_code: str) -> str:
    labels = {
        "space": "просторные апартаменты",
        "quiet": "тихая локация",
        "pool": "бассейн",
        "parking": "парковка",
        "kitchen": "кухня",
        "clean": "чистота",
        "airport": "близость к аэропорту",
        "family": "семейный формат",
        "beach_distance": "ожидание близости к пляжу",
        "car_dependency": "зависимость от машины",
        "aircraft_noise": "шум самолётов",
    }
    return labels.get(theme_code, theme_code)


def _dedupe_text_list(items: List[str], limit: int = 6) -> List[str]:
    result: List[str] = []
    seen = set()
    for raw_item in items:
        item = str(raw_item or "").strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= max(1, limit):
            break
    return result


def _detect_audit_profile(business_type: Any, business_name: Any, overview: Any) -> str:
    if _is_hospitality_business(business_type, business_name, overview):
        return "hospitality"
    business_type_text = str(business_type or "").strip().lower()
    business_name_text = str(business_name or "").strip().lower()
    category_text = ""
    description_text = ""
    service_names_list: List[str] = []
    parts: List[str] = [
        business_type_text,
        business_name_text,
    ]
    if isinstance(overview, dict):
        category_text = str(overview.get("category") or "").strip().lower()
        description_text = str(overview.get("description") or "").strip().lower()
        parts.append(category_text)
        parts.append(description_text)
        categories = overview.get("categories")
        if isinstance(categories, list):
            for item in categories:
                parts.append(str(item or "").strip().lower())
        service_names = overview.get("service_names")
        if isinstance(service_names, list):
            for item in service_names[:30]:
                normalized_item = str(item or "").strip().lower()
                if normalized_item:
                    service_names_list.append(normalized_item)
                    parts.append(normalized_item)
    combined = " ".join([item for item in parts if item]).strip()
    if not combined:
        return "default_local_business"
    strong_medical_service_hits = 0
    for service_name in service_names_list[:15]:
        if any(token in service_name for token in STRONG_MEDICAL_SERVICE_HINTS):
            strong_medical_service_hits += 1
    medical_identity_present = any(token in combined for token in MEDICAL_IDENTITY_HINTS)
    if strong_medical_service_hits >= 2:
        return "medical"
    profile_scores: Dict[str, int] = {}
    for profile_name in ("medical", "beauty", "fashion", "wellness", "food", "fitness"):
        hints = AUDIT_PROFILE_HINTS.get(profile_name) or ()
        score = 0
        for token in hints:
            if token in combined:
                score += 1
            if token and token in business_type_text:
                score += 4
            elif token and token in business_name_text:
                score += 2
            if token and token in category_text:
                score += 2
            if token and token in description_text:
                score += 2
            for service_name in service_names_list[:15]:
                if token and token in service_name:
                    score += 3
        profile_scores[profile_name] = score
    best_profile = max(profile_scores.items(), key=lambda item: item[1])
    if best_profile[0] == "medical" and not medical_identity_present and strong_medical_service_hits <= 0:
        return "default_local_business"
    if best_profile[1] > 0:
        return best_profile[0]
    return "default_local_business"


def _extract_hospitality_intent_modifiers(text: str) -> List[str]:
    source = str(text or "").strip().lower()
    if not source:
        return []
    found: List[str] = []
    for terms, intents in HOSPITALITY_INTENT_MODIFIERS:
        if any(term in source for term in terms):
            found.extend(intents)
    return _dedupe_text_list(found, limit=6)


def _build_reasoning_fields(
    *,
    audit_profile: str,
    business_name: str,
    city: str,
    address: str,
    overview_text: str,
    services_count: int,
    has_description: bool,
    photos_count: int,
    reviews_count: int,
    unanswered_reviews_count: int,
    service_names: Optional[List[str]] = None,
    top_positive: Optional[List[str]] = None,
    top_negative: Optional[List[str]] = None,
) -> Dict[str, Any]:
    location = city or "вашем городе"
    positive_labels = [_theme_label(item) for item in (top_positive or [])]
    negative_labels = [_theme_label(item) for item in (top_negative or [])]

    best_fit: List[str]
    weak_fit: List[str]
    intents: List[str]
    photo_shots: List[str]
    positioning_focus: List[str]

    if audit_profile == "hospitality":
        hospitality_context = " ".join(
            part for part in [business_name, city, address, overview_text] if str(part or "").strip()
        ).lower()
        intent_modifiers = _extract_hospitality_intent_modifiers(hospitality_context)
        best_fit = [
            f"Гости, которые ищут спокойное размещение в {location}",
            "Семьи и пары, которым важны простор, бассейн и понятный формат отдыха",
            "Путешественники, которым удобно передвигаться на машине",
        ]
        if positive_labels:
            best_fit.append(f"Те, кто ценит: {', '.join(positive_labels[:3])}")
        weak_fit = [
            "Гости, которые ожидают первую линию и мгновенный доступ к пляжу",
            "Путешественники, которым важен формат классического hotel-by-the-sea",
        ]
        if negative_labels:
            weak_fit.append(f"Риск mismatch ожиданий сейчас связан с темами: {', '.join(negative_labels[:2])}")
        intents = [
            f"hotel in {location}",
            f"budget hotel {location}",
            f"quiet stay near {location}",
            f"family stay in {location}",
            f"hotel with breakfast / Wi-Fi in {location}",
        ]
        intents.extend(intent_modifiers)
        photo_shots = [
            "Фасад, вывеска и вход, чтобы объект было легко узнать на месте",
            "Номера или апартаменты целиком: спальня, ванная, гостиная, кухня",
            "Завтраки, зона reception, бассейн, парковка и реальные удобства объекта",
            "Фото вида из окна, ближайшей инфраструктуры и реального пути до ключевых точек",
        ]
        positioning_focus = [
            "Честно объяснить формат проживания и кому объект подходит лучше всего",
            "Убрать обещания, которые создают завышенное ожидание",
            "Упаковать сильные стороны из отзывов в описание и ответы на отзывы",
            "Добавить trust-triggers: free Wi-Fi, breakfast, airport transfer, 24/7 reception, best price guarantee — если они реально доступны",
        ]
    elif audit_profile == "medical":
        best_fit = [
            f"Пациенты, которые ищут конкретную процедуру или врача в {location}",
            "Люди, которым важны понятные показания, формат услуги и доверие к специалисту",
            "Клиенты, которые сравнивают не только цену, но и опыт, оборудование и профиль врача",
        ]
        weak_fit = [
            "Аудитория, которая не понимает, чем отличается приём, процедура и диагностика",
            "Холодный трафик, если карточка не раскрывает направления и специализацию",
        ]
        intents = [
            f"невролог {location}",
            f"диагностика {location}",
            f"лечение и консультация {location}",
            f"процедуры и восстановление {location}",
        ]
        photo_shots = [
            "Вход, ресепшен и навигация по клинике",
            "Кабинеты, оборудование и рабочие зоны без визуального шума",
            "Врачи и специалисты в рабочей среде",
            "Фото, которые помогают понять уровень сервиса и доверия",
        ]
        positioning_focus = [
            "Сделать акцент на специализации, показаниях и понятном маршруте пациента",
            "Разделить консультации, диагностику и процедуры как отдельные входы в спрос",
            "Снизить тревожность через ясное описание формата визита и ожиданий",
        ]
    elif audit_profile == "beauty":
        beauty_focus_terms = _derive_beauty_focus_terms(service_names or [], overview_text)
        focus_text = ", ".join(beauty_focus_terms[:3]) if beauty_focus_terms else "ключевые направления"
        best_fit = [
            f"Клиенты, которые ищут конкретную beauty-услугу рядом в {location}",
            "Аудитория, которой важны понятные цены, фото результата и удобная запись",
            "Повторные клиенты, если карточка регулярно показывает новинки и работы",
        ]
        if beauty_focus_terms:
            best_fit.append(f"Те, кто уже ищет: {focus_text}")
        weak_fit = [
            "Пользователи, которые не понимают разницу между направлениями услуг",
            "Новый трафик, если названия услуг общие и без цены",
        ]
        intents = [f"салон красоты {location}"]
        if beauty_focus_terms:
            intents.extend([f"{term} {location}" for term in beauty_focus_terms[:3]])
        else:
            intents.extend(
                [
                    f"лазерная эпиляция {location}",
                    f"маникюр {location}",
                    f"косметология {location}",
                ]
            )
        intents.append(f"процедура с ценой и примерами работ {location}")
        photo_shots = [
            f"Работы до/после или итоговый результат по направлениям: {focus_text}",
            "Кабинеты, мастера и рабочая атмосфера",
            "Фото хитов услуг и понятных форматов записи",
        ]
        positioning_focus = [
            f"Показывать {focus_text} как конкретные точки входа в спрос, а не общим списком",
            "Соединить услуги, цены и фото в единый конверсионный блок",
            "Делать ответы на отзывы продолжением обещания бренда",
        ]
    elif audit_profile == "fashion":
        best_fit = [
            f"Клиенты, которые ищут custom dresses и bridal wear в {location}",
            "Покупатели, которым важны premium stitching, индивидуальный подход и fittings",
            "Аудитория, которая сравнивает bridal designer, formal wear studio и custom tailoring",
        ]
        weak_fit = [
            "Пользователи, которые ждут ready-to-buy магазин, если студия работает под custom заказ",
            "Новый трафик, если карточка не объясняет dress categories, pricing logic и процесс пошива",
        ]
        intents = [
            f"fashion designer {location}",
            f"custom dresses {location}",
            f"bridal designer {location}",
            f"bridal wear {location}",
            f"designer studio / stitching {location}",
        ]
        photo_shots = [
            "Bridal dresses, custom dresses и signature looks по категориям",
            "Stitching process, fittings, выбор тканей и детали пошива",
            "Студия, команда, консультационная зона и готовые образы на клиентах или манекенах",
        ]
        positioning_focus = [
            "Объяснить, какие типы платьев и заказов студия делает лучше всего",
            "Разделить bridal, formal и custom stitching как отдельные точки входа в спрос",
            "Усилить доверие через fit-story, процесс пошива и отзывы клиентов",
        ]
    elif audit_profile == "wellness":
        best_fit = [
            f"Клиенты, которые ищут восстановление, релакс и wellness-процедуры в {location}",
            "Люди, которым важно сочетание процедур, атмосферы и доверия",
            "Аудитория, которая выбирает между spa, массажем и оздоровительными программами",
        ]
        weak_fit = [
            "Пользователи, которым непонятно, это medical, spa или relax-формат",
            "Холодный трафик, если процедуры описаны слишком абстрактно",
        ]
        intents = [
            f"spa {location}",
            f"massage {location}",
            f"wellness center {location}",
            f"body recovery / detox {location}",
        ]
        photo_shots = [
            "Процедурные кабинеты и оборудование",
            "Атмосфера пространства, вход, reception",
            "Процесс процедур и ключевые зоны комплекса",
        ]
        positioning_focus = [
            "Чётко объяснить, это релакс, восстановление, медицинский или premium wellness",
            "Развернуть процедуры как отдельные SEO-единицы с ценой и результатом",
            "Показать оборудование и сценарий визита, а не только красивый интерьер",
        ]
    elif audit_profile == "food":
        best_fit = [
            f"Гости, которые ищут конкретный формат заведения в {location}",
            "Трафик по сценариям: завтрак, ужин, доставка, бизнес-ланч, speciality",
            "Пользователи, которым важны фото, меню и быстрый сигнал доверия",
        ]
        weak_fit = [
            "Гости, которые не понимают специализацию кухни и формат визита",
            "Новый трафик, если в карточке нет хитов меню и поводов прийти",
        ]
        intents = [
            f"кафе {location}",
            f"ресторан {location}",
            f"завтрак / ужин {location}",
            f"фирменные блюда и меню {location}",
        ]
        photo_shots = [
            "Хиты меню и визуально сильные блюда",
            "Интерьер, посадка и атмосфера",
            "Фасад и вход, чтобы заведение было легко найти",
        ]
        positioning_focus = [
            "Продавать сценарий визита, а не только сам факт существования заведения",
            "Сделать меню и хиты частью локального SEO",
            "Собрать доверие через фото, отзывы и ответы с локальным контекстом",
        ]
    elif audit_profile == "fitness":
        best_fit = [
            f"Люди, которые ищут конкретный формат тренировок в {location}",
            "Клиенты, которым важны расписание, оборудование и понятная точка входа",
            "Пользователи, которые сравнивают групповые и персональные форматы",
        ]
        weak_fit = [
            "Новый трафик, если карточка не объясняет уровень, формат и оборудование",
            "Пользователи, для которых неясно, чем отличаются тренеры и абонементы",
        ]
        intents = [
            f"pilates / yoga / fitness {location}",
            f"персональная тренировка {location}",
            f"групповые занятия {location}",
            f"абонементы и reformer / studio {location}",
        ]
        photo_shots = [
            "Залы, оборудование и тренажёры / reformer / studio setup",
            "Фото занятий в группе и персонального формата",
            "Тренеры и рабочая атмосфера",
        ]
        positioning_focus = [
            "Показывать формат тренировок, уровень и оборудование как главные отличия",
            "Разделить персональный и групповой входящий спрос",
            "Усилить карточку через фото, абонементы и понятные сценарии записи",
        ]
    else:
        best_fit = [
            f"Люди, которые ищут конкретную услугу рядом в {location}",
            "Пользователи, которым важны доверие, понятный прайс и удобный контакт",
        ]
        weak_fit = [
            "Новый трафик, если карточка не объясняет формат услуги и её результат",
        ]
        intents = [
            f"услуга рядом {location}",
            f"цена / отзывы / запись {location}",
            f"конкретная услуга + {location}",
        ]
        photo_shots = [
            "Фасад или вход, чтобы бизнес было легко найти",
            "Команда, рабочая зона и примеры результата",
            "Ключевые услуги или товарные группы",
        ]
        positioning_focus = [
            "Превратить карточку из визитки в понятную точку входа в спрос",
            "Усилить доверие через контакты, фото и конкретику по услугам",
        ]

    reasoning = {
        "audit_profile": audit_profile,
        "audit_profile_label": AUDIT_PROFILE_LABELS.get(audit_profile, AUDIT_PROFILE_LABELS["default_local_business"]),
        "best_fit_customer_profile": _dedupe_text_list(best_fit, limit=4),
        "weak_fit_customer_profile": _dedupe_text_list(weak_fit, limit=4),
        "search_intents_to_target": _dedupe_text_list(intents, limit=5),
        "photo_shots_missing": _dedupe_text_list(photo_shots, limit=5),
        "positioning_focus": _dedupe_text_list(positioning_focus, limit=4),
        "strength_themes": _dedupe_text_list(positive_labels, limit=4),
        "objection_themes": _dedupe_text_list(negative_labels, limit=4),
        "description_gap": not has_description,
        "services_gap": services_count <= 0,
        "photos_gap": photos_count <= 0,
        "review_signal_strength": "strong" if reviews_count >= 50 else ("medium" if reviews_count >= 15 else "weak"),
        "review_response_gap": unanswered_reviews_count > 0,
    }
    reasoning["best_fit_guest_profile"] = list(reasoning["best_fit_customer_profile"])
    reasoning["weak_fit_guest_profile"] = list(reasoning["weak_fit_customer_profile"])
    return reasoning


def _extract_services_from_products_payload(products_payload: Any, *, limit: int = 8) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    products_payload = _safe_json(products_payload) or products_payload
    if isinstance(products_payload, dict):
        products_payload = [
            {"category": str(category_name or "").strip(), "items": items}
            for category_name, items in products_payload.items()
        ]
    if not isinstance(products_payload, list):
        return rows

    def _push_item(item: Any, fallback_category: str = "Парсинг карточки") -> None:
        if not isinstance(item, dict):
            return
        name = str(item.get("name") or "").strip()
        if not name:
            return
        description = str(item.get("description") or "").strip()
        if _is_editorial_service_entry(name, description):
            return
        category = str(
            item.get("category")
            or item.get("category_name")
            or item.get("group")
            or item.get("section")
            or fallback_category
        ).strip() or fallback_category
        if category.lower() in SERVICE_EXCLUDED_CATEGORIES:
            return
        price = item.get("price") or item.get("price_from") or item.get("price_to")
        if (price is None or not str(price).strip()) and not description:
            return
        category = str(
            category
        ).strip() or fallback_category
        note_parts = []
        if price is not None and str(price).strip():
            note_parts.append(f"Цена: {str(price).strip()}")
        if category:
            note_parts.append(f"Источник: {category}")
        rows.append(
            {
                "current_name": name,
                "suggested_name": name,
                "note": " • ".join(note_parts) if note_parts else "Парсинг карточки",
                "description": description or None,
                "_price_present": bool(price is not None and str(price).strip()),
            }
        )

    for block in products_payload:
        if isinstance(block, dict):
            block_category = str(block.get("category") or block.get("name") or "Парсинг карточки").strip() or "Парсинг карточки"
            block_items = block.get("items") if isinstance(block.get("items"), list) else None
            if block_items is not None:
                for item in block_items:
                    _push_item(item, block_category)
            else:
                _push_item(block, block_category)
        elif isinstance(block, list):
            for item in block:
                _push_item(item, "Парсинг карточки")

        if len(rows) >= max(1, limit):
            break

    return rows[: max(1, limit)]


def _extract_lead_import_payload(lead: Dict[str, Any]) -> Dict[str, Any]:
    payload = _safe_json(lead.get("search_payload_json")) or {}
    if not isinstance(payload, dict):
        return {
            "logo_url": None,
            "photos": [],
            "services_preview": [],
            "services_total_count": 0,
            "services_with_price_count": 0,
            "reviews_preview": [],
            "news_preview": [],
            "reviews_count": None,
            "social_links": [],
        }
    logo_url = _normalize_media_url(payload.get("logo_url")) or None
    photos_raw = payload.get("photos")
    photos: List[str] = []
    if isinstance(photos_raw, list):
        for item in photos_raw:
            value = _normalize_media_url(item)
            if value:
                photos.append(value)
    services_preview: List[Dict[str, Any]] = []
    full_services_payload = payload.get("menu_full")
    if not isinstance(full_services_payload, list):
        full_services_payload = payload.get("services_full")
    menu_preview = payload.get("menu_preview")
    preview_source = menu_preview if isinstance(menu_preview, list) else full_services_payload if isinstance(full_services_payload, list) else []
    full_source = full_services_payload if isinstance(full_services_payload, list) else preview_source
    services_total_count = _extract_int(payload.get("services_total_count") or 0)
    services_with_price_count = _extract_int(payload.get("services_with_price_count") or 0)

    if services_total_count <= 0 and isinstance(full_source, list):
        for item in full_source:
            if not isinstance(item, dict):
                continue
            name = str(item.get("title") or item.get("name") or "").strip()
            if not name:
                continue
            description = str(item.get("description") or "").strip()
            if _is_editorial_service_entry(name, description):
                continue
            services_total_count += 1
            if str(item.get("price") or "").strip():
                services_with_price_count += 1

    if isinstance(preview_source, list):
        for item in preview_source:
            if not isinstance(item, dict):
                continue
            name = str(item.get("title") or item.get("name") or "").strip()
            if not name:
                continue
            description = str(item.get("description") or "").strip()
            if _is_editorial_service_entry(name, description):
                continue
            description_value = description or None
            price = str(item.get("price") or "").strip()
            category = str(item.get("category") or "").strip()
            note_parts = []
            if price:
                note_parts.append(f"Цена: {price}")
            if category:
                note_parts.append(f"Источник: {category}")
            services_preview.append(
                {
                    "current_name": name,
                    "suggested_name": name,
                    "note": " • ".join(note_parts) if note_parts else "Импорт Apify",
                    "description": description_value,
                    "category": category or None,
                    "price": price or None,
                }
            )
        services_preview = services_preview[:20]
    reviews_preview: List[Dict[str, Any]] = []
    imported_reviews = payload.get("reviews_preview")
    if isinstance(imported_reviews, list):
        for item in imported_reviews[:6]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("review") or item.get("text") or "").strip()
            if not text:
                continue
            response_text = str(item.get("business_comment") or item.get("response_text") or "").strip()
            if _is_placeholder_review_entry(text, response_text):
                continue
            rating = item.get("rating")
            suffix = f" (оценка: {rating})" if rating not in (None, "") else ""
            reviews_preview.append(
                {
                    "review": f"{text}{suffix}",
                    "reply_preview": response_text or "Ответа пока нет",
                }
            )
    social_links = payload.get("social_links") if isinstance(payload.get("social_links"), list) else []
    return {
        "logo_url": logo_url,
        "photos": photos,
        "services_preview": services_preview,
        "services_total_count": services_total_count,
        "services_with_price_count": services_with_price_count,
        "reviews_preview": reviews_preview,
        "news_preview": [],
        "reviews_count": _extract_numeric(payload.get("reviews_count")),
        "social_links": social_links,
    }


def _resolve_lead_business_snapshot(lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Try to resolve an existing LocalOS business for a lead and enrich preview metrics.
    Returns partial snapshot; empty dict means no business match found.
    """
    explicit_business_id = str(lead.get("business_id") or "").strip()
    raw_source_url = str(lead.get("source_url") or "").strip()
    normalized_source_url = normalize_map_url(raw_source_url) if raw_source_url else ""
    source_url = normalized_source_url or raw_source_url
    google_place_id = ""
    if source_url:
        google_match = re.search(r"cid=(\d+)|!1s(0x[0-9a-f]+:0x[0-9a-f]+)", source_url, flags=re.IGNORECASE)
        if google_match:
            google_place_id = str(google_match.group(1) or google_match.group(2) or "").strip()
    source_external_id = str(
        lead.get("source_external_id")
        or lead.get("external_source_id")
        or lead.get("external_place_id")
        or lead.get("google_id")
        or google_place_id
        or _extract_yandex_org_id_from_url(source_url)
        or ""
    ).strip()
    lead_name = str(lead.get("name") or "").strip()
    lead_city = str(lead.get("city") or "").strip()
    source_url_lower = source_url.lower()
    source_map_type = ""
    if "google." in source_url_lower or "maps.app.goo.gl" in source_url_lower:
        source_map_type = "google"
    elif "yandex." in source_url_lower:
        source_map_type = "yandex"
    elif "2gis." in source_url_lower:
        source_map_type = "2gis"

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'businesses'
            """
        )
        business_columns = set()
        for row in cursor.fetchall():
            if hasattr(row, "get"):
                column_name = row.get("column_name")
            else:
                column_name = row[0] if row else None
            if column_name:
                business_columns.add(str(column_name))

        business = None
        if explicit_business_id:
            cursor.execute(
                """
                SELECT *
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (explicit_business_id,),
            )
            business = _to_dict(cursor, cursor.fetchone())

        if not business and source_external_id and "yandex_org_id" in business_columns:
            cursor.execute(
                """
                SELECT *
                FROM businesses
                WHERE yandex_org_id = %s
                LIMIT 1
                """,
                (source_external_id,),
            )
            business = _to_dict(cursor, cursor.fetchone())

        if not business and source_url and _table_exists(cursor, "businessmaplinks"):
            businessmap_where = ["LOWER(COALESCE(l.url, '')) = LOWER(%s)"]
            businessmap_params: List[Any] = [source_url]
            if source_map_type:
                businessmap_where.append("LOWER(COALESCE(l.map_type, '')) = LOWER(%s)")
                businessmap_params.append(source_map_type)
            cursor.execute(
                f"""
                SELECT b.*
                FROM businessmaplinks l
                JOIN businesses b ON b.id = l.business_id
                WHERE {" AND ".join(businessmap_where)}
                ORDER BY l.created_at DESC
                LIMIT 1
                """,
                tuple(businessmap_params),
            )
            business = _to_dict(cursor, cursor.fetchone())

        strong_external_id = _has_strong_external_id(source_external_id)

        if not business and source_url and _table_exists(cursor, "parsequeue"):
            parsequeue_filters = ["pq.business_id IS NOT NULL", "pq.status IN ('completed', 'done')"]
            parsequeue_params: List[Any] = []
            parsequeue_exact: List[str] = []
            if source_url:
                parsequeue_exact.append("LOWER(COALESCE(pq.url, '')) = LOWER(%s)")
                parsequeue_params.append(source_url)
            if strong_external_id:
                parsequeue_exact.append("LOWER(COALESCE(pq.url, '')) LIKE LOWER(%s)")
                parsequeue_params.append(f"%{source_external_id}%")
            if parsequeue_exact:
                cursor.execute(
                    f"""
                    SELECT b.*
                    FROM parsequeue pq
                    JOIN businesses b ON b.id = pq.business_id
                    WHERE {" AND ".join(parsequeue_filters)}
                      AND ({" OR ".join(parsequeue_exact)})
                    ORDER BY pq.updated_at DESC NULLS LAST, pq.created_at DESC
                    LIMIT 1
                    """,
                    tuple(parsequeue_params),
                )
                business = _to_dict(cursor, cursor.fetchone())

        if not business and source_url and "yandex_url" in business_columns:
            if strong_external_id and source_map_type in {"", "yandex"}:
                cursor.execute(
                    """
                    SELECT *
                    FROM businesses
                    WHERE yandex_url = %s
                       OR yandex_url ILIKE %s
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (source_url, f"%{source_external_id}%"),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM businesses
                    WHERE yandex_url = %s
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (source_url,),
                )
            business = _to_dict(cursor, cursor.fetchone())

        if not business and lead_name and lead_city:
            cursor.execute(
                """
                SELECT *
                FROM businesses
                WHERE LOWER(name) = LOWER(%s)
                  AND (%s = '' OR LOWER(COALESCE(city, '')) = LOWER(%s))
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT 1
                """,
                (lead_name, lead_city, lead_city),
            )
            business = _to_dict(cursor, cursor.fetchone())

        if not business and lead_name:
            cursor.execute(
                """
                SELECT *
                FROM businesses
                WHERE LOWER(name) = LOWER(%s)
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT 2
                """,
                (lead_name,),
            )
            exact_name_rows = [_to_dict(cursor, row) or {} for row in (cursor.fetchall() or [])]
            if len(exact_name_rows) == 1:
                business = exact_name_rows[0]

        if not business:
            return {}

        if not _lead_matches_business_identity(
            lead,
            business,
            source_url=source_url,
            source_external_id=source_external_id,
        ):
            return {}

        business_id = business.get("id")
        if not business_id:
            return {}

        cursor.execute(
            """
            SELECT name, description, price, source
            FROM userservices
            WHERE business_id = %s
              AND (is_active IS TRUE OR is_active IS NULL)
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            """,
            (business_id,),
        )
        all_service_rows = cursor.fetchall() or []
        valid_service_rows: List[Dict[str, Any]] = []
        for raw_row in all_service_rows:
            service_row = _to_dict(cursor, raw_row) or {}
            name = str(service_row.get("name") or "").strip()
            if not name:
                continue
            description = str(service_row.get("description") or "").strip()
            if _is_editorial_service_entry(name, description):
                continue
            valid_service_rows.append(
                {
                    "name": name,
                    "description": description,
                    "price": str(service_row.get("price") or "").strip(),
                    "source": str(service_row.get("source") or "").strip(),
                }
            )
        active_services = len(valid_service_rows)
        priced_services = len([row for row in valid_service_rows if str(row.get("price") or "").strip()])

        cursor.execute(
            """
            SELECT *
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (business_id,),
        )
        recent_cards = [_to_dict(cursor, row) or {} for row in (cursor.fetchall() or [])]
        latest_card = recent_cards[0] if recent_cards else {}
        rich_card = _select_preferred_rich_card(recent_cards) or latest_card
        metrics_card = _select_preferred_metrics_card(recent_cards) or latest_card

        cursor.execute(
            """
            SELECT id, status, updated_at, retry_after, error_message
            FROM parsequeue
            WHERE business_id = %s
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        latest_parse = _to_dict(cursor, cursor.fetchone()) or {}

        photos_payload = _safe_json(rich_card.get("photos"))
        news_payload = _safe_json(rich_card.get("news"))
        products_payload = _safe_json(rich_card.get("products"))
        overview_payload = _safe_json(rich_card.get("overview")) or {}
        overview_social_links = overview_payload.get("social_links") if isinstance(overview_payload, dict) else None
        social_links = _extract_contact_links(overview_social_links)
        parsed_contacts = _extract_telegram_whatsapp_email_from_links(social_links)

        photo_urls: List[str] = []
        if isinstance(photos_payload, list):
            for raw_photo in photos_payload:
                if isinstance(raw_photo, dict):
                    candidate = _normalize_media_url(
                        raw_photo.get("url")
                        or raw_photo.get("imageUrl")
                        or raw_photo.get("src")
                        or raw_photo.get("originalUrl")
                    )
                else:
                    candidate = _normalize_media_url(raw_photo)
                if candidate:
                    photo_urls.append(candidate)
        if photo_urls:
            photo_urls = list(dict.fromkeys(photo_urls))[:8]

        services_preview: List[Dict[str, Any]] = []
        for service_row in valid_service_rows[:8]:
            name = str(service_row.get("name") or "").strip()
            description = str(service_row.get("description") or "").strip()
            price = str(service_row.get("price") or "").strip()
            source = str(service_row.get("source") or "").strip()
            note_parts = []
            if price:
                note_parts.append(f"Цена: {price}")
            if source:
                note_parts.append(f"Источник: {source}")
            services_preview.append(
                {
                    "current_name": name,
                    "suggested_name": name,
                    "note": " • ".join(note_parts) if note_parts else "Парсинг карточки",
                    "description": description or None,
                }
            )

        if not services_preview:
            services_preview = _extract_services_from_products_payload(products_payload, limit=8)
            if services_preview and active_services <= 0:
                active_services = len(services_preview)
                priced_services = len([row for row in services_preview if row.get("_price_present")])

        reviews_preview: List[Dict[str, Any]] = []
        reviews_count_from_table: Optional[int] = None
        if _table_exists(cursor, "externalbusinessreviews"):
            cursor.execute(
                """
                WITH preferred_source AS (
                    SELECT CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM externalbusinessreviews r2
                            WHERE r2.business_id = %s
                              AND r2.source = 'yandex_maps'
                        ) THEN 'yandex_maps'
                        ELSE 'yandex_business'
                    END AS source
                )
                SELECT text AS review_text, response_text, rating
                FROM externalbusinessreviews r, preferred_source ps
                WHERE r.business_id = %s
                  AND r.source = ps.source
                ORDER BY published_at DESC NULLS LAST, created_at DESC
                LIMIT 200
                """,
                (business_id, business_id),
            )
            valid_reviews_count = 0
            for row in cursor.fetchall() or []:
                review_row = _to_dict(cursor, row) or {}
                review_text = str(review_row.get("review_text") or "").strip()
                if not review_text:
                    continue
                response_text = str(review_row.get("response_text") or "").strip()
                if _is_placeholder_review_entry(review_text, response_text):
                    continue
                valid_reviews_count += 1
                rating = review_row.get("rating")
                rating_suffix = ""
                if rating is not None and str(rating).strip() != "":
                    rating_suffix = f" (оценка: {rating})"
                if len(reviews_preview) < 6:
                    reviews_preview.append(
                        {
                            "review": f"{review_text}{rating_suffix}",
                            "reply_preview": response_text or "Ответа пока нет",
                        }
                    )
            reviews_count_from_table = valid_reviews_count

        news_preview: List[Dict[str, Any]] = []
        if isinstance(news_payload, list):
            for item in news_payload[:6]:
                if isinstance(item, dict):
                    title = str(item.get("title") or item.get("name") or "").strip() or "Новость"
                    body = str(item.get("body") or item.get("text") or item.get("description") or "").strip()
                    if title or body:
                        news_preview.append({"title": title, "body": body or "Без текста"})
                elif isinstance(item, str):
                    text = item.strip()
                    if text:
                        news_preview.append({"title": "Новость", "body": text})

        if active_services > 0 and not services_preview:
            active_services = 0
            priced_services = 0
        reviews_count_value = int(metrics_card.get("reviews_count") or business.get("yandex_reviews_total") or 0)
        if reviews_count_from_table is not None:
            if reviews_count_from_table <= 0:
                reviews_count_value = 0
            elif reviews_count_value <= 0:
                reviews_count_value = reviews_count_from_table

        return {
            "business": business,
            "services_count": active_services,
            "priced_services_count": priced_services,
            "rating": _extract_numeric(metrics_card.get("rating")) if metrics_card.get("rating") is not None else _extract_numeric(business.get("yandex_rating")),
            "reviews_count": reviews_count_value,
            "unanswered_reviews_count": int(metrics_card.get("unanswered_reviews_count") or latest_card.get("unanswered_reviews_count") or 0),
            "photos_count": len(photos_payload) if isinstance(photos_payload, list) else 0,
            "photo_urls": photo_urls,
            "news_count": len(news_payload) if isinstance(news_payload, list) else 0,
            "has_recent_activity": bool(metrics_card.get("updated_at") or rich_card.get("updated_at") or latest_parse.get("updated_at")),
            "last_parse_at": latest_parse.get("updated_at") or metrics_card.get("updated_at") or rich_card.get("updated_at") or business.get("updated_at"),
            "last_parse_status": latest_parse.get("status") or "completed",
            "last_parse_task_id": latest_parse.get("id"),
            "last_parse_retry_after": latest_parse.get("retry_after"),
            "last_parse_error": latest_parse.get("error_message"),
            "source_url": business.get("yandex_url") or source_url,
            "description_present": bool(str(overview_payload.get("description") or "").strip()) if isinstance(overview_payload, dict) else False,
            "parsed_contacts": {
                "phone": str(metrics_card.get("phone") or rich_card.get("phone") or business.get("phone") or "").strip() or None,
                "website": str(metrics_card.get("site") or rich_card.get("site") or business.get("website") or "").strip() or None,
                "email": parsed_contacts.get("email"),
                "telegram_url": parsed_contacts.get("telegram_url"),
                "whatsapp_url": parsed_contacts.get("whatsapp_url"),
                "social_links": social_links,
            },
            "services_preview": services_preview,
            "reviews_preview": reviews_preview,
            "news_preview": news_preview,
        }
    except Exception as exc:
        print(f"lead preview business resolution fallback: {exc}")
        return {}
    finally:
        db.close()


def _lead_demo_services_preview(business_type: str) -> List[Dict[str, Any]]:
    normalized = business_type.lower()
    if "school" in normalized or "education" in normalized:
        return [
            {
                "current_name": "Курс / занятие без структуры",
                "suggested_name": "Пробное занятие для новых учеников",
                "note": "Лучше вынести понятную точку входа, чтобы карточка конвертировала первый интерес.",
            },
            {
                "current_name": "Общее направление обучения",
                "suggested_name": "Индивидуальные занятия по ключевому предмету",
                "note": "Показывайте конкретные направления, а не только общий профиль школы.",
            },
            {
                "current_name": "Без цены или формата",
                "suggested_name": "Абонемент на месяц / курс с понятным форматом",
                "note": "Цена и формат повышают доверие и сокращают лишние вопросы.",
            },
        ]
    if any(token in normalized for token in ("beauty", "salon", "nail", "cosmetology", "massage", "barber")):
        return [
            {
                "current_name": "Общая услуга без структуры",
                "suggested_name": "Базовая услуга с понятным названием и сегментом",
                "note": "Карточка лучше работает, когда названия услуг сразу отвечают на запрос клиента.",
            },
            {
                "current_name": "Услуга без цены",
                "suggested_name": "Ключевая процедура с ценой или ценовым диапазоном",
                "note": "Даже ориентировочная цена снижает трение перед первым контактом.",
            },
            {
                "current_name": "Нет отдельных направлений",
                "suggested_name": "Выделенные услуги по основным направлениям салона",
                "note": "Разделите ключевые услуги на отдельные позиции вместо одного общего описания.",
            },
        ]
    if any(token in normalized for token in ("cafe", "coffee", "restaurant")):
        return [
            {
                "current_name": "Общий формат заведения",
                "suggested_name": "Завтраки / бизнес-ланч / фирменные позиции",
                "note": "Показывайте поводы прийти, а не только сам факт существования заведения.",
            },
            {
                "current_name": "Меню без акцентов",
                "suggested_name": "Хиты меню с понятной ценой",
                "note": "Лучше выделить 3–5 ключевых позиций, чем оставлять абстрактное меню.",
            },
        ]
    return [
        {
            "current_name": "Общее описание без структуры",
            "suggested_name": "Ключевая услуга с понятным названием",
            "note": "Нужны конкретные точки входа, чтобы карточка отвечала на поисковый запрос.",
        },
        {
            "current_name": "Нет цены или формата",
            "suggested_name": "Понятный формат услуги с диапазоном цены",
            "note": "Это повышает доверие и сокращает путь до первого обращения.",
        },
    ]


def _lead_demo_reviews_preview(lead_name: str, business_type: str, rating: Optional[float], reviews_count: int) -> List[Dict[str, Any]]:
    trust_line = "Рейтинг уже помогает карточке, но ответы усиливают доверие." if (rating or 0) >= 4.7 else "Даже при хорошем продукте слабая работа с отзывами снижает доверие."
    return [
        {
            "review": f"Нравится формат {business_type.lower() if business_type else 'услуг'}, но хотелось бы больше ясности по условиям и цене.",
            "reply_preview": f"Спасибо за обратную связь. Мы готовы подробнее объяснить формат, стоимость и подобрать удобный вариант под ваш запрос.",
        },
        {
            "review": f"Интересный вариант, но по карточке не до конца понятно, чем {lead_name} отличается от конкурентов.",
            "reply_preview": f"Спасибо, это важный комментарий. Мы усиливаем карточку и уточняем ключевые преимущества, чтобы выбор был понятнее уже на этапе просмотра.",
        },
        {
            "review": trust_line,
            "reply_preview": "Регулярные ответы на отзывы делают карточку живой и помогают перевести интерес в обращение.",
        },
    ]


def _lead_demo_news_preview(business_type: str) -> List[Dict[str, Any]]:
    return [
        {
            "title": "Пример новости: что нового в карточке",
            "body": f"Покажите актуальное предложение по направлению «{business_type}», чтобы карточка выглядела живой и помогала принять решение.",
        },
        {
            "title": "Пример новости: повод обратиться сейчас",
            "body": "Добавьте короткий инфоповод: сезонное предложение, новый формат, удобное время или обновлённую услугу.",
        },
    ]


def _infer_baseline_revenue(*, business_type: Any, average_check: Optional[float], current_revenue: Optional[float], services_count: int, reviews_count: int) -> Dict[str, Any]:
    if current_revenue and current_revenue > 0:
        exact_value = round(current_revenue)
        return {"value": exact_value, "min": exact_value, "max": exact_value, "source": "actual"}

    normalized_type = str(business_type or "").strip().lower()
    baseline = 0.0
    baseline_source = None

    if average_check and average_check > 0:
        estimated_purchases = max(20, services_count * 8, min(reviews_count, 80))
        baseline = average_check * estimated_purchases
        baseline_source = "estimated_from_average_check"
    else:
        for key, value in CATEGORY_BASELINE_REVENUE.items():
            if key in normalized_type:
                baseline_range = _normalize_baseline_range(value)
                baseline = baseline_range["value"]
                baseline_min = baseline_range["min"]
                baseline_max = baseline_range["max"]
                baseline_source = "category_baseline"
                return {
                    "value": round(baseline),
                    "min": round(baseline_min),
                    "max": round(baseline_max),
                    "source": baseline_source,
                }

    if baseline <= 0:
        baseline = 120000.0
        baseline_source = "default_baseline"

    exact_value = round(baseline)
    return {"value": exact_value, "min": exact_value, "max": exact_value, "source": baseline_source}


def estimate_card_revenue_gap(
    *,
    rating: Optional[float],
    services_count: int,
    priced_services_count: int,
    unanswered_reviews_count: int,
    reviews_count: int,
    photos_count: int,
    news_count: int,
    average_check: Optional[float],
    current_revenue: Optional[float],
    business_type: Optional[str],
) -> Dict[str, Any]:
    baseline = _infer_baseline_revenue(
        business_type=business_type,
        average_check=average_check,
        current_revenue=current_revenue,
        services_count=services_count,
        reviews_count=reviews_count,
    )
    baseline_min_value = float(baseline.get("min") or baseline["value"])
    baseline_max_value = float(baseline.get("max") or baseline["value"])

    rating_penalty_min = 0.0
    rating_penalty_max = 0.0
    if rating is not None:
        if rating < 4.4:
            rating_penalty_min, rating_penalty_max = 0.06, 0.15
        elif rating < 4.7:
            rating_penalty_min, rating_penalty_max = 0.02, 0.06
        else:
            rating_penalty_min, rating_penalty_max = 0.0, 0.02
        if unanswered_reviews_count >= 5:
            rating_penalty_max += 0.02

    content_penalty_min = 0.0
    content_penalty_max = 0.0
    if photos_count <= 0:
        content_penalty_min += 0.03
        content_penalty_max += 0.06
    elif photos_count < 5:
        content_penalty_min += 0.01
        content_penalty_max += 0.03
    if news_count <= 0:
        content_penalty_min += 0.01
        content_penalty_max += 0.03
    if not reviews_count:
        content_penalty_min += 0.01
        content_penalty_max += 0.02
    if unanswered_reviews_count >= 5:
        content_penalty_min += 0.01
        content_penalty_max += 0.03
    content_penalty_max = min(content_penalty_max, 0.10)

    service_penalty_min = 0.0
    service_penalty_max = 0.0
    if services_count <= 0:
        service_penalty_min += 0.08
        service_penalty_max += 0.15
    elif services_count < 5:
        service_penalty_min += 0.04
        service_penalty_max += 0.10
    if services_count > 0 and priced_services_count <= 0:
        service_penalty_min += 0.02
        service_penalty_max += 0.05
    elif services_count > 0 and priced_services_count < max(1, services_count // 2):
        service_penalty_min += 0.01
        service_penalty_max += 0.03
    service_penalty_max = min(service_penalty_max, 0.15)

    rating_min = round(baseline_min_value * rating_penalty_min)
    rating_max = round(baseline_max_value * rating_penalty_max)
    content_min = round(baseline_min_value * content_penalty_min)
    content_max = round(baseline_max_value * content_penalty_max)
    service_min = round(baseline_min_value * service_penalty_min)
    service_max = round(baseline_max_value * service_penalty_max)
    return {
        "mode": "estimate_v1",
        "baseline_monthly_revenue": baseline,
        "rating_gap": {"min": rating_min, "max": rating_max},
        "content_gap": {"min": content_min, "max": content_max},
        "service_gap": {"min": service_min, "max": service_max},
        "total_min": rating_min + content_min + service_min,
        "total_max": rating_max + content_max + service_max,
        "confidence": "medium",
        "disclaimer": "Оценка ориентировочная и основана на модели карточки, а не на полном доступе к вашим продажам.",
        "currency": "RUB",
    }


def _issue_priority_rank(priority: str) -> int:
    mapping = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return mapping.get(str(priority or "").lower(), 9)


def _build_top_issues(issue_blocks: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    sorted_blocks = sorted(issue_blocks, key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    top: List[Dict[str, Any]] = []
    for item in sorted_blocks[:max(0, limit)]:
        top.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "priority": item.get("priority"),
                "problem": item.get("problem"),
            }
        )
    return top


def _build_action_plan(
    issue_blocks: List[Dict[str, Any]],
    *,
    cadence_news_min: int,
    cadence_photos_min: int,
    cadence_response_hours_max: int,
) -> Dict[str, List[str]]:
    sorted_blocks = sorted(issue_blocks, key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    next_24h: List[str] = []
    next_7d: List[str] = []
    for item in sorted_blocks:
        fix_text = str(item.get("fix") or "").strip()
        if not fix_text:
            continue
        priority = str(item.get("priority") or "").lower()
        if priority in {"critical", "high"} and len(next_24h) < 4:
            next_24h.append(fix_text)
            continue
        if priority in {"medium", "low"} and len(next_7d) < 4:
            next_7d.append(fix_text)

    if not next_24h:
        next_24h.append("Проверить карточку по 3 ключевым зонам: услуги, отзывы, контакты.")
    if not next_7d:
        next_7d.append("Доработать формулировки услуг и закрыть пробелы карточки.")

    ongoing = [
        f"Публиковать новости/обновления минимум {cadence_news_min} раз(а) в месяц.",
        f"Добавлять новые фото минимум {cadence_photos_min} раз(а) в месяц.",
        f"Отвечать на отзывы не позднее {cadence_response_hours_max} часов.",
    ]
    return {
        "next_24h": next_24h,
        "next_7d": next_7d,
        "ongoing": ongoing,
    }


def _build_hospitality_action_plan(
    *,
    has_description: bool,
    has_real_services: bool,
    photos_count: int,
    top_negative: List[str],
    unanswered_reviews_count: int,
    rating: Optional[float],
    reviews_count: int,
) -> Dict[str, List[str]]:
    next_24h: List[str] = []
    next_7d: List[str] = []

    if not has_description:
        next_24h.append(
            "Переписать описание карточки: добавить search-intents, nearby landmarks, честное позиционирование и кому объект подходит лучше всего."
        )
    if rating is None or rating < 4.2:
        next_24h.append(
            "Запустить review engine как главный рычаг роста: QR после заселения/выезда, напоминание в WhatsApp и ответы на все новые отзывы."
        )
    if "beach_distance" in top_negative or "car_dependency" in top_negative:
        next_24h.append(
            "Снять mismatch ожиданий: прямо объяснить формат локации, сценарий отдыха и кому объект особенно подходит."
        )
    if not has_real_services:
        next_24h.append(
            "Убрать booking-offers из блока услуг и заменить их на реальные единицы предложения: stay format, amenities, wellness/spa services или room types."
        )
    if unanswered_reviews_count > 0:
        next_24h.append("Ответить на ключевые отзывы так, чтобы усилить доверие, поддержать видимость карточки и снять повторяющиеся возражения.")

    if photos_count < 12:
        next_7d.append(
            "Собрать фото-историю объекта: фасад, вывеска, номера, завтраки, reception, парковка, вид из окна и what-you-really-get."
        )
    next_7d.append(
        "Проверить категории и атрибуты: hotel / budget hotel / family hotel / breakfast / airport transfer / Wi-Fi / 24-7 reception — по факту доступных опций."
    )
    next_7d.append(
        "Собрать trust-triggers и вынести их в карточку и описание: breakfast, free Wi-Fi, airport transfer, 24/7 reception, best price guarantee — только если это реально доступно."
    )
    next_7d.append(
        "Запустить регулярные posts/updates под сценарии поиска: near landmark, budget stay, breakfast included, airport transfer, family stay."
    )
    if reviews_count < 120:
        next_7d.append(
            "Нарастить объём свежих отзывов по правильному сценарию: просить конкретику про локацию, чистоту, сервис и удобство проживания."
        )

    if not next_24h:
        next_24h.append("Уточнить позиционирование карточки и проверить, совпадает ли оно с ожиданиями гостей.")

    ongoing = [
        "Отвечать на новые отзывы так, чтобы усиливать реальное позиционирование объекта, доверие и сигналы видимости карточки.",
        "Публиковать свежие фото и updates минимум 1–2 раза в неделю.",
        "Регулярно проверять, не расходится ли обещание карточки с фактическим опытом гостя.",
    ]
    return {"next_24h": next_24h[:4], "next_7d": next_7d[:4], "ongoing": ongoing}


def _build_wellness_action_plan(
    *,
    has_description: bool,
    services_count: int,
    photos_count: int,
    unanswered_reviews_count: int,
) -> Dict[str, List[str]]:
    next_24h: List[str] = []
    next_7d: List[str] = []
    if not has_description:
        next_24h.append("Добавить сильное описание карточки: spa / massage / wellness center, процедуры, формат визита и кому это подходит.")
    if services_count <= 0:
        next_24h.append("Развернуть 10–15 ключевых процедур как отдельные SEO-единицы с ценами и понятным эффектом.")
    if unanswered_reviews_count > 0:
        next_24h.append("Ответить на отзывы не формально, а как на маркетинговый актив: усиливать доверие и локальный поиск.")
    if photos_count < 10:
        next_7d.append("Добавить конверсионные фото: фасад, кабинеты, оборудование, процесс процедур, атмосфера пространства.")
    next_7d.append("Проверить категории и атрибуты: Spa, Massage therapist, Wellness center, recovery / therapy.")
    next_7d.append("Запустить 3–5 posts: как проходит процедура, кейсы, оборудование, recovery journeys, спецпредложения.")
    if not next_24h:
        next_24h.append("Проверить, совпадает ли карточка с тем, как центр хотят находить в поиске.")
    ongoing = [
        "Публиковать 1–2 обновления в неделю и регулярно добавлять фото.",
        "Поддерживать услуги, цены и описания в актуальном состоянии.",
        "Собирать новые отзывы с деталями по процедурам и результатам.",
    ]
    return {"next_24h": next_24h[:4], "next_7d": next_7d[:4], "ongoing": ongoing}


def _build_medical_action_plan(
    *,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    unanswered_reviews_count: int,
) -> Dict[str, List[str]]:
    next_24h: List[str] = []
    next_7d: List[str] = []
    if not has_description:
        next_24h.append(
            "Добавить ясное описание карточки: специализации, какие проблемы решает клиника, как проходит первичный визит и кому подходит формат обращения."
        )
    if services_count <= 0:
        next_24h.append(
            "Разделить консультации, диагностику и процедуры на отдельные SEO-единицы, чтобы пациент понимал маршрут обращения ещё в карточке."
        )
    elif priced_services_count <= 0:
        next_24h.append(
            "Добавить цены или ориентиры по ключевым услугам: первичный приём, повторный приём, диагностика, основные процедуры."
        )
    if unanswered_reviews_count > 0:
        next_24h.append(
            "Ответить на отзывы так, чтобы усиливать доверие: объяснять формат помощи, внимание к пациенту и понятный следующий шаг."
        )
    if photos_count < 8:
        next_7d.append(
            "Добавить фото входа, ресепшен, кабинетов, оборудования и врачей в рабочей среде без визуального шума."
        )
    next_7d.append(
        "Проверить категории и атрибуты: clinic / medical center / diagnostics / rehabilitation / specialty doctor."
    )
    next_7d.append(
        "Подготовить 3–5 updates: как проходит приём, какие есть направления, как подготовиться к диагностике, когда обращаться."
    )
    if not next_24h:
        next_24h.append("Проверить, совпадает ли карточка с реальным маршрутом пациента: от запроса до записи.")
    ongoing = [
        "Поддерживать услуги, цены и описания в актуальном состоянии по основным направлениям.",
        "Регулярно отвечать на отзывы, снижая тревожность и усиливая доверие к клинике.",
        "Публиковать обновления по услугам, оборудованию, врачам и полезным сценариям обращения.",
    ]
    return {"next_24h": next_24h[:4], "next_7d": next_7d[:4], "ongoing": ongoing}


def _build_beauty_action_plan(
    *,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    unanswered_reviews_count: int,
    focus_terms: Optional[List[str]] = None,
) -> Dict[str, List[str]]:
    next_24h: List[str] = []
    next_7d: List[str] = []
    focus_text = ", ".join((focus_terms or [])[:3]) or "ключевые направления"
    if not has_description:
        next_24h.append(
            f"Добавить понятное описание карточки: основные направления ({focus_text}), для кого салон, ключевые услуги и что отличает мастеров или студию."
        )
    if services_count <= 0:
        next_24h.append(
            f"Развернуть ключевые услуги как отдельные SEO-единицы: {focus_text}, цены и понятные точки входа в запись."
        )
    elif priced_services_count <= 0:
        next_24h.append(
            "Добавить цены к ключевым услугам и выделить 5–10 главных процедур, чтобы карточка быстрее конвертировала в запись."
        )
    if unanswered_reviews_count > 0:
        next_24h.append(
            "Ответить на отзывы в стиле бренда: усиливать доверие, качество сервиса и повторную запись, а не просто благодарить формально."
        )
    if photos_count < 10:
        next_7d.append(
            "Добавить конверсионные фото: работы до/после, мастера, кабинеты, атмосфера салона и хиты услуг."
        )
    next_7d.append(
        f"Проверить категории и структуру услуг: салон, {focus_text} и другие реальные точки входа."
    )
    next_7d.append(
        "Запустить 3–5 updates: новинки, сезонные услуги, кейсы работ, спецпредложения и расписание записи."
    )
    if not next_24h:
        next_24h.append("Проверить, насколько карточка помогает выбрать услугу и записаться без лишних вопросов.")
    ongoing = [
        "Регулярно обновлять услуги, цены и фото работ по главным направлениям.",
        "Отвечать на отзывы так, чтобы усиливать повторную запись и доверие к мастерам.",
        "Поддерживать живую активность карточки через фото, кейсы и сезонные обновления.",
    ]
    return {"next_24h": next_24h[:4], "next_7d": next_7d[:4], "ongoing": ongoing}


def _build_fashion_action_plan(
    *,
    has_description: bool,
    services_count: int,
    photos_count: int,
    reviews_count: int,
) -> Dict[str, List[str]]:
    next_24h: List[str] = []
    next_7d: List[str] = []
    if not has_description:
        next_24h.append(
            "Переписать описание карточки под SEO спрос: custom dresses, bridal wear, stitching, designer studio, Lahore."
        )
    if services_count <= 0:
        next_24h.append(
            "Добавить 10–15 услуг как отдельные точки входа в спрос: bridal dresses, custom dresses, bridal consultation, formal wear, stitching, fittings."
        )
    if reviews_count < 15:
        next_24h.append(
            "Запустить review engine: собрать первые 15–30 отзывов через WhatsApp, после выдачи заказа и после примерки."
        )
    if photos_count < 10:
        next_7d.append(
            "Разбить фото на серии: bridal dresses, custom dresses, stitching process, fittings, готовые образы и детали пошива."
        )
    next_7d.append(
        "Проверить категории и позиционирование: fashion designer / bridal designer / custom dresses / stitching / boutique."
    )
    next_7d.append(
        "Запустить недельный контент-ритм: 1 post в неделю и 2–3 новых фото в неделю с кейсами, процессом и готовыми образами."
    )
    if not next_24h:
        next_24h.append("Проверить, понимает ли новый клиент из карточки, какие именно изделия здесь можно заказать и почему студия стоит внимания.")
    ongoing = [
        "Держать в карточке актуальные направления: bridal, formal, custom stitching, consultations и сезонные коллекции.",
        "Отвечать на каждый отзыв, усиливая trust layer через quality, fit, premium stitching и bridal expertise.",
        "Поддерживать живую карточку через weekly posts, новые фотосерии и кейсы клиентов.",
    ]
    return {"next_24h": next_24h[:4], "next_7d": next_7d[:4], "ongoing": ongoing}


def _build_food_action_plan(
    *,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    unanswered_reviews_count: int,
) -> Dict[str, List[str]]:
    next_24h: List[str] = []
    next_7d: List[str] = []
    if not has_description:
        next_24h.append(
            "Переписать описание карточки так, чтобы оно продавало не просто заведение, а сценарий визита: что это за кухня, зачем сюда идти, что попробовать первым и почему точка релевантна именно в этой локации."
        )
    if services_count <= 0:
        next_24h.append(
            "Собрать меню как входящий спрос: вынести 5–10 хитов, отдельные категории, фирменные блюда, завтраки/ужины/доставку, а не оставлять карточку без явных поводов выбрать заведение."
        )
    elif priced_services_count <= 0:
        next_24h.append(
            "Добавить цены хотя бы к ключевым позициям: без среднего чека и ориентиров по меню гость чаще уходит сравнивать другие места."
        )
    if unanswered_reviews_count > 0:
        next_24h.append(
            "Ответить на отзывы так, чтобы они продавали заведение дальше: вкус, сервис, скорость, атмосфера, посадка, takeaway/delivery и локальный контекст визита."
        )
    if photos_count < 10:
        next_7d.append(
            "Доснять конверсионную фотосерию: хиты меню крупным планом, интерьер, посадка, фасад, витрина/бар и реальный опыт гостя, а не случайный набор фотографий."
        )
    next_7d.append(
        "Проверить категории и атрибуты под реальный спрос: restaurant / cafe / breakfast / brunch / delivery / specialty coffee / bakery / kebab / dessert — в зависимости от формата точки."
    )
    next_7d.append(
        "Запустить 3–5 updates, которые дают повод прийти сейчас: сезонные блюда, новинки меню, lunch offers, завтраки, комбо, десерты, события и спецпозиции."
    )
    if not next_24h:
        next_24h.append("Проверить, считывается ли из карточки главный повод зайти именно сейчас: еда, атмосфера, скорость, формат визита или спецпозиции.")
    ongoing = [
        "Держать меню, цены и визуальные хиты в актуальном виде, чтобы карточка не выглядела устаревшей.",
        "Использовать отзывы как продолжение маркетинга: усиливать вкус, атмосферу, сервис и конкретные поводы выбрать заведение.",
        "Поддерживать ощущение живой точки через новинки, сезонные офферы, события и регулярные фотообновления.",
    ]
    return {"next_24h": next_24h[:4], "next_7d": next_7d[:4], "ongoing": ongoing}


def _build_fitness_action_plan(
    *,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    unanswered_reviews_count: int,
) -> Dict[str, List[str]]:
    next_24h: List[str] = []
    next_7d: List[str] = []
    if not has_description:
        next_24h.append(
            "Переписать описание карточки так, чтобы новичок сразу понимал формат: что это за студия, кому подходит, с какого уровня можно начать, какое оборудование используется и как попасть на первое занятие."
        )
    if services_count <= 0:
        next_24h.append(
            "Разделить направления как отдельные входы в спрос: пробное занятие, персоналка, мини-группа, reformer/pilates, yoga, recovery, абонементы и пакеты."
        )
    elif priced_services_count <= 0:
        next_24h.append(
            "Добавить цены или хотя бы понятные ориентиры по пробному занятию, персональному формату и абонементам, чтобы убрать страх первого шага."
        )
    if unanswered_reviews_count > 0:
        next_24h.append(
            "Ответить на отзывы так, чтобы усиливать доверие к тренерам, атмосфере студии, понятному прогрессу и комфорту новичка."
        )
    if photos_count < 10:
        next_7d.append(
            "Доснять студию как продукт: зал, reformer/оборудование, тренеров, групповые и персональные форматы, вход, ресепшен и реальную атмосферу занятий."
        )
    next_7d.append(
        "Проверить категории и атрибуты так, чтобы карточка закрывала реальные сценарии выбора: fitness studio / pilates / yoga / personal trainer / reformer / group classes."
    )
    next_7d.append(
        "Запустить 3–5 updates, которые снижают трение перед первой записью: расписание, новые группы, тренеры, пробные занятия, результаты клиентов и спецформаты."
    )
    if not next_24h:
        next_24h.append("Проверить, понятно ли из карточки, кому подходит студия, чем она отличается и как начать заниматься без лишних вопросов.")
    ongoing = [
        "Поддерживать в актуальном состоянии абонементы, форматы тренировок, тренеров и визуальную подачу пространства.",
        "Использовать отзывы как способ снижать тревогу первого визита и усиливать доверие к тренерам.",
        "Публиковать обновления про расписание, программы, пробные форматы и понятные точки входа в студию каждую неделю.",
    ]
    return {"next_24h": next_24h[:4], "next_7d": next_7d[:4], "ongoing": ongoing}


def _build_default_local_business_action_plan(
    *,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    unanswered_reviews_count: int,
) -> Dict[str, List[str]]:
    next_24h: List[str] = []
    next_7d: List[str] = []
    if not has_description:
        next_24h.append(
            "Добавить описание, которое объясняет бизнес как решение задачи: кто вы, кому помогаете, с чем к вам приходят и почему выбрать именно вас, а не соседнюю карточку."
        )
    if services_count <= 0:
        next_24h.append(
            "Собрать 5–10 ключевых услуг или товарных групп как отдельные точки входа в спрос, чтобы карточка перестала быть абстрактной визиткой."
        )
    elif priced_services_count <= 0:
        next_24h.append(
            "Добавить цены или понятные ориентиры по главным услугам: без этого клиент чаще откладывает решение и продолжает сравнение."
        )
    if unanswered_reviews_count > 0:
        next_24h.append(
            "Закрыть отзывы без ответа и превратить их в слой доверия: объяснять сервис, скорость, качество результата и как проходит работа."
        )
    if photos_count < 8:
        next_7d.append(
            "Доснять вход, команду, процесс работы, примеры результата и реальную среду сервиса, чтобы карточка выглядела живой и понятной."
        )
    next_7d.append(
        "Проверить категории, контакты и атрибуты, чтобы карточка соответствовала не общему профилю бизнеса, а конкретным коммерческим сценариям поиска."
    )
    next_7d.append(
        "Подготовить 3–5 updates, которые отвечают на реальный входящий спрос: кейсы, новые услуги, частые вопросы, сезонные предложения и рабочие процессы."
    )
    if not next_24h:
        next_24h.append("Проверить, понимает ли новый клиент из карточки, за чем именно сюда обращаться и что он получает на выходе.")
    ongoing = [
        "Поддерживать актуальность услуг, цен, фото и контактов, чтобы карточка не расходилась с реальностью.",
        "Регулярно отвечать на отзывы и превращать их в понятный social proof, а не просто закрывать долг.",
        "Держать карточку живой через кейсы, обновления и визуальные подтверждения реальной работы.",
    ]
    return {"next_24h": next_24h[:4], "next_7d": next_7d[:4], "ongoing": ongoing}


def _build_hospitality_issue_blocks(
    *,
    business_name: str,
    city: str,
    has_description: bool,
    has_real_services: bool,
    booking_offer_count: int,
    photos_count: int,
    reviews_count: int,
    unanswered_reviews_count: int,
    rating: Optional[float],
    top_positive: List[str],
    top_negative: List[str],
    expectation_mismatch: bool,
) -> List[Dict[str, Any]]:
    issue_blocks: List[Dict[str, Any]] = []

    if not has_description:
        issue_blocks.append(
            {
                "id": "positioning_description_gap",
                "section": "positioning",
                "priority": "high",
                "title": "Описание не продаёт объект под поисковое намерение",
                "problem": "Карточка не объясняет, что это за формат отдыха и кому он подходит.",
                "evidence": f"У объекта {business_name} нет сильного описания под сценарии поиска по {city}.",
                "impact": "Падает конверсия из просмотра карточки в клик и бронь.",
                "fix": "Добавить описание 500–1000 символов: формат объекта, nearby landmarks, сильные стороны, локация, кому подходит и какие ожидания важно выставить заранее.",
            }
        )

    if rating is None or rating < 4.2:
        issue_blocks.append(
            {
                "id": "rating_gap",
                "section": "reviews",
                "priority": "high",
                "title": "Репутация карточки ниже порога доверия для отеля",
                "problem": "Низкий рейтинг становится главным bottleneck для видимости и бронирований.",
                "evidence": f"Текущий рейтинг: {f'{rating:.1f}' if rating is not None else 'н/д'}. Для hotel-формата это уже влияет на выбор особенно сильно.",
                "impact": "Карточка хуже конвертирует в бронь и теряет часть показов по коммерческим сценариям.",
                "fix": "Дожать review engine: QR после заселения/выезда, WhatsApp-напоминание и ответы на каждый новый отзыв.",
            }
        )

    if reviews_count < 120:
        issue_blocks.append(
            {
                "id": "reviews_low_count",
                "section": "reviews",
                "priority": "medium",
                "title": "Объём review engine ещё не даёт устойчивого преимущества",
                "problem": "Карточке не хватает свежих управляемых отзывов, чтобы перекрывать слабую репутацию и усиливать social proof.",
                "evidence": f"Сейчас отзывов: {reviews_count}. Для hotel-кейса этого ещё мало, чтобы уверенно выигрывать локальную конкуренцию при среднем рейтинге.",
                "impact": "Репутация растёт медленно, а новый спрос дольше колеблется перед бронированием.",
                "fix": "Запустить сбор отзывов по сценарию после визита и просить конкретику про локацию, чистоту, сервис и удобство проживания.",
            }
        )

    if expectation_mismatch:
        negative_labels = ", ".join([_theme_label(item) for item in top_negative[:3]])
        issue_blocks.append(
            {
                "id": "expectation_mismatch",
                "section": "positioning",
                "priority": "high",
                "title": "Карточка слабо управляет ожиданиями гостей",
                "problem": "По отзывам видно повторяющиеся возражения, которые карточка не снимает заранее.",
                "evidence": f"В отзывах повторяются темы: {negative_labels}.",
                "impact": "Гости приходят с неверным ожиданием и оставляют более жёсткий негатив после заселения.",
                "fix": "Честно перепаковать позиционирование: не обещать больше, чем объект реально даёт, и заранее подсветить правильный сценарий проживания.",
            }
        )

    if not has_real_services or booking_offer_count > 0:
        issue_blocks.append(
            {
                "id": "services_booking_offers_gap",
                "section": "services",
                "priority": "high",
                "title": "Вместо услуг отображаются booking-offers или абстрактные позиции",
                "problem": "Карточка не показывает реальное предложение объекта как SEO-единицы.",
                "evidence": f"Booking-offer позиций: {booking_offer_count}. Реальных услуг/amenities: {'нет' if not has_real_services else 'есть, но блок загрязнён'}.",
                "impact": "Карточка хуже ранжируется под сценарные запросы и слабее продаёт ценность объекта.",
                "fix": "Показывать не агрегаторы бронирования, а реальное предложение: тип размещения, wellness/spa-процедуры, amenities, family-friendly features, parking, pool, kitchen.",
            }
        )

    if photos_count < 12:
        issue_blocks.append(
            {
                "id": "photo_story_gap",
                "section": "visual",
                "priority": "medium",
                "title": "Фото не формируют доверие и не снимают возражения",
                "problem": "Недостаточно визуального сценария what-you-really-get.",
                "evidence": f"Фото в карточке: {photos_count}. Для hospitality этого мало.",
                "impact": "Пользователь не видит, за что именно платит, и чаще уходит сравнивать другие объекты.",
                "fix": "Добавить фото фасада, бассейна, номера/апартаментов, кухни, парковки, пути до инфраструктуры и реального окружения.",
            }
        )

    if reviews_count >= 30 and unanswered_reviews_count > 0:
        issue_blocks.append(
            {
                "id": "reviews_unanswered",
                "section": "reviews",
                "priority": "medium",
                "title": "Отзывы есть, но ответы не дожимают доверие и видимость",
                "problem": "Карточка получает trust из отзывов, но не усиливает его регулярными ответами и управляемой рамкой.",
                "evidence": f"Отзывов: {reviews_count}, без ответа: {unanswered_reviews_count}. Позитивные темы: {', '.join([_theme_label(item) for item in top_positive[:3]]) or 'нужен разбор'}.",
                "impact": "Потенциал social proof не превращается в бронь, карточка выглядит менее живой и слабее поддерживает локальную видимость.",
                "fix": "Отвечать на отзывы с правильной рамкой: подчеркивать реальные сильные стороны, спокойно объяснять ограничения формата и поддерживать сигналы активности карточки.",
            }
        )

    issue_blocks.append(
        {
            "id": "category_positioning_gap",
            "section": "profile",
            "priority": "medium",
            "title": "Категории, атрибуты и trust-triggers недораскрывают формат объекта",
            "problem": "Карточка не использует все сигналы, которые помогают туристу быстро понять уровень и формат проживания.",
            "evidence": "Для hotel-кейсов особенно важны категории, nearby context и понятные promises: breakfast, Wi-Fi, airport transfer, family stay, 24/7 reception.",
            "impact": "Карточка теряет часть поисковых сценариев и хуже конвертирует холодный туристический трафик.",
            "fix": "Проверить категории и атрибуты, а в тексте и карточке явно показать реальные trust-triggers, если они доступны.",
        }
    )

    issue_blocks.append(
        {
            "id": "landmark_search_gap",
            "section": "seo",
            "priority": "medium",
            "title": "Карточка недоиспользует landmark и nearby-intent запросы",
            "problem": "Отель можно находить не только по названию, но и по сценариям рядом с ключевыми точками района.",
            "evidence": f"Для hospitality в {city} важны nearby-intent формулировки: old city / landmark / airport / family stay / budget stay.",
            "impact": "Карточка недополучает трафик из туристических сценариев поиска и слабее конкурирует с более конкретно упакованными объектами.",
            "fix": "Добавить в описание, posts и ответы на отзывы nearby-intent сценарии: near landmark, old city, airport convenience, family stay, quiet stay — только там, где это соответствует фактической локации объекта.",
        }
    )

    issue_blocks.append(
        {
            "id": "conversion_promises_gap",
            "section": "conversion",
            "priority": "medium",
            "title": "Карточка слабо продаёт trust-triggers и обещание проживания",
            "problem": "Даже при хорошей локации карточка не даёт пользователю быстрых причин выбрать именно этот объект.",
            "evidence": "Для hotel-кейса критичны короткие обещания и подтверждения формата: breakfast, Wi-Fi, airport transfer, 24/7 reception, best price guarantee.",
            "impact": "Пользователь видит объект, но не получает достаточно поводов перейти к бронированию или прямому контакту.",
            "fix": "Вынести реальные trust-triggers в описание, категории, ответы на отзывы и фото-подачу. Использовать только подтверждённые обещания, без маркетинговых преувеличений.",
        }
    )

    issue_blocks.append(
        {
            "id": "activity_signals_gap",
            "section": "activity",
            "priority": "medium",
            "title": "Недостаточно сигналов активности",
            "problem": "Карточка не выглядит как живой активный объект.",
            "evidence": "Для hospitality алгоритмы и пользователи ждут регулярные posts, фото и обновления.",
            "impact": "Снижается доверие, а карточка реже выигрывает по freshness и вовлечению.",
            "fix": "Добавить регулярные posts: процедуры, nearby tips, family stay, quiet stay, airport convenience, spa journeys.",
        }
    )

    issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    return issue_blocks


def _build_medical_issue_blocks(
    *,
    business_name: str,
    city: str,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    reviews_count: int,
    unanswered_reviews_count: int,
) -> List[Dict[str, Any]]:
    issue_blocks: List[Dict[str, Any]] = []
    if not has_description:
        issue_blocks.append(
            {
                "id": "positioning_description_gap",
                "section": "positioning",
                "priority": "high",
                "title": "Описание карточки не объясняет, как и с чем сюда обращаться",
                "problem": "Карточка не раскрывает специализацию, показания и формат приёма.",
                "evidence": f"У {business_name} нет сильного описания под медицинские сценарии поиска в {city}.",
                "impact": "Пациенту сложнее понять, подходит ли клиника под его запрос, и он уходит сравнивать другие варианты.",
                "fix": "Добавить описание: специализация, виды помощи, как проходит визит, кому подходит центр и какие ожидания нужно выставить заранее.",
            }
        )
    if services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_medical_gap",
                "section": "services",
                "priority": "high",
                "title": "Услуги не раскрывают маршрут пациента",
                "problem": "Карточка не разделяет приём, диагностику и процедуры как отдельные точки входа в спрос.",
                "evidence": f"Услуг в срезе: {services_count}.",
                "impact": "Карточка теряет поисковые сценарии и хуже переводит интерес в запись.",
                "fix": "Добавить отдельные услуги: первичный приём, повторный приём, диагностика, ключевые процедуры и программы восстановления.",
            }
        )
    elif priced_services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_no_price",
                "section": "services",
                "priority": "medium",
                "title": "По ключевым услугам нет ценовых ориентиров",
                "problem": "Пациент не понимает порядок стоимости и чаще откладывает обращение.",
                "evidence": f"С ценами: {priced_services_count} из {services_count}.",
                "impact": "Падает доверие и растёт число лишних уточняющих вопросов.",
                "fix": "Добавить цены или понятные диапазоны по главным услугам и консультациям.",
            }
        )
    if photos_count < 8:
        issue_blocks.append(
            {
                "id": "photo_story_gap",
                "section": "visual",
                "priority": "medium",
                "title": "Фото не усиливают доверие к клинике",
                "problem": "Пользователь не видит пространство, оборудование и реальный уровень сервиса.",
                "evidence": f"Фото в карточке: {photos_count}.",
                "impact": "Сложнее сформировать ощущение надёжности и качества до визита.",
                "fix": "Добавить фото входа, ресепшен, кабинетов, оборудования, врачей и навигации внутри клиники.",
            }
        )
    if reviews_count >= 15:
        issue_blocks.append(
            {
                "id": "reviews_trust_underused",
                "section": "reviews",
                "priority": "medium",
                "title": "Отзывы дают доверие, но не работают как управляемый слой репутации",
                "problem": "Карточка не использует ответы на отзывы, чтобы снижать тревожность и усиливать понятность лечения.",
                "evidence": f"Отзывов: {reviews_count}, без ответа: {unanswered_reviews_count}.",
                "impact": "Social proof есть, но он хуже конвертируется в запись.",
                "fix": "Отвечать на отзывы так, чтобы подсвечивать внимательность, понятный маршрут пациента и доверие к специалистам.",
            }
        )
    issue_blocks.append(
        {
            "id": "category_positioning_gap",
            "section": "profile",
            "priority": "medium",
            "title": "Категории и профиль клиники можно усилить",
            "problem": "Слишком общий профиль размывает медицинские сценарии поиска.",
            "evidence": "Для medical вертикали особенно важны специализация, направления, атрибуты и Q&A по формату визита.",
            "impact": "Карточка слабее ранжируется по узким медицинским запросам и хуже отрабатывает доверие.",
            "fix": "Проверить категории, атрибуты, специализации и добавить Q&A: как записаться, как подготовиться, какие есть направления и форматы консультации.",
        }
    )
    issue_blocks.append(
        {
            "id": "activity_signals_gap",
            "section": "activity",
            "priority": "medium",
            "title": "Карточке не хватает управляемой активности",
            "problem": "Нет достаточного числа обновлений, которые показывают, что клиника живая и экспертная.",
            "evidence": "Пациенты и алгоритмы ждут понятные обновления: врачи, услуги, диагностика, полезные сценарии обращения.",
            "impact": "Снижается доверие и карточка недобирает по freshness и экспертности.",
            "fix": "Публиковать updates о направлениях, форматах приёма, оборудовании, подготовке к визиту и понятных сценариях обращения.",
        }
    )
    issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    return issue_blocks


def _build_beauty_issue_blocks(
    *,
    business_name: str,
    city: str,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    reviews_count: int,
    unanswered_reviews_count: int,
    focus_terms: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    issue_blocks: List[Dict[str, Any]] = []
    focus_text = ", ".join((focus_terms or [])[:3]) or "ключевые направления"
    if not has_description:
        issue_blocks.append(
            {
                "id": "positioning_description_gap",
                "section": "positioning",
                "priority": "high",
                "title": "Описание карточки не продаёт салон под реальный спрос",
                "problem": f"Карточка не объясняет, какие направления здесь ключевые ({focus_text}) и почему клиенту стоит выбрать именно этот бизнес.",
                "evidence": f"У {business_name} нет сильного beauty-описания под поиск в {city}.",
                "impact": "Падает конверсия из просмотра в запись и карточка хуже отрабатывает локальные запросы.",
                "fix": f"Добавить описание: главные направления ({focus_text}), для кого салон, ключевые услуги, чем отличаются мастера и в чём удобство записи.",
            }
        )
    if services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_beauty_gap",
                "section": "services",
                "priority": "high",
                "title": "Услуги не оформлены как понятные точки входа в запись",
                "problem": "Карточка не показывает ключевые beauty-услуги по отдельности.",
                "evidence": f"Услуг в срезе: {services_count}.",
                "impact": "Пользователь не находит нужную процедуру и уходит к конкурентам с более понятной карточкой.",
                "fix": "Выделить ключевые услуги по направлениям: эпиляция, косметология, маникюр, brow/lashes, массаж и другие основные входы в спрос.",
            }
        )
    elif priced_services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_no_price",
                "section": "services",
                "priority": "medium",
                "title": "Услуги есть, но без ценовых ориентиров",
                "problem": "Клиенту сложно быстро принять решение о записи.",
                "evidence": f"С ценами: {priced_services_count} из {services_count}.",
                "impact": "Теряются клики и растёт число лишних вопросов в директ/мессенджеры.",
                "fix": "Добавить цены или диапазоны к 5–10 самым коммерческим услугам.",
            }
        )
    if photos_count < 10:
        issue_blocks.append(
            {
                "id": "photo_story_gap",
                "section": "visual",
                "priority": "medium",
                "title": "Фото не продают качество услуг и результат",
                "problem": "Карточка не даёт достаточного визуального доверия.",
                "evidence": f"Фото в карточке: {photos_count}.",
                "impact": "Пользователь не видит результат, атмосферу и уровень мастеров.",
                "fix": "Добавить фото работ до/после, мастеров, кабинетов, атмосферы и ключевых услуг.",
            }
        )
    if reviews_count >= 15:
        issue_blocks.append(
            {
                "id": "reviews_marketing_underused",
                "section": "reviews",
                "priority": "medium",
                "title": "Отзывы есть, но они не работают как маркетинговый актив",
                "problem": "Карточка не превращает отзывы в управляемое доверие и повторную запись.",
                "evidence": f"Отзывов: {reviews_count}, без ответа: {unanswered_reviews_count}.",
                "impact": "Social proof есть, но он слабее влияет на выбор и лояльность.",
                "fix": "Отвечать на отзывы в стиле бренда, подчеркивая сервис, комфорт, качество работ и результат.",
            }
        )
    issue_blocks.append(
        {
            "id": "category_positioning_gap",
            "section": "profile",
            "priority": "medium",
                "title": "Категории и направления можно сделать точнее",
                "problem": "Слишком общая структура карточки размывает коммерческие запросы.",
            "evidence": f"Для beauty вертикали особенно важны точные категории, направления услуг ({focus_text}), цены и регулярные фото-обновления.",
            "impact": "Карточка слабее отрабатывает поисковые запросы по конкретным процедурам.",
            "fix": f"Проверить категории и разделить направления так, чтобы клиент быстро находил {focus_text} без лишнего поиска.",
        }
    )
    issue_blocks.append(
        {
            "id": "activity_signals_gap",
            "section": "activity",
            "priority": "medium",
            "title": "Карточке не хватает сигналов активности",
            "problem": "Если в карточке мало новых фото, кейсов и updates, она выглядит менее живой и менее желанной.",
            "evidence": "Для beauty особенно важны свежие работы, сезонные офферы, новинки и ритм публикаций.",
            "impact": "Снижается доверие и карточка недобирает по freshness и вовлечению.",
            "fix": "Публиковать фото работ, новинки услуг, сезонные предложения и небольшие кейсы 1–2 раза в неделю.",
        }
    )
    issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    return issue_blocks


def _build_wellness_issue_blocks(
    *,
    business_name: str,
    city: str,
    has_description: bool,
    services_count: int,
    photos_count: int,
    reviews_count: int,
    unanswered_reviews_count: int,
) -> List[Dict[str, Any]]:
    issue_blocks: List[Dict[str, Any]] = []
    if not has_description:
        issue_blocks.append(
            {
                "id": "positioning_description_gap",
                "section": "positioning",
                "priority": "high",
                "title": "Описание карточки не продаёт центр под поисковое намерение",
                "problem": "Карточка не объясняет, это spa, массажный центр, wellness space или восстановительный формат.",
                "evidence": f"У {business_name} нет сильного SEO-описания под сценарии поиска в {city}.",
                "impact": "Точка недобирает локальный трафик и хуже конвертирует в запись.",
                "fix": "Добавить описание 500–1000 символов: ключевые процедуры, формат, оборудование, кому подходит и в чём УТП центра.",
            }
        )
    if services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_seo_gap",
                "section": "services",
                "priority": "high",
                "title": "Услуги не оформлены как SEO-единицы",
                "problem": "В карточке нет понятного списка процедур с ценами и сценариями выбора.",
                "evidence": f"Услуг в срезе: {services_count}.",
                "impact": "Карточка теряет показы и клики по коммерческим запросам вроде massage, spa, wellness center, recovery therapy.",
                "fix": "Развернуть процедуры поштучно: Hydromassage, RF-lifting, body recovery, detox, massage therapy, vacuum massage и т.д.",
            }
        )
    if photos_count < 10:
        issue_blocks.append(
            {
                "id": "photo_story_gap",
                "section": "visual",
                "priority": "medium",
                "title": "Фото не формируют доверие и не продают процедуры",
                "problem": "Не хватает структуры фото и конверсионного визуального слоя.",
                "evidence": f"Фото в карточке: {photos_count}.",
                "impact": "Пользователь не понимает уровень центра, оборудование и как выглядит сам визит.",
                "fix": "Добавить фото входа, кабинетов, оборудования, процесса процедур и атмосферных зон центра.",
            }
        )
    if reviews_count >= 20:
        issue_blocks.append(
            {
                "id": "reviews_marketing_underused",
                "section": "reviews",
                "priority": "medium",
                "title": "Отзывы сильные, но не используются как маркетинговый актив",
                "problem": "Отзывы дают доверие, но карточка почти не превращает их в SEO и conversion layer.",
                "evidence": f"Отзывов: {reviews_count}, без ответа: {unanswered_reviews_count}.",
                "impact": "Потенциал social proof недорабатывает и не усиливает запись.",
                "fix": "Отвечать на отзывы с ключевыми словами, просить детали о процедурах и собирать новые отзывы после визита.",
            }
        )
    issue_blocks.append(
        {
            "id": "category_positioning_gap",
            "section": "profile",
            "priority": "medium",
            "title": "Категории и позиционирование можно усилить",
            "problem": "Карточка может терять часть поисковых сценариев из-за слишком общего профиля.",
            "evidence": "Для wellness/spa особенно важны категории, атрибуты и Q&A по процедурам, языкам и записи.",
            "impact": "Слабее отрабатываются запросы вроде spa, massage therapist, wellness center, detox, recovery.",
            "fix": "Проверить и усилить категории, добавить Q&A и локальные связки с партнёрами вокруг точки.",
        }
    )
    issue_blocks.append(
        {
            "id": "activity_signals_gap",
            "section": "activity",
            "priority": "medium",
            "title": "Недостаточно сигналов активности",
            "problem": "Карточка выглядит менее живой, чем могла бы.",
            "evidence": "Алгоритмы и пользователи ждут posts, новые фото, ответы на отзывы и обновляемые услуги.",
            "impact": "Снижается доверие и карточка реже выигрывает по freshness.",
            "fix": "Публиковать кейсы, объяснения процедур, акционные поводы и process-content 1–2 раза в неделю.",
        }
    )
    issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    return issue_blocks


def _build_fashion_issue_blocks(
    *,
    business_name: str,
    city: str,
    has_description: bool,
    services_count: int,
    photos_count: int,
    reviews_count: int,
) -> List[Dict[str, Any]]:
    issue_blocks: List[Dict[str, Any]] = []
    if not has_description:
        issue_blocks.append(
            {
                "id": "positioning_description_gap",
                "section": "positioning",
                "priority": "high",
                "title": "Описание карточки не продаёт студию под поисковое намерение",
                "problem": "Карточка не объясняет, это bridal designer, custom dresses studio или atelier под индивидуальный пошив.",
                "evidence": f"У {business_name} нет сильного fashion-описания под сценарии поиска в {city}.",
                "impact": "Карточка хуже ранжируется по designer и bridal запросам и слабее конвертирует в обращение.",
                "fix": "Добавить описание с ключами custom dresses, bridal wear, stitching, designer studio, Lahore и объяснить, для кого студия подходит лучше всего.",
            }
        )
    if services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_missing",
                "section": "services",
                "priority": "high",
                "title": "Нет структуры услуг под bridal и custom спрос",
                "problem": "Карточка не показывает понятные направления: bridal dresses, custom dresses, stitching, fittings, formal wear.",
                "evidence": f"Сейчас услуг: {services_count}.",
                "impact": "Пользователь не понимает, что именно можно заказать, и карточка теряет коммерческие поисковые сценарии.",
                "fix": "Добавить 10–15 услуг с ключами: bridal dresses, custom dresses, bridal consultation, formal wear, stitching, fittings.",
            }
        )
    if photos_count < 10:
        issue_blocks.append(
            {
                "id": "photo_story_gap",
                "section": "visual",
                "priority": "medium",
                "title": "Фото есть, но они не работают как fashion-каталог",
                "problem": "Карточка не разбивает визуал по bridal dresses, casual dresses, stitching process и готовым образам.",
                "evidence": f"Фото в карточке: {photos_count}.",
                "impact": "Фото не усиливают SEO, доверие и ощущение реального качества пошива.",
                "fix": "Собрать фото в серии: bridal dresses, custom looks, stitching process, fittings, детали ткани и готовые образы.",
            }
        )
    if reviews_count < 15:
        issue_blocks.append(
            {
                "id": "reviews_low_count",
                "section": "reviews",
                "priority": "high" if reviews_count <= 5 else "medium",
                "title": "Рейтинг есть, но доверия пока нет",
                "problem": "Один высокий рейтинг ещё не создаёт устойчивого trust layer для нового клиента.",
                "evidence": f"Сейчас отзывов: {reviews_count}. Для designer / bridal кейса ориентир — 15–30+.",
                "impact": "Карточка не получает достаточного social proof и слабее растёт в показах.",
                "fix": "Довести карточку минимум до 15–30 отзывов: WhatsApp aftercare, просьба после выдачи заказа и после примерки, ответы на каждый отзыв с ключевыми словами.",
            }
        )
    issue_blocks.append(
        {
            "id": "activity_signals_gap",
            "section": "activity",
            "priority": "medium",
            "title": "Карточка выглядит как неактивное fashion-портфолио",
            "problem": "Нет регулярных posts и фотосерий, которые показывают новые работы, кейсы и процесс пошива.",
            "evidence": "Для fashion/designer карточки важны регулярные posts, фото новых работ, bridal кейсы и процессы fittings/stitching.",
            "impact": "Алгоритм считает карточку менее живой, а пользователю сложнее поверить в актуальность студии.",
            "fix": "Публиковать 1 post в неделю и добавлять 2–3 новых фото в неделю: новые работы, bridal кейсы, процессы и готовые изделия.",
        }
    )
    issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    return issue_blocks


def _build_food_issue_blocks(
    *,
    business_name: str,
    city: str,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    reviews_count: int,
    unanswered_reviews_count: int,
) -> List[Dict[str, Any]]:
    issue_blocks: List[Dict[str, Any]] = []
    if not has_description:
        issue_blocks.append(
            {
                "id": "positioning_description_gap",
                "section": "positioning",
                "priority": "high",
                "title": "Описание карточки не продаёт формат заведения",
                "problem": "Карточка не объясняет кухню, сценарий визита и зачем сюда идти именно в этом районе.",
                "evidence": f"У {business_name} нет сильного food-описания под поиск в {city}.",
                "impact": "Падает конверсия из просмотра карточки в визит, заказ или бронь.",
                "fix": "Добавить описание: формат заведения, хиты меню, атмосфера, сценарии визита и локальные поводы прийти.",
            }
        )
    if services_count <= 0:
        issue_blocks.append(
            {
                "id": "menu_structure_gap",
                "section": "services",
                "priority": "high",
                "title": "Меню не оформлено как точки входа в спрос",
                "problem": "Карточка не показывает ключевые блюда, категории и поводы выбрать именно это заведение.",
                "evidence": f"Позиции меню в срезе: {services_count}.",
                "impact": "Карточка теряет показы по коммерческим сценариям вроде завтрак, ужин, specialty coffee, dessert, delivery.",
                "fix": "Развернуть хиты меню, категории и фирменные позиции как отдельные SEO-единицы с понятными названиями и ценами.",
            }
        )
    elif priced_services_count <= 0:
        issue_blocks.append(
            {
                "id": "menu_no_price",
                "section": "services",
                "priority": "medium",
                "title": "В меню нет ценовых ориентиров",
                "problem": "Гость не понимает средний чек и быстрее уходит сравнивать альтернативы.",
                "evidence": f"С ценами: {priced_services_count} из {services_count}.",
                "impact": "Снижается CTR и растёт число сомнений перед визитом или заказом.",
                "fix": "Добавить цены к ключевым блюдам, сетам, завтракам, напиткам и другим точкам входа в спрос.",
            }
        )
    if photos_count < 10:
        issue_blocks.append(
            {
                "id": "photo_story_gap",
                "section": "visual",
                "priority": "medium",
                "title": "Фото не продают еду и атмосферу",
                "problem": "Карточка не показывает, как выглядит реальный опыт гостя.",
                "evidence": f"Фото в карточке: {photos_count}.",
                "impact": "Гость не получает нужного эмоционального сигнала и чаще уходит к более визуально сильным конкурентам.",
                "fix": "Добавить фото хитов меню, интерьера, посадки, фасада, витрины, бара и реальной подачи блюд.",
            }
        )
    if reviews_count >= 15:
        issue_blocks.append(
            {
                "id": "reviews_marketing_underused",
                "section": "reviews",
                "priority": "medium",
                "title": "Отзывы есть, но недорабатывают как маркетинговый слой",
                "problem": "Карточка не превращает отзывы в управляемое доверие по еде, сервису и атмосфере.",
                "evidence": f"Отзывов: {reviews_count}, без ответа: {unanswered_reviews_count}.",
                "impact": "Social proof есть, но он слабее влияет на выбор заведения.",
                "fix": "Отвечать на отзывы так, чтобы усиливать вкус, сервис, скорость, атмосферу и локальный контекст визита.",
            }
        )
    issue_blocks.append(
        {
            "id": "activity_signals_gap",
            "section": "activity",
            "priority": "medium",
            "title": "Карточке не хватает свежих сигналов активности",
            "problem": "Нет достаточного числа поводов вернуться к карточке и выбрать заведение прямо сейчас.",
            "evidence": "Для food особенно важны новинки меню, сезонные предложения, события и визуально сильные обновления.",
            "impact": "Карточка хуже работает на повторные визиты и ситуативный спрос.",
            "fix": "Публиковать новинки меню, special dishes, завтраки, brunch, события и сезонные поводы 1–2 раза в неделю.",
        }
    )
    issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    return issue_blocks


def _build_fitness_issue_blocks(
    *,
    business_name: str,
    city: str,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    reviews_count: int,
    unanswered_reviews_count: int,
) -> List[Dict[str, Any]]:
    issue_blocks: List[Dict[str, Any]] = []
    if not has_description:
        issue_blocks.append(
            {
                "id": "positioning_description_gap",
                "section": "positioning",
                "priority": "high",
                "title": "Описание карточки не продаёт формат тренировок",
                "problem": "Карточка не объясняет уровень, формат занятий, оборудование и сценарий входа для нового клиента.",
                "evidence": f"У {business_name} нет сильного fitness-описания под спрос в {city}.",
                "impact": "Падает конверсия из просмотра в пробную запись и абонемент.",
                "fix": "Добавить описание: групповой/персональный формат, для кого студия, что по уровню, оборудованию и как начать заниматься.",
            }
        )
    if services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_fitness_gap",
                "section": "services",
                "priority": "high",
                "title": "Направления тренировок не оформлены как отдельные входы в спрос",
                "problem": "Карточка не показывает, какие именно форматы можно купить или попробовать.",
                "evidence": f"Направлений/абонементов в срезе: {services_count}.",
                "impact": "Карточка теряет трафик по запросам вроде pilates, yoga, group training, personal training, reformer.",
                "fix": "Выделить отдельные форматы: пробное занятие, групповая тренировка, персональная тренировка, абонементы, reformer / studio programs.",
            }
        )
    elif priced_services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_no_price",
                "section": "services",
                "priority": "medium",
                "title": "Нет ценовых ориентиров по тренировкам и абонементам",
                "problem": "Пользователь не понимает стоимость входа и откладывает решение.",
                "evidence": f"С ценами: {priced_services_count} из {services_count}.",
                "impact": "Падает конверсия в пробное посещение и покупку абонемента.",
                "fix": "Добавить цены или ориентиры для пробного занятия, персоналки и основных абонементов.",
            }
        )
    if photos_count < 10:
        issue_blocks.append(
            {
                "id": "photo_story_gap",
                "section": "visual",
                "priority": "medium",
                "title": "Фото не показывают формат тренировок и пространство",
                "problem": "Карточка не даёт понятного визуального сигнала о студии, тренерах и оборудовании.",
                "evidence": f"Фото в карточке: {photos_count}.",
                "impact": "Новому клиенту сложнее представить, как всё устроено, и он чаще уходит сравнивать другие студии.",
                "fix": "Добавить фото пространства, оборудования, тренеров, групповых и персональных тренировок, входа и атмосферы.",
            }
        )
    if reviews_count >= 15:
        issue_blocks.append(
            {
                "id": "reviews_marketing_underused",
                "section": "reviews",
                "priority": "medium",
                "title": "Отзывы не дорабатывают как слой доверия к тренерам и результату",
                "problem": "Карточка не использует отзывы, чтобы снижать страх первого визита и усиливать доверие к студии.",
                "evidence": f"Отзывов: {reviews_count}, без ответа: {unanswered_reviews_count}.",
                "impact": "Social proof есть, но он хуже конвертируется в запись на тренировку.",
                "fix": "Отвечать на отзывы так, чтобы усиливать атмосферу, работу тренеров, понятный прогресс и комфорт новичка.",
            }
        )
    issue_blocks.append(
        {
            "id": "activity_signals_gap",
            "section": "activity",
            "priority": "medium",
            "title": "Карточке не хватает сигналов живой студии",
            "problem": "Мало свежих поводов зайти в карточку и начать заниматься именно сейчас.",
            "evidence": "Для fitness важны расписание, новые группы, пробные форматы, тренеры и регулярные updates.",
            "impact": "Карточка хуже работает на входящий спрос и повторный интерес.",
            "fix": "Публиковать updates про расписание, тренеров, пробные занятия, мини-группы, абонементы и новые программы.",
        }
    )
    issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    return issue_blocks


def _build_default_local_business_issue_blocks(
    *,
    business_name: str,
    city: str,
    has_description: bool,
    services_count: int,
    priced_services_count: int,
    photos_count: int,
    reviews_count: int,
    unanswered_reviews_count: int,
) -> List[Dict[str, Any]]:
    issue_blocks: List[Dict[str, Any]] = []
    if not has_description:
        issue_blocks.append(
            {
                "id": "positioning_description_gap",
                "section": "positioning",
                "priority": "high",
                "title": "Описание карточки не объясняет ценность бизнеса",
                "problem": "Карточка не даёт понять, что это за бизнес, для кого он и с чем сюда обращаться.",
                "evidence": f"У {business_name} нет сильного описания под локальный спрос в {city}.",
                "impact": "Падает доверие и карточка хуже конвертирует в обращение.",
                "fix": "Добавить описание: кто вы, какие задачи решаете, в чём сильные стороны и что клиент получает на выходе.",
            }
        )
    if services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_missing",
                "section": "services",
                "priority": "high",
                "title": "Нет понятной структуры услуг или предложения",
                "problem": "Карточка слишком абстрактна и не показывает точки входа в спрос.",
                "evidence": f"Сейчас услуг: {services_count}.",
                "impact": "Клиенту сложно быстро понять, зачем сюда обращаться.",
                "fix": "Собрать ключевые услуги или категории предложения как отдельные, понятные и коммерчески полезные позиции.",
            }
        )
    elif priced_services_count <= 0:
        issue_blocks.append(
            {
                "id": "services_no_price",
                "section": "services",
                "priority": "medium",
                "title": "Нет ценовых ориентиров",
                "problem": "Карточка не помогает быстро оценить порог входа.",
                "evidence": f"С ценами: {priced_services_count} из {services_count}.",
                "impact": "Пользователь чаще откладывает обращение и продолжает сравнение.",
                "fix": "Добавить цены или диапазоны к главным услугам, чтобы снизить трение перед первым контактом.",
            }
        )
    if photos_count < 8:
        issue_blocks.append(
            {
                "id": "photo_story_gap",
                "section": "visual",
                "priority": "medium",
                "title": "Фото не дают понятного визуального доверия",
                "problem": "Карточка не показывает вход, процесс, команду и результат.",
                "evidence": f"Фото в карточке: {photos_count}.",
                "impact": "Сложнее убедить клиента в реальности и качестве предложения.",
                "fix": "Добавить фото входа, команды, процесса работы, пространства и ключевых результатов.",
            }
        )
    if reviews_count >= 15:
        issue_blocks.append(
            {
                "id": "reviews_marketing_underused",
                "section": "reviews",
                "priority": "medium",
                "title": "Отзывы есть, но не управляются как слой доверия",
                "problem": "Карточка не превращает отзывы в понятный social proof.",
                "evidence": f"Отзывов: {reviews_count}, без ответа: {unanswered_reviews_count}.",
                "impact": "Доверие есть, но работает слабее, чем могло бы.",
                "fix": "Отвечать на отзывы так, чтобы подчеркивать качество сервиса, скорость, результат и надёжность бизнеса.",
            }
        )
    issue_blocks.append(
        {
            "id": "activity_signals_gap",
            "section": "activity",
            "priority": "medium",
            "title": "Карточке не хватает сигналов активности",
            "problem": "Нет достаточного числа обновлений, чтобы карточка выглядела живой и современной.",
            "evidence": "Для локального бизнеса важны регулярные фото, updates, ответы на отзывы и актуальные услуги.",
            "impact": "Снижается freshness, доверие и вероятность обращения.",
            "fix": "Публиковать обновления, кейсы, новости и новые фото на регулярной основе.",
        }
    )
    issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    return issue_blocks


def build_lead_card_preview_snapshot(lead: Dict[str, Any]) -> Dict[str, Any]:
    rating_risk_max = policy_value("rating", "risk_max", 4.4)
    rating_target_min = policy_value("rating", "target_min", 4.7)
    reviews_target_min = int(policy_value("reviews", "target_min", 30))
    strong_min = policy_value("health_thresholds", "strong_min", 80.0)
    growth_min = policy_value("health_thresholds", "growth_min", 55.0)
    profile_weight = policy_value("weights", "profile", 0.20)
    reputation_weight = policy_value("weights", "reputation", 0.35)
    services_weight = policy_value("weights", "services", 0.30)
    activity_weight = policy_value("weights", "activity", 0.15)

    lead_name = str(lead.get("name") or "Лид").strip() or "Лид"
    business_type = str(lead.get("category") or lead.get("business_type") or "").strip() or "Локальный бизнес"
    raw_city = str(lead.get("city") or "").strip()
    address = str(lead.get("address") or "").strip()
    city = raw_city
    if not city and address:
        city = str(address.split(",", 1)[0] or "").strip()
    snapshot = _resolve_lead_business_snapshot(lead)
    lead_import_payload = _extract_lead_import_payload(lead)
    business = snapshot.get("business") or {}
    imported_services_preview = lead_import_payload.get("services_preview") if isinstance(lead_import_payload.get("services_preview"), list) else []
    snapshot_services_preview = snapshot.get("services_preview") if isinstance(snapshot.get("services_preview"), list) else []
    profile_overview = {"category": lead.get("category")}
    profile_service_names: List[str] = []
    for item in snapshot_services_preview[:20]:
        if isinstance(item, dict):
            profile_service_names.append(str(item.get("current_name") or item.get("suggested_name") or "").strip())
    for item in imported_services_preview[:20]:
        if isinstance(item, dict):
            profile_service_names.append(str(item.get("current_name") or item.get("suggested_name") or item.get("name") or "").strip())
    profile_service_names = [item for item in profile_service_names if item]
    beauty_focus_terms = _derive_beauty_focus_terms(profile_service_names, str(lead.get("description") or ""))
    if profile_service_names:
        profile_overview["service_names"] = profile_service_names
    audit_profile = _detect_audit_profile(
        business.get("business_type") or business_type,
        business.get("name") or lead_name,
        profile_overview,
    )

    rating_raw = snapshot.get("rating") if snapshot.get("rating") is not None else lead.get("rating")
    rating = _extract_numeric(rating_raw)
    imported_reviews_count = _extract_int(
        lead_import_payload.get("reviews_count")
        if lead_import_payload.get("reviews_count") is not None
        else (lead.get("reviews_count") or 0)
    )
    snapshot_reviews_count = _extract_int(snapshot.get("reviews_count") or 0)
    reviews_count = imported_reviews_count if imported_reviews_count > 0 else snapshot_reviews_count
    parsed_contacts = snapshot.get("parsed_contacts") or {}
    has_website = bool(str(lead.get("website") or parsed_contacts.get("website") or business.get("website") or "").strip())
    has_phone = bool(str(lead.get("phone") or parsed_contacts.get("phone") or business.get("phone") or "").strip())
    has_email = bool(str(lead.get("email") or parsed_contacts.get("email") or business.get("email") or "").strip())
    has_messenger = bool(
        str(lead.get("telegram_url") or parsed_contacts.get("telegram_url") or "").strip()
        or str(lead.get("whatsapp_url") or parsed_contacts.get("whatsapp_url") or "").strip()
        or _safe_json(lead.get("messenger_links_json"))
        or parsed_contacts.get("social_links")
        or lead_import_payload.get("social_links")
    )

    imported_services_total_count = _extract_int(lead_import_payload.get("services_total_count") or len(imported_services_preview) or 0)
    imported_services_with_price_count = _extract_int(lead_import_payload.get("services_with_price_count") or 0)
    snapshot_services_count = _extract_int(snapshot.get("services_count") or 0)
    snapshot_priced_services_count = _extract_int(snapshot.get("priced_services_count") or 0)
    services_count = max(snapshot_services_count, imported_services_total_count)
    priced_services_count = max(snapshot_priced_services_count, imported_services_with_price_count)
    unanswered_reviews_count = _extract_int(snapshot.get("unanswered_reviews_count") or 0)
    imported_photos = lead_import_payload.get("photos") if isinstance(lead_import_payload.get("photos"), list) else []
    snapshot_photos = snapshot.get("photo_urls") if isinstance(snapshot.get("photo_urls"), list) else []
    effective_photos = imported_photos if imported_photos else snapshot_photos
    photos_count = _extract_int(snapshot.get("photos_count") or len(effective_photos) or 0)
    news_count = _extract_int(snapshot.get("news_count") or 0)
    has_recent_activity = bool(snapshot.get("has_recent_activity"))
    cadence_news_min = int(policy_value("cadence", "news_posts_per_month_min", 4))
    cadence_photos_min = int(policy_value("cadence", "photos_per_month_min", 8))
    cadence_response_hours_max = int(policy_value("cadence", "reviews_response_hours_max", 48))
    photos_state = "good" if photos_count >= cadence_photos_min else ("weak" if photos_count > 0 else "missing")

    profile_score = 100
    if not has_website:
        profile_score -= 12
    if not has_phone:
        profile_score -= 10
    if not (has_email or has_messenger):
        profile_score -= 8
    if not str(lead.get("source_url") or "").strip():
        profile_score -= 10
    if not str(lead.get("address") or "").strip():
        profile_score -= 8
    profile_score = max(35, min(100, profile_score))

    reputation_score = 100
    if rating is None:
        reputation_score -= 18
    elif rating < rating_risk_max:
        reputation_score -= 28
    elif rating < rating_target_min:
        reputation_score -= 12
    if reviews_count < max(1, reviews_target_min // 2):
        reputation_score -= 16
    elif reviews_count < reviews_target_min:
        reputation_score -= 8
    reputation_score = max(30, min(100, reputation_score))

    service_score = 48
    if services_count <= 0:
        service_score -= 20
    if priced_services_count <= 0:
        service_score -= 8
    service_score = max(20, min(100, service_score))

    activity_score = 42
    if has_recent_activity:
        activity_score += 12
    if news_count > 0:
        activity_score += 6
    activity_score = max(20, min(100, activity_score))

    summary_score = round(
        profile_score * profile_weight
        + reputation_score * reputation_weight
        + service_score * services_weight
        + activity_score * activity_weight
    )

    if summary_score >= strong_min:
        health_level = "strong"
        health_label = "Сильная карточка"
    elif summary_score >= growth_min:
        health_level = "growth"
        health_label = "Есть точки роста"
    else:
        health_level = "risk"
        health_label = "Карточка теряет клиентов"

    raw_services_preview = snapshot_services_preview or imported_services_preview
    booking_offer_count = 0
    services_preview: List[Dict[str, Any]] = []
    hospitality_mode = audit_profile == "hospitality"
    for item in raw_services_preview:
        if not isinstance(item, dict):
            continue
        current_name = str(item.get("current_name") or item.get("suggested_name") or item.get("name") or "").strip()
        description_value = str(item.get("description") or "").strip()
        note_value = str(item.get("note") or "").strip()
        if hospitality_mode and _is_booking_offer_service(current_name, description_value, note_value):
            booking_offer_count += 1
            continue
        services_preview.append(item)
    has_real_services = bool(services_preview)

    issue_blocks: List[Dict[str, Any]] = []
    review_signal_rows: List[Dict[str, Any]] = []
    reviews_preview = (
        snapshot.get("reviews_preview")
        or (lead_import_payload.get("reviews_preview") if isinstance(lead_import_payload.get("reviews_preview"), list) else None)
        or []
    )
    for item in reviews_preview:
        if not isinstance(item, dict):
            continue
        review_signal_rows.append({"review_text": item.get("review") or item.get("text") or ""})
    hospitality_signals = _extract_hospitality_review_signals(review_signal_rows) if hospitality_mode else {}

    if hospitality_mode:
        issue_blocks = _build_hospitality_issue_blocks(
            business_name=lead_name,
            city=city,
            has_description=bool(snapshot.get("description_present") or lead.get("description")),
            has_real_services=has_real_services,
            booking_offer_count=booking_offer_count,
            photos_count=photos_count,
            reviews_count=reviews_count,
            unanswered_reviews_count=unanswered_reviews_count,
            rating=rating,
            top_positive=hospitality_signals.get("top_positive") or [],
            top_negative=hospitality_signals.get("top_negative") or [],
            expectation_mismatch=bool(hospitality_signals.get("expectation_mismatch")),
        )
    elif audit_profile == "medical":
        issue_blocks = _build_medical_issue_blocks(
            business_name=lead_name,
            city=city,
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            reviews_count=reviews_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )
    elif audit_profile == "beauty":
        issue_blocks = _build_beauty_issue_blocks(
            business_name=lead_name,
            city=city,
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            reviews_count=reviews_count,
            unanswered_reviews_count=unanswered_reviews_count,
            focus_terms=beauty_focus_terms,
        )
    elif audit_profile == "fashion":
        issue_blocks = _build_fashion_issue_blocks(
            business_name=lead_name,
            city=city,
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            photos_count=photos_count,
            reviews_count=reviews_count,
        )
    elif audit_profile == "wellness":
        issue_blocks = _build_wellness_issue_blocks(
            business_name=lead_name,
            city=city,
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            photos_count=photos_count,
            reviews_count=reviews_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )
    elif audit_profile == "food":
        issue_blocks = _build_food_issue_blocks(
            business_name=lead_name,
            city=city,
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            reviews_count=reviews_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )
    elif audit_profile == "fitness":
        issue_blocks = _build_fitness_issue_blocks(
            business_name=lead_name,
            city=city,
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            reviews_count=reviews_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )
    else:
        issue_blocks = _build_default_local_business_issue_blocks(
            business_name=lead_name,
            city=city,
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            reviews_count=reviews_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )

    missing_contacts_count = int(not has_website) + int(not has_phone) + int(not (has_email or has_messenger))
    if missing_contacts_count >= 2 and not (audit_profile == "fashion" and has_website):
        missing_contacts: List[str] = []
        if not has_website:
            missing_contacts.append("сайт")
        if not has_phone:
            missing_contacts.append("телефон")
        if not (has_email or has_messenger):
            missing_contacts.append("email/мессенджер")
        issue_blocks.append(
            {
                "id": "profile_contacts_gap",
                "section": "profile",
                "priority": "high" if len(missing_contacts) >= 2 else "medium",
                "title": "Не заполнены контакты карточки",
                "problem": "Не все каналы связи доступны в карточке.",
                "evidence": f"Не хватает: {', '.join(missing_contacts)}.",
                "impact": "Часть потенциальных клиентов не доходит до контакта.",
                "fix": "Заполнить отсутствующие контакты и проверить кликабельность ссылок.",
            }
        )

    if audit_profile not in {"hospitality"} and (rating is None or rating < rating_target_min):
        issue_blocks.append(
            {
                "id": "rating_gap",
                "section": "reviews",
                "priority": "high" if (rating is None or rating < rating_risk_max) else "medium",
                "title": "Рейтинг ниже целевой зоны",
                "problem": "Рейтинг карточки пока ниже уровня стабильного доверия.",
                "evidence": f"Текущий рейтинг: {f'{rating:.1f}' if rating is not None else 'н/д'}, целевой: {rating_target_min:.1f}+.",
                "impact": "Снижается видимость карточки и доля входящих обращений.",
                "fix": "Собрать свежие отзывы и закрыть негатив корректными ответами.",
            }
        )

    if reviews_count < reviews_target_min and audit_profile not in {"fashion", "hospitality"}:
        issue_blocks.append(
            {
                "id": "reviews_low_count",
                "section": "reviews",
                "priority": "medium",
                "title": "Недостаточно отзывов",
                "problem": "Объём social proof пока слабый.",
                "evidence": f"Сейчас отзывов: {reviews_count}, ориентир: {reviews_target_min}+.",
                "impact": "Новым клиентам сложнее доверять карточке.",
                "fix": "Запустить сбор отзывов после визита и закрепить еженедельный ритм.",
            }
        )

    if unanswered_reviews_count > 0 and audit_profile not in {"hospitality"}:
        issue_blocks.append(
            {
                "id": "reviews_unanswered",
                "section": "reviews",
                "priority": "high" if unanswered_reviews_count >= 3 else "medium",
                "title": "Есть отзывы без ответа",
                "problem": "Часть отзывов остаётся без реакции бизнеса.",
                "evidence": f"Без ответа: {unanswered_reviews_count}.",
                "impact": "Падает доверие, карточка выглядит менее живой и слабее поддерживает видимость в локальном поиске.",
                "fix": f"Закрыть бэклог отзывов и отвечать в пределах {cadence_response_hours_max} часов, используя ответы как слой доверия и сигнала активности карточки.",
            }
        )

    if photos_count <= 0 and audit_profile not in {"hospitality"}:
        issue_blocks.append(
            {
                "id": "visual_no_photos",
                "section": "visual",
                "priority": "medium",
                "title": "Нет актуальных фото",
                "problem": "В карточке не видно визуального подтверждения качества.",
                "evidence": f"Фото в срезе: {photos_count}.",
                "impact": "Снижается доверие и переходы в контакт.",
                "fix": "Добавить свежие фото работ, команды или интерьера.",
            }
        )

    if not has_recent_activity and audit_profile not in {"hospitality"}:
        issue_blocks.append(
            {
                "id": "activity_low",
                "section": "activity",
                "priority": "medium",
                "title": "Карточка выглядит неактивной",
                "problem": "Нет регулярных признаков ведения карточки.",
                "evidence": f"Новости в срезе: {news_count}, свежая активность: {'нет' if not has_recent_activity else 'есть'}.",
                "impact": "Карточка хуже удерживает внимание и реже попадает в приоритетные показы.",
                "fix": f"Публиковать не менее {cadence_news_min} обновлений в месяц и добавлять новые фото.",
            }
        )

    revenue_potential = estimate_card_revenue_gap(
        rating=rating,
        services_count=services_count,
        priced_services_count=priced_services_count,
        unanswered_reviews_count=unanswered_reviews_count,
        reviews_count=reviews_count,
        photos_count=photos_count,
        news_count=news_count,
        average_check=None,
        current_revenue=None,
        business_type=business_type,
    )

    top_driver = "заполнении карточки"
    if revenue_potential["rating_gap"]["max"] >= max(
        revenue_potential["content_gap"]["max"],
        revenue_potential["service_gap"]["max"],
    ):
        top_driver = "рейтинге и доверии"
    elif revenue_potential["service_gap"]["max"] >= revenue_potential["content_gap"]["max"]:
        top_driver = "структуре услуг"

    service_examples = [str(item.get("current_name") or "").strip() for item in imported_services_preview[:3] if isinstance(item, dict)]
    service_examples = [item for item in service_examples if item]
    website_state = "есть" if has_website else "нет"
    activity_state = "есть" if has_recent_activity else "нет"
    rating_text = f"{rating:.1f}" if rating is not None else "н/д"
    if hospitality_mode:
        top_positive = hospitality_signals.get("top_positive") or []
        top_negative = hospitality_signals.get("top_negative") or []
        positive_text = ", ".join([_theme_label(item) for item in top_positive[:3]]) or "сильные стороны объекта"
        negative_text = ", ".join([_theme_label(item) for item in top_negative[:2]]) or "ожидания гостей"
        if rating is None or rating < 4.2:
            summary_text = (
                f"{health_label}. Локация и базовый social proof уже дают карточке потенциал, но главный bottleneck сейчас — репутация и review engine. "
                f"Сильные стороны по отзывам: {positive_text}. "
                f"Главные зоны риска — рейтинг, {negative_text} и слабая упаковка объекта под поисковые сценарии и landmarks."
            )
        else:
            summary_text = (
                f"{health_label}. Карточка уже имеет сильный social proof, но пока слабо управляет ожиданиями и позиционированием. "
                f"Сильные стороны по отзывам: {positive_text}. "
                f"Главная зона риска сейчас — {negative_text} и слабая упаковка объекта под поисковые сценарии."
            )
    elif audit_profile == "medical":
        summary_text = (
            f"{health_label}. Карточка уже может собирать доверие через отзывы, но пока недостаточно хорошо объясняет специализацию, маршрут пациента и ключевые услуги. "
            f"Главные зоны роста сейчас — сильное описание, структура медицинских услуг и визуальный слой доверия."
        )
    elif audit_profile == "beauty":
        summary_text = (
            f"{health_label}. Карточка уже может приводить запись из локального поиска, но пока слабо продаёт направления услуг, цены и результат. "
            f"Главные зоны роста сейчас — понятные beauty-услуги, фото работ и живой ритм обновлений."
        )
    elif audit_profile == "fashion":
        summary_text = (
            f"{health_label}. У карточки уже есть базовый trust signal через рейтинг, но она почти не объясняет, что именно студия делает и по каким запросам её можно находить. "
            f"Главные зоны роста сейчас — SEO-описание, структура услуг под bridal/custom спрос, review engine и регулярный визуальный контент."
        )
    elif audit_profile == "wellness":
        summary_text = (
            f"{health_label}. Карточка уже может опираться на доверие из отзывов, но пока недорабатывает в локальном SEO и конверсии. "
            f"Главные зоны роста сейчас — сильное описание, услуги как SEO-единицы и конверсионные фото пространства и процедур."
        )
    elif audit_profile == "food":
        summary_text = (
            f"{health_label}. Карточка уже может приводить гостей из локального поиска, но пока слабо продаёт формат заведения, меню и повод прийти именно сейчас. "
            f"Главные зоны роста сейчас — сильное описание, хиты меню как SEO-единицы и визуально сильные фото еды и атмосферы."
        )
    elif audit_profile == "fitness":
        summary_text = (
            f"{health_label}. Карточка уже может привлекать запись на тренировки, но пока недостаточно ясно объясняет формат занятий, уровень входа и отличие студии. "
            f"Главные зоны роста сейчас — понятные направления, абонементы, оборудование и фото пространства."
        )
    else:
        summary_text = (
            f"{health_label}. Карточка {lead_name}: рейтинг {rating_text}, отзывов {reviews_count}, услуг {services_count}. "
            f"Сайт: {website_state}, свежая активность: {activity_state}. "
            f"Основной потенциал роста сейчас в {top_driver}."
        )
        if service_examples:
            summary_text += f" Примеры текущих услуг: {', '.join(service_examples)}."

    issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
    findings: List[Dict[str, Any]] = [
        {
            "code": str(item.get("id") or ""),
            "severity": str(item.get("priority") or "medium"),
            "title": str(item.get("title") or ""),
            "description": str(item.get("problem") or ""),
        }
        for item in issue_blocks
    ]
    recommended_actions: List[Dict[str, Any]] = [
        {
            "priority": str(item.get("priority") or "medium"),
            "title": str(item.get("title") or ""),
            "description": str(item.get("fix") or ""),
        }
        for item in issue_blocks[:5]
    ]
    top_issues = _build_top_issues(issue_blocks, limit=3)
    if hospitality_mode:
        action_plan = _build_hospitality_action_plan(
            has_description=bool(snapshot.get("description_present") or lead.get("description")),
            has_real_services=has_real_services,
            photos_count=photos_count,
            top_negative=hospitality_signals.get("top_negative") or [],
            unanswered_reviews_count=unanswered_reviews_count,
            rating=rating,
            reviews_count=reviews_count,
        )
    elif audit_profile == "medical":
        action_plan = _build_medical_action_plan(
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )
    elif audit_profile == "beauty":
        action_plan = _build_beauty_action_plan(
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            unanswered_reviews_count=unanswered_reviews_count,
            focus_terms=beauty_focus_terms,
        )
    elif audit_profile == "fashion":
        action_plan = _build_fashion_action_plan(
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            photos_count=photos_count,
            reviews_count=reviews_count,
        )
    elif audit_profile == "wellness":
        action_plan = _build_wellness_action_plan(
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            photos_count=photos_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )
    elif audit_profile == "food":
        action_plan = _build_food_action_plan(
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )
    elif audit_profile == "fitness":
        action_plan = _build_fitness_action_plan(
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )
    else:
        action_plan = _build_default_local_business_action_plan(
            has_description=bool(snapshot.get("description_present")),
            services_count=services_count,
            priced_services_count=priced_services_count,
            photos_count=photos_count,
            unanswered_reviews_count=unanswered_reviews_count,
        )
    snapshot_services_preview = snapshot.get("services_preview") if isinstance(snapshot.get("services_preview"), list) else []
    if snapshot_services_preview:
        services_preview = snapshot_services_preview
    elif imported_services_preview and not hospitality_mode:
        services_preview = imported_services_preview
    elif not services_preview:
        services_preview = _lead_demo_services_preview(business_type)
    news_preview = (
        snapshot.get("news_preview")
        or (lead_import_payload.get("news_preview") if isinstance(lead_import_payload.get("news_preview"), list) else None)
        or []
    )
    last_parse_status = snapshot.get("last_parse_status") or "lead_preview"
    no_new_services_found = bool(
        services_count <= 0 and str(last_parse_status).lower() not in {"lead_preview", "preview"}
    )
    reasoning = _build_reasoning_fields(
        audit_profile=audit_profile,
        business_name=lead_name,
        city=city,
        address=str(lead.get("address") or "").strip(),
        overview_text=str(lead.get("description") or profile_overview or "").strip(),
        services_count=services_count,
        has_description=bool(snapshot.get("description_present") or lead.get("description")),
        photos_count=photos_count,
        reviews_count=reviews_count,
        unanswered_reviews_count=unanswered_reviews_count,
        service_names=profile_service_names,
        top_positive=hospitality_signals.get("top_positive") if hospitality_mode else None,
        top_negative=hospitality_signals.get("top_negative") if hospitality_mode else None,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "business": {
            "id": lead.get("id"),
            "name": lead_name,
            "business_type": business_type,
            "city": city or None,
        },
        "parse_context": {
            "last_parse_at": snapshot.get("last_parse_at") or lead.get("updated_at") or lead.get("created_at"),
            "last_parse_status": last_parse_status,
            "last_parse_task_id": snapshot.get("last_parse_task_id"),
            "last_parse_retry_after": snapshot.get("last_parse_retry_after"),
            "last_parse_error": snapshot.get("last_parse_error"),
            "no_new_services_found": no_new_services_found,
        },
        "summary_score": summary_score,
        "health_level": health_level,
        "health_label": health_label,
        "audit_profile": audit_profile,
        "audit_profile_label": reasoning.get("audit_profile_label"),
        "summary_text": summary_text,
        "subscores": {
            "profile": profile_score,
            "reputation": reputation_score,
            "services": service_score,
            "activity": activity_score,
        },
        "findings": findings[:5],
        "current_state": {
            "rating": rating,
            "reviews_count": reviews_count,
            "unanswered_reviews_count": unanswered_reviews_count,
            "services_count": services_count,
            "services_with_price_count": priced_services_count,
            "has_website": has_website,
            "has_recent_activity": has_recent_activity,
            "photos_state": photos_state,
            "photos_count": photos_count,
            "description_present": bool(snapshot.get("description_present") or lead.get("description")),
            "booking_offer_count": booking_offer_count if hospitality_mode else 0,
        },
        "revenue_potential": revenue_potential,
        "recommended_actions": recommended_actions,
        "issue_blocks": issue_blocks[:8],
        "top_3_issues": top_issues,
        "action_plan": action_plan,
        "best_fit_customer_profile": reasoning.get("best_fit_customer_profile"),
        "weak_fit_customer_profile": reasoning.get("weak_fit_customer_profile"),
        "best_fit_guest_profile": reasoning.get("best_fit_guest_profile"),
        "weak_fit_guest_profile": reasoning.get("weak_fit_guest_profile"),
        "search_intents_to_target": reasoning.get("search_intents_to_target"),
        "photo_shots_missing": reasoning.get("photo_shots_missing"),
        "positioning_focus": reasoning.get("positioning_focus"),
        "strength_themes": reasoning.get("strength_themes"),
        "objection_themes": reasoning.get("objection_themes"),
        "cadence": {
            "news_posts_per_month_min": cadence_news_min,
            "photos_per_month_min": cadence_photos_min,
            "reviews_response_hours_max": cadence_response_hours_max,
        },
        "services_preview": services_preview or _lead_demo_services_preview(business_type),
        "reviews_preview": reviews_preview,
        "news_preview": news_preview,
        "preview_meta": {
            "business_id": business.get("id"),
            "has_phone": has_phone,
            "has_email": has_email,
            "has_messenger": has_messenger,
            "source": lead.get("source"),
            "source_url": snapshot.get("source_url") or lead.get("source_url"),
            "logo_url": lead_import_payload.get("logo_url"),
            "photo_urls": effective_photos[:8],
        },
    }


def build_card_audit_snapshot(business_id: str) -> Dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        rating_risk_max = policy_value("rating", "risk_max", 4.4)
        rating_target_min = policy_value("rating", "target_min", 4.7)
        reviews_target_min = int(policy_value("reviews", "target_min", 30))
        services_minimum_visible = int(policy_value("services", "minimum_visible", 5))
        photos_good_min = int(policy_value("photos", "good_min", 5))
        recent_days = int(policy_value("activity", "recent_days", 45))
        unanswered_high_min = int(policy_value("unanswered_reviews", "high_severity_min", 3))
        cadence_news_min = int(policy_value("cadence", "news_posts_per_month_min", 4))
        cadence_photos_min = int(policy_value("cadence", "photos_per_month_min", 8))
        cadence_response_hours_max = int(policy_value("cadence", "reviews_response_hours_max", 48))
        strong_min = policy_value("health_thresholds", "strong_min", 80.0)
        growth_min = policy_value("health_thresholds", "growth_min", 55.0)
        profile_weight = policy_value("weights", "profile", 0.20)
        reputation_weight = policy_value("weights", "reputation", 0.35)
        services_weight = policy_value("weights", "services", 0.30)
        activity_weight = policy_value("weights", "activity", 0.15)

        cursor.execute(
            """
            SELECT id, name, business_type, city, website
            FROM businesses
            WHERE id = %s
            """,
            (business_id,),
        )
        business = _to_dict(cursor, cursor.fetchone())
        if not business:
            raise ValueError("Бизнес не найден")

        cursor.execute(
            """
            SELECT rating, reviews_count, overview, products, news, photos, updated_at, created_at, phone, site
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (business_id,),
        )
        recent_cards = [_to_dict(cursor, row) or {} for row in (cursor.fetchall() or [])]
        latest_card = recent_cards[0] if recent_cards else {}
        rich_card = _select_preferred_rich_card(recent_cards) or latest_card
        metrics_card = _select_preferred_metrics_card(recent_cards) or latest_card

        cursor.execute(
            """
            SELECT status, updated_at
            FROM parsequeue
            WHERE business_id = %s
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        latest_parse = _to_dict(cursor, cursor.fetchone()) or {}

        cursor.execute(
            """
            SELECT updated_at
            FROM parsequeue
            WHERE business_id = %s
              AND status IN ('completed', 'done', 'success')
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        latest_successful_parse = _to_dict(cursor, cursor.fetchone()) or {}

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_services,
                COUNT(*) FILTER (WHERE is_active IS TRUE OR is_active IS NULL) AS active_services,
                COUNT(*) FILTER (
                    WHERE (is_active IS TRUE OR is_active IS NULL)
                      AND COALESCE(TRIM(price), '') <> ''
                ) AS priced_services,
                MAX(updated_at) AS last_service_update,
                COUNT(*) FILTER (
                    WHERE (is_active IS TRUE OR is_active IS NULL)
                      AND source = ANY(%s)
                ) AS active_yandex_services
            FROM userservices
            WHERE business_id = %s
            """,
            (list(YMAP_SOURCES), business_id),
        )
        services_row = _to_dict(cursor, cursor.fetchone()) or {}
        cursor.execute(
            """
            SELECT name, description
            FROM userservices
            WHERE business_id = %s
              AND (is_active IS TRUE OR is_active IS NULL)
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
        service_name_rows: List[Dict[str, Any]] = []
        for raw_row in cursor.fetchall() or []:
            service_row = _to_dict(cursor, raw_row) or {}
            service_name = str(service_row.get("name") or "").strip()
            service_description = str(service_row.get("description") or "").strip()
            if not service_name:
                continue
            if _is_editorial_service_entry(service_name, service_description):
                continue
            service_name_rows.append(
                {
                    "name": service_name,
                    "description": service_description,
                }
            )

        unanswered_reviews_count = 0
        recent_review_rows: List[Dict[str, Any]] = []
        if _table_exists(cursor, "externalbusinessreviews"):
            cursor.execute(
                """
                WITH preferred_source AS (
                    SELECT CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM externalbusinessreviews r2
                            WHERE r2.business_id = %s
                              AND r2.source = 'yandex_maps'
                        ) THEN 'yandex_maps'
                        ELSE 'yandex_business'
                    END AS source
                )
                SELECT COUNT(*) AS cnt
                FROM externalbusinessreviews r, preferred_source ps
                WHERE r.business_id = %s
                  AND r.source = ps.source
                  AND (r.response_text IS NULL OR TRIM(COALESCE(r.response_text, '')) = '')
                """,
                (business_id, business_id),
            )
            unanswered_reviews_count = int((_to_dict(cursor, cursor.fetchone()) or {}).get("cnt") or 0)
            cursor.execute(
                """
                SELECT text AS review_text, response_text, rating, published_at, source
                FROM externalbusinessreviews
                WHERE business_id = %s
                ORDER BY published_at DESC NULLS LAST, created_at DESC
                LIMIT 200
                """,
                (business_id,),
            )
            recent_review_rows = []
            for row in cursor.fetchall() or []:
                review_row = _to_dict(cursor, row) or {}
                review_text = str(review_row.get("review_text") or "").strip()
                response_text = str(review_row.get("response_text") or "").strip()
                if not review_text or _is_placeholder_review_entry(review_text, response_text):
                    continue
                recent_review_rows.append(review_row)

        cursor.execute(
            """
            SELECT data
            FROM businessoptimizationwizard
            WHERE business_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        wizard_row = _to_dict(cursor, cursor.fetchone()) or {}
        wizard_data = _safe_json(wizard_row.get("data")) or {}

        overview = _safe_json(rich_card.get("overview")) or {}
        photos = _safe_json(rich_card.get("photos"))
        news = _safe_json(rich_card.get("news"))
        products_payload = _safe_json(rich_card.get("products"))

        photos_count = len(photos) if isinstance(photos, list) else int(overview.get("photos_count") or 0)
        if isinstance(news, list):
            news_count = len(news)
        elif isinstance(news, dict):
            news_count = len(news)
        else:
            news_count = 0

        rating = metrics_card.get("rating")
        rating_value = float(rating) if rating is not None else None
        reviews_count = int(metrics_card.get("reviews_count") or 0)
        total_services = int(services_row.get("total_services") or 0)
        services_count = int(services_row.get("active_services") or 0)
        if services_count <= 0 and total_services > 0:
            # В части проектов данные уже записаны, но флаг активности не выставлен.
            # Для аудита считаем такие услуги как доступные, чтобы не давать ложное
            # "услуги не заполнены".
            services_count = total_services
        priced_services_count = int(services_row.get("priced_services") or 0)
        active_yandex_services = int(services_row.get("active_yandex_services") or 0)
        if services_count <= 0:
            fallback_services = _extract_services_from_products_payload(products_payload, limit=200)
            if fallback_services:
                services_count = len(fallback_services)
                priced_services_count = sum(1 for row in fallback_services if row.get("_price_present"))

        average_check = _extract_numeric(wizard_data.get("average_check"))
        current_revenue = _extract_numeric(wizard_data.get("revenue"))
        description_text = str(overview.get("description") or "").strip() if isinstance(overview, dict) else ""
        profile_overview = dict(overview) if isinstance(overview, dict) else {}
        profile_service_names = [str(row.get("name") or "").strip() for row in service_name_rows[:30] if str(row.get("name") or "").strip()]
        beauty_focus_terms = _derive_beauty_focus_terms(profile_service_names, description_text)
        if profile_service_names:
            profile_overview["service_names"] = profile_service_names
        audit_profile = _detect_audit_profile(business.get("business_type"), business.get("name"), profile_overview)
        hospitality_mode = audit_profile == "hospitality"

        has_website = bool(str(business.get("website") or "").strip())
        parse_dt = _coerce_dt(latest_parse.get("updated_at"))
        now = datetime.now(timezone.utc)
        has_recent_activity = bool(parse_dt and parse_dt >= now - timedelta(days=recent_days)) or news_count > 0

        photos_state = "good" if photos_count >= photos_good_min else "weak" if photos_count > 0 else "missing"

        profile_score = 100
        if not has_website:
            profile_score -= 12
        if not overview:
            profile_score -= 12
        if photos_count <= 0:
            profile_score -= 18
        elif photos_count < 5:
            profile_score -= 8
        if latest_parse.get("status") not in ("completed", "success"):
            profile_score -= 8
        profile_score = max(0, min(100, profile_score))

        reputation_score = 100
        if rating_value is None:
            reputation_score -= 30
        elif rating_value < rating_risk_max:
            reputation_score -= 30
        elif rating_value < rating_target_min:
            reputation_score -= 14
        if reviews_count < reviews_target_min:
            reputation_score -= 10
        if unanswered_reviews_count > 0:
            reputation_score -= min(22, unanswered_reviews_count * 3)
        reputation_score = max(0, min(100, reputation_score))

        service_score = 100
        if services_count <= 0:
            service_score -= 45
        elif services_count < services_minimum_visible:
            service_score -= 22
        if services_count > 0 and priced_services_count <= 0:
            service_score -= 12
        elif services_count > 0 and priced_services_count < max(1, services_count // 2):
            service_score -= 6
        service_score = max(0, min(100, service_score))

        activity_score = 100
        if not has_recent_activity:
            activity_score -= 20
        if news_count <= 0:
            activity_score -= 10
        activity_score = max(0, min(100, activity_score))

        summary_score = int(round(
            profile_score * profile_weight
            + reputation_score * reputation_weight
            + service_score * services_weight
            + activity_score * activity_weight
        ))

        if summary_score >= strong_min:
            health_level = "strong"
            health_label = "Сильная карточка"
        elif summary_score >= growth_min:
            health_level = "growth"
            health_label = "Есть точки роста"
        else:
            health_level = "risk"
            health_label = "Карточка теряет клиентов"

        phone_value = overview.get("phone") if isinstance(overview, dict) else None
        if not phone_value and isinstance(overview, dict):
            phones_list = overview.get("phones")
            if isinstance(phones_list, list):
                for phone_item in phones_list:
                    text = str(phone_item or "").strip()
                    if text:
                        phone_value = text
                        break
        has_phone = bool(str(phone_value or "").strip())
        has_email = bool(str((overview.get("email") if isinstance(overview, dict) else "") or "").strip())
        messenger_value = overview.get("messengers") if isinstance(overview, dict) else None
        has_messenger = bool(messenger_value)

        raw_services_preview = _extract_services_from_products_payload(products_payload, limit=20)
        booking_offer_count = 0
        services_preview: List[Dict[str, Any]] = []
        for item in raw_services_preview:
            current_name = str(item.get("current_name") or "").strip()
            description_value = str(item.get("description") or "").strip()
            note_value = str(item.get("note") or "").strip()
            if hospitality_mode and _is_booking_offer_service(current_name, description_value, note_value):
                booking_offer_count += 1
                continue
            services_preview.append(item)
        has_real_services = bool(services_preview) or (services_count > 0 and booking_offer_count < max(services_count, 1))

        issue_blocks: List[Dict[str, Any]] = []
        hospitality_signals: Dict[str, Any] = {}
        if hospitality_mode:
            hospitality_signals = _extract_hospitality_review_signals(recent_review_rows)
            issue_blocks = _build_hospitality_issue_blocks(
                business_name=str(business.get("name") or "").strip(),
                city=str(business.get("city") or "").strip(),
                has_description=bool(description_text),
                has_real_services=has_real_services,
                booking_offer_count=booking_offer_count,
                photos_count=photos_count,
                reviews_count=reviews_count,
                unanswered_reviews_count=unanswered_reviews_count,
                rating=rating_value,
                top_positive=hospitality_signals.get("top_positive") or [],
                top_negative=hospitality_signals.get("top_negative") or [],
                expectation_mismatch=bool(hospitality_signals.get("expectation_mismatch")),
            )
        elif audit_profile == "wellness":
            issue_blocks = _build_wellness_issue_blocks(
                business_name=str(business.get("name") or "").strip(),
                city=str(business.get("city") or "").strip(),
                has_description=bool(description_text),
                services_count=services_count,
                photos_count=photos_count,
                reviews_count=reviews_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )
        elif audit_profile == "medical":
            issue_blocks = _build_medical_issue_blocks(
                business_name=str(business.get("name") or "").strip(),
                city=str(business.get("city") or "").strip(),
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                reviews_count=reviews_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )
        elif audit_profile == "beauty":
            issue_blocks = _build_beauty_issue_blocks(
                business_name=str(business.get("name") or "").strip(),
                city=str(business.get("city") or "").strip(),
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                reviews_count=reviews_count,
                unanswered_reviews_count=unanswered_reviews_count,
                focus_terms=beauty_focus_terms,
            )
        elif audit_profile == "food":
            issue_blocks = _build_food_issue_blocks(
                business_name=str(business.get("name") or "").strip(),
                city=str(business.get("city") or "").strip(),
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                reviews_count=reviews_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )
        elif audit_profile == "fitness":
            issue_blocks = _build_fitness_issue_blocks(
                business_name=str(business.get("name") or "").strip(),
                city=str(business.get("city") or "").strip(),
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                reviews_count=reviews_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )
        else:
            issue_blocks = _build_default_local_business_issue_blocks(
                business_name=str(business.get("name") or "").strip(),
                city=str(business.get("city") or "").strip(),
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                reviews_count=reviews_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )

        if (
            audit_profile == "default_local_business"
            and services_count > 0
            and services_count < services_minimum_visible
        ):
            issue_blocks.append({
                "id": "services_short_list",
                "section": "services",
                "priority": "high",
                "title": "Список услуг слишком короткий",
                "problem": "Карточка выглядит неполной по ассортименту.",
                "evidence": f"Активных услуг: {services_count}, ориентир: {services_minimum_visible}+.",
                "impact": "Снижается доля коммерческих переходов из карт.",
                "fix": "Расширить список услуг и проверить корректность категорий.",
            })

        if audit_profile == "default_local_business" and services_count > 0 and priced_services_count <= 0:
            issue_blocks.append({
                "id": "services_no_price",
                "section": "services",
                "priority": "medium",
                "title": "Услуги без цен",
                "problem": "По услугам отсутствуют цены.",
                "evidence": f"С ценами: {priced_services_count} из {services_count}.",
                "impact": "Падает доверие и скорость принятия решения.",
                "fix": "Добавить цены к приоритетным услугам.",
            })

        missing_contacts: List[str] = []
        if not has_website:
            missing_contacts.append("сайт")
        if not has_phone:
            missing_contacts.append("телефон")
        if not has_email and not has_messenger:
            missing_contacts.append("email/мессенджер")
        if missing_contacts:
            issue_blocks.append({
                "id": "profile_contacts_gap",
                "section": "profile",
                "priority": "high" if len(missing_contacts) >= 2 else "medium",
                "title": "Не заполнены контакты карточки",
                "problem": "Часть каналов связи недоступна.",
                "evidence": f"Не хватает: {', '.join(missing_contacts)}.",
                "impact": "Теряются обращения на этапе первого контакта.",
                "fix": "Заполнить недостающие контакты и проверить кликабельность.",
            })

        if not hospitality_mode and (rating_value is None or rating_value < rating_target_min):
            issue_blocks.append({
                "id": "rating_gap",
                "section": "reviews",
                "priority": "high" if (rating_value is None or rating_value < rating_risk_max) else "medium",
                "title": "Рейтинг ниже целевой зоны",
                "problem": "Уровень доверия к карточке ниже целевого.",
                "evidence": f"Рейтинг: {f'{rating_value:.1f}' if rating_value is not None else 'н/д'}, целевой: {rating_target_min:.1f}+.",
                "impact": "Снижается видимость карточки и конверсия в обращения.",
                "fix": "Собрать свежие отзывы и отработать негатив.",
            })

        if reviews_count < reviews_target_min:
            issue_blocks.append({
                "id": "reviews_low_count",
                "section": "reviews",
                "priority": "medium",
                "title": "Недостаточно отзывов",
                "problem": "Social proof карточки пока слабый.",
                "evidence": f"Отзывов: {reviews_count}, ориентир: {reviews_target_min}+.",
                "impact": "Новые клиенты чаще откладывают выбор.",
                "fix": "Просить клиентов оставлять отзывы после визита и закрепить еженедельный ритм сбора.",
            })

        if unanswered_reviews_count > 0 and not hospitality_mode:
            issue_blocks.append({
                "id": "reviews_unanswered",
                "section": "reviews",
                "priority": "high" if unanswered_reviews_count >= unanswered_high_min else "medium",
                "title": "Есть отзывы без ответа",
                "problem": "Часть обращений в отзывах остаётся без реакции.",
                "evidence": f"Без ответа: {unanswered_reviews_count}.",
                "impact": "Падает доверие к сервису, карточка выглядит менее живой и теряет часть сигналов видимости.",
                "fix": f"Закрыть отзывы без ответа и соблюдать SLA до {cadence_response_hours_max} часов, используя ответы как слой доверия и активности карточки.",
            })

        if photos_state == "missing" and not hospitality_mode:
            issue_blocks.append({
                "id": "visual_no_photos",
                "section": "visual",
                "priority": "medium",
                "title": "Не хватает фото",
                "problem": "Карточка без фото выглядит менее убедительно.",
                "evidence": f"Фото в карточке: {photos_count}.",
                "impact": "Снижается визуальное доверие и кликабельность.",
                "fix": "Добавить актуальные фото работ, интерьера и команды.",
            })

        if not has_recent_activity and not hospitality_mode:
            issue_blocks.append({
                "id": "activity_low",
                "section": "activity",
                "priority": "medium",
                "title": "Карточка выглядит неактивной",
                "problem": "Нет регулярных обновлений карточки.",
                "evidence": f"Новости в срезе: {news_count}, свежая активность: {'нет' if not has_recent_activity else 'есть'}.",
                "impact": "Карточка реже выигрывает по вовлечению и показам.",
                "fix": f"Публиковать минимум {cadence_news_min} обновлений и добавлять {cadence_photos_min} новых фото в месяц.",
            })

        revenue_potential = estimate_card_revenue_gap(
            rating=rating_value,
            services_count=services_count,
            priced_services_count=priced_services_count,
            unanswered_reviews_count=unanswered_reviews_count,
            reviews_count=reviews_count,
            photos_count=photos_count,
            news_count=news_count,
            average_check=average_check,
            current_revenue=current_revenue,
            business_type=business.get("business_type"),
        )

        issue_blocks.sort(key=lambda item: _issue_priority_rank(str(item.get("priority") or "")))
        findings: List[Dict[str, Any]] = [
            {
                "code": str(item.get("id") or ""),
                "severity": str(item.get("priority") or "medium"),
                "title": str(item.get("title") or ""),
                "description": str(item.get("problem") or ""),
            }
            for item in issue_blocks
        ]
        recommended_actions: List[Dict[str, Any]] = [
            {
                "priority": str(item.get("priority") or "medium"),
                "title": str(item.get("title") or ""),
                "description": str(item.get("fix") or ""),
            }
            for item in issue_blocks[:5]
        ]
        top_issues = _build_top_issues(issue_blocks, limit=3)
        if hospitality_mode:
            action_plan = _build_hospitality_action_plan(
                has_description=bool(description_text),
                has_real_services=has_real_services,
                photos_count=photos_count,
                top_negative=hospitality_signals.get("top_negative") or [],
                unanswered_reviews_count=unanswered_reviews_count,
                rating=rating_value,
                reviews_count=reviews_count,
            )
        elif audit_profile == "wellness":
            action_plan = _build_wellness_action_plan(
                has_description=bool(description_text),
                services_count=services_count,
                photos_count=photos_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )
        elif audit_profile == "medical":
            action_plan = _build_medical_action_plan(
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )
        elif audit_profile == "beauty":
            action_plan = _build_beauty_action_plan(
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                unanswered_reviews_count=unanswered_reviews_count,
                focus_terms=beauty_focus_terms,
            )
        elif audit_profile == "food":
            action_plan = _build_food_action_plan(
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )
        elif audit_profile == "fitness":
            action_plan = _build_fitness_action_plan(
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )
        elif audit_profile == "default_local_business":
            action_plan = _build_default_local_business_action_plan(
                has_description=bool(description_text),
                services_count=services_count,
                priced_services_count=priced_services_count,
                photos_count=photos_count,
                unanswered_reviews_count=unanswered_reviews_count,
            )
        else:
            action_plan = _build_action_plan(
                issue_blocks,
                cadence_news_min=cadence_news_min,
                cadence_photos_min=cadence_photos_min,
                cadence_response_hours_max=cadence_response_hours_max,
            )

        top_driver = max(
            [
                ("рейтинга", revenue_potential["rating_gap"]["max"]),
                ("неполной карточки", revenue_potential["content_gap"]["max"]),
                ("структуры услуг", revenue_potential["service_gap"]["max"]),
            ],
            key=lambda item: item[1],
        )[0]
        if hospitality_mode:
            top_positive = hospitality_signals.get("top_positive") or []
            top_negative = hospitality_signals.get("top_negative") or []
            positive_text = ", ".join([_theme_label(item) for item in top_positive[:3]]) or "сильные стороны объекта"
            negative_text = ", ".join([_theme_label(item) for item in top_negative[:2]]) or "ожидания гостей"
            if rating_value is None or rating_value < 4.2:
                summary_text = (
                    f"{health_label}. Локация и базовый social proof уже дают карточке потенциал, но главный bottleneck сейчас — репутация и review engine. "
                    f"Сильные стороны по отзывам: {positive_text}. "
                    f"Главные зоны риска — рейтинг, {negative_text} и слабая упаковка объекта под поисковые сценарии и landmarks."
                )
            else:
                summary_text = (
                    f"{health_label}. Карточка уже имеет сильный social proof, но пока слабо управляет ожиданиями и позиционированием. "
                    f"Сильные стороны по отзывам: {positive_text}. "
                    f"Главная зона риска сейчас — {negative_text} и слабая упаковка объекта под поисковые сценарии."
                )
        elif audit_profile == "wellness":
            summary_text = (
                f"{health_label}. Карточка уже может опираться на доверие из отзывов, но пока недорабатывает в локальном SEO и конверсии. "
                f"Главные зоны роста сейчас — сильное описание, услуги как SEO-единицы и конверсионные фото пространства и процедур."
            )
        elif audit_profile == "medical":
            summary_text = (
                f"{health_label}. Карточка уже может собирать доверие через отзывы, но пока недостаточно хорошо объясняет специализацию, маршрут пациента и ключевые услуги. "
                f"Главные зоны роста сейчас — сильное описание, структура медицинских услуг и визуальный слой доверия."
            )
        elif audit_profile == "beauty":
            summary_text = (
                f"{health_label}. Карточка уже может приводить запись из локального поиска, но пока слабо продаёт направления услуг, цены и результат. "
                f"Главные зоны роста сейчас — понятные beauty-услуги, фото работ и живой ритм обновлений."
            )
        elif audit_profile == "food":
            summary_text = (
                f"{health_label}. Карточка уже может приводить гостей из локального поиска, но пока слабо продаёт формат заведения, меню и повод прийти именно сейчас. "
                f"Главные зоны роста сейчас — сильное описание, хиты меню как SEO-единицы и визуально сильные фото еды и атмосферы."
            )
        elif audit_profile == "fitness":
            summary_text = (
                f"{health_label}. Карточка уже может привлекать запись на тренировки, но пока недостаточно ясно объясняет формат занятий, уровень входа и отличие студии. "
                f"Главные зоны роста сейчас — понятные направления, абонементы, оборудование и фото пространства."
            )
        elif audit_profile == "default_local_business":
            summary_text = (
                f"{health_label}. Карточка уже может приводить локальный спрос, но пока слишком слабо объясняет, за чем именно сюда обращаться и почему выбрать этот бизнес. "
                f"Главные зоны роста сейчас — ясное позиционирование, понятные услуги и визуальный слой доверия."
            )
        else:
            summary_text = (
                f"{health_label}. "
                f"Ориентировочный недобор из-за карточки: {revenue_potential['total_min']:,}–{revenue_potential['total_max']:,} ₽ в месяц. "
                f"Главная зона потерь сейчас — из-за {top_driver}."
            ).replace(",", " ")

        reasoning = _build_reasoning_fields(
            audit_profile=audit_profile,
            business_name=str(business.get("name") or "").strip(),
            city=str(business.get("city") or "").strip(),
            address=str(business.get("address") or "").strip(),
            overview_text=str(description_text or profile_overview or "").strip(),
            services_count=services_count,
            has_description=bool(description_text),
            photos_count=photos_count,
            reviews_count=reviews_count,
            unanswered_reviews_count=unanswered_reviews_count,
            service_names=profile_service_names,
            top_positive=hospitality_signals.get("top_positive") if hospitality_mode else None,
            top_negative=hospitality_signals.get("top_negative") if hospitality_mode else None,
        )

        no_new_services_found = bool(
            latest_parse.get("status") in ("completed", "success")
            and active_yandex_services == 0
            and services_count > 0
        )
        has_successful_parse = bool(latest_successful_parse.get("updated_at"))

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "business": {
                "id": business.get("id"),
                "name": business.get("name"),
                "business_type": business.get("business_type"),
                "city": business.get("city"),
            },
            "parse_context": {
                "last_parse_at": latest_parse.get("updated_at"),
                "last_parse_status": latest_parse.get("status"),
                "last_successful_parse_at": latest_successful_parse.get("updated_at"),
                "has_successful_parse": has_successful_parse,
                "no_new_services_found": no_new_services_found,
            },
            "audit_mode": "hospitality" if hospitality_mode else "default",
            "audit_profile": audit_profile,
            "audit_profile_label": reasoning.get("audit_profile_label"),
            "summary_score": summary_score,
            "health_level": health_level,
            "health_label": health_label,
            "summary_text": summary_text,
            "findings": findings[:5],
            "subscores": {
                "profile": profile_score,
                "reputation": reputation_score,
                "services": service_score,
                "activity": activity_score,
            },
            "revenue_potential": revenue_potential,
            "recommended_actions": recommended_actions[:5],
            "issue_blocks": issue_blocks[:10],
            "top_3_issues": top_issues,
            "action_plan": action_plan,
            "best_fit_customer_profile": reasoning.get("best_fit_customer_profile"),
            "weak_fit_customer_profile": reasoning.get("weak_fit_customer_profile"),
            "best_fit_guest_profile": reasoning.get("best_fit_guest_profile"),
            "weak_fit_guest_profile": reasoning.get("weak_fit_guest_profile"),
            "search_intents_to_target": reasoning.get("search_intents_to_target"),
            "photo_shots_missing": reasoning.get("photo_shots_missing"),
            "positioning_focus": reasoning.get("positioning_focus"),
            "strength_themes": reasoning.get("strength_themes"),
            "objection_themes": reasoning.get("objection_themes"),
            "cadence": {
                "news_posts_per_month_min": cadence_news_min,
                "photos_per_month_min": cadence_photos_min,
                "reviews_response_hours_max": cadence_response_hours_max,
            },
            "current_state": {
                "rating": rating_value,
                "reviews_count": reviews_count,
                "unanswered_reviews_count": unanswered_reviews_count,
                "services_count": services_count,
                "services_with_price_count": priced_services_count,
                "has_website": has_website,
                "has_recent_activity": has_recent_activity,
                "photos_state": photos_state,
                "photos_count": photos_count,
                "description_present": bool(description_text),
                "booking_offer_count": booking_offer_count,
            },
            "services_preview": services_preview[:12] if hospitality_mode else raw_services_preview[:12],
        }
    finally:
        db.close()
    rating_risk_max = policy_value("rating", "risk_max", 4.4)
    rating_target_min = policy_value("rating", "target_min", 4.7)
    reviews_target_min = int(policy_value("reviews", "target_min", 20))
    services_minimum_visible = int(policy_value("services", "minimum_visible", 5))
    strong_min = policy_value("health_thresholds", "strong_min", 80.0)
    growth_min = policy_value("health_thresholds", "growth_min", 55.0)
    profile_weight = policy_value("weights", "profile", 0.20)
    reputation_weight = policy_value("weights", "reputation", 0.35)
    services_weight = policy_value("weights", "services", 0.30)
    activity_weight = policy_value("weights", "activity", 0.15)
