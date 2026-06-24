import hashlib
import json
import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json

from auth_system import verify_session
from core.helpers import get_business_owner_id
from database_manager import DatabaseManager
from services.gigachat_client import analyze_text_with_gigachat


average_ticket_bp = Blueprint("average_ticket_api", __name__)
PROMPT_TYPE = "average_ticket_matrix"
EVENT_TYPES = {
    "offered",
    "bought",
    "declined",
    "next_visit_booked",
    "package_offered",
    "package_bought",
}
EDITABLE_LINK_FIELDS = {
    "reason",
    "admin_script",
    "master_script",
    "offer_timing",
    "compatibility",
    "priority",
    "expected_effect",
    "status",
}


def _row_value(row, key, index=None, default=None):
    if row is None:
        return default
    if hasattr(row, "get"):
        return row.get(key, default)
    if index is None:
        return default
    try:
        return row[index]
    except Exception:
        return default


def _require_business_access():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None, (jsonify({"error": "Требуется авторизация"}), 401)

    token = auth_header.split(" ")[1]
    user_data = verify_session(token)
    if not user_data:
        return None, None, (jsonify({"error": "Недействительный токен"}), 401)

    business_id = str(
        request.args.get("business_id")
        or (request.get_json(silent=True) or {}).get("business_id")
        or ""
    ).strip()
    if not business_id:
        return user_data, None, (jsonify({"error": "business_id обязателен"}), 400)

    db = DatabaseManager()
    cursor = db.conn.cursor()
    owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
    db.close()
    if not owner_id:
        return user_data, business_id, (jsonify({"error": "Бизнес не найден"}), 404)
    if owner_id != user_data.get("user_id") and not user_data.get("is_superadmin"):
        return user_data, business_id, (jsonify({"error": "Нет доступа к бизнесу"}), 403)
    return user_data, business_id, None


