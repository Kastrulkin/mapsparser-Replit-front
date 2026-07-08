from flask import Blueprint, jsonify, request
import sqlite3
import os
import sys
from datetime import datetime
import re
import uuid
import difflib

# Adjust path to import modules from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database_manager import get_db_connection
from auth_system import verify_session
from core.helpers import get_business_owner_id
from core.seo_keywords import collect_ranked_keywords
from service_categorizer import categorizer
from wordstat_client import WORDSTAT_TEMPORARILY_UNAVAILABLE_MESSAGE, WordstatClient, WordstatTemporaryUnavailable
from wordstat_config import config

wordstat_bp = Blueprint('wordstat_api', __name__, url_prefix='/api/wordstat')

STOP_WORDS = {
    "и", "в", "на", "с", "по", "для", "или", "от", "до", "под", "при", "за", "к", "из", "о",
    "the", "and", "for", "with", "from", "to", "of",
    "услуга", "услуги", "салон", "beauty", "service", "services",
}

SEED_STOP_WORDS = STOP_WORDS | {
    "network",
    "сеть",
    "точка",
    "адрес",
    "город",
    "рядом",
}

BUSINESS_TYPE_HINTS = {
    "beauty_salon": ["салон красоты", "косметология", "маникюр", "педикюр", "парикмахерская"],
    "barbershop": ["барбершоп", "мужская стрижка", "борода", "бритье"],
    "nail_studio": ["маникюр", "педикюр", "ногти", "гель лак"],
    "spa": ["спа", "массаж", "релакс", "уход за телом"],
    "massage": ["массаж", "релакс", "лечебный массаж"],
    "cosmetology": ["косметология", "чистка лица", "пилинг", "уход за лицом"],
    "brows_lashes": ["брови", "ресницы", "ламинирование ресниц"],
    "auto_service": ["автосервис", "сто", "ремонт авто", "диагностика авто", "техобслуживание"],
    "gas_station": [
        "азс",
        "азс рядом",
        "заправка",
        "заправка рядом",
        "заправка на карте",
        "круглосуточная азс",
        "бензин",
        "бензин 92",
        "бензин 95",
        "дизель",
        "дт",
        "топливо",
        "цены на бензин",
        "цены на дизель",
        "заправиться рядом",
    ],
    "cafe": ["кафе", "кофе", "обед", "завтрак", "доставка еды"],
    "school": ["школа", "обучение", "курсы", "уроки", "дети"],
    "workshop": ["мастерская", "ремонт", "изготовление", "срочный ремонт"],
    "shoe_repair": ["ремонт обуви", "обувная мастерская", "набoйки", "растяжка обуви"],
    "gym": ["спортзал", "фитнес", "тренировки", "тренажерный зал"],
    "shawarma": ["шаверма", "шаурма", "быстрое питание", "фастфуд"],
    "theater": ["театр", "спектакль", "сцена", "билеты"],
}

BEAUTY_BUSINESS_TYPES = {
    "beauty_salon", "barbershop", "nail_studio", "spa", "massage", "cosmetology", "brows_lashes", "makeup", "tanning"
}
BEAUTY_CATEGORIES = {"barber", "cosmetology", "eyebrows", "nails", "spa", "beauty", "hair", "makeup", "lashes"}
BEAUTY_TERMS = {"маникюр", "педикюр", "ногти", "барбер", "косметолог", "ресниц", "бров", "спа", "стрижк", "окрашив"}


def _extract_terms(text: str):
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", (text or "").lower())
    result = []
    for w in words:
        if len(w) < 3 or w in STOP_WORDS or w.isdigit():
            continue
        result.append(w)
    return result