def _ensure_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS averageticketmatrices (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'draft',
            source_services_hash TEXT,
            matrix_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            generated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_averageticketmatrices_business_id ON averageticketmatrices(business_id, generated_at DESC)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS averageticketevents (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            matrix_id TEXT REFERENCES averageticketmatrices(id) ON DELETE SET NULL,
            link_id TEXT,
            package_id TEXT,
            booking_id TEXT,
            main_service_id TEXT REFERENCES userservices(id) ON DELETE SET NULL,
            addon_service_id TEXT REFERENCES userservices(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,
            event_date DATE DEFAULT CURRENT_DATE,
            amount NUMERIC(12, 2),
            master_id TEXT,
            client_name TEXT,
            notes TEXT,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_averageticketevents_business_date
        ON averageticketevents(business_id, event_date DESC, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_averageticketevents_booking
        ON averageticketevents(business_id, booking_id)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS averageticketpackages (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            service_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            service_names JSONB NOT NULL DEFAULT '[]'::jsonb,
            base_total NUMERIC(12, 2) DEFAULT 0,
            package_price NUMERIC(12, 2),
            bonus_text TEXT,
            positioning TEXT,
            script TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_averageticketpackages_business_status
        ON averageticketpackages(business_id, status)
        """
    )


def _table_columns(cursor, table_name):
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (str(table_name).lower(),),
    )
    columns = set()
    for row in cursor.fetchall() or []:
        name = _row_value(row, "column_name", 0)
        if name:
            columns.add(str(name).lower())
    return columns


def _table_exists(cursor, table_name):
    cursor.execute("SELECT to_regclass(%s)", (f"public.{str(table_name).lower()}",))
    row = cursor.fetchone()
    return bool(_row_value(row, "to_regclass", 0))


def _load_business(cursor, business_id):
    cursor.execute(
        """
        SELECT id, name, business_type, industry, city, country
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    return {
        "id": _row_value(row, "id", 0),
        "name": _row_value(row, "name", 1),
        "business_type": _row_value(row, "business_type", 2),
        "industry": _row_value(row, "industry", 3),
        "city": _row_value(row, "city", 4),
        "country": _row_value(row, "country", 5),
    }


def _load_services(cursor, business_id):
    cursor.execute(
        """
        SELECT id, category, name, optimized_name, description, optimized_description, price
        FROM userservices
        WHERE business_id = %s AND (is_active IS TRUE OR is_active IS NULL)
        ORDER BY category NULLS LAST, name NULLS LAST
        """,
        (business_id,),
    )
    services = []
    for row in cursor.fetchall() or []:
        services.append(
            {
                "id": str(_row_value(row, "id", 0) or ""),
                "category": str(_row_value(row, "category", 1) or "Без категории"),
                "name": str(_row_value(row, "name", 2) or ""),
                "optimized_name": str(_row_value(row, "optimized_name", 3) or ""),
                "description": str(_row_value(row, "description", 4) or ""),
                "optimized_description": str(_row_value(row, "optimized_description", 5) or ""),
                "price": str(_row_value(row, "price", 6) or ""),
            }
        )
    return [item for item in services if item["id"] and item["name"]]


def _services_hash(services):
    compact = [
        {
            "id": item.get("id"),
            "category": item.get("category"),
            "name": item.get("name"),
            "optimized_name": item.get("optimized_name"),
            "price": item.get("price"),
        }
        for item in services
    ]
    raw = json.dumps(compact, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _date_string(value):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _money_to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _parse_money(value):
    text = str(value or "").replace("\xa0", " ")
    match = re.search(r"-?\d+(?:[\s.,]\d{3})*(?:[,.]\d{1,2})?", text)
    if not match:
        return Decimal("0")
    raw = match.group(0).replace(" ", "")
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    raw = raw.replace(",", "")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def _service_price_map(services):
    return {item.get("id"): _parse_money(item.get("price")) for item in services}


def _find_service_by_name(services, service_name):
    needle = _norm(service_name)
    if not needle:
        return None
    for service in services:
        if needle == _norm(_service_display_name(service)) or needle == _norm(service.get("name")):
            return service
    for service in services:
        haystack = _norm(_service_display_name(service))
        if needle in haystack or haystack in needle:
            return service
    return None


def _load_packages(cursor, business_id):
    _ensure_table(cursor)
    cursor.execute(
        """
        SELECT id, name, service_ids, service_names, base_total, package_price, bonus_text,
               positioning, script, status, created_at, updated_at
        FROM averageticketpackages
        WHERE business_id = %s
        ORDER BY updated_at DESC, created_at DESC
        """,
        (business_id,),
    )
    packages = []
    for row in cursor.fetchall() or []:
        packages.append(
            {
                "id": _row_value(row, "id", 0),
                "name": _row_value(row, "name", 1),
                "service_ids": _row_value(row, "service_ids", 2) or [],
                "service_names": _row_value(row, "service_names", 3) or [],
                "base_total": _money_to_float(_row_value(row, "base_total", 4)) or 0,
                "package_price": _money_to_float(_row_value(row, "package_price", 5)),
                "bonus_text": _row_value(row, "bonus_text", 6) or "",
                "positioning": _row_value(row, "positioning", 7) or "",
                "script": _row_value(row, "script", 8) or "",
                "status": _row_value(row, "status", 9) or "draft",
                "created_at": _date_string(_row_value(row, "created_at", 10)),
                "updated_at": _date_string(_row_value(row, "updated_at", 11)),
            }
        )
    return packages


def _calculate_package_totals(services, service_ids, package_price):
    prices = _service_price_map(services)
    selected_services = [item for item in services if item.get("id") in service_ids]
    base_total = sum(prices.get(item.get("id"), Decimal("0")) for item in selected_services)
    service_names = [_service_display_name(item) for item in selected_services]
    parsed_package_price = None
    if package_price not in {None, ""}:
        try:
            parsed_package_price = Decimal(str(package_price))
        except InvalidOperation:
            parsed_package_price = _parse_money(package_price)
    return base_total, parsed_package_price, service_names


def _load_latest_matrix(cursor, business_id):
    _ensure_table(cursor)
    cursor.execute(
        """
        SELECT id, business_id, status, source_services_hash, matrix_json, generated_by, generated_at, updated_at
        FROM averageticketmatrices
        WHERE business_id = %s
        ORDER BY generated_at DESC
        LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": _row_value(row, "id", 0),
        "business_id": _row_value(row, "business_id", 1),
        "status": _row_value(row, "status", 2),
        "source_services_hash": _row_value(row, "source_services_hash", 3),
        "matrix": _row_value(row, "matrix_json", 4) or {},
        "generated_by": _row_value(row, "generated_by", 5),
        "generated_at": str(_row_value(row, "generated_at", 6) or ""),
        "updated_at": str(_row_value(row, "updated_at", 7) or ""),
    }


def _prompt_from_db(cursor):
    cursor.execute(
        "SELECT prompt_text FROM aiprompts WHERE prompt_type = %s LIMIT 1",
        (PROMPT_TYPE,),
    )
    row = cursor.fetchone()
    prompt_text = str(_row_value(row, "prompt_text", 0) or "").strip()
    return prompt_text or _default_generation_prompt()


def _default_generation_prompt():
    return """Ты — коммерческий методолог салона красоты и локального сервиса.
На основе полного списка услуг из LocalOS создай матрицу увеличения среднего чека.

Жесткие правила:
1) Используй только услуги из входного списка. Не придумывай новые услуги.
2) Не предлагай медицински или косметологически рискованные сочетания как same_visit. Для инъекций, пилингов, лазера и агрессивных процедур используй consultation_required или next_visit.
3) Не дублируй вкладку Финансы: финансы только контекст, результат — практические связки, скрипты и пакеты.
4) Ответ только JSON, без markdown.

Верни JSON:
{
  "upsell_matrix": [
    {
      "main_service_id": "...",
      "main_service": "...",
      "main_category": "...",
      "recommended_addons": [
        {
          "id": "stable-link-id",
          "service_id": "...",
          "service": "...",
          "category": "...",
          "price": "...",
          "offer_timing": "before_visit|during_visit|checkout|next_visit",
          "priority": "high|medium|low",
          "compatibility": "same_visit|next_visit|consultation_required|avoid",
          "reason": "...",
          "admin_script": "...",
          "master_script": "...",
          "expected_effect": "add_on|cross_sell|package|rebooking",
          "status": "draft"
        }
      ]
    }
  ],
  "cross_sell_pairs": [],
  "packages": [],
  "risks": [],
  "implementation_priorities": []
}"""


def _build_generation_payload(business, services):
    trimmed_services = services[:450]
    return {
        "business": business,
        "services_source": "Работа с картами",
        "services_count": len(services),
        "services": trimmed_services,
        "finance_context": {
            "note": "Финансовые KPI показываются ссылкой на Финансы. Здесь нужен операционный план роста среднего чека.",
            "target_metrics": ["average_ticket", "add_on_rate", "cross_sell_rate", "package_sales"],
        },
    }


def _build_prompt(prompt_template, payload):
    return (
        prompt_template
        + "\n\nВходные данные LocalOS:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _extract_json_object(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _norm(value):
    return re.sub(r"[^a-zа-я0-9]+", " ", str(value or "").lower().replace("ё", "е")).strip()


def _service_display_name(service):
    return service.get("optimized_name") or service.get("name") or ""


def _fallback_matrix(services):
    by_category = {}
    for service in services:
        category = service.get("category") or "Без категории"
        by_category.setdefault(category, []).append(service)

    def find_candidates(main_service):
        main_name = _norm(_service_display_name(main_service))
        main_category = _norm(main_service.get("category"))
        candidates = []
        for service in services:
            if service.get("id") == main_service.get("id"):
                continue
            name = _norm(_service_display_name(service))
            category = _norm(service.get("category"))
            score = 0
            if "окраш" in main_name or "блонд" in main_name or "тонир" in main_name:
                if any(key in name for key in ["уход", "счастье", "коллаген", "увлаж", "тонир", "уклад", "челк"]):
                    score += 5
            if "стриж" in main_name and "муж" in main_category:
                if any(key in name for key in ["бород", "усов", "камуфляж", "уклад", "бров"]):
                    score += 5
            if "стриж" in main_name and "жен" in main_category:
                if any(key in name for key in ["уклад", "уход", "счастье", "бров", "ресниц"]):
                    score += 5
            if "маник" in main_name:
                if any(key in name for key in ["парафин", "укреп", "ремонт", "педик", "лечеб"]):
                    score += 5
            if "педик" in main_name:
                if any(key in name for key in ["маник", "парафин", "покрыт", "лечеб"]):
                    score += 5
            if any(key in main_name for key in ["губ", "ботулин", "биорев", "контур"]):
                if any(key in name for key in ["маска", "консультац"]):
                    score += 5
            if category != main_category and score > 0:
                score += 1
            if score > 0:
                candidates.append((score, service))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in candidates[:5]]

    matrix = []
    for service in services[:120]:
        addons = []
        for candidate in find_candidates(service):
            link_id = f"{service.get('id')}:{candidate.get('id')}"
            category = candidate.get("category") or ""
            compatibility = "same_visit"
            timing = "during_visit"
            name_norm = _norm(_service_display_name(candidate))
            if any(key in name_norm for key in ["ботулин", "биорев", "пилинг", "лазер", "инъек", "губ"]):
                compatibility = "consultation_required"
                timing = "next_visit"
            addons.append(
                {
                    "id": link_id,
                    "service_id": candidate.get("id"),
                    "service": _service_display_name(candidate),
                    "category": category,
                    "price": candidate.get("price") or "",
                    "offer_timing": timing,
                    "priority": "high" if len(addons) < 2 else "medium",
                    "compatibility": compatibility,
                    "reason": "Логичная допродажа к текущей услуге из существующего прайса.",
                    "admin_script": f"К этой записи можно добавить {_service_display_name(candidate)}. Хотите предложить клиенту?",
                    "master_script": f"По результату процедуры можно рекомендовать {_service_display_name(candidate)} как следующий шаг.",
                    "expected_effect": "add_on" if compatibility == "same_visit" else "rebooking",
                    "status": "draft",
                }
            )
        if addons:
            matrix.append(
                {
                    "main_service_id": service.get("id"),
                    "main_service": _service_display_name(service),
                    "main_category": service.get("category") or "",
                    "recommended_addons": addons,
                }
            )

    categories = list(by_category.keys())
    return {
        "upsell_matrix": matrix,
        "cross_sell_pairs": [
            {
                "from_category": item,
                "to_category": other,
                "reason": "Категории можно проверять на кросс-сейл по расписанию и профилю клиента.",
                "status": "draft",
            }
            for item in categories[:4]
            for other in categories[:4]
            if item != other
        ][:8],
        "packages": [],
        "risks": [
            "Проверяйте медицинские и косметологические ограничения перед совмещением процедур.",
            "Все предложения являются черновиком и требуют подтверждения владельца или ведущего мастера.",
        ],
        "implementation_priorities": [
            "Утвердить 10-20 связок с высоким приоритетом.",
            "Запустить скрипты на администраторах и мастерах.",
            "Еженедельно смотреть конверсию предложили → купили.",
        ],
        "generation_mode": "fallback",
    }


def _normalize_matrix(raw_matrix, services):
    matrix = raw_matrix if isinstance(raw_matrix, dict) else {}
    service_ids = {item.get("id") for item in services}
    service_by_id = {item.get("id"): item for item in services}
    normalized_rows = []

    for row in matrix.get("upsell_matrix") or []:
        if not isinstance(row, dict):
            continue
        main_service_id = str(row.get("main_service_id") or "")
        if main_service_id not in service_ids:
            continue
        main_service = service_by_id.get(main_service_id) or {}
        addons = []
        for addon in row.get("recommended_addons") or []:
            if not isinstance(addon, dict):
                continue
            service_id = str(addon.get("service_id") or "")
            if service_id not in service_ids or service_id == main_service_id:
                continue
            candidate = service_by_id.get(service_id) or {}
            link_id = str(addon.get("id") or f"{main_service_id}:{service_id}")
            addons.append(
                {
                    "id": link_id,
                    "service_id": service_id,
                    "service": str(addon.get("service") or _service_display_name(candidate)),
                    "category": str(addon.get("category") or candidate.get("category") or ""),
                    "price": str(addon.get("price") or candidate.get("price") or ""),
                    "offer_timing": str(addon.get("offer_timing") or "during_visit"),
                    "priority": str(addon.get("priority") or "medium"),
                    "compatibility": str(addon.get("compatibility") or "same_visit"),
                    "reason": str(addon.get("reason") or ""),
                    "admin_script": str(addon.get("admin_script") or ""),
                    "master_script": str(addon.get("master_script") or ""),
                    "expected_effect": str(addon.get("expected_effect") or "add_on"),
                    "status": str(addon.get("status") or "draft"),
                }
            )
        if addons:
            normalized_rows.append(
                {
                    "main_service_id": main_service_id,
                    "main_service": str(row.get("main_service") or _service_display_name(main_service)),
                    "main_category": str(row.get("main_category") or main_service.get("category") or ""),
                    "recommended_addons": addons[:6],
                }
            )

    normalized = dict(matrix)
    normalized["upsell_matrix"] = normalized_rows
    normalized["cross_sell_pairs"] = matrix.get("cross_sell_pairs") or []
    normalized["packages"] = matrix.get("packages") or []
    normalized["risks"] = matrix.get("risks") or []
    normalized["implementation_priorities"] = matrix.get("implementation_priorities") or []
    return normalized


def _matrix_stats(matrix):
    rows = matrix.get("upsell_matrix") or []
    links = []
    accepted = 0
    active = 0
    for row in rows:
        for addon in row.get("recommended_addons") or []:
            links.append(addon)
            status = str(addon.get("status") or "")
            if status == "active":
                active += 1
            if status in {"active", "accepted"}:
                accepted += 1
    return {
        "main_services": len(rows),
        "links": len(links),
        "active_links": active,
        "accepted_links": accepted,
        "packages": len(matrix.get("packages") or []),
        "cross_sell_pairs": len(matrix.get("cross_sell_pairs") or []),
    }


def _all_matrix_links(matrix):
    links = []
    for row in matrix.get("upsell_matrix") or []:
        for addon in row.get("recommended_addons") or []:
            item = dict(addon)
            item["main_service_id"] = row.get("main_service_id")
            item["main_service"] = row.get("main_service")
            item["main_category"] = row.get("main_category")
            links.append(item)
    return links


def _active_links_for_service(matrix, service_id, service_name):
    links = []
    service_name_norm = _norm(service_name)
    for row in matrix.get("upsell_matrix") or []:
        row_id = str(row.get("main_service_id") or "")
        row_name_norm = _norm(row.get("main_service"))
        if service_id and row_id == service_id:
            pass
        elif service_name_norm and (service_name_norm == row_name_norm or service_name_norm in row_name_norm or row_name_norm in service_name_norm):
            pass
        else:
            continue
        for addon in row.get("recommended_addons") or []:
            if str(addon.get("status") or "") == "active":
                item = dict(addon)
                item["main_service_id"] = row.get("main_service_id")
                item["main_service"] = row.get("main_service")
                item["main_category"] = row.get("main_category")
                links.append(item)
    return links


def _load_events(cursor, business_id, start_date=None, end_date=None):
    _ensure_table(cursor)
    params = [business_id]
    filters = ["business_id = %s"]
    if start_date:
        filters.append("event_date >= %s")
        params.append(start_date)
    if end_date:
        filters.append("event_date <= %s")
        params.append(end_date)
    cursor.execute(
        f"""
        SELECT id, business_id, matrix_id, link_id, package_id, booking_id, main_service_id,
               addon_service_id, event_type, event_date, amount, master_id, client_name,
               notes, created_by, created_at
        FROM averageticketevents
        WHERE {' AND '.join(filters)}
        ORDER BY event_date DESC, created_at DESC
        """,
        tuple(params),
    )
    events = []
    for row in cursor.fetchall() or []:
        events.append(
            {
                "id": _row_value(row, "id", 0),
                "business_id": _row_value(row, "business_id", 1),
                "matrix_id": _row_value(row, "matrix_id", 2),
                "link_id": _row_value(row, "link_id", 3),
                "package_id": _row_value(row, "package_id", 4),
                "booking_id": _row_value(row, "booking_id", 5),
                "main_service_id": _row_value(row, "main_service_id", 6),
                "addon_service_id": _row_value(row, "addon_service_id", 7),
                "event_type": _row_value(row, "event_type", 8),
                "event_date": _date_string(_row_value(row, "event_date", 9)),
                "amount": _money_to_float(_row_value(row, "amount", 10)),
                "master_id": _row_value(row, "master_id", 11),
                "client_name": _row_value(row, "client_name", 12),
                "notes": _row_value(row, "notes", 13),
                "created_by": _row_value(row, "created_by", 14),
                "created_at": _date_string(_row_value(row, "created_at", 15)),
            }
        )
    return events


def _load_daily_plan(cursor, business_id, services, matrix, target_date=None):
    if not _table_exists(cursor, "bookings"):
        return []
    columns = _table_columns(cursor, "bookings")
    if not columns:
        return []
    selected = ["id"]
    for column in [
        "client_name",
        "client_phone",
        "service_id",
        "service_name",
        "booking_date",
        "booking_time",
        "booking_time_local",
        "master_id",
        "status",
        "notes",
    ]:
        if column in columns:
            selected.append(column)
    date_value = target_date or date.today().isoformat()
    params = [business_id]
    filters = ["business_id = %s"]
    if "booking_date" in columns:
        filters.append("booking_date = %s")
        params.append(date_value)
    elif "booking_time" in columns:
        filters.append("DATE(booking_time) = %s")
        params.append(date_value)
    elif "booking_time_local" in columns:
        filters.append("DATE(booking_time_local) = %s")
        params.append(date_value)
    if "status" in columns:
        filters.append("(status IS NULL OR status NOT IN ('cancelled', 'canceled', 'rejected'))")
    order_column = "booking_time" if "booking_time" in columns else "created_at"
    if order_column not in columns:
        order_column = "id"
    cursor.execute(
        f"""
        SELECT {', '.join(selected)}
        FROM bookings
        WHERE {' AND '.join(filters)}
        ORDER BY {order_column} ASC
        LIMIT 120
        """,
        tuple(params),
    )
    booking_rows = cursor.fetchall() or []
    booking_description = list(cursor.description or [])
    events = _load_events(cursor, business_id, date_value, date_value)
    events_by_booking = {}
    for event in events:
        booking_id = event.get("booking_id")
        if booking_id:
            events_by_booking.setdefault(booking_id, []).append(event)
    service_by_id = {item.get("id"): item for item in services}
    plan = []
    for row in booking_rows:
        row_map = {}
        for index, desc in enumerate(booking_description):
            row_map[desc[0]] = _row_value(row, desc[0], index)
        service_id = str(row_map.get("service_id") or "")
        service_name = str(row_map.get("service_name") or "")
        service = service_by_id.get(service_id) or _find_service_by_name(services, service_name)
        resolved_service_id = service_id or (service.get("id") if service else "")
        resolved_service_name = service_name or (_service_display_name(service) if service else "")
        recommendations = _active_links_for_service(matrix, resolved_service_id, resolved_service_name)
        if not recommendations:
            continue
        booking_id = str(row_map.get("id") or "")
        plan.append(
            {
                "booking_id": booking_id,
                "time": _date_string(row_map.get("booking_time_local") or row_map.get("booking_time")),
                "client": row_map.get("client_name") or row_map.get("client_phone") or "Клиент",
                "service_id": resolved_service_id,
                "service_name": resolved_service_name,
                "master_id": row_map.get("master_id"),
                "status": row_map.get("status"),
                "recommendations": recommendations[:3],
                "events": events_by_booking.get(booking_id, []),
            }
        )
    return plan


def _safe_pct(part, total):
    if not total:
        return None
    return round(part * 100 / total, 1)


def _load_finance_metrics(cursor, business_id, events, matrix):
    today = date.today()
    current_start = today - timedelta(days=30)
    previous_start = today - timedelta(days=60)
    cursor.execute(
        """
        SELECT COUNT(*) AS orders, COALESCE(SUM(amount), 0) AS revenue, COALESCE(AVG(amount), 0) AS average_ticket
        FROM financialtransactions
        WHERE business_id = %s AND transaction_date >= %s AND transaction_date <= %s
        """,
        (business_id, current_start.isoformat(), today.isoformat()),
    )
    current = cursor.fetchone()
    cursor.execute(
        """
        SELECT COUNT(*) AS orders, COALESCE(SUM(amount), 0) AS revenue, COALESCE(AVG(amount), 0) AS average_ticket
        FROM financialtransactions
        WHERE business_id = %s AND transaction_date >= %s AND transaction_date < %s
        """,
        (business_id, previous_start.isoformat(), current_start.isoformat()),
    )
    previous = cursor.fetchone()
    current_average = _money_to_float(_row_value(current, "average_ticket", 2)) or 0
    previous_average = _money_to_float(_row_value(previous, "average_ticket", 2)) or 0
    delta = None
    if previous_average:
        delta = round((current_average - previous_average) * 100 / previous_average, 1)

    offered = [event for event in events if event.get("event_type") in {"offered", "package_offered"}]
    bought = [event for event in events if event.get("event_type") in {"bought", "package_bought"}]
    package_bought = [event for event in events if event.get("event_type") == "package_bought"]
    package_offered = [event for event in events if event.get("event_type") == "package_offered"]
    addon_revenue = sum(float(event.get("amount") or 0) for event in bought)
    active_links = [item for item in _all_matrix_links(matrix) if item.get("status") == "active"]
    avg_addon_price = 0
    priced_links = [_parse_money(item.get("price")) for item in active_links]
    priced_links = [item for item in priced_links if item > 0]
    if priced_links:
        avg_addon_price = float(sum(priced_links) / len(priced_links))
    total_bookings = _row_value(current, "orders", 0) or 0
    potential_growth = None
    if total_bookings and avg_addon_price:
        baseline_conversion = 0.12
        potential_growth = round(float(total_bookings) * avg_addon_price * baseline_conversion)

    master_map = {}
    category_map = {}
    link_by_id = {item.get("id"): item for item in _all_matrix_links(matrix)}
    for event in offered:
        master_id = event.get("master_id") or "Не указан"
        master_map.setdefault(master_id, {"offered": 0, "bought": 0})
        master_map[master_id]["offered"] += 1
        link = link_by_id.get(event.get("link_id")) or {}
        category = link.get("category") or "Без категории"
        category_map.setdefault(category, {"offered": 0, "bought": 0})
        category_map[category]["offered"] += 1
    for event in bought:
        master_id = event.get("master_id") or "Не указан"
        master_map.setdefault(master_id, {"offered": 0, "bought": 0})
        master_map[master_id]["bought"] += 1
        link = link_by_id.get(event.get("link_id")) or {}
        category = link.get("category") or "Без категории"
        category_map.setdefault(category, {"offered": 0, "bought": 0})
        category_map[category]["bought"] += 1

    return {
        "average_ticket": round(current_average, 2) if current_average else None,
        "average_ticket_delta_30d": delta,
        "add_on_rate": _safe_pct(len(bought), max(total_bookings, len(offered))),
        "upsell_conversion": _safe_pct(len(bought), len(offered)),
        "cross_sell_rate": _safe_pct(
            len([event for event in bought if (link_by_id.get(event.get("link_id")) or {}).get("expected_effect") == "cross_sell"]),
            len(offered),
        ),
        "package_sales": len(package_bought),
        "package_conversion": _safe_pct(len(package_bought), len(package_offered)),
        "upsell_revenue": round(addon_revenue, 2),
        "potential_growth": potential_growth,
        "average_ticket_with_upsell": round(current_average + (addon_revenue / len(bought)), 2) if current_average and bought else None,
        "average_ticket_without_upsell": round(current_average, 2) if current_average else None,
        "events": {
            "offered": len(offered),
            "bought": len(bought),
            "declined": len([event for event in events if event.get("event_type") == "declined"]),
            "next_visit_booked": len([event for event in events if event.get("event_type") == "next_visit_booked"]),
            "package_offered": len(package_offered),
            "package_bought": len(package_bought),
        },
        "by_master": [
            {"master_id": key, **value, "conversion": _safe_pct(value["bought"], value["offered"])}
            for key, value in master_map.items()
        ],
        "by_category": [
            {"category": key, **value, "conversion": _safe_pct(value["bought"], value["offered"])}
            for key, value in category_map.items()
        ],
    }


@average_ticket_bp.route("/api/average-ticket/overview", methods=["GET", "OPTIONS"])
def get_average_ticket_overview():
    if request.method == "OPTIONS":
        return ("", 204)
    user_data, business_id, error_response = _require_business_access()
    if error_response:
        return error_response

    db = None
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        business = _load_business(cursor, business_id)
        services = _load_services(cursor, business_id)
        latest = _load_latest_matrix(cursor, business_id)
        matrix = latest.get("matrix") if latest else {}
        events = _load_events(
            cursor,
            business_id,
            (date.today() - timedelta(days=30)).isoformat(),
            date.today().isoformat(),
        )
        packages = _load_packages(cursor, business_id)
        target_date = request.args.get("date") or date.today().isoformat()
        daily_plan = _load_daily_plan(cursor, business_id, services, matrix or {}, target_date)
        kpis = _load_finance_metrics(cursor, business_id, events, matrix or {})
        return jsonify(
            {
                "success": True,
                "business": business,
                "services_count": len(services),
                "services": services,
                "services_hash": _services_hash(services),
                "latest_matrix": latest,
                "stats": _matrix_stats(matrix or {}),
                "kpis": kpis,
                "daily_plan": daily_plan,
                "events": events,
                "packages": packages,
                "finance_link": "/dashboard/finance",
            }
        )
    except Exception:
        return jsonify({"error": "Ошибка загрузки раздела Средний чек"}), 500
    finally:
        if db:
            db.close()


@average_ticket_bp.route("/api/average-ticket/generate", methods=["POST", "OPTIONS"])
def generate_average_ticket_matrix():
    if request.method == "OPTIONS":
        return ("", 204)
    user_data, business_id, error_response = _require_business_access()
    if error_response:
        return error_response

    db = None
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        _ensure_table(cursor)
        business = _load_business(cursor, business_id)
        services = _load_services(cursor, business_id)
        if len(services) < 2:
            return jsonify({"error": "Недостаточно услуг в разделе Работа с картами"}), 400

        prompt_template = _prompt_from_db(cursor)
        payload = _build_generation_payload(business, services)
        prompt = _build_prompt(prompt_template, payload)
        generation_mode = "gigachat"
        raw_matrix = None
        error_note = None
        try:
            result = analyze_text_with_gigachat(
                prompt,
                task_type=PROMPT_TYPE,
                business_id=business_id,
                user_id=user_data.get("user_id"),
            )
            raw_matrix = _extract_json_object(result)
        except Exception:
            error_note = "GigaChat недоступен или вернул ошибку, использован локальный fallback."

        if not raw_matrix:
            raw_matrix = _fallback_matrix(services)
            generation_mode = "fallback"
        matrix = _normalize_matrix(raw_matrix, services)
        matrix["generation_mode"] = generation_mode
        if error_note:
            matrix["generation_note"] = error_note

        matrix_id = str(uuid.uuid4())
        source_hash = _services_hash(services)
        cursor.execute(
            """
            INSERT INTO averageticketmatrices
            (id, business_id, status, source_services_hash, matrix_json, generated_by)
            VALUES (%s, %s, 'draft', %s, %s, %s)
            """,
            (matrix_id, business_id, source_hash, Json(matrix), user_data.get("user_id")),
        )
        db.conn.commit()
        latest = _load_latest_matrix(cursor, business_id)
        return jsonify(
            {
                "success": True,
                "matrix_id": matrix_id,
                "generation_mode": generation_mode,
                "latest_matrix": latest,
                "stats": _matrix_stats(matrix),
            }
        )
    except Exception:
        if db:
            db.conn.rollback()
        return jsonify({"error": "Ошибка генерации матрицы среднего чека"}), 500
    finally:
        if db:
            db.close()


@average_ticket_bp.route("/api/average-ticket/matrix/<matrix_id>/link", methods=["PATCH", "OPTIONS"])
def update_average_ticket_link(matrix_id):
    if request.method == "OPTIONS":
        return ("", 204)
    user_data, business_id, error_response = _require_business_access()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    link_id = str(data.get("link_id") or "").strip()
    status = str(data.get("status") or "").strip()
    updates = {key: data.get(key) for key in EDITABLE_LINK_FIELDS if key in data}
    if status:
        updates["status"] = status
    if not link_id or not updates:
        return jsonify({"error": "Нужны link_id и хотя бы одно поле для обновления"}), 400
    if "status" in updates and str(updates["status"]) not in {"draft", "active", "disabled"}:
        return jsonify({"error": "status должен быть draft|active|disabled"}), 400

    db = None
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        _ensure_table(cursor)
        cursor.execute(
            """
            SELECT matrix_json
            FROM averageticketmatrices
            WHERE id = %s AND business_id = %s
            LIMIT 1
            """,
            (matrix_id, business_id),
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Матрица не найдена"}), 404
        matrix = _row_value(row, "matrix_json", 0) or {}
        updated = False
        for item in matrix.get("upsell_matrix") or []:
            for addon in item.get("recommended_addons") or []:
                if str(addon.get("id") or "") == link_id:
                    for key, value in updates.items():
                        addon[key] = str(value or "")
                    updated = True
        if not updated:
            return jsonify({"error": "Связка не найдена"}), 404

        cursor.execute(
            """
            UPDATE averageticketmatrices
            SET matrix_json = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            """,
            (Json(matrix), matrix_id, business_id),
        )
        db.conn.commit()
        latest = _load_latest_matrix(cursor, business_id)
        return jsonify({"success": True, "latest_matrix": latest, "stats": _matrix_stats(matrix)})
    except Exception:
        if db:
            db.conn.rollback()
        return jsonify({"error": "Ошибка обновления связки"}), 500
    finally:
        if db:
            db.close()


@average_ticket_bp.route("/api/average-ticket/matrix/<matrix_id>/link", methods=["POST", "OPTIONS"])
def create_average_ticket_link(matrix_id):
    if request.method == "OPTIONS":
        return ("", 204)
    user_data, business_id, error_response = _require_business_access()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    main_service_id = str(data.get("main_service_id") or "").strip()
    addon_service_id = str(data.get("addon_service_id") or "").strip()
    if not main_service_id or not addon_service_id or main_service_id == addon_service_id:
        return jsonify({"error": "Нужны разные main_service_id и addon_service_id"}), 400

    db = None
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        _ensure_table(cursor)
        services = _load_services(cursor, business_id)
        service_by_id = {item.get("id"): item for item in services}
        main_service = service_by_id.get(main_service_id)
        addon_service = service_by_id.get(addon_service_id)
        if not main_service or not addon_service:
            return jsonify({"error": "Услуга не найдена в разделе Работа с картами"}), 404
        cursor.execute(
            """
            SELECT matrix_json
            FROM averageticketmatrices
            WHERE id = %s AND business_id = %s
            LIMIT 1
            """,
            (matrix_id, business_id),
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Матрица не найдена"}), 404
        matrix = _row_value(row, "matrix_json", 0) or {}
        link_id = str(data.get("id") or f"{main_service_id}:{addon_service_id}")
        new_link = {
            "id": link_id,
            "service_id": addon_service_id,
            "service": _service_display_name(addon_service),
            "category": addon_service.get("category") or "",
            "price": addon_service.get("price") or "",
            "offer_timing": str(data.get("offer_timing") or "during_visit"),
            "priority": str(data.get("priority") or "medium"),
            "compatibility": str(data.get("compatibility") or "same_visit"),
            "reason": str(data.get("reason") or "Добавлено вручную."),
            "admin_script": str(data.get("admin_script") or ""),
            "master_script": str(data.get("master_script") or ""),
            "expected_effect": str(data.get("expected_effect") or "add_on"),
            "status": str(data.get("status") or "draft"),
        }
        target_row = None
        for matrix_row in matrix.get("upsell_matrix") or []:
            if str(matrix_row.get("main_service_id") or "") == main_service_id:
                target_row = matrix_row
        if not target_row:
            target_row = {
                "main_service_id": main_service_id,
                "main_service": _service_display_name(main_service),
                "main_category": main_service.get("category") or "",
                "recommended_addons": [],
            }
            matrix.setdefault("upsell_matrix", []).append(target_row)
        for addon in target_row.get("recommended_addons") or []:
            if str(addon.get("id") or "") == link_id or str(addon.get("service_id") or "") == addon_service_id:
                return jsonify({"error": "Такая связка уже есть"}), 409
        target_row.setdefault("recommended_addons", []).append(new_link)
        cursor.execute(
            """
            UPDATE averageticketmatrices
            SET matrix_json = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
            """,
            (Json(matrix), matrix_id, business_id),
        )
        db.conn.commit()
        latest = _load_latest_matrix(cursor, business_id)
        return jsonify({"success": True, "latest_matrix": latest, "stats": _matrix_stats(matrix)})
    except Exception:
        if db:
            db.conn.rollback()
        return jsonify({"error": "Ошибка создания связки"}), 500
    finally:
        if db:
            db.close()


@average_ticket_bp.route("/api/average-ticket/events", methods=["POST", "OPTIONS"])
def create_average_ticket_event():
    if request.method == "OPTIONS":
        return ("", 204)
    user_data, business_id, error_response = _require_business_access()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    event_type = str(data.get("event_type") or "").strip()
    if event_type not in EVENT_TYPES:
        return jsonify({"error": "Некорректный тип события"}), 400
    event_id = str(uuid.uuid4())
    amount = data.get("amount")
    amount_value = None
    if amount not in {None, ""}:
        amount_value = _parse_money(amount)
    event_date = str(data.get("event_date") or date.today().isoformat())

    db = None
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        _ensure_table(cursor)
        cursor.execute(
            """
            INSERT INTO averageticketevents
            (id, business_id, matrix_id, link_id, package_id, booking_id, main_service_id,
             addon_service_id, event_type, event_date, amount, master_id, client_name,
             notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_id,
                business_id,
                data.get("matrix_id"),
                data.get("link_id"),
                data.get("package_id"),
                data.get("booking_id"),
                data.get("main_service_id"),
                data.get("addon_service_id"),
                event_type,
                event_date,
                amount_value,
                data.get("master_id"),
                data.get("client_name"),
                data.get("notes"),
                user_data.get("user_id"),
            ),
        )
        db.conn.commit()
        events = _load_events(cursor, business_id, (date.today() - timedelta(days=30)).isoformat(), date.today().isoformat())
        latest = _load_latest_matrix(cursor, business_id)
        kpis = _load_finance_metrics(cursor, business_id, events, latest.get("matrix") if latest else {})
        return jsonify({"success": True, "event_id": event_id, "kpis": kpis})
    except Exception:
        if db:
            db.conn.rollback()
        return jsonify({"error": "Ошибка сохранения события среднего чека"}), 500
    finally:
        if db:
            db.close()


@average_ticket_bp.route("/api/average-ticket/packages", methods=["POST", "OPTIONS"])
def create_average_ticket_package():
    if request.method == "OPTIONS":
        return ("", 204)
    user_data, business_id, error_response = _require_business_access()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    service_ids = [str(item) for item in data.get("service_ids") or [] if str(item).strip()]
    if not name or not service_ids:
        return jsonify({"error": "Нужны название и состав пакета"}), 400

    db = None
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        _ensure_table(cursor)
        services = _load_services(cursor, business_id)
        valid_ids = {item.get("id") for item in services}
        clean_service_ids = [item for item in service_ids if item in valid_ids]
        if not clean_service_ids:
            return jsonify({"error": "В составе нет услуг из раздела Работа с картами"}), 400
        base_total, package_price, service_names = _calculate_package_totals(services, clean_service_ids, data.get("package_price"))
        package_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO averageticketpackages
            (id, business_id, name, service_ids, service_names, base_total, package_price,
             bonus_text, positioning, script, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                package_id,
                business_id,
                name,
                Json(clean_service_ids),
                Json(service_names),
                base_total,
                package_price,
                data.get("bonus_text"),
                data.get("positioning"),
                data.get("script"),
                data.get("status") if data.get("status") in {"draft", "active"} else "draft",
                user_data.get("user_id"),
            ),
        )
        db.conn.commit()
        return jsonify({"success": True, "package_id": package_id, "packages": _load_packages(cursor, business_id)})
    except Exception:
        if db:
            db.conn.rollback()
        return jsonify({"error": "Ошибка создания пакета"}), 500
    finally:
        if db:
            db.close()


@average_ticket_bp.route("/api/average-ticket/packages/<package_id>", methods=["PATCH", "OPTIONS"])
def update_average_ticket_package(package_id):
    if request.method == "OPTIONS":
        return ("", 204)
    user_data, business_id, error_response = _require_business_access()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    db = None
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        _ensure_table(cursor)
        services = _load_services(cursor, business_id)
        cursor.execute(
            "SELECT id FROM averageticketpackages WHERE id = %s AND business_id = %s LIMIT 1",
            (package_id, business_id),
        )
        if not cursor.fetchone():
            return jsonify({"error": "Пакет не найден"}), 404
        fields = []
        params = []
        for field in ["name", "bonus_text", "positioning", "script"]:
            if field in data:
                fields.append(f"{field} = %s")
                params.append(data.get(field))
        if "status" in data and data.get("status") in {"draft", "active", "disabled"}:
            fields.append("status = %s")
            params.append(data.get("status"))
        if "service_ids" in data or "package_price" in data:
            service_ids = [str(item) for item in data.get("service_ids") or [] if str(item).strip()]
            valid_ids = {item.get("id") for item in services}
            clean_service_ids = [item for item in service_ids if item in valid_ids]
            base_total, package_price, service_names = _calculate_package_totals(services, clean_service_ids, data.get("package_price"))
            fields.extend(["service_ids = %s", "service_names = %s", "base_total = %s", "package_price = %s"])
            params.extend([Json(clean_service_ids), Json(service_names), base_total, package_price])
        if not fields:
            return jsonify({"error": "Нет полей для обновления"}), 400
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([package_id, business_id])
        cursor.execute(
            f"""
            UPDATE averageticketpackages
            SET {', '.join(fields)}
            WHERE id = %s AND business_id = %s
            """,
            tuple(params),
        )
        db.conn.commit()
        return jsonify({"success": True, "packages": _load_packages(cursor, business_id)})
    except Exception:
        if db:
            db.conn.rollback()
        return jsonify({"error": "Ошибка обновления пакета"}), 500
    finally:
        if db:
            db.close()