def _row_get(row, key: str, idx: int = 0, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            pass
    if isinstance(row, (tuple, list)):
        return row[idx] if len(row) > idx else default
    return default


def _normalize_keyword_search_text(value: str) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def _dedupe_preserve_order(values, limit: int = 40):
    seen = set()
    result = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        key = _normalize_keyword_search_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _keyword_terms(value: str):
    terms = []
    for term in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", str(value or "").lower()):
        if len(term) < 3 or term in SEED_STOP_WORDS or term.isdigit():
            continue
        terms.append(term)
    return terms


def _resolve_wordstat_update_targets(cursor, business_id: str):
    cursor.execute(
        """
        SELECT id, name, city, business_type, network_id
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    selected = cursor.fetchone()
    if not selected:
        return [], "business"

    selected_dict = dict(selected) if not isinstance(selected, dict) and hasattr(selected, "keys") else selected
    network_id = str(_row_get(selected_dict, "network_id", 4, "") or "").strip()
    selected_id = str(_row_get(selected_dict, "id", 0, "") or "").strip()
    is_network_scope = bool(network_id) and selected_id == network_id

    if not is_network_scope:
        return [selected_dict], "business"

    cursor.execute(
        """
        SELECT id, name, city, business_type, network_id
        FROM businesses
        WHERE network_id = %s
          AND (is_active IS TRUE OR is_active IS NULL)
        ORDER BY CASE WHEN id = %s THEN 0 ELSE 1 END, name
        """,
        (network_id, network_id),
    )
    rows = cursor.fetchall() or []
    targets = [dict(row) if not isinstance(row, dict) and hasattr(row, "keys") else row for row in rows]
    return targets or [selected_dict], "network"


def _build_business_wordstat_seeds(cursor, business_row):
    business_id = str(_row_get(business_row, "id", 0, "") or "").strip()
    business_name = str(_row_get(business_row, "name", 1, "") or "").strip()
    city = str(_row_get(business_row, "city", 2, "") or "").strip()
    business_type = str(_row_get(business_row, "business_type", 3, "") or "").strip()

    seeds = []
    relevance_terms = []

    if business_type:
        cursor.execute(
            "SELECT label, description FROM businesstypes WHERE type_key = %s OR id = %s LIMIT 1",
            (business_type, business_type),
        )
        bt_row = cursor.fetchone()
        label = _row_get(bt_row, "label", 0, "") or ""
        description = _row_get(bt_row, "description", 1, "") or ""
        seeds.extend([label, description])
        relevance_terms.extend(_keyword_terms(label))
        relevance_terms.extend(_keyword_terms(description))
        for hint in BUSINESS_TYPE_HINTS.get(business_type, []):
            seeds.append(hint)
            relevance_terms.extend(_keyword_terms(hint))

    cursor.execute(
        """
        SELECT name, description
        FROM userservices
        WHERE business_id = %s
          AND (is_active IS TRUE OR is_active IS NULL)
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 80
        """,
        (business_id,),
    )
    for row in cursor.fetchall() or []:
        service_name = str(_row_get(row, "name", 0, "") or "").strip()
        service_description = str(_row_get(row, "description", 1, "") or "").strip()
        if service_name:
            seeds.append(service_name)
            relevance_terms.extend(_keyword_terms(service_name))
        if service_description:
            relevance_terms.extend(_keyword_terms(service_description))

    for token in _keyword_terms(business_type):
        relevance_terms.append(token)
    for token in _keyword_terms(business_name):
        relevance_terms.append(token)

    base_seeds = _dedupe_preserve_order(seeds, limit=10)
    if city:
        city_seeds = [f"{seed} {city}" for seed in base_seeds[:3]]
        base_seeds = _dedupe_preserve_order(base_seeds + city_seeds, limit=13)

    return base_seeds, set(_dedupe_preserve_order(relevance_terms, limit=120))


def _filter_business_wordstat_rows(rows, relevance_terms):
    if not rows:
        return []
    result = []
    by_keyword = {}
    strong_terms = [term for term in relevance_terms if len(term) >= 4]
    for row in rows:
        keyword = str(row.get("keyword") or "").strip()
        if not keyword:
            continue
        normalized = _normalize_keyword_search_text(keyword)
        if strong_terms and not any(term in normalized for term in strong_terms):
            continue
        previous = by_keyword.get(normalized)
        if previous is None or int(row.get("views") or 0) > int(previous.get("views") or 0):
            by_keyword[normalized] = row
    result = sorted(by_keyword.values(), key=lambda item: int(item.get("views") or 0), reverse=True)
    return result[:80]


def _save_business_wordstat_items(cursor, business_id: str, items: list[dict]):
    _ensure_custom_table(cursor)
    created_count = 0
    updated_count = 0
    for item in items:
        keyword = str(item.get("keyword") or "").strip()
        if not keyword:
            continue
        cursor.execute(
            """
            INSERT INTO wordstatkeywordscustom (id, business_id, keyword, views, category, updated_at, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (business_id, keyword)
            DO UPDATE SET
                views = EXCLUDED.views,
                category = COALESCE(NULLIF(EXCLUDED.category, ''), wordstatkeywordscustom.category),
                updated_at = CURRENT_TIMESTAMP
            RETURNING (xmax = 0) AS inserted
            """,
            (
                str(uuid.uuid4()),
                business_id,
                keyword,
                int(item.get("views") or 0),
                str(item.get("category") or "custom").strip() or "custom",
            ),
        )
        row = cursor.fetchone()
        inserted = bool(_row_get(row, "inserted", 0, False))
        if inserted:
            created_count += 1
        else:
            updated_count += 1
    return created_count, updated_count


def _count_existing_business_wordstat_items(cursor, business_id: str):
    targets, scope = _resolve_wordstat_update_targets(cursor, business_id)
    target_ids = [
        str(_row_get(target, "id", 0, "") or "").strip()
        for target in targets
        if str(_row_get(target, "id", 0, "") or "").strip()
    ]
    if not target_ids:
        return {"scope": scope, "targets": 0, "existing": 0, "last_update": None}

    _ensure_custom_table(cursor)
    placeholders = ",".join(["%s"] * len(target_ids))
    cursor.execute(
        f"""
        SELECT COUNT(*) AS existing, MAX(updated_at) AS last_update
        FROM wordstatkeywordscustom
        WHERE business_id IN ({placeholders})
        """,
        tuple(target_ids),
    )
    row = cursor.fetchone()
    return {
        "scope": scope,
        "targets": len(target_ids),
        "existing": int(_row_get(row, "existing", 0, 0) or 0),
        "last_update": _row_get(row, "last_update", 1, None),
    }


def _refresh_business_wordstat_keywords(cursor, business_id: str):
    if not config.is_configured():
        raise WordstatTemporaryUnavailable("Wordstat API is not configured")

    targets, scope = _resolve_wordstat_update_targets(cursor, business_id)
    client = WordstatClient.from_config(config)
    if config.oauth_token:
        client.set_access_token(config.oauth_token)

    summary = {
        "scope": scope,
        "targets": len(targets),
        "created": 0,
        "updated": 0,
        "fetched": 0,
        "saved": 0,
        "skipped_targets": 0,
    }

    for target in targets:
        target_id = str(_row_get(target, "id", 0, "") or "").strip()
        if not target_id:
            continue
        seeds, relevance_terms = _build_business_wordstat_seeds(cursor, target)
        if not seeds:
            summary["skipped_targets"] += 1
            continue
        payload = client.get_popular_queries(seeds, config.default_region)
        rows = _extract_live_wordstat_queries(payload)
        summary["fetched"] += len(rows)
        filtered_rows = _filter_business_wordstat_rows(rows, relevance_terms)
        categorized = []
        for row in filtered_rows:
            keyword = str(row.get("keyword") or "").strip()
            if not keyword:
                continue
            categorized.append(
                {
                    "keyword": keyword,
                    "views": int(row.get("views") or 0),
                    "category": _categorize_wordstat_keyword(keyword),
                }
            )
        created_count, updated_count = _save_business_wordstat_items(cursor, target_id, categorized)
        summary["created"] += created_count
        summary["updated"] += updated_count
        summary["saved"] += len(categorized)

    if summary["saved"] == 0:
        raise WordstatTemporaryUnavailable("Wordstat returned no rows for scoped business update")

    return summary


def _extract_live_wordstat_queries(api_payload):
    if not api_payload:
        return []

    blocks = api_payload if isinstance(api_payload, list) else [api_payload]
    rows = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        for section in ("results", "topRequests", "top_requests", "associations", "alsoSearch"):
            section_items = block.get(section) or []
            if not isinstance(section_items, list):
                continue
            for raw_item in section_items:
                if not isinstance(raw_item, dict):
                    continue
                text = str(
                    raw_item.get("text")
                    or raw_item.get("phrase")
                    or raw_item.get("query")
                    or raw_item.get("key")
                    or ""
                ).strip()
                if not text:
                    continue
                count = raw_item.get("count") or raw_item.get("shows") or raw_item.get("clicks") or 0
                try:
                    count = int(count)
                except Exception:
                    count = 0
                rows.append({"keyword": text, "views": count})

    by_keyword = {}
    for item in rows:
        key = _normalize_keyword_search_text(item.get("keyword") or "")
        if not key:
            continue
        previous = by_keyword.get(key)
        if not previous or int(item.get("views") or 0) > int(previous.get("views") or 0):
            by_keyword[key] = item
    return list(by_keyword.values())


def _categorize_wordstat_keyword(keyword: str) -> str:
    try:
        category, confidence, _matched = categorizer.categorize_service(keyword)
        if float(confidence or 0) >= 0.3:
            return str(category or "other").strip() or "other"
    except Exception:
        pass
    return "other"


def _load_live_wordstat_search(query: str, limit: int) -> list[dict]:
    if not config.is_configured():
        return []

    client = WordstatClient.from_config(config)
    if config.oauth_token:
        client.set_access_token(config.oauth_token)
    try:
        live_payload = client.get_popular_queries([query], config.default_region)
    except WordstatTemporaryUnavailable as error:
        print(f"Wordstat live search unavailable: {error}", flush=True)
        live_payload = None
    rows = _extract_live_wordstat_queries(live_payload)
    normalized_query = _normalize_keyword_search_text(query)
    if not rows and normalized_query:
        rows = [{"keyword": query, "views": 0}]

    items = []
    for row in rows:
        keyword = str(row.get("keyword") or "").strip()
        if not keyword:
            continue
        normalized_keyword = _normalize_keyword_search_text(keyword)
        if normalized_query and normalized_query not in normalized_keyword:
            ratio = difflib.SequenceMatcher(None, normalized_query, normalized_keyword).ratio()
            if ratio < 0.55:
                continue
        items.append(
            {
                "keyword": keyword,
                "views": int(row.get("views") or 0),
                "category": _categorize_wordstat_keyword(keyword),
                "updated_at": datetime.now().isoformat(),
                "source": "live_wordstat",
            }
        )
        if len(items) >= max(limit, 50):
            break
    return items


def _save_live_wordstat_items(cursor, items: list[dict]) -> None:
    if not items:
        return
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wordstatkeywords (
            id TEXT PRIMARY KEY,
            keyword TEXT UNIQUE NOT NULL,
            views INTEGER DEFAULT 0,
            category TEXT DEFAULT 'other',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_views ON wordstatkeywords(views DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_category ON wordstatkeywords(category)")
    for item in items:
        keyword = str(item.get("keyword") or "").strip()
        if not keyword:
            continue
        cursor.execute(
            """
            INSERT INTO wordstatkeywords (id, keyword, views, category, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (keyword)
            DO UPDATE SET
                views = GREATEST(wordstatkeywords.views, EXCLUDED.views),
                category = COALESCE(NULLIF(EXCLUDED.category, ''), wordstatkeywords.category),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                str(uuid.uuid4()),
                keyword,
                int(item.get("views") or 0),
                str(item.get("category") or "other").strip() or "other",
            ),
        )


def _score_keyword(keyword_text: str, terms):
    text = (keyword_text or "").lower()
    score = 0
    for t in terms:
        if t in text:
            score += 2 if len(t) >= 6 else 1
    return score


def _is_beauty_keyword(keyword_text: str, category: str) -> bool:
    category_l = (category or "").strip().lower()
    if category_l in BEAUTY_CATEGORIES:
        return True
    text = (keyword_text or "").lower()
    return any(term in text for term in BEAUTY_TERMS)


def _require_auth():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None, (jsonify({'success': False, 'error': 'Требуется авторизация'}), 401)
    user_data = verify_session(auth_header.split(' ', 1)[1])
    if not user_data:
        return None, (jsonify({'success': False, 'error': 'Недействительный токен'}), 401)
    return user_data, None


def _ensure_business_access(cursor, user_data, business_id: str):
    owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
    is_superadmin = bool(user_data.get('is_superadmin'))
    current_user_id = user_data.get('user_id') or user_data.get('id')
    if not owner_id:
        return (jsonify({'success': False, 'error': 'Бизнес не найден'}), 404)
    if owner_id != current_user_id and not is_superadmin:
        return (jsonify({'success': False, 'error': 'Нет доступа к бизнесу'}), 403)
    return None


def _wordstat_update_error_response(details: str, user_data):
    clean_message = WORDSTAT_TEMPORARILY_UNAVAILABLE_MESSAGE
    payload = {
        'success': False,
        'error': clean_message,
        'code': 'wordstat_api_temporarily_unavailable',
    }
    if bool((user_data or {}).get('is_superadmin')):
        payload['superadmin'] = details
    return jsonify(payload), 503


def _ensure_excluded_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wordstatkeywordsexcluded (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (business_id, keyword)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wordstat_excluded_business ON wordstatkeywordsexcluded(business_id)"
    )


def _ensure_custom_table(cursor):
    # Avoid race errors on first concurrent requests that try to initialize the same table.
    cursor.execute(
        """
        DO $$
        BEGIN
            CREATE TABLE wordstatkeywordscustom (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                keyword TEXT NOT NULL,
                views INTEGER DEFAULT 0,
                category TEXT DEFAULT 'custom',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (business_id, keyword)
            );
        EXCEPTION
            WHEN duplicate_table OR unique_violation THEN
                NULL;
        END
        $$;
        """
    )
    cursor.execute(
        """
        DO $$
        BEGIN
            CREATE INDEX idx_wordstat_custom_business ON wordstatkeywordscustom(business_id);
        EXCEPTION
            WHEN duplicate_table OR duplicate_object THEN
                NULL;
        END
        $$;
        """
    )


def _ensure_negative_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS seonegativekeywords (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            phrase TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'global',
            category TEXT DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (business_id, phrase, scope, category)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_seo_negative_business ON seonegativekeywords(business_id)"
    )


def _load_negative_rows(cursor, business_id: str):
    _ensure_negative_table(cursor)
    cursor.execute(
        """
        SELECT id, phrase, scope, category, created_at
        FROM seonegativekeywords
        WHERE business_id = %s
          AND is_active IS TRUE
        ORDER BY created_at DESC
        """,
        (business_id,),
    )
    return cursor.fetchall() or []


def _negative_reason_for(keyword: str, category: str, negative_rows):
    keyword_l = (keyword or "").strip().lower()
    category_l = (category or "").strip().lower()
    if not keyword_l:
        return ""
    for row in negative_rows:
        phrase = str(_row_get(row, 'phrase', 1, '') or '').strip().lower()
        scope = str(_row_get(row, 'scope', 2, 'global') or 'global').strip().lower()
        row_category = str(_row_get(row, 'category', 3, '') or '').strip().lower()
        if not phrase:
            continue
        if scope == 'category':
            if row_category and row_category == category_l and phrase in keyword_l:
                return f"category:{row_category}:{phrase}"
            continue
        if phrase in keyword_l:
            return f"global:{phrase}"
    return ""


@wordstat_bp.route('/keywords', methods=['GET'])
def get_keywords():
    """Get popular keywords filtered by business context (services/type/city)."""
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    business_id = (request.args.get('business_id') or '').strip()
    use_city = (request.args.get('use_city') or '').strip().lower() in ('1', 'true', 'yes')
    include_blocked = (request.args.get('include_blocked') or '').strip().lower() in ('1', 'true', 'yes')

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            SELECT to_regclass('public.wordstatkeywords') AS t
            """
        )
        reg_row = cursor.fetchone() or {}
        table_exists = (reg_row.get('t') if isinstance(reg_row, dict) else None)
        if not table_exists:
            return jsonify({
                'success': True,
                'count': 0,
                'items': [],
                'grouped': {}
            })

        if business_id:
            access_error = _ensure_business_access(cursor, user_data, business_id)
            if access_error:
                return access_error
        keywords_payload = collect_ranked_keywords(
            cursor,
            business_id=business_id or None,
            user_id=(user_data.get('user_id') or user_data.get('id')),
            limit=600,
            add_city_suffix=use_city,
            fallback_global_when_empty_terms=False,
            long_weight=2,
            short_weight=1,
            include_negative_blocked=include_blocked,
        )
        keywords = keywords_payload.get('items', [])
        if business_id:
            _ensure_custom_table(cursor)
            _ensure_excluded_table(cursor)
            negative_rows = _load_negative_rows(cursor, business_id)
            cursor.execute(
                "SELECT keyword FROM wordstatkeywordsexcluded WHERE business_id = %s",
                (business_id,),
            )
            excluded = {
                str(_row_get(row, 'keyword', 0, '') or '').strip().lower()
                for row in (cursor.fetchall() or [])
            }
            cursor.execute(
                """
                SELECT keyword, views, category, updated_at
                FROM wordstatkeywordscustom
                WHERE business_id = %s
                ORDER BY updated_at DESC NULLS LAST
                """,
                (business_id,),
            )
            custom_keywords = []
            for row in cursor.fetchall() or []:
                keyword = str(_row_get(row, 'keyword', 0, '') or '').strip()
                keyword_l = keyword.lower()
                if not keyword or keyword_l in excluded:
                    continue
                category = str(_row_get(row, 'category', 2, '') or '').strip()
                reason = _negative_reason_for(keyword, category, negative_rows)
                if reason and not include_blocked:
                    continue
                item = {
                    'keyword': keyword,
                    'views': int(_row_get(row, 'views', 1, 0) or 0),
                    'category': category or 'custom',
                    'updated_at': _row_get(row, 'updated_at', 3, None),
                    'is_custom': True,
                    'source': 'custom',
                    'negative_blocked': bool(reason),
                    'negative_reason': reason or '',
                }
                if use_city:
                    keywords_city = (keywords_payload.get('city') or '').strip()
                    if keywords_city and keywords_city.lower() not in keyword_l:
                        item['keyword_with_city'] = f"{keyword} {keywords_city}"
                    else:
                        item['keyword_with_city'] = keyword
                custom_keywords.append(item)

            seen_keywords = set()
            merged_keywords = []
            for item in custom_keywords + keywords:
                keyword_l = str(item.get('keyword') or '').strip().lower()
                if not keyword_l or keyword_l in seen_keywords:
                    continue
                seen_keywords.add(keyword_l)
                merged_keywords.append(item)
            keywords = merged_keywords[:600]

        by_category = {}
        for item in keywords:
            category = str(item.get('category') or 'other').strip() or 'other'
            by_category.setdefault(category, []).append(item)
            
        return jsonify({
            'success': True,
            'count': len(keywords),
            'items': keywords,
            'grouped': by_category
        })
        
    except Exception as e:
        print(f"Error fetching wordstat keywords: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@wordstat_bp.route('/search', methods=['GET'])
def search_keywords():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    business_id = (request.args.get('business_id') or '').strip()
    query = (request.args.get('q') or '').strip()
    normalized_query = _normalize_keyword_search_text(query)
    try:
        limit = int(request.args.get('limit') or 10)
    except Exception:
        limit = 10
    limit = min(max(limit, 1), 50)
    include_blocked = (request.args.get('include_blocked') or '').strip().lower() in ('1', 'true', 'yes')

    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400
    if len(query) < 2:
        return jsonify({'success': True, 'count': 0, 'items': []})

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error

        _ensure_excluded_table(cursor)
        _ensure_custom_table(cursor)
        negative_rows = _load_negative_rows(cursor, business_id)

        cursor.execute(
            "SELECT keyword FROM wordstatkeywordsexcluded WHERE business_id = %s",
            (business_id,),
        )
        excluded = {
            str(_row_get(r, 'keyword', 0, '') or '').strip().lower()
            for r in (cursor.fetchall() or [])
        }

        cursor.execute(
            """
            SELECT keyword, views, category, updated_at
            FROM wordstatkeywordscustom
            WHERE business_id = %s
            """,
            (business_id,),
        )
        custom_existing = {
            str(_row_get(r, 'keyword', 0, '') or '').strip().lower()
            for r in (cursor.fetchall() or [])
        }

        like_q = f"%{normalized_query}%"
        cursor.execute(
            """
            SELECT keyword, views, category, updated_at
            FROM wordstatkeywords
            WHERE LOWER(keyword) LIKE %s
            ORDER BY views DESC
            LIMIT 200
            """,
            (like_q,),
        )
        rows = cursor.fetchall() or []
        items = []
        for row in rows:
            item = dict(row) if not isinstance(row, dict) else row
            kw = (item.get('keyword') or '').strip().lower()
            if not kw:
                continue
            if kw in excluded or kw in custom_existing:
                continue
            reason = _negative_reason_for(item.get('keyword') or '', item.get('category') or '', negative_rows)
            if reason:
                if include_blocked:
                    item['negative_blocked'] = True
                    item['negative_reason'] = reason
                    items.append(item)
                continue
            item['negative_blocked'] = False
            item['negative_reason'] = ''
            items.append(item)
            if len(items) >= limit:
                break

        if len(items) == 0 and normalized_query:
            fuzzy_seed = normalized_query[: max(4, len(normalized_query) - 2)]
            cursor.execute(
                """
                SELECT keyword, views, category, updated_at
                FROM wordstatkeywords
                WHERE LOWER(keyword) LIKE %s
                ORDER BY views DESC
                LIMIT 500
                """,
                (f"%{fuzzy_seed}%",),
            )
            fuzzy_rows = cursor.fetchall() or []
            scored_items = []
            for row in fuzzy_rows:
                item = dict(row) if not isinstance(row, dict) else row
                keyword_value = str(item.get('keyword') or '').strip()
                keyword_lower = keyword_value.lower()
                if not keyword_lower:
                    continue
                if keyword_lower in excluded or keyword_lower in custom_existing:
                    continue
                reason = _negative_reason_for(keyword_value, item.get('category') or '', negative_rows)
                if reason and not include_blocked:
                    continue

                ratio = difflib.SequenceMatcher(
                    None,
                    normalized_query,
                    _normalize_keyword_search_text(keyword_value),
                ).ratio()
                if ratio < 0.55 and fuzzy_seed not in _normalize_keyword_search_text(keyword_value):
                    continue

                item['negative_blocked'] = bool(reason)
                item['negative_reason'] = reason or ''
                item['_score'] = ratio
                scored_items.append(item)

            scored_items.sort(
                key=lambda item: (
                    -float(item.get('_score') or 0),
                    -int(item.get('views') or 0),
                )
            )
            items = []
            for item in scored_items:
                item.pop('_score', None)
                items.append(item)
                if len(items) >= limit:
                    break

        if len(items) == 0 and normalized_query:
            live_items = _load_live_wordstat_search(query, limit=50)
            if live_items:
                _save_live_wordstat_items(cursor, live_items)
                conn.commit()
            for item in live_items:
                keyword_value = str(item.get('keyword') or '').strip()
                keyword_lower = keyword_value.lower()
                if not keyword_lower:
                    continue
                if keyword_lower in excluded or keyword_lower in custom_existing:
                    continue
                reason = _negative_reason_for(keyword_value, item.get('category') or '', negative_rows)
                if reason:
                    if include_blocked:
                        item['negative_blocked'] = True
                        item['negative_reason'] = reason
                        items.append(item)
                    continue
                item['negative_blocked'] = False
                item['negative_reason'] = ''
                items.append(item)
                if len(items) >= limit:
                    break

        return jsonify({'success': True, 'count': len(items), 'items': items})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@wordstat_bp.route('/update', methods=['POST'])
def trigger_update():
    """Refresh Wordstat keywords for the selected business or network."""
    conn = None
    try:
        user_data, auth_error = _require_auth()
        if auth_error:
            return auth_error

        payload = request.get_json(silent=True) or {}
        business_id = (payload.get('business_id') or request.args.get('business_id') or '').strip()
        if not business_id:
            return jsonify({'success': False, 'error': 'Не указан business_id'}), 400

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error

        if not config.is_configured():
            return jsonify({
                'success': False,
                'error': 'Wordstat API не настроен: задайте YANDEX_WORDSTAT_API_KEY и YANDEX_WORDSTAT_FOLDER_ID'
            }), 400

        summary = _refresh_business_wordstat_keywords(cursor, business_id)
        conn.commit()
        scope_label = 'сети' if summary.get('scope') == 'network' else 'точки'
        return jsonify({
            'success': True,
            'message': (
                f"SEO-запросы для {scope_label} обновлены: "
                f"новых {summary.get('created', 0)}, обновлено {summary.get('updated', 0)}."
            ),
            'summary': summary,
        })
    except WordstatTemporaryUnavailable as error:
        if conn is not None:
            try:
                cached_summary = _count_existing_business_wordstat_items(cursor, business_id)
                if int(cached_summary.get("existing") or 0) > 0:
                    conn.rollback()
                    scope_label = 'сети' if cached_summary.get('scope') == 'network' else 'точки'
                    payload = {
                        'success': True,
                        'message': (
                            f"Wordstat ограничил частоту запросов. "
                            f"Показываем уже сохранённые SEO-запросы для {scope_label}; "
                            f"повторите обновление позже."
                        ),
                        'warning': 'wordstat_rate_limited_using_cached_keywords',
                        'summary': cached_summary,
                    }
                    if bool((user_data or {}).get('is_superadmin')):
                        payload['superadmin'] = str(error)
                    return jsonify(payload)
            except Exception:
                pass
            conn.rollback()
        return _wordstat_update_error_response(str(error), user_data if 'user_data' in locals() else None)
    except Exception as e:
        if conn is not None:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn is not None:
            conn.close()


@wordstat_bp.route('/keywords', methods=['DELETE'])
def exclude_keyword():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    business_id = (payload.get('business_id') or '').strip()
    keyword = (payload.get('keyword') or '').strip()

    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400
    if not keyword:
        return jsonify({'success': False, 'error': 'Не указан keyword'}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error

        _ensure_excluded_table(cursor)
        cursor.execute(
            """
            INSERT INTO wordstatkeywordsexcluded (id, business_id, keyword, created_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (business_id, keyword) DO NOTHING
            """,
            (str(uuid.uuid4()), business_id, keyword),
        )
        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Ключевой запрос удалён и исключён из оптимизации'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@wordstat_bp.route('/keywords/custom', methods=['POST'])
def add_custom_keyword():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    business_id = (payload.get('business_id') or '').strip()
    keyword = (payload.get('keyword') or '').strip()
    category = (payload.get('category') or 'custom').strip() or 'custom'
    try:
        views = int(payload.get('views') or 0)
    except Exception:
        views = 0

    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400
    if not keyword:
        return jsonify({'success': False, 'error': 'Не указан keyword'}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error

        _ensure_custom_table(cursor)
        cursor.execute(
            """
            INSERT INTO wordstatkeywordscustom (id, business_id, keyword, views, category, updated_at, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (business_id, keyword)
            DO UPDATE SET
                views = EXCLUDED.views,
                category = COALESCE(NULLIF(EXCLUDED.category, ''), wordstatkeywordscustom.category),
                updated_at = CURRENT_TIMESTAMP
            """,
            (str(uuid.uuid4()), business_id, keyword, views, category),
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Ключевой запрос добавлен'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@wordstat_bp.route('/metadata', methods=['GET'])
def get_metadata():
    """Get metadata about last update"""
    try:
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'prompts')
        metadata_path = os.path.join(prompts_dir, 'wordstat_metadata.json')
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                import json
                data = json.load(f)
                return jsonify({'success': True, 'metadata': data})
        else:
            return jsonify({'success': False, 'error': 'No metadata found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@wordstat_bp.route('/negative-keywords', methods=['GET'])
def list_negative_keywords():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    business_id = (request.args.get('business_id') or '').strip()
    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error
        rows = _load_negative_rows(cursor, business_id)
        items = []
        for row in rows:
            items.append({
                'id': _row_get(row, 'id', 0, ''),
                'phrase': _row_get(row, 'phrase', 1, ''),
                'scope': _row_get(row, 'scope', 2, 'global') or 'global',
                'category': _row_get(row, 'category', 3, '') or '',
                'created_at': _row_get(row, 'created_at', 4, None),
            })
        return jsonify({'success': True, 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@wordstat_bp.route('/negative-keywords', methods=['POST'])
def add_negative_keyword():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    business_id = (payload.get('business_id') or '').strip()
    phrase = (payload.get('phrase') or '').strip().lower()
    scope = (payload.get('scope') or 'global').strip().lower()
    category = (payload.get('category') or '').strip().lower()

    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400
    if not phrase:
        return jsonify({'success': False, 'error': 'Не указано минус-слово'}), 400
    if scope not in ('global', 'category'):
        return jsonify({'success': False, 'error': 'Неверный scope'}), 400
    if scope == 'category' and not category:
        return jsonify({'success': False, 'error': 'Для category scope укажите category'}), 400
    if scope == 'global':
        category = ''

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error
        _ensure_negative_table(cursor)
        cursor.execute(
            """
            INSERT INTO seonegativekeywords (id, business_id, phrase, scope, category, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (business_id, phrase, scope, category)
            DO UPDATE SET
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            """,
            (str(uuid.uuid4()), business_id, phrase, scope, category),
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Минус-слово добавлено'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@wordstat_bp.route('/negative-keywords/bulk', methods=['POST'])
def add_negative_keywords_bulk():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    business_id = (payload.get('business_id') or '').strip()
    scope = (payload.get('scope') or 'global').strip().lower()
    category = (payload.get('category') or '').strip().lower()
    raw_text = payload.get('raw_text') or ''
    items = payload.get('items') or []

    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400
    if scope not in ('global', 'category'):
        return jsonify({'success': False, 'error': 'Неверный scope'}), 400
    if scope == 'category' and not category:
        return jsonify({'success': False, 'error': 'Для category scope укажите category'}), 400
    if scope == 'global':
        category = ''

    phrases: list[str] = []
    if isinstance(raw_text, str) and raw_text.strip():
        phrases.extend([line.strip().lower() for line in raw_text.splitlines() if line.strip()])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, str) and item.strip():
                phrases.append(item.strip().lower())
            elif isinstance(item, dict):
                phrase = str(item.get('phrase') or '').strip().lower()
                if phrase:
                    phrases.append(phrase)
    phrases = list(dict.fromkeys(phrases))
    if not phrases:
        return jsonify({'success': False, 'error': 'Нет минус-слов для добавления'}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error
        _ensure_negative_table(cursor)
        for phrase in phrases:
            cursor.execute(
                """
                INSERT INTO seonegativekeywords (id, business_id, phrase, scope, category, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (business_id, phrase, scope, category)
                DO UPDATE SET
                    is_active = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (str(uuid.uuid4()), business_id, phrase, scope, category),
            )
        conn.commit()
        return jsonify({'success': True, 'count': len(phrases), 'message': f'Добавлено минус-слов: {len(phrases)}'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@wordstat_bp.route('/negative-keywords', methods=['DELETE'])
def delete_negative_keyword():
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    business_id = (payload.get('business_id') or '').strip()
    negative_id = (payload.get('id') or '').strip()
    phrase = (payload.get('phrase') or '').strip().lower()
    scope = (payload.get('scope') or 'global').strip().lower()
    category = (payload.get('category') or '').strip().lower()

    if not business_id:
        return jsonify({'success': False, 'error': 'Не указан business_id'}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        access_error = _ensure_business_access(cursor, user_data, business_id)
        if access_error:
            return access_error
        _ensure_negative_table(cursor)
        if negative_id:
            cursor.execute(
                "DELETE FROM seonegativekeywords WHERE business_id = %s AND id = %s",
                (business_id, negative_id),
            )
        elif phrase:
            cursor.execute(
                """
                DELETE FROM seonegativekeywords
                WHERE business_id = %s
                  AND phrase = %s
                  AND scope = %s
                  AND COALESCE(category, '') = %s
                """,
                (business_id, phrase, scope, category if scope == 'category' else ''),
            )
        else:
            return jsonify({'success': False, 'error': 'Укажите id или phrase'}), 400
        conn.commit()
        return jsonify({'success': True, 'message': 'Минус-слово удалено'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()
