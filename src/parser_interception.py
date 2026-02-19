"""
parser_interception.py — Парсер Яндекс.Карт через Network Interception

Перехватывает API запросы во время загрузки страницы и извлекает данные из JSON ответов.
Это в 10x быстрее, чем парсинг HTML через Playwright.
"""

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import json
import re
import time
import random
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, parse_qs
import os
from datetime import datetime

from browser_session import BrowserSession, BrowserSessionManager

DEBUG_DIR = os.getenv("DEBUG_DIR", "/app/debug_data")

# Только ключи, передаваемые в manager.open_session (parser_interception) или используемые воркером.
ALLOWED_SESSION_KWARGS = {
    "headless",
    "cookies",
    "user_agent",
    "viewport",
    "locale",
    "timezone_id",
    "proxy",
    "launch_args",
    "init_scripts",
    "geolocation",
}

def _find_paths(obj: Any, target_keys: List[str], max_depth: int = 6, max_preview_len: int = 120,
                max_results_per_key: int = 20) -> Dict[str, List[Dict[str, str]]]:
    """
    Dev-only утилита: найти пути к ключам target_keys в произвольном JSON (dict/list).

    Возвращает словарь:
      { key: [ { "path": "payload.company.rubrics[0].name", "preview": "..." }, ... ] }
    """
    targets = set(target_keys)
    results: Dict[str, List[Dict[str, str]]] = {k: [] for k in targets}

    def _add_result(key: str, path: str, value: Any) -> None:
        bucket = results.setdefault(key, [])
        if len(bucket) >= max_results_per_key:
            return
        try:
            if isinstance(value, (dict, list)):
                preview = json.dumps(value, ensure_ascii=False)
            else:
                preview = str(value)
        except Exception:
            preview = repr(value)
        if len(preview) > max_preview_len:
            preview = preview[:max_preview_len] + "…"
        bucket.append({"path": path, "preview": preview})

    def _walk(node: Any, path: str, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                new_path = f"{path}.{k}" if path else k
                if k in targets:
                    _add_result(k, new_path, v)
                _walk(v, new_path, depth + 1)
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                new_path = f"{path}[{idx}]" if path else f"[{idx}]"
                _walk(item, new_path, depth + 1)

    _walk(obj, "", 0)
    return {k: v for k, v in results.items() if v}


def _pick_first(d: Any, paths: List[List[str]]) -> Any:
    """
    Достать первое непустое значение по одному из путей.
    paths: [["data", "items", "0", "title"], ["data", "name"], ...]
    Поддерживает числовые индексы для списков ("0", "1").
    """
    for p in paths:
        cur = d
        ok = True
        for k in p:
            if isinstance(cur, list) and k.isdigit():
                idx = int(k)
                if idx < 0 or idx >= len(cur):
                    ok = False
                    break
                cur = cur[idx]
            elif isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and cur is not None and cur != "":
            return cur
    return None


def _is_empty(val: Any) -> bool:
    """Проверка на пустое значение (для merge_non_empty)."""
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip()
    if isinstance(val, (list, dict)):
        return len(val) == 0
    return False


def _is_non_empty(val: Any) -> bool:
    """Проверка на непустое значение (truthy для скаляров, len>0 для list/dict)."""
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (list, dict)):
        return len(val) > 0
    return bool(val)


# --- Identity fields & source priority (Part A) ---
IDENTITY_FIELDS = frozenset({"title", "title_or_name", "address", "categories", "rating", "reviews_count"})
IDENTITY_SAFE_SOURCES = frozenset({"search_api", "org_api", "html_fallback"})
# На org_page: location-info разрешён только для safe-полей
LOCATION_INFO_SAFE_FIELDS = frozenset({"hours", "hours_full", "phone", "site", "url", "coordinates", "ll", "social_links"})


def _is_identity_safe(source: str, org_page: bool) -> bool:
    """
    На org_page: True только для search_api, org_api, html_fallback.
    На non-org: location_info разрешён.
    """
    if not org_page:
        return True
    return source in IDENTITY_SAFE_SOURCES


def merge_non_empty(
    dst: Dict[str, Any],
    src: Dict[str, Any],
    meta_src: Optional[Dict[str, str]] = None,
    *,
    source: Optional[str] = None,
    org_page: bool = False,
    forbidden_fields: Optional[set] = None,
) -> None:
    """
    Мерджит src в dst без затирания валидных полей пустыми.
    - Скаляры: копировать только если src_val truthy и dst пусто.
    - Списки: только если len > 0 и dst пусто.
    - Dict: рекурсивно по ключам, не затирать непустое пустым.
    meta_src: {field: source} — при копировании поля записать meta[field+"_source"]=source.
    """
    if not isinstance(src, dict):
        return
    meta = dst.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        dst["meta"] = meta

    blocked = forbidden_fields or set()
    if source and org_page and not _is_identity_safe(source, org_page):
        blocked = blocked | IDENTITY_FIELDS

    for k, v in src.items():
        if k in ("meta", "_search_debug"):
            continue
        if k in blocked:
            continue
        if not _is_non_empty(v):
            continue
        current = dst.get(k)
        if isinstance(v, dict) and not isinstance(v, list):
            if not isinstance(current, dict):
                dst[k] = dict(v)
            else:
                merge_non_empty(current, v, meta_src)
        elif isinstance(v, list):
            if len(v) > 0 and _is_empty(current):
                dst[k] = v
                if meta_src and k in meta_src:
                    meta[k + "_source"] = meta_src[k]
        else:
            if _is_empty(current):
                dst[k] = v
                if meta_src and k in meta_src:
                    meta[k + "_source"] = meta_src[k]


def _normalize_title_fields(payload: Dict[str, Any]) -> None:
    """
    Гарантирует наличие title_or_name и title, если есть хоть один источник.
    Вызывать на финальном payload перед return.
    """
    t = (
        payload.get("title_or_name")
        or payload.get("title")
        or payload.get("name")
        or payload.get("page_title_short")
        or payload.get("og_title")
    )
    if t and isinstance(t, str) and t.strip():
        payload.setdefault("title_or_name", t)
        payload.setdefault("title", t)
        ov = payload.get("overview")
        if isinstance(ov, dict):
            ov.setdefault("title", t)


def _set_if_empty(result: Dict[str, Any], key: str, value: Any) -> None:
    """
    Поставить result[key] только если там сейчас "пусто" и value осмысленное.
    Пусто: None, '', [], {}.
    """
    if value is None:
        return
    if isinstance(value, str) and not value.strip():
        return

    current = result.get(key)
    if current is None or current == "" or current == [] or current == {}:
        result[key] = value


def _extend_unique(result: Dict[str, Any], key: str, items: List[Any]) -> None:
    """
    Добавить строки в список result[key] без дублей, не затирая существующее.
    """
    if not items:
        return

    # Для categories храним только список строк (имен/меток), без dict и других типов.
    if key == "categories":
        def _cat_str_from_item(it: Any) -> Optional[str]:
            if isinstance(it, str):
                s = it.strip()
                return s or None
            if isinstance(it, dict):
                for k in ("name", "label", "text", "title"):
                    v = it.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
            return None

        existing_raw = result.get(key)
        existing_list: List[str] = []
        if isinstance(existing_raw, list):
            for it in existing_raw:
                s = _cat_str_from_item(it)
                if s and s not in existing_list:
                    existing_list.append(s)
        elif isinstance(existing_raw, str) and existing_raw.strip():
            existing_list = [existing_raw.strip()]

        seen = set(existing_list)
        for item in items:
            s = _cat_str_from_item(item)
            if not s or s in seen:
                continue
            existing_list.append(s)
            seen.add(s)

        result[key] = existing_list
        return

    # Общий случай: сохраняем типы как есть, но избегаем дублей по строковому представлению.
    existing = result.get(key)
    if existing is None:
        existing_list: List[Any] = []
    elif isinstance(existing, list):
        existing_list = existing
    else:
        existing_list = [existing]

    seen = {str(x) for x in existing_list}
    for item in items:
        s = str(item)
        if s in seen:
            continue
        existing_list.append(item)
        seen.add(s)

    result[key] = existing_list


def _get_nested(obj: Any, path: str) -> Any:
    """
    Достать значение по пути вида "payload.company.rubrics[0].name"
    с поддержкой индексов [0].
    """
    if not path:
        return obj

    # Разбиваем по точкам, внутри каждой части могут быть индексы [0]
    for part in path.split("."):
        if not part:
            continue
        # Выделяем ключ и индексы.
        # Пример part: "rubrics[0][1]"
        i = 0
        key = ""
        # Собираем буквенно-цифровую часть до первой скобки
        while i < len(part) and part[i] != "[":
            key += part[i]
            i += 1

        if key:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
            if obj is None:
                return None

        # Обрабатываем индексы вида [0]
        while i < len(part):
            if part[i] != "[":
                return None
            j = part.find("]", i)
            if j == -1:
                return None
            index_str = part[i + 1 : j]
            try:
                idx = int(index_str)
            except ValueError:
                return None
            if not isinstance(obj, list) or idx < 0 or idx >= len(obj):
                return None
            obj = obj[idx]
            i = j + 1

    return obj


class YandexMapsInterceptionParser:
    """Парсер Яндекс.Карт через перехват сетевых запросов"""
    
    def __init__(self, debug_bundle_id: Optional[str] = None):
        self.api_responses: Dict[str, Any] = {}
        self.api_responses_list: List[tuple] = []  # [(url, json_data), ...] — журнал без перезаписи
        self.location_info_payload: Optional[Dict[str, Any]] = None  # лучший org-bound (backward compat)
        self.location_info_candidates: List[tuple] = []  # [(json_data, timestamp), ...] org-bound
        self.reviews_pages: List[Dict[str, Any]] = []
        self.products_pages: List[Dict[str, Any]] = []
        self.search_api_payload: Optional[Dict[str, Any]] = None  # search?business_oid=...
        self._search_api_debug: Optional[Dict[str, Any]] = None  # для selected_item_debug.json
        self._search_api_contributed_identity: bool = False  # True если search_api дал title/address/categories
        self.org_id: Optional[str] = None
        self.debug_bundle_id: Optional[str] = debug_bundle_id
        self._identity_debug: Dict[str, Any] = {}  # blocked_candidates, identity, warnings
        _base = os.getenv("DEBUG_DIR", "/app/debug_data")
        self.debug_bundle_dir: Optional[str] = os.path.join(_base, debug_bundle_id) if debug_bundle_id else None
        self._debug_raw_services_count: int = 0
        
    def extract_org_id(self, url: str) -> Optional[str]:
        """Извлечь org_id из URL Яндекс.Карт
        
        Поддерживает форматы:
        - /org/123456/ (старый формат)
        - /org/slug/123456/ (новый формат с slug)
        """
        # Сначала пробуем новый формат: /org/slug/123456/
        match = re.search(r'/org/[^/]+/(\d+)', url)
        if match:
            return match.group(1)
        
        # Fallback на старый формат: /org/123456/
        match = re.search(r'/org/(\d+)', url)
        return match.group(1) if match else None

    @property
    def org_page(self) -> bool:
        """True если парсим org-страницу (/maps/org/... + org_id)."""
        return bool(self.org_id)

    def _extract_business_id_from_url(self, url: str) -> Optional[str]:
        """Извлечь businessId/orgId/oid из URL (query или path)."""
        if not url:
            return None
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for param in ("businessId", "orgId", "business_oid", "oid"):
            vals = qs.get(param, [])
            if vals and vals[0]:
                return str(vals[0]).strip()
        m = re.search(r"business_oid[=:](\d+)", url, re.I)
        if m:
            return m.group(1)
        m = re.search(r"/org/[^/]+/(\d+)", url)
        if m:
            return m.group(1)
        return None

    def _extract_ll_z_from_url(self, url: str) -> tuple:
        """Извлечь ll и z из URL карты. Возвращает (ll, z) или (None, None)."""
        if not url:
            return (None, None)
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            ll = qs.get("ll", [None])[0]
            z = qs.get("z", [None])[0]
            return (ll, z)
        except Exception:
            return (None, None)

    def _build_overview_url(self, base_url: str, ll: Optional[str] = None, z: Optional[str] = None) -> str:
        """Собрать URL overview карточки с ll и z."""
        # Убираем /prices/ из URL, берём только path без query
        full = re.sub(r"/prices/?", "/", base_url)
        parsed = urlparse(full)
        path = (parsed.path or "").rstrip("/")
        if not path.endswith("/"):
            path += "/"
        base = f"{parsed.scheme or 'https'}://{parsed.netloc or 'yandex.ru'}{path}"
        if ll and z:
            return f"{base}?ll={ll}&z={z}"
        return base

    def _is_location_info_org_bound(self, json_data: Any, request_url: str = "") -> bool:
        """
        Рекурсивно проверяет, привязан ли ответ location-info к нашей организации (org_id).
        org-bound если: скаляр == org_id; строка содержит oid=<org_id>; путь /org/.../<org_id>.
        Лимиты: depth 20, nodes 50000. Безопасно к типам.
        """
        if not self.org_id or not json_data:
            return False
        target = str(self.org_id)
        oid_pattern = re.compile(r"oid=(\d+)", re.I)
        path_oid_pattern = re.compile(r"/org/[^/]*/" + re.escape(target) + r"(?:/|$)", re.I)

        def _scalar_matches(val: Any) -> bool:
            if val is None:
                return False
            if isinstance(val, (int, float)):
                return str(int(val)) == target
            if isinstance(val, str):
                if val.strip() == target:
                    return True
                m = oid_pattern.search(val)
                if m and m.group(1) == target:
                    return True
                if path_oid_pattern.search(val) or val.endswith("/" + target) or val.endswith("/" + target + "/"):
                    return True
            return False

        def _contains_oid(node: Any, depth: int, nodes_left: List[int]) -> bool:
            nodes_left[0] -= 1
            if nodes_left[0] <= 0 or depth > 20:
                return False
            try:
                if isinstance(node, dict):
                    for k, v in node.items():
                        if _scalar_matches(v):
                            return True
                        if _contains_oid(v, depth + 1, nodes_left):
                            return True
                elif isinstance(node, list):
                    for item in node:
                        if _scalar_matches(item):
                            return True
                        if _contains_oid(item, depth + 1, nodes_left):
                            return True
                else:
                    return _scalar_matches(node)
            except (TypeError, RecursionError, KeyError):
                pass
            return False

        return _contains_oid(json_data, 0, [50000])

    def _extract_org_object_from_location_info(self, json_data: Any) -> Optional[Dict[str, Any]]:
        """
        Извлекает объект организации из location-info по org_id.
        Ищет в items/showcase/features/results — объект с id/oid == org_id или uri содержит oid=<org_id>.
        Возвращает только этот объект или None.
        """
        if not self.org_id or not json_data:
            return None
        target = str(self.org_id)

        def _obj_matches(obj: Any) -> bool:
            if not isinstance(obj, dict):
                return False
            oid = obj.get("id") or obj.get("oid") or obj.get("businessOid")
            if oid is not None and str(oid) == target:
                return True
            uri = obj.get("uri") or ""
            if isinstance(uri, str):
                m = re.search(r"oid=(\d+)", uri, re.I)
                if m and m.group(1) == target:
                    return True
            return False

        def _find_in_list(items: List[Any]) -> Optional[Dict[str, Any]]:
            for it in items:
                if _obj_matches(it):
                    return it
                if isinstance(it, dict):
                    for key in ("items", "showcase", "features", "results", "children"):
                        sub = it.get(key)
                        if isinstance(sub, list):
                            found = _find_in_list(sub)
                            if found:
                                return found
            return None

        def _walk(node: Any, depth: int) -> Optional[Dict[str, Any]]:
            if depth > 12:
                return None
            if isinstance(node, list):
                return _find_in_list(node)
            if isinstance(node, dict):
                if _obj_matches(node):
                    return node
                for key in ("data", "items", "showcase", "features", "results", "toponymSearchResult"):
                    sub = node.get(key)
                    if sub is not None:
                        found = _find_in_list(sub) if isinstance(sub, list) else (_walk(sub, depth + 1) if isinstance(sub, dict) else None)
                        if found:
                            return found
            return None

        try:
            return _walk(json_data, 0)
        except (TypeError, RecursionError, KeyError):
            return None

    def _score_location_info_payload(self, data: Any) -> int:
        """Оценка заполненности core-полей. +1 за каждое непустое поле."""
        if not isinstance(data, dict):
            return 0
        core_keys = ("phone", "site", "hours", "hours_full", "rating", "description")
        score = 0
        for k in core_keys:
            v = data.get(k)
            if v is None:
                continue
            if isinstance(v, str) and v.strip():
                score += 1
            elif isinstance(v, (list, dict)) and len(v) > 0:
                score += 1
            elif not isinstance(v, (str, list, dict)) and v:
                score += 1
        return score

    def parse_yandex_card(self, url: str, session: BrowserSession) -> Dict[str, Any]:
        """
        Парсит публичную страницу Яндекс.Карт через Network Interception.
        
        Args:
            url: URL карточки бизнеса (например, https://yandex.ru/maps/org/123456/)
            
        Returns:
            Словарь с данными в том же формате, что и parser.py
        """
        print(f"🔍 Начинаем парсинг через Network Interception: {url}")
        print("DEBUG: VERSION 2026-01-29 REDIRECT FIX + TIMEOUTS")
        
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError(f"Некорректная ссылка: {url}")
        
        self.org_id = self.extract_org_id(url)
        if not self.org_id:
            raise ValueError(f"Не удалось извлечь org_id из URL: {url}")

        # org-centric: llz_anchor фиксируем ОДИН РАЗ из request URL, никогда не перезаписываем
        self._llz_anchor = self._extract_ll_z_from_url(url)
        self._overview_url_canonical = self._build_overview_url(url, self._llz_anchor[0], self._llz_anchor[1])
        if self._llz_anchor[0] and self._llz_anchor[1]:
            print(f"📍 llz_anchor: ll={self._llz_anchor[0]}, z={self._llz_anchor[1]} (из request URL)")
        print(f"📋 Извлечен org_id: {self.org_id}")

        def _is_world_view(page_url: str) -> bool:
            """z<=3 = world-view, area-based location-info бесполезен."""
            ll, z = self._extract_ll_z_from_url(page_url)
            if z is None:
                return False
            try:
                return int(z) <= 3
            except (ValueError, TypeError):
                return False

        def _is_captcha_page(title: str) -> bool:
            """Проверка капчи по заголовку (регистронезависимо, рус/англ)."""
            t = (title or "").lower()
            return (
                "ой!" in t or "captcha" in t or "robot" in t
                or "подтвердите, что вы не робот" in t
                or "are you not a robot" in t
                or "confirm that you" in t
                or "запросы отправляли вы" in t
            )

        def _is_captcha_url(page_url: str) -> bool:
            u = (page_url or "").lower()
            return "showcaptcha" in u or "/captcha" in u

        # Инициализируем bundle-директорию для этого прогона (если ещё не задана в __init__)
        if not self.debug_bundle_id:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.debug_bundle_id = f"yandex_{self.org_id}_{ts}"
        if not self.debug_bundle_dir:
            self.debug_bundle_dir = os.path.join(os.getenv("DEBUG_DIR", "/app/debug_data"), self.debug_bundle_id)
        try:
            if self.debug_bundle_dir:
                os.makedirs(self.debug_bundle_dir, exist_ok=True)
        except Exception as e:
            print(f"⚠️ Не удалось создать debug bundle dir {self.debug_bundle_dir}: {e}")
        else:
            if self.debug_bundle_dir:
                print(f"[DEBUG_BUNDLE] {self.debug_bundle_dir}")

        context = session.context
        page = session.page

        # Базовая информация для debug bundle
        initial_url = url
        main_http_status: Optional[int] = None

        # Очищаем предыдущие ответы
        self.api_responses = {}
        self.api_responses_list = []
        self.location_info_payload = None
        self.location_info_candidates = []
        self.reviews_pages = []
        self.products_pages = []
        self.search_api_payload = None
        self._search_api_debug = None
        self._search_api_contributed_identity = False
        self._identity_debug = {}
        self._search_api_contributed_identity = False
        self._identity_debug = {}

        # Перехватываем все ответы
        def handle_response(response):
            """Обработчик для перехвата сетевых запросов"""
            try:
                url = response.url

                # Ищем API запросы Яндекс.Карт (yandex.com при редиректе региона!)
                if any(h in url for h in ("yandex.ru", "yandex.net", "yandex.com")):
                    # Проверяем, это JSON ответ?
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type or "json" in url.lower() or "ajax=1" in url:
                        try:
                            # Пытаемся получить JSON
                            json_data = response.json()

                            # DEBUG: Save to file for inspection (только при наличии bundle)
                            if self.debug_bundle_dir:
                                try:
                                    os.makedirs(self.debug_bundle_dir, exist_ok=True)
                                    clean_url = url.split("?")[0].replace("/", "_").replace(":", "")[-50:]
                                    timestamp = int(time.time() * 1000)
                                    filename = f"{timestamp}_{clean_url}.json"
                                    filepath = os.path.join(self.debug_bundle_dir, filename)
                                    with open(filepath, "w", encoding="utf-8") as f:
                                        json.dump(json_data, f, ensure_ascii=False, indent=2)
                                except Exception as e:
                                    print(f"Failed to save debug json: {e}")

                            # Check for organization data (search or location-info)
                            if json_data:
                                # Сохраняем ответ (последний по URL для обратной совместимости)
                                self.api_responses[url] = {
                                    "data": json_data,
                                    "status": response.status,
                                    "headers": dict(response.headers),
                                }
                                self.api_responses_list.append((url, json_data))
                                # Агрегаты: location-info — только org-bound, накапливаем кандидатов
                                if "location-info" in url:
                                    if self._is_location_info_org_bound(json_data, url):
                                        ts = time.time()
                                        self.location_info_candidates.append((json_data, ts))
                                        if self.location_info_payload is None:
                                            self.location_info_payload = json_data  # backward compat
                                        print(f"✅ [LOCATION_INFO] location_info_accepted_org_bound (org_id в ответе)")
                                if "fetchReviews" in url or ("reviews" in url.lower() and "business" in url.lower()):
                                    self.reviews_pages.append(json_data)
                                if "fetchGoods" in url or "prices" in url.lower() or "goods" in url.lower():
                                    self.products_pages.append(json_data)
                                if "search" in url and "business_oid" in url:
                                    self.search_api_payload = json_data
                                # Показываем только важные запросы
                                if any(
                                    keyword in url
                                    for keyword in [
                                        "org",
                                        "organization",
                                        "business",
                                        "company",
                                        "reviews",
                                        "feedback",
                                        "location-info",
                                    ]
                                ):
                                    print(f"✅ Перехвачен важный API запрос: {url[:100]}...")
                        except Exception:
                            # Не JSON, пропускаем
                            pass
            except Exception:
                # Поглощаем ошибки перехватчика, чтобы не ломать главный поток
                pass

        page.on("response", handle_response)

        # Загружаем страницу (interception зарегистрирован ДО goto — все ответы будут перехвачены)
        print("🌐 Загружаем страницу и перехватываем API запросы...")
        try:
            main_response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                if main_response is not None:
                    main_http_status = main_response.status
            except Exception:
                main_http_status = None

            # Проверяем на капчу с ожиданием решения
            for _ in range(24):  # Ждем до 120 секунд
                try:
                    # Более точная проверка капчи (регистронезависимо + рус/англ)
                    title = page.title()
                    is_captcha = (
                        _is_captcha_page(title)
                        or page.get_by_text("Подтвердите, что вы не робот").is_visible()
                        or page.get_by_text("Are you not a robot", exact=False).is_visible()
                        or page.locator(".smart-captcha").count() > 0
                        or page.locator("input[name='smart-token']").count() > 0
                    )

                    if is_captcha:
                        print("⚠️ Обнаружена капча! Ждем 15 секунд... (не трогаем страницу)")
                        page.wait_for_timeout(15000)
                    else:
                        break
                except Exception:
                    break
        except PlaywrightTimeoutError:
            print("⚠️ Страница не загрузилась полностью (таймаут), но продолжаем...")
        except Exception:
            print("⚠️ Страница не загрузилась полностью, но продолжаем...")

        # Double check if we are still stuck on Captcha
        title = page.title()
        if _is_captcha_page(title) or _is_captcha_url(page.url):
            print(f"❌ Капча не была решена за отведённое время. Заголовок: {title}")
            # Возвращаем специальную ошибку, чтобы воркер знал о капче
            return {"error": "captcha_detected", "captcha_url": page.url}

        try:
            print("⏳ Ожидание загрузки карточки организации...")
            # Ждем заголовок или название организации (добавлен user selector)
            page.wait_for_selector(
                "h1, div.business-card-title-view, div.card-title-view__title, "
                "div.orgpage-header-view__header, div.orgpage-header-view__header-wrapper > h1",
                timeout=15000,
            )
            print("✅ Карточка загружена")
        except PlaywrightTimeoutError:
            print("⚠️ Не удалось дождаться загрузки карточки. Возможно, капча не решена или бан.")

        # Проверка редиректа на главную или другую страницу
        current_url = page.url
        title = page.title()
        print(f"📍 Текущий URL: {current_url}, Заголовок: {title}")

        if _is_captcha_url(current_url) or _is_captcha_page(title):
            print("❌ Обнаружен редирект на капчу после загрузки карточки.")
            return {"error": "captcha_detected", "captcha_url": current_url}

        # org-centric: world-view (z<=3) — карта сломалась, возвращаемся на overview
        if _is_world_view(current_url):
            print("⚠️ World-view (z<=3): карта улетела. Переходим на overview_url_canonical...")
            try:
                page.goto(self._overview_url_canonical, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                current_url = page.url
                print(f"✅ Вернулись: {current_url}")
            except Exception as e:
                print(f"⚠️ Не удалось вернуться: {e}")

        # Редирект на /prices/ — на странице цен нет address/rating/categories. Возвращаемся на overview.
        if "/prices/" in current_url or current_url.rstrip("/").endswith("/prices"):
            print("⚠️ Редирект на страницу цен (/prices/). Переходим на overview_url_canonical...")
            overview_url = self._overview_url_canonical
            if not overview_url or "/prices/" in overview_url:
                overview_url = re.sub(r"/prices/?", "/", current_url)
            try:
                # Ждём org API при переходе на overview
                def _is_org_api_resp(r):
                    u = r.url
                    return any(kw in u for kw in ("org", "location-info", "organization", "business"))
                with page.expect_response(_is_org_api_resp, timeout=20000) as resp_info:
                    page.goto(overview_url, wait_until="domcontentloaded", timeout=15000)
                try:
                    resp_info.value
                    print("✅ Org API перехвачен при переходе на overview")
                except Exception:
                    pass
                page.wait_for_timeout(3000)
                current_url = page.url
                print(f"📍 После перехода на overview: {current_url}")
            except Exception as e:
                print(f"⚠️ Не удалось перейти на overview: {e}")

        # Более строгая проверка: ищем заголовок организации
        is_business_card = False
        try:
            # Селекторы именно заголовка организации (добавлен user selector)
            is_business_card = (
                page.locator(
                    "h1.orgpage-header-view__header, "
                    "div.business-title-view, "
                    "div.card-title-view__title, "
                    "div.orgpage-header-view__header-wrapper > h1"
                ).count()
                > 0
            )
        except Exception:
            pass

        if (not is_business_card) or ("yandex" in current_url and "/org/" not in current_url):
            print("⚠️ Не похоже на карточку организации! (Редирект?). Пробуем перейти по ссылке снова...")

            # Debug: Save bad page (только при наличии bundle)
            if self.debug_bundle_dir:
                try:
                    html_redirect = page.content()
                    os.makedirs(self.debug_bundle_dir, exist_ok=True)
                    with open(os.path.join(self.debug_bundle_dir, "redirect_page.html"), "w", encoding="utf-8") as f:
                        f.write(html_redirect or "")
                except Exception:
                    pass

            page.goto(url, wait_until="domcontentloaded")
            try:
                print("⏳ Повторное ожидание заголовка организации...")
                page.wait_for_selector(
                    "h1.orgpage-header-view__header, "
                    "div.business-title-view, "
                    "div.card-title-view__title, "
                    "h1[itemprop='name'], "
                    "div.orgpage-header-view__header-wrapper > h1",
                    timeout=20000,
                )
                print("✅ Карточка загружена (после повторного перехода)")
            except PlaywrightTimeoutError:
                print("❌ Не удалось загрузить карточку даже после повторного перехода. Возможно бан.")
                if self.debug_bundle_dir:
                    try:
                        html_failed = page.content()
                        os.makedirs(self.debug_bundle_dir, exist_ok=True)
                        with open(os.path.join(self.debug_bundle_dir, "failed_page_final.html"), "w", encoding="utf-8") as f:
                            f.write(html_failed or "")
                    except Exception:
                        pass
        else:
            print("✅ Страница похожа на карточку организации.")

        # Вспомогательная функция для прокрутки
        def scroll_page(times: int = 5) -> None:
            for _ in range(times):
                page.mouse.wheel(0, 1000)
                time.sleep(random.uniform(0.5, 1.0))

        def wait_for_location_info(timeout_sec: float = 5.0) -> bool:
            """Ожидание загрузки location-info API (где title). Возвращает True если загружен."""
            start = time.time()
            while time.time() - start < timeout_sec:
                if any("location-info" in u for u in self.api_responses):
                    print("✅ [WAIT] location-info загружен")
                    return True
                time.sleep(0.5)
                try:
                    page.evaluate("window.scrollBy(0, 100)")
                except Exception:
                    pass
            print("⏱️ [WAIT] Таймаут ожидания location-info")
            return False

        extra_photos_count = 0
        ui_counts: Dict[str, int] = {"reviews": 0, "photos": 0, "services": 0}

        # 1. Скроллим основную страницу
        print("📜 Скроллим основную страницу...")
        scroll_page(3)

        # 1.5 Ожидание location-info перед переходом по вкладкам (title берётся оттуда)
        if not wait_for_location_info():
            print("⚠️ Переход по вкладкам без location-info — title может отсутствовать")

        # 2. Кликаем и скроллим Отзывы (Reviews)
        try:
            reviews_tab = page.query_selector("div.tabs-select-view__title._name_reviews")
            if reviews_tab:
                print("💬 Переходим во вкладку Отзывы...")
                reviews_tab.click(force=True)
                time.sleep(2)

                # Скроллим отзывы (очень агрессивно)
                print("📜 Скроллим отзывы (глубокий скролл - загрузка всех)...")
                for i in range(80):  # Increased to 80
                    # Random scroll amount
                    delta = random.randint(2000, 4000)
                    page.mouse.wheel(0, delta)
                    page.evaluate(f"window.scrollBy(0, {delta//2})")  # JS scroll helper

                    time.sleep(random.uniform(0.5, 1.2))

                    # Small "wobble" (scroll up slightly) to trigger intersection observers
                    if i % 5 == 0:
                        page.mouse.wheel(0, -500)
                        time.sleep(0.5)
                        page.mouse.wheel(0, 500)

                    # Move mouse to trigger hover events
                    page.mouse.move(random.randint(100, 800), random.randint(100, 800))

                    # Пытаемся кликнуть "Показать еще" если есть
                    try:
                        more_btn = page.query_selector("button:has-text('Показать ещё')") or page.query_selector(
                            "div.reviews-view__more"
                        )
                        if more_btn and more_btn.is_visible():
                            more_btn.click()
                            time.sleep(2)
                    except Exception:
                        pass
            else:
                print("ℹ️ Вкладка Отзывы не найдена (селектор)")
        except Exception as e:
            print(f"⚠️ Ошибка при обработке отзывов: {e}")

        # 3. Кликаем и скроллим Фото (Photos)
        try:
            photos_tab = page.query_selector("div.tabs-select-view__title._name_gallery")
            if photos_tab:
                print("📷 Переходим во вкладку Фото...")

                # Пытаемся получить количество фото
                try:
                    photos_text = photos_tab.inner_text()
                    print(f"ℹ️ Текст вкладки фото: {photos_text}")
                    match = re.search(r"(\d+)", photos_text)
                    if match:
                        extra_photos_count = int(match.group(1))
                except Exception:
                    pass

                photos_tab.click(force=True)
                time.sleep(2)
                print("📜 Скроллим фото...")
                scroll_page(10)
            else:
                print("ℹ️ Вкладка Фото не найдена")
        except Exception as e:
            print(f"⚠️ Ошибка при обработке фото: {e}")

        # 4. Кликаем и скроллим Новости (News/Posts)
        try:
            news_tab = page.query_selector("div.tabs-select-view__title._name_posts")
            if news_tab:
                print("📰 Переходим во вкладку Новости...")
                news_tab.click(force=True)
                time.sleep(2)
                print("📜 Скроллим новости...")
                scroll_page(10)
            else:
                print("ℹ️ Вкладка Новости не найдена")
        except Exception as e:
            print(f"⚠️ Ошибка при обработке новостей: {e}")

        # 5. Кликаем и скроллим Товары/Услуги (Prices/Goods)
        # org-centric: используем llz_anchor (из request URL), не page.url
        overview_url_for_return = self._overview_url_canonical

        try:
            # Пробуем разные селекторы для таба товаров
            services_tab = page.query_selector("div.tabs-select-view__title._name_price")
            if not services_tab:
                services_tab = page.query_selector("div.tabs-select-view__title._name_goods")
            if not services_tab:
                # User provided selector (simplified) - 2nd tab in carousel
                services_tab = page.query_selector("div.carousel__content > div:nth-child(2) > div")

            # Fallback на поиск по тексту
            if not services_tab:
                for text in ["Цены", "Товары и услуги", "Услуги", "Товары", "Меню", "Прайс"]:
                    try:
                        found = page.get_by_text(text, exact=False)
                        if found.count() > 0:
                            # Check visibility to avoid hidden elements
                            if found.first.is_visible():
                                services_tab = found.first
                                print(f"✅ Нашли таб услуг по тексту: {text}")
                                break
                    except Exception:
                        pass

            if services_tab:
                print("💰 Переходим во вкладку Цены/Услуги...")
                services_tab.click(force=True)
                time.sleep(3)  # Чуть больше времени на загрузку
                print("📜 Скроллим услуги...")
                scroll_page(20)  # Больше скролла

                # Дожидаемся fetchGoods перед возвратом — избегаем гонок
                n0 = len(self.products_pages)
                for _ in range(8):
                    page.wait_for_timeout(200)
                    n = len(self.products_pages)
                    if n > n0:
                        n0 = n
                    elif n0 > 0:
                        page.wait_for_timeout(400)
                        break

                # Возврат на overview — защита от "улета" карты на /prices/
                current_after = page.url
                if "/prices/" in current_after or current_after.rstrip("/").endswith("/prices") or _is_world_view(current_after):
                    if overview_url_for_return:
                        try:
                            print("📍 Возвращаемся на overview (карта уехала на /prices/)...")
                            page.goto(overview_url_for_return, wait_until="domcontentloaded", timeout=15000)
                            page.wait_for_timeout(2000)
                            print(f"✅ Вернулись на overview: {page.url}")
                        except Exception as e:
                            print(f"⚠️ Не удалось вернуться на overview: {e}")
                    else:
                        # Fallback: убираем /prices/ из URL
                        fallback = re.sub(r"/prices/?", "/", current_after)
                        if fallback != current_after:
                            try:
                                page.goto(fallback, wait_until="domcontentloaded", timeout=15000)
                                page.wait_for_timeout(2000)
                            except Exception:
                                pass
            else:
                print("ℹ️ Вкладка Цены/Услуги не найдена")
        except Exception as e:
            print(f"⚠️ Ошибка при обработке услуг: {e}")

        # Сбор ui_counts из текста вкладок (что видно на UI: 74 отзыва, 64 фото, 36 услуг)
        try:
            for sel, key in [
                ("div.tabs-select-view__title._name_reviews", "reviews"),
                ("div.tabs-select-view__title._name_gallery", "photos"),
                ("div.tabs-select-view__title._name_price", "services"),
            ]:
                tab = page.query_selector(sel) or page.query_selector(
                    "div.tabs-select-view__title._name_goods" if key == "services" else ""
                )
                if tab:
                    txt = tab.inner_text()
                    m = re.search(r"(\d+)", txt)
                    if m:
                        ui_counts[key] = int(m.group(1))
        except Exception:
            pass

        # Проверка верификации через HTML (так как в JSON это может быть спрятано)
        is_verified = False
        try:
            verified_selectors = [
                ".business-verified-badge-view",
                "div._name_verified",
                ".business-card-view__verified-badge",
                "span[aria-label='Информация подтверждена владельцем']",
                "span.business-verified-badge",
                "div.business-verified-badge",
            ]
            for sel in verified_selectors:
                # Используем короткий таймаут для проверки
                try:
                    if page.query_selector(sel):
                        is_verified = True
                        print("✅ Найдена галочка верификации (HTML)")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"Ошибка проверки верификации: {e}")

        print(f"📦 Перехвачено {len(self.api_responses)} API запросов")

        # org-centric: финальная проверка — /prices/ или world-view → goto overview_url_canonical
        current_before_extract = page.url
        if "/prices/" in current_before_extract or current_before_extract.rstrip("/").endswith("/prices") or _is_world_view(current_before_extract):
            try:
                print("📍 Финальный возврат на overview_url_canonical перед сбором payload...")
                page.goto(self._overview_url_canonical, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"⚠️ Не удалось вернуться на overview: {e}")

        # Извлекаем данные из перехваченных ответов (api_payload)
        api_payload = self._extract_data_from_responses()
        data = dict(api_payload)  # final будет мерджиться с html
        data["is_verified"] = is_verified

        # Жёсткий fail: org API не перехвачен, критичных полей нет — не low_quality, а org_api_not_loaded
        has_org_api = any(
            kw in u for u in self.api_responses
            for kw in ("org", "location-info", "organization", "business", "company")
        )
        has_critical = bool(
            data.get("address") or data.get("rating")
            or (data.get("categories") and len(data.get("categories", [])) > 0)
        )

        if _is_captcha_url(page.url):
            print("❌ Финальная страница капчи, возвращаем captcha_detected.")
            return {"error": "captcha_detected", "captcha_url": page.url}

        if not has_org_api and not has_critical:
            print("❌ Org API не перехвачен, критичных полей нет. Возвращаем org_api_not_loaded.")
            return {"error": "org_api_not_loaded", "url": page.url}
        if extra_photos_count > 0:
            data["photos_count"] = extra_photos_count

        # Если не удалось извлечь данные через API, fallback на HTML парсинг
        # ПЕРЕД ЭТИМ: Hybrid Mode для отдельных секций

        # 1. Услуги/Товары (часто скрыты в API)
        if not data.get("products"):
            print("⚠️ Услуги не найдены через API, пробуем HTML парсинг (Hybrid Mode)...")
            try:
                # Импорт здесь, чтобы избежать циклических зависимостей
                from yandex_maps_scraper import parse_products

                # Убедимся, что мы на вкладке товаров (мы туда кликали ранее)
                # Но на всякий случай проверим
                html_products = parse_products(page)
                if html_products:
                    print(f"✅ Услуги найдены через HTML: {len(html_products)}")
                    data["products"] = html_products
                    data["fallback_used"] = True  # MARKER for worker.py warning

                    # Пересобираем overview grouped products
                    grouped_products = {}
                    for prod in html_products:
                        cat = prod.get("category", "Другое") or "Другое"
                        if cat not in grouped_products:
                            grouped_products[cat] = []
                        grouped_products[cat].append(prod)

                    final_products = []
                    for cat, items in grouped_products.items():
                        final_products.append({"category": cat, "items": items})
                    data["products"] = final_products
                else:
                    print("⚠️ HTML парсинг услуг тоже не вернул результатов")
            except Exception as e:
                print(f"⚠️ Ошибка Hybrid Mode для услуг: {e}")

        # HTML fallback: merge_non_empty — не затираем валидные API-поля пустыми
        html_payload = self._extract_from_html_fallback(page)
        meta_src_html = {k: "html_fallback" for k in html_payload if html_payload.get(k)}
        merge_non_empty(data, html_payload, meta_src_html, source="html_fallback", org_page=self.org_page)
        if data.get("title") and (data.get("meta") or {}).get("title_source") == "html_fallback":
            print(f"[IDENTITY] chosen title={data.get('title', '')[:50]} source=html_fallback")

        # Верификация через user selector (если еще не найдено)
        if not is_verified:
            try:
                verified_el = page.query_selector(
                    "div.orgpage-header-view__header-wrapper > h1 > span.business-verified-badge, "
                    "div.orgpage-header-view__header-wrapper > h1 > span"
                )
                if verified_el:
                    data["is_verified"] = True
                    print("✅ Найдена галочка верификации (User CSS)")
            except Exception:
                pass

        # Передаем селектор пользователя в парсер (products HTML)
        try:
            if not data.get("products"):
                print("🛠 Parsing services via HTML with USER Selectors...")
                products_html: List[Dict[str, Any]] = []
                groups = page.query_selector_all("div.business-full-items-grouped-view__content > div")
                for group in groups:
                    cat_title_el = group.query_selector("div.business-full-items-grouped-view__title")
                    cat_title = cat_title_el.inner_text() if cat_title_el else "Другое"
                    items = group.query_selector_all(
                        "div.business-full-items-grouped-view__item, div.related-product-view"
                    )
                    if not items:
                        items = group.query_selector_all("div.business-full-items-grouped-view__items._grid > div")
                    for item in items:
                        try:
                            name_el = item.query_selector("div.related-product-view__title")
                            price_el = item.query_selector("div.related-product-view__price")
                            if name_el:
                                products_html.append({
                                    "name": name_el.inner_text(),
                                    "price": price_el.inner_text() if price_el else "",
                                    "category": cat_title,
                                    "description": "",
                                    "photo": "",
                                })
                        except Exception:
                            pass
                if not products_html:
                    try:
                        from yandex_maps_scraper import parse_products
                        products_html = parse_products(page)
                    except ImportError:
                        pass
                if products_html:
                    print(f"✅ HTML Fallback нашел {len(products_html)} услуг")
                    current = data.get("products", [])
                    current.extend(products_html)
                    data["products"] = current
        except Exception as e:
            print(f"⚠️ Ошибка user-selector HTML parsing: {e}")

        # page_title для fallback в worker
        try:
            pt = page.title()
            if pt and _is_empty(data.get("page_title")):
                data["page_title"] = pt
        except Exception:
            pass

        # Warnings по полноте извлечения (ui_counts vs extracted)
        extracted_reviews = len(data.get("reviews") or [])
        extracted_photos = data.get("photos_count") or len(data.get("photos") or [])
        products_raw = data.get("products") or []
        extracted_services = sum(len(g.get("items", [])) for g in products_raw if isinstance(g, dict)) if products_raw else 0
        if not extracted_services and products_raw:
            extracted_services = len(products_raw)
        warnings_list: List[str] = list(data.get("warnings") or [])
        # Identity warnings из _identity_debug (Part D)
        warnings_list.extend(self._identity_debug.get("warnings") or [])
        warnings_list = list(dict.fromkeys(warnings_list))  # dedup
        if ui_counts.get("reviews", 0) >= 50 and extracted_reviews < ui_counts["reviews"] * 0.8:
            warnings_list.append("reviews_incomplete")
        if ui_counts.get("photos", 0) > 0 and extracted_photos == 0:
            warnings_list.append("photos_not_extracted")
        if ui_counts.get("services", 0) > 0 and extracted_services < ui_counts["services"] * 0.8:
            warnings_list.append("services_incomplete")
        # identity_weak_sources_only: org_page, search_api не дал identity, только html_fallback title
        if self.org_page and not self._search_api_contributed_identity:
            meta = data.get("meta") or {}
            title_src = meta.get("title_source") or meta.get("title_or_name_source")
            if title_src == "html_fallback" and (
                _is_empty(data.get("address")) or _is_empty(data.get("categories"))
            ):
                warnings_list.append("identity_weak_sources_only")
        data["warnings"] = warnings_list

        # Нормализация title_or_name ПЕРЕД return (инвариант)
        _normalize_title_fields(data)

        # org-centric: url в ответе — canonical overview для стабильной ссылки (не world-view)
        if self._overview_url_canonical:
            data["url"] = self._overview_url_canonical

        # DEBUG BUNDLE (dev): сохранить сводку по странице и перехваченным данным (только при наличии bundle)
        if self.debug_bundle_dir:
            try:
                debug_dir = self.debug_bundle_dir
                os.makedirs(debug_dir, exist_ok=True)

                final_url = page.url
                page_title = ""
                try:
                    page_title = page.title()
                except Exception:
                    pass

                html_content = ""
                try:
                    html_content = page.content()
                except Exception:
                    pass
                html_length = len(html_content or "")

                intercepted_json_count = len(self.api_responses)
                all_urls = list(self.api_responses.keys())
                last_10_urls = all_urls[-10:]

                # Топ-3 самых крупных JSON-ответа по длине body
                sized = []
                for u, info in self.api_responses.items():
                    try:
                        body = info.get("data")
                        body_str = json.dumps(body, ensure_ascii=False)
                        sized.append((u, len(body_str)))
                    except Exception:
                        continue
                sized.sort(key=lambda x: x[1], reverse=True)
                top_3_urls = [u for (u, _) in sized[:3]]

                # Информация о cookies и доменах
                cookie_domains = set()
                final_host = ""
                try:
                    parsed = urlparse(final_url)
                    final_host = parsed.hostname or ""
                except Exception:
                    final_host = ""

                try:
                    cookies = context.cookies()
                    for c in cookies:
                        dom = c.get("domain")
                        if dom:
                            cookie_domains.add(dom)
                except Exception:
                    pass

                # Признаки блокировки / капчи (регистронезависимо, рус/англ)
                blocked_flags = {
                    "has_captcha_text": _is_captcha_page(page_title or ""),
                    "html_contains_captcha": ("smart-captcha" in (html_content or "")),
                }

                timestamp = int(time.time() * 1000)
                safe_org = (self.org_id or "unknown")[:32]
                summary_name = f"debug_{timestamp}_{safe_org}.json"
                html_name = f"debug_{timestamp}_{safe_org}.html"
                screenshot_name = f"debug_{timestamp}_{safe_org}.png"

                summary_path = os.path.join(debug_dir, summary_name)
                html_path = os.path.join(debug_dir, html_name)
                screenshot_path = os.path.join(debug_dir, screenshot_name)

                debug_summary = {
                    "final_url": final_url,
                    "overview_url_canonical": getattr(self, "_overview_url_canonical", None),
                    "org_id": self.org_id,
                    "page_title": page_title,
                    "html_length": html_length,
                    "intercepted_json_count": intercepted_json_count,
                    "last_10_json_urls": last_10_urls,
                    "top_3_largest_json_urls": top_3_urls,
                    "cookie_domains": sorted(cookie_domains),
                    "final_host": final_host,
                    "blocked_flags": blocked_flags,
                }

                # Поиск ключевых путей в крупнейших JSON-ответах
                target_keys = [
                    "address",
                    "address_name",
                    "fullAddress",
                    "rating",
                    "score",
                    "ratingData",
                    "rubrics",
                    "categories",
                    "rubric",
                ]
                found_key_paths: Dict[str, List[Dict[str, str]]] = {}
                for u in top_3_urls:
                    info = self.api_responses.get(u)
                    if not info:
                        continue
                    raw_json = info.get("data")
                    try:
                        paths = _find_paths(raw_json, target_keys)
                        for key, items in paths.items():
                            bucket = found_key_paths.setdefault(key, [])
                            # лимитируем общий размер по ключу
                            for item in items:
                                if len(bucket) >= 30:
                                    break
                                bucket.append({"url": u, **item})
                    except Exception:
                        continue

                if found_key_paths:
                    debug_summary["found_key_paths"] = found_key_paths

                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(debug_summary, f, ensure_ascii=False, indent=2)

                if html_content:
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)

                try:
                    page.screenshot(path=screenshot_path, full_page=True)
                except Exception:
                    pass

                print(f"💾 Debug bundle saved: {summary_name}, {html_name}, {screenshot_name}")
            except Exception as e:
                print(f"⚠️ Failed to save debug bundle: {e}")

        # DEV-лог по итоговым полям
        try:
            cats = data.get("categories") or []
            if isinstance(cats, list):
                categories_count = len(cats)
            elif cats:
                categories_count = 1
            else:
                categories_count = 0

            quality_score = None
            meta = data.get("_meta")
            if isinstance(meta, dict):
                quality_score = meta.get("quality_score")

            print(
                f"DEV summary: title='{str(data.get('title', ''))[:80]}', "
                f"address_present={bool(data.get('address'))}, "
                f"rating='{data.get('rating', '')}', "
                f"reviews_count={data.get('reviews_count')}, "
                f"categories_count={categories_count}, "
                f"quality_score={quality_score}"
            )
        except Exception:
            pass

        # Канонический debug bundle для расследований:
        # request_url.txt, final_url.txt, http_status.txt, page.html, payload.json
        if self.debug_bundle_dir:
            try:
                bundle_dir = self.debug_bundle_dir
                os.makedirs(bundle_dir, exist_ok=True)

                # HTML последней страницы — всегда сохраняем
                try:
                    page_html = page.content()
                except Exception:
                    page_html = html_content or ""
                with open(os.path.join(bundle_dir, "page.html"), "w", encoding="utf-8") as f:
                    f.write(page_html or "")

                # Исходный URL
                try:
                    with open(os.path.join(bundle_dir, "request_url.txt"), "w", encoding="utf-8") as f:
                        f.write(initial_url or "")
                except Exception:
                    pass

                # Финальный URL
                try:
                    with open(os.path.join(bundle_dir, "final_url.txt"), "w", encoding="utf-8") as f:
                        f.write(final_url or "")
                except Exception:
                    pass

                # HTTP статус основного запроса
                try:
                    with open(os.path.join(bundle_dir, "http_status.txt"), "w", encoding="utf-8") as f:
                        f.write("" if main_http_status is None else str(main_http_status))
                except Exception:
                    pass

                # api_extract.json — результат extractor'а из API (до HTML merge)
                try:
                    api_extract = {
                        "title": api_payload.get("title"),
                        "title_or_name": api_payload.get("title_or_name"),
                        "address": api_payload.get("address"),
                        "categories": api_payload.get("categories"),
                        "rating": api_payload.get("rating"),
                        "reviews_count": api_payload.get("reviews_count"),
                    }
                    # location-info structure helper: top-level keys и 1–2 уровня
                    li_struct = None
                    if self.location_info_payload:
                        li = self.location_info_payload
                        li_keys = list(li.keys())[:20] if isinstance(li, dict) else []
                        li_nested = {}
                        if isinstance(li, dict) and "data" in li:
                            d = li["data"]
                            li_nested["data_keys"] = list(d.keys())[:25] if isinstance(d, dict) else []
                            if isinstance(d, dict) and "toponymSearchResult" in d:
                                tsr = d["toponymSearchResult"]
                                li_nested["toponymSearchResult_keys"] = list(tsr.keys())[:15] if isinstance(tsr, dict) else []
                        li_struct = {"top_keys": li_keys, "nested": li_nested}
                    api_extract["location_info_structure"] = li_struct
                    with open(os.path.join(bundle_dir, "api_extract.json"), "w", encoding="utf-8") as f:
                        json.dump(api_extract, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"⚠️ Failed to write api_extract.json: {e}")

                # payload.json (legacy) и final_payload.json — то, что возвращается из parse_yandex_card
                try:
                    with open(os.path.join(bundle_dir, "payload.json"), "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    with open(os.path.join(bundle_dir, "final_payload.json"), "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"⚠️ Failed to write payload.json/final_payload.json: {e}")

                # selected_item_debug.json — search API: сколько items, какой выбран, по какому ключу
                try:
                    if getattr(self, "_search_api_debug", None):
                        with open(os.path.join(bundle_dir, "selected_item_debug.json"), "w", encoding="utf-8") as f:
                            json.dump(self._search_api_debug, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"⚠️ Failed to write selected_item_debug.json: {e}")

                # identity_sources.json — источники identity-полей, blocked_candidates (Part E)
                try:
                    meta = data.get("meta") or {}
                    identity_map = {}
                    for f in IDENTITY_FIELDS:
                        val = data.get(f)
                        if _is_non_empty(val):
                            src = meta.get(f"{f}_source") or (meta.get("title_or_name_source") or meta.get("title_source") if f == "title_or_name" else None) or "unknown"
                            identity_map[f] = {"value": val if not isinstance(val, list) else val[:10], "source": src}
                    identity_sources = {
                        "org_id": self.org_id,
                        "identity": identity_map,
                        "blocked_candidates": self._identity_debug.get("blocked_candidates") or [],
                        "warnings": list(data.get("warnings") or []),
                    }
                    with open(os.path.join(bundle_dir, "identity_sources.json"), "w", encoding="utf-8") as f:
                        json.dump(identity_sources, f, ensure_ascii=False, indent=2, default=str)
                except Exception as e:
                    print(f"⚠️ Failed to write identity_sources.json: {e}")

                # Счётчики для сравнения с UI
                try:
                    services_list = data.get("products") or []
                    if isinstance(services_list, list):
                        services_count = sum(len(g.get("items", [])) for g in services_list if isinstance(g, dict)) or len(services_list)
                    else:
                        services_count = 0
                    counts = {
                        "extracted": {
                            "services": services_count,
                            "reviews": len(data.get("reviews") or []),
                            "photos": data.get("photos_count") or len(data.get("photos") or []),
                        },
                        "raw_before_dedup": {
                            "services": getattr(self, "_debug_raw_services_count", 0),
                        },
                    }
                    with open(os.path.join(bundle_dir, "counts_comparison.json"), "w", encoding="utf-8") as f:
                        json.dump(counts, f, ensure_ascii=False, indent=2)
                except Exception as ce:
                    print(f"⚠️ Failed to write counts_comparison.json: {ce}")
            except Exception as e:
                print(f"⚠️ Failed to write canonical debug bundle files: {e}")

        # [PHOTOS_COUNT]
        photos_count = data.get("photos_count") or len(data.get("photos") or [])
        print(f"[PHOTOS_COUNT] extracted={photos_count}")

        # Конкуренты: API не отдаёт, дополняем из HTML (секция «Похожие места»)
        if not (data.get("competitors") or []):
            try:
                from yandex_maps_scraper import parse_competitors
                comps = parse_competitors(page)
                if comps:
                    data["competitors"] = comps
                    print(f"📊 Конкуренты из HTML: {len(comps)}")
            except Exception as ce:
                print(f"⚠️ parse_competitors: {ce}")

        # DATA_TRACE
        print(f"[DATA_TRACE] data.title: {data.get('title')}, title_or_name: {data.get('title_or_name')}")

        print(
            f"✅ Парсинг завершен. Найдено: название='{data.get('title', '')}', адрес='{data.get('address', '')}'"
        )
        return data
    
    def _extract_data_from_responses(self) -> Dict[str, Any]:
        """Извлекает данные из перехваченных API ответов"""
        data = {
            'url': '',
            'title': '',
            'address': '',
            'phone': '',
            'site': '',
            'description': '',
            'rating': '',
            'ratings_count': 0,
            'reviews_count': 0,
            'reviews': [],
            'news': [],
            'photos': [],
            'photos_count': 0,
            'rubric': '',
            'categories': [],
            'hours': '',
            'hours_full': '',
            'social_links': [],
            'features_full': {},
            'competitors': [],
            'products': [],
            'overview': {}
        }
        
        # 1) СНАЧАЛА search API (business_oid) — приоритет для title/address на org-страницах
        for url, response_info in self.api_responses.items():
            if 'search' in url and 'business_oid' in url:
                json_data = response_info['data']
                search_data = self._extract_search_api_business(json_data)
                if search_data:
                    print(f"✅ Извлечены данные из search API (business_oid)")
                    _search_debug = search_data.pop("_search_debug", None)
                    if _search_debug is not None:
                        self._search_api_debug = _search_debug
                    meta_src = search_data.pop("meta", None) or {}
                    merge_non_empty(data, search_data, meta_src, source="search_api", org_page=self.org_page)
                    if any(_is_non_empty(search_data.get(f)) for f in IDENTITY_FIELDS):
                        self._search_api_contributed_identity = True
                    # [IDENTITY] log
                    if search_data.get("title"):
                        print(f"[IDENTITY] chosen title={search_data.get('title', '')[:50]} source=search_api")
                break  # один search API достаточно

        # 2.1) location-info: собираем org-bound, извлекаем объект, выбираем лучший по score
        location_info_scored: List[tuple] = []  # [(org_data, score, idx)]
        api_urls = list(self.api_responses.keys())
        for idx, url in enumerate(api_urls):
            if 'location-info' not in url:
                continue
            json_data = self.api_responses[url].get('data')
            if not self._is_location_info_org_bound(json_data, url):
                self._identity_debug.setdefault("warnings", []).append("location_info_rejected_not_org_bound")
                print(f"⚠️ [LOCATION_INFO] location_info_rejected_not_org_bound (area-based)")
                continue
            org_obj = self._extract_org_object_from_location_info(json_data)
            if org_obj is None:
                self._identity_debug.setdefault("warnings", []).append("location_info_org_object_not_found_in_payload")
                print(f"⚠️ [LOCATION_INFO] location_info_org_object_not_found_in_payload — reject для core")
                continue
            org_data = self._extract_location_info(org_obj)
            if not org_data:
                continue
            score = self._score_location_info_payload(org_data)
            location_info_scored.append((org_data, score, idx))
            print(f"✅ [LOCATION_INFO] location_info_org_bound_scored (score={score})")

        if location_info_scored:
            best = max(location_info_scored, key=lambda x: (x[1], x[2]))  # max score, tie-break: last (higher idx)
            org_data, score, idx = best
            # backward compat для debug
            if idx < len(api_urls):
                self.location_info_payload = self.api_responses[api_urls[idx]].get("data")
            print(f"✅ [LOCATION_INFO] location_info_org_bound_selected_best (score={score})")
            self._identity_debug.setdefault("warnings", []).append("location_info_org_object_extracted")
            blocked = []
            if self.org_page:
                for f in IDENTITY_FIELDS:
                    val = org_data.get(f)
                    if _is_non_empty(val):
                        blocked.append({
                            "source": "location_info",
                            "field": f,
                            "value": val[:80] + "…" if isinstance(val, str) and len(val) > 80 else val,
                            "reason": "org_page_identity_forbidden",
                        })
                        if f in ("title", "title_or_name"):
                            print(f"[IDENTITY] blocked location-info title={str(val)[:50]} (org_page)")
                for f in list(org_data.keys()):
                    if f in IDENTITY_FIELDS:
                        org_data.pop(f, None)
                if org_data:
                    org_data = {k: v for k, v in org_data.items() if k in LOCATION_INFO_SAFE_FIELDS and _is_non_empty(v)}
                if blocked:
                    self._identity_debug.setdefault("blocked_candidates", []).extend(blocked)
                    self._identity_debug.setdefault("warnings", []).append("identity_mismatch:location_info")
                if org_data:
                    print(f"✅ Извлечены данные из location-info (safe fields only)")
            else:
                print(f"✅ Извлечены данные организации из location-info API")
            if org_data:
                meta_src = {k: "location_info" for k in org_data if k not in ("meta",) and org_data.get(k)}
                merge_non_empty(data, org_data, meta_src, source="location_info", org_page=self.org_page)

        # 2.2) Остальные ответы (reviews, products, org_api, posts) — продолжаем итерацию
        accumulated_reviews: List[Dict[str, Any]] = []
        seen_review_keys: set[str] = set()
        accumulated_photos: List[Dict[str, Any]] = []
        seen_photo_keys: set[str] = set()
        review_only_photo_keys: set[str] = set()

        def _photo_key(photo: Dict[str, Any]) -> Optional[str]:
            if not isinstance(photo, dict):
                return None
            pid = photo.get("id")
            if pid:
                return f"id:{pid}"
            purl = photo.get("url")
            if purl:
                return f"url:{purl}"
            return None

        def _merge_photos(photos_batch: List[Dict[str, Any]]) -> None:
            if not photos_batch:
                return
            for p in photos_batch:
                if not isinstance(p, dict):
                    continue
                key = _photo_key(p) or str(p)
                if key in seen_photo_keys:
                    continue
                seen_photo_keys.add(key)
                accumulated_photos.append(p)
            if accumulated_photos:
                data["photos"] = accumulated_photos
                data["photos_count"] = max(len(accumulated_photos), int(data.get("photos_count") or 0))

        def _extract_review_photos(payload: Any) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            if not isinstance(payload, dict):
                return out
            reviews_arr = _pick_first(payload, [["data", "reviews"], ["reviews"], ["result", "reviews"]])
            if not isinstance(reviews_arr, list):
                return out
            for rev in reviews_arr:
                if not isinstance(rev, dict):
                    continue
                for ph in rev.get("photos") or []:
                    if not isinstance(ph, dict):
                        continue
                    purl = ph.get("url") or ph.get("urlTemplate") or ph.get("href")
                    if not purl:
                        continue
                    out.append({"url": str(purl), "id": ph.get("id", "")})
            return out

        def _merge_review_photos_count(photos_batch: List[Dict[str, Any]]) -> None:
            if not photos_batch:
                return
            for p in photos_batch:
                if not isinstance(p, dict):
                    continue
                key = _photo_key(p) or str(p)
                if key in seen_photo_keys or key in review_only_photo_keys:
                    continue
                review_only_photo_keys.add(key)
            if review_only_photo_keys:
                data["photos_count"] = max(
                    int(data.get("photos_count") or 0),
                    len(accumulated_photos) + len(review_only_photo_keys),
                )

        def _merge_reviews(reviews_batch: List[Dict[str, Any]], source_payload: Any = None) -> None:
            if not reviews_batch:
                return
            for r in reviews_batch:
                if not isinstance(r, dict):
                    continue
                review_id = r.get("id") or r.get("review_id") or r.get("external_review_id")
                if review_id:
                    key = f"id:{review_id}"
                else:
                    key = (
                        f"{(r.get('author') or '').strip()}|"
                        f"{(r.get('date') or '').strip()}|"
                        f"{(r.get('text') or '').strip()[:120]}"
                    )
                if key in seen_review_keys:
                    continue
                seen_review_keys.add(key)
                accumulated_reviews.append(r)

            api_count = None
            if source_payload is not None:
                api_count = _pick_first(
                    source_payload,
                    [["data", "params", "count"], ["params", "count"], ["result", "params", "count"]],
                )
            try:
                api_count_int = int(api_count) if api_count is not None else 0
            except (TypeError, ValueError):
                api_count_int = 0

            data["reviews"] = accumulated_reviews
            data["reviews_count"] = max(len(accumulated_reviews), int(data.get("reviews_count") or 0), api_count_int)

        for url, response_info in self.api_responses.items():
            json_data = response_info['data']
            if 'location-info' in url:
                continue  # уже обработано выше
            # Специальная обработка для fetchReviews API
            if 'fetchReviews' in url or 'reviews' in url.lower():
                if self.org_page:
                    url_bid = self._extract_business_id_from_url(url)
                    if url_bid and str(url_bid) != str(self.org_id):
                        self._identity_debug.setdefault("warnings", []).append("identity_mismatch:reviews_url_business")
                    else:
                        reviews = self._extract_reviews_from_api(json_data, url)
                        if reviews:
                            _merge_reviews(reviews, json_data)
                else:
                    reviews = self._extract_reviews_from_api(json_data, url)
                    if reviews:
                        _merge_reviews(reviews, json_data)
                review_photos = _extract_review_photos(json_data)
                if review_photos:
                    _merge_review_photos_count(review_photos)
            # Специальная обработка для fetchGoods/Prices API
            elif 'fetchGoods' in url or 'prices' in url.lower() or 'goods' in url.lower() or 'product' in url.lower() or 'search' in url.lower() or 'catalog' in url.lower():
                if self.org_page:
                    url_bid = self._extract_business_id_from_url(url)
                    if url_bid and str(url_bid) != str(self.org_id):
                        print(f"⚠️ [PRODUCTS] fetchGoods URL businessId={url_bid} != org_id={self.org_id}, ignore")
                        self._identity_debug.setdefault("warnings", []).append("identity_mismatch:products_url_business")
                    else:
                        products = self._extract_products_from_api(json_data)
                        if products:
                            print(f"✅ Извлечено {len(products)} услуг/товаров из API запроса")
                            current_products = data.get('products', [])
                            current_products.extend(products)
                            data['products'] = current_products
                else:
                    products = self._extract_products_from_api(json_data)
                    if products:
                        print(f"✅ Извлечено {len(products)} услуг/товаров из API запроса")
                        current_products = data.get('products', [])
                        current_products.extend(products)
                        data['products'] = current_products
            
            # Пытаемся найти данные организации (org_api)
            elif self._is_organization_data(json_data):
                org_data = self._extract_organization_data(json_data)
                if org_data:
                    # Проверка orgId в ответе (если есть)
                    resp_oid = _pick_first(json_data, [["data", "orgId"], ["orgId"], ["organizationId"], ["data", "organizationId"]])
                    if self.org_page and resp_oid and str(resp_oid) != str(self.org_id):
                        print(f"⚠️ [ORG_API] orgId в ответе={resp_oid} != org_id={self.org_id}, identity не мерджим")
                        self._identity_debug.setdefault("warnings", []).append("identity_mismatch:org_api_org_id")
                        for f in list(org_data.keys()):
                            if f in IDENTITY_FIELDS:
                                org_data.pop(f, None)
                    if org_data:
                        meta_src = {k: "org_api" for k in org_data if k not in ("meta",) and org_data.get(k)}
                        merge_non_empty(data, org_data, meta_src, source="org_api", org_page=self.org_page)
            
            # Пытаемся найти отзывы (общий поиск)
            elif self._is_reviews_data(json_data):
                reviews = self._extract_reviews(json_data)
                if reviews:
                    _merge_reviews(reviews, json_data)
            
            # Пытаемся найти новости/посты
            elif self._is_posts_data(json_data):
                posts = self._extract_posts(json_data)
                if posts:
                    data['news'] = posts

            # getByBusinessId — org-bound фото (id= в URL)
            elif 'getByBusinessId' in url:
                if self.org_page:
                    url_bid = re.search(r'[?&]id=(\d+)', url)
                    url_bid = url_bid.group(1) if url_bid else None
                    if url_bid and str(url_bid) != str(self.org_id):
                        pass
                    else:
                        photos = self._extract_photos_from_api(json_data)
                        if photos:
                            _merge_photos(photos)
                            print(f"✅ Извлечено {len(photos)} фото из getByBusinessId")
                else:
                    photos = self._extract_photos_from_api(json_data)
                    if photos:
                        _merge_photos(photos)
                        print(f"✅ Извлечено {len(photos)} фото из getByBusinessId")
        
        # 2. Если продукты не найдены по URL, ищем во ВСЕХ ответах (Brute Force)
        if not data.get('products'):
            print("⚠️ Товары не найдены по URL фильтру, ищем во всех ответах...")
            for url, response_info in self.api_responses.items():
                try:
                    if self.org_page:
                        url_bid = self._extract_business_id_from_url(url)
                        if url_bid and str(url_bid) != str(self.org_id):
                            continue  # skip wrong business
                    json_data = response_info['data']
                    products = self._extract_products_from_api(json_data)
                    if products:
                        print(f"✅ Извлечено {len(products)} услуг из API (Brute Force): {url[-50:]}")
                        current_products = data.get('products', [])
                        current_products.extend(products)
                        data['products'] = current_products
                        break
                except Exception:
                    pass
        
        # Deduplicate products by name and price
        raw_services_count = 0
        if data.get('products'):
            raw_services_count = len(data['products'])
            self._debug_raw_services_count = raw_services_count
            unique_products = {}
            for p in data['products']:
                # Key: Name + Price (to distinguish "Haircut" 500 vs "Haircut" 1000)
                # Normalize name to lower case to catch case sensitivity issues
                key = (p.get('name', '').strip(), p.get('price', '').strip())
                if key not in unique_products:
                    unique_products[key] = p
            data['products'] = list(unique_products.values())
            unique_count = len(data['products'])
            print(f"✅ Уникальных услуг после дедупликации: {unique_count}")
            print(f"[SERVICES_COUNT] raw_extracted={raw_services_count}, after_dedup={unique_count}")
            if raw_services_count != unique_count:
                print(f"[SERVICES_DUPLICATES] found {raw_services_count - unique_count} duplicates")
        
        # Группируем товары по категориям (для совместимости с отчетом)
        if data.get('products'):
            raw_products = data['products']
            grouped_products = {}
            for prod in raw_products:
                cat = prod.get('category', 'Другое')
                if not cat:
                    cat = 'Другое'
                if cat not in grouped_products:
                    grouped_products[cat] = []
                grouped_products[cat].append(prod)
            
            final_products = []
            for cat, items in grouped_products.items():
                final_products.append({
                    'category': cat,
                    'items': items
                })
            data['products'] = final_products

        # Рейтинг: fallback из среднего по отзывам, если core пустой
        if not data.get('rating') or str(data.get('rating', '')).strip() in ('', '0', '0.0'):
            reviews = data.get('reviews') or []
            ratings = []
            for r in reviews:
                if isinstance(r, dict):
                    rt = r.get('rating') or r.get('score')
                    if rt is not None:
                        try:
                            ratings.append(float(rt))
                        except (ValueError, TypeError):
                            pass
            if ratings:
                avg = sum(ratings) / len(ratings)
                data['rating'] = str(round(avg, 1))
                print(f"✅ Рейтинг из отзывов: {data['rating']} (n={len(ratings)})")
        
        # Создаем overview
        overview_keys = [
            'title', 'address', 'phone', 'site', 'description',
            'rubric', 'categories', 'hours', 'hours_full', 'rating', 
            'ratings_count', 'reviews_count', 'social_links'
        ]
        data['overview'] = {k: data.get(k, '') for k in overview_keys}
        data['overview']['reviews_count'] = data.get('reviews_count', 0)

        reviews_count = len(data.get('reviews', []))
        print(f"[REVIEWS_COUNT] extracted={reviews_count}")
        if reviews_count < 50:
            print(f"[REVIEWS_MISSING] possible pagination or filtering issue (count={reviews_count})")
        
        return data
    
    def _is_organization_data(self, json_data: Any) -> bool:
        """Проверяет, содержит ли JSON данные об организации"""
        if not isinstance(json_data, dict):
            return False
        
        # Ищем ключевые поля организации
        org_fields = ['name', 'title', 'address', 'rating', 'orgId', 'organizationId', 'company']
        return any(field in json_data for field in org_fields) or \
               any(isinstance(v, dict) and any(f in v for f in org_fields) for v in json_data.values() if isinstance(v, dict))
    
    def _extract_search_api_data(self, json_data: Any) -> Dict[str, Any]:
        """Извлекает данные организации из search API"""
        result = {}
        
        def extract_nested(data):
            if isinstance(data, dict):
                # Ищем данные организации в разных структурах
                if 'data' in data and isinstance(data['data'], dict):
                    data = data['data']
                
                if 'result' in data and isinstance(data['result'], dict):
                    data = data['result']
                
                # Ищем название
                title_cand = ''
                if 'name' in data:
                    title_cand = data['name']
                elif 'title' in data:
                    title_cand = data['title']
                
                # Filter out generic toponyms
                if title_cand and title_cand not in ['Санкт-Петербург', 'Россия', 'Яндекс Карты', 'Москва']:
                    result['title'] = title_cand
                
                # Ищем адрес (стандартный ключ + альтернативы для разных эндпоинтов)
                addr_val = None
                if 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        addr_val = addr.get('formatted', '') or addr.get('full', '') or addr.get('text', '') or str(addr)
                    else:
                        addr_val = str(addr)
                if not addr_val:
                    addr_val = data.get('address_name') or data.get('fullAddress') or data.get('full_address') or ''
                if addr_val and isinstance(addr_val, str) and len(addr_val.strip()) > 2:
                    _set_if_empty(result, "address", addr_val.strip())
                
                # Ищем рейтинг
                if 'rating' in data:
                    rating = data['rating']
                    if isinstance(rating, (int, float)):
                        _set_if_empty(result, "rating", str(rating))
                    elif isinstance(rating, dict):
                        _set_if_empty(
                            result,
                            "rating",
                            str(rating.get('value', rating.get('score', rating.get('val', '')))),
                        )
                elif 'score' in data:
                    _set_if_empty(result, "rating", str(data['score']))
                
                # Ищем количество отзывов
                if 'reviewsCount' in data:
                    try:
                        _set_if_empty(result, "reviews_count", int(data['reviewsCount']))
                    except (TypeError, ValueError):
                        pass
                elif 'reviews_count' in data:
                    try:
                        _set_if_empty(result, "reviews_count", int(data['reviews_count']))
                    except (TypeError, ValueError):
                        pass
                
                # Рекурсивно обходим вложенные объекты
                for value in data.values():
                    if isinstance(value, (dict, list)):
                        extract_nested(value)
        
        extract_nested(json_data)
        return result
    
    def _extract_from_html_fallback(self, page) -> Dict[str, Any]:
        """
        Извлекает title/address из HTML (og:title, page title, h1).
        Возвращает dict — результат мерджится в final, только заполняя пустые слоты.
        """
        out: Dict[str, Any] = {}
        try:
            og_title = page.locator("meta[property='og:title']").get_attribute("content")
            if og_title:
                out["og_title"] = og_title
                clean = og_title.replace(" — Яндекс Карты", "").replace(" - Яндекс Карты", "").split("|")[0].split(",")[0].strip()
                t = clean or og_title.split("|")[0].strip()
                if t:
                    out["title_or_name"] = t
                    out["title"] = t
                    print(f"✅ [HTML_FALLBACK] og:title -> {t[:50]}")
            if not out.get("title"):
                pt = page.title()
                if pt:
                    out["page_title"] = pt
                    t = pt.replace(" — Яндекс Карты", "").replace(" - Яндекс Карты", "").split("|")[0].split("-")[0].strip()
                    if t:
                        out["title_or_name"] = t
                        out["title"] = t
                        print(f"✅ [HTML_FALLBACK] page_title -> {t[:50]}")
            if not out.get("title"):
                h1 = page.query_selector("div.orgpage-header-view__header-wrapper > h1, h1.orgpage-header-view__header")
                if h1:
                    t = h1.inner_text().strip()
                    if t:
                        out["title_or_name"] = t
                        out["title"] = t
                        print(f"✅ [HTML_FALLBACK] h1 -> {t[:50]}")
            # Адрес (короткий таймаут — meta может отсутствовать, не блокируем og:title)
            meta_addr = None
            try:
                loc = page.locator("meta[property='business:contact_data:street_address']")
                loc.set_default_timeout(2000)
                meta_addr = loc.get_attribute("content")
            except Exception:
                pass
            if meta_addr:
                out["address"] = meta_addr
            elif not out.get("address"):
                addr_el = page.query_selector("div.orgpage-header-view__address, a.orgpage-header-view__address, div.business-contacts-view__address-link")
                if addr_el:
                    out["address"] = addr_el.inner_text().strip()
        except Exception as e:
            print(f"⚠️ [HTML_FALLBACK] error: {e}")
        return out

    def _extract_search_api_business(self, json_data: Any) -> Dict[str, Any]:
        """
        Извлекает данные бизнеса из search API (business_oid=...).
        Выбирает item, где id/oid/businessOid совпадает с self.org_id.
        Если не найден — возвращает пустой result (не используем search API).
        """
        result: Dict[str, Any] = {}
        expected_oid = self.org_id
        items = _pick_first(json_data, [["data", "items"], ["items"]])
        if not isinstance(items, list) or not items:
            return result

        # Найти item с совпадающим org_id (id, oid, businessOid, uri oid=)
        def _item_oid(it: Any) -> Optional[str]:
            if not isinstance(it, dict):
                return None
            oid = it.get("id") or it.get("oid") or it.get("businessOid")
            if oid is not None:
                return str(oid)
            uri = it.get("uri") or ""
            if isinstance(uri, str) and "oid=" in uri:
                m = re.search(r"oid=(\d+)", uri)
                if m:
                    return m.group(1)
            return None

        item = None
        matched_key = None
        selected_index = -1
        for i, it in enumerate(items):
            oid = _item_oid(it)
            if oid and expected_oid and str(oid) == str(expected_oid):
                item = it
                selected_index = i
                if it.get("id") is not None and str(it.get("id")) == str(expected_oid):
                    matched_key = "id"
                elif it.get("oid") is not None and str(it.get("oid")) == str(expected_oid):
                    matched_key = "oid"
                elif it.get("businessOid") is not None and str(it.get("businessOid")) == str(expected_oid):
                    matched_key = "businessOid"
                else:
                    matched_key = "uri"
                break

        if not item or not isinstance(item, dict):
            return result

        # meta для источников полей
        meta_src: Dict[str, str] = {}
        BLACKLIST = ("Санкт-Петербург", "Россия", "Яндекс Карты", "Москва")
        title = item.get("title") or item.get("shortTitle") or item.get("name")
        if title and str(title).strip() not in BLACKLIST:
            result["title"] = str(title).strip()
            result["title_or_name"] = result["title"]
            meta_src["title"] = meta_src["title_or_name"] = "search_api"
        addr = item.get("fullAddress") or item.get("address")
        if addr and isinstance(addr, str) and len(addr.strip()) > 2:
            result["address"] = addr.strip()
            meta_src["address"] = "search_api"
        if item.get("categories"):
            cats = []
            for c in item["categories"]:
                if isinstance(c, dict) and c.get("name"):
                    cats.append(str(c["name"]))
                elif isinstance(c, str):
                    cats.append(c)
            if cats:
                result["categories"] = cats
                meta_src["categories"] = "search_api"
        rd = item.get("ratingData")
        if isinstance(rd, dict):
            rv = rd.get("ratingValue") or rd.get("rating") or rd.get("value")
            if rv is not None and rv != 0:
                result["rating"] = str(rv)
                meta_src["rating"] = "search_api"
            rc = rd.get("reviewCount") or rd.get("reviewsCount") or rd.get("count")
            if rc is not None:
                try:
                    result["reviews_count"] = int(rc)
                    meta_src["reviews_count"] = "search_api"
                except (TypeError, ValueError):
                    pass
        # Fallback: иногда рейтинг лежит в modularPin.subtitleHints[].text, например "4.8"
        if not result.get("rating"):
            subtitle_hints = _pick_first(item, [["modularPin", "subtitleHints"]])
            if isinstance(subtitle_hints, list):
                for hint in subtitle_hints:
                    if not isinstance(hint, dict):
                        continue
                    text_val = str(hint.get("text") or "").strip()
                    hint_type = str(hint.get("type") or "").upper()
                    if not text_val:
                        continue
                    if hint_type != "RATING" and not re.search(r"\b[0-5][\.,]\d\b", text_val):
                        continue
                    m = re.search(r"\b([0-5][\.,]\d)\b", text_val)
                    if m:
                        result["rating"] = m.group(1).replace(",", ".")
                        meta_src["rating"] = "search_api"
                        break
        # org-centric: phones, urls, hours из search API (org-bound, не зависят от карты)
        phones = item.get("phones")
        if isinstance(phones, list) and phones:
            p0 = phones[0]
            if isinstance(p0, dict):
                phone_val = p0.get("number") or p0.get("formatted") or p0.get("value")
            else:
                phone_val = str(p0)
            if phone_val:
                result["phone"] = str(phone_val).strip()
                meta_src["phone"] = "search_api"
        urls = item.get("urls")
        if isinstance(urls, list) and urls:
            site_val = urls[0] if isinstance(urls[0], str) else None
            if site_val:
                result["site"] = str(site_val).strip()
                meta_src["site"] = "search_api"
        hours_text = item.get("workingTimeText")
        if hours_text and isinstance(hours_text, str) and hours_text.strip():
            result["hours"] = hours_text.strip()
            meta_src["hours"] = "search_api"
        working_time = item.get("workingTime")
        if isinstance(working_time, list) and working_time:
            result["hours_full"] = working_time
            if "hours" not in result and hours_text:
                result["hours"] = hours_text.strip()
        result["meta"] = meta_src
        result["_search_debug"] = {
            "items_count": len(items),
            "selected_index": selected_index,
            "matched_key": matched_key,
            "expected_oid": expected_oid,
        }
        return result

    def _extract_location_info(self, json_data: Any) -> Dict[str, Any]:
        """
        Извлекает данные организации из location-info API.
        Использует _pick_first с реальными путями из JSON.
        location-info: data.toponymSearchResult.items[0].title (город), бизнес в showcase.
        search API — основной источник для org-страниц.
        """
        result = {}
        BLACKLIST = ("Санкт-Петербург", "Россия", "Яндекс Карты", "Москва")

        # Прямые пути из location-info (по реальным bundle)
        title = _pick_first(json_data, [
            ["data", "toponymSearchResult", "items", "0", "toponymDiscovery", "categories", "0", "showcase", "0", "title"],
            ["data", "toponymSearchResult", "exactResult", "toponymDiscovery", "categories", "0", "showcase", "0", "title"],
            ["data", "toponymSearchResult", "items", "0", "title"],
            ["data", "toponymSearchResult", "exactResult", "title"],
        ])
        if title and str(title).strip() not in BLACKLIST:
            result["title"] = str(title).strip()
            result["title_or_name"] = result["title"]

        addr = _pick_first(json_data, [
            ["data", "toponymSearchResult", "items", "0", "toponymDiscovery", "categories", "0", "showcase", "0", "fullAddress"],
            ["data", "toponymSearchResult", "items", "0", "toponymDiscovery", "categories", "0", "showcase", "0", "address"],
            ["data", "toponymSearchResult", "items", "0", "fullAddress"],
            ["data", "toponymSearchResult", "items", "0", "address"],
            ["data", "toponymSearchResult", "exactResult", "address"],
        ])
        if addr and isinstance(addr, str) and len(addr.strip()) > 2 and addr.strip() not in BLACKLIST:
            result["address"] = addr.strip()

        # ratingData из showcase
        rd = _pick_first(json_data, [
            ["data", "toponymSearchResult", "items", "0", "toponymDiscovery", "categories", "0", "showcase", "0", "ratingData"],
            ["data", "toponymSearchResult", "items", "0", "ratingData"],
        ])
        if isinstance(rd, dict):
            rv = rd.get("ratingValue") or rd.get("rating") or rd.get("value")
            if rv is not None:
                result["rating"] = str(rv)
            rc = rd.get("reviewCount") or rd.get("reviewsCount") or rd.get("count")
            if rc is not None:
                try:
                    result["reviews_count"] = int(rc)
                except (TypeError, ValueError):
                    pass

        def extract_nested(data):
            if isinstance(data, dict):
                # Ищем название
                title_cand = ''
                if 'name' in data:
                    title_cand = data['name']
                elif 'title' in data:
                    title_cand = data['title']
                
                # Filter out generic toponyms
                if title_cand:
                    if title_cand in ['Санкт-Петербург', 'Россия', 'Яндекс Карты', 'Москва']:
                        # print(f"⚠️ [Parser] Ignored title '{title_cand}' (in blacklist)") 
                        pass # Don't spam, but we skip it
                    else:
                        # print(f"✅ [Parser] Found title: {title_cand}")
                        result['title'] = title_cand
                
                # Ищем адрес (стандартный ключ + альтернативы для разных эндпоинтов)
                addr_val = None
                if 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        addr_val = addr.get('formatted', '') or addr.get('full', '') or addr.get('text', '') or str(addr)
                    else:
                        addr_val = str(addr)
                if not addr_val:
                    addr_val = data.get('address_name') or data.get('fullAddress') or data.get('full_address') or ''
                if addr_val and isinstance(addr_val, str) and len(addr_val.strip()) > 2:
                    result['address'] = addr_val.strip()
                
                # Ищем рейтинг
                if 'rating' in data:
                    rating = data['rating']
                    if isinstance(rating, (int, float)):
                        result['rating'] = str(rating)
                    elif isinstance(rating, dict):
                        result['rating'] = str(rating.get('value', rating.get('score', '')))
                
                # Fallback rating
                elif 'score' in data:
                     result['rating'] = str(data['score'])

                # Ищем рейтинг внутри ratingData (часто бывает в location-info)
                elif 'ratingData' in data:
                    rd = data['ratingData']
                    if isinstance(rd, dict):
                         val = rd.get('rating') or rd.get('value') or rd.get('score')
                         if val: result['rating'] = str(val)
                         
                         count = rd.get('count') or rd.get('reviewCount')
                         if count: result['reviews_count'] = int(count)
                
                # Ищем количество отзывов
                if 'reviewsCount' in data:
                    result['reviews_count'] = int(data['reviewsCount'])
                elif 'reviews_count' in data:
                    result['reviews_count'] = int(data['reviews_count'])
                
                # Ищем категории / рубрики
                if 'rubrics' in data and isinstance(data['rubrics'], list):
                    names = []
                    for r in data['rubrics']:
                        if isinstance(r, dict):
                            n = r.get('name') or r.get('label')
                            if n:
                                names.append(str(n))
                    if names:
                        result['categories'] = names
                elif 'categories' in data:
                    cats = data['categories']
                    if isinstance(cats, list) and cats:
                        # Уже список строк или объектов
                        result['categories'] = cats
                    elif isinstance(cats, dict) and cats:
                        result['categories'] = [cats]
                elif 'rubric' in data:
                    rub = data['rubric']
                    if isinstance(rub, str) and rub.strip():
                        result['categories'] = [rub.strip()]
                    elif isinstance(rub, dict):
                        n = rub.get('name') or rub.get('label')
                        if n:
                            result['categories'] = [str(n)]
                
                # Ищем категории / рубрики
                if 'rubrics' in data and isinstance(data['rubrics'], list):
                    names = []
                    for r in data['rubrics']:
                        if isinstance(r, dict):
                            n = r.get('name') or r.get('label')
                            if n:
                                names.append(str(n))
                    if names:
                        _extend_unique(result, 'categories', names)
                elif 'categories' in data:
                    cats = data['categories']
                    if isinstance(cats, list) and cats:
                        _extend_unique(result, 'categories', cats)
                    elif isinstance(cats, dict) and cats:
                        _extend_unique(result, 'categories', [cats])
                elif 'rubric' in data:
                    rub = data['rubric']
                    if isinstance(rub, str) and rub.strip():
                        _extend_unique(result, 'categories', [rub.strip()])
                    elif isinstance(rub, dict):
                        n = rub.get('name') or rub.get('label')
                        if n:
                            _extend_unique(result, 'categories', [str(n)])
                
                # Ищем телефон
                if 'phones' in data:
                    phones = data['phones']
                    if isinstance(phones, list) and phones:
                        phone_obj = phones[0]
                        if isinstance(phone_obj, dict):
                            result['phone'] = phone_obj.get('formatted', '') or phone_obj.get('number', '')
                        else:
                            result['phone'] = str(phone_obj)
                    elif isinstance(phones, dict):
                        result['phone'] = phones.get('formatted', '') or phones.get('number', '')
                
                # Рекурсивно обходим вложенные объекты
                for value in data.values():
                    extract_nested(value)
        
        extract_nested(json_data)

        # Fallback по наиболее частым путям (payload.company.*)
        try:
            addr_nested = (
                _get_nested(json_data, "payload.company.address.formatted")
                or _get_nested(json_data, "payload.company.address_name")
                or _get_nested(json_data, "payload.company.fullAddress")
            )
            _set_if_empty(result, "address", addr_nested)
        except Exception:
            pass

        try:
            rating_nested = (
                _get_nested(json_data, "payload.company.ratingData.rating")
                or _get_nested(json_data, "payload.company.ratingData.score")
            )
            _set_if_empty(result, "rating", rating_nested)
        except Exception:
            pass

        try:
            cnt = _get_nested(json_data, "payload.company.ratingData.count")
            if isinstance(cnt, (int, float, str)):
                try:
                    cnt_int = int(cnt)
                    _set_if_empty(result, "reviews_count", cnt_int)
                except ValueError:
                    pass
        except Exception:
            pass

        try:
            rubrics = _get_nested(json_data, "payload.company.rubrics") or []
            names = []
            if isinstance(rubrics, list):
                for r in rubrics:
                    if isinstance(r, dict):
                        n = r.get("name") or r.get("label")
                        if n:
                            names.append(str(n))
            if names:
                _extend_unique(result, "categories", names)
        except Exception:
            pass

        return result
    
    def _extract_organization_data(self, json_data: Any) -> Dict[str, Any]:
        """Извлекает данные организации из JSON"""
        result = {}
        
        def extract_nested(data, path=''):
            """Рекурсивно извлекает данные"""
            if isinstance(data, dict):
                # Прямые поля
                if 'name' in data or 'title' in data:
                    result['title'] = data.get('name') or data.get('title', '')
                
                # Адрес: стандартный ключ + альтернативы (разные эндпоинты Яндекса)
                addr_val = None
                if 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        addr_val = addr.get('formatted', '') or addr.get('full', '') or addr.get('text', '') or str(addr)
                    else:
                        addr_val = str(addr)
                if not addr_val and 'address_name' in data:
                    addr_val = data.get('address_name') or ''
                if not addr_val and 'fullAddress' in data:
                    addr_val = data.get('fullAddress') or ''
                if not addr_val and 'full_address' in data:
                    addr_val = data.get('full_address') or ''
                if addr_val and isinstance(addr_val, str) and len(addr_val.strip()) > 2:
                    _set_if_empty(result, "address", addr_val.strip())
                
                if 'rating' in data:
                    rating = data['rating']
                    if isinstance(rating, (int, float)):
                        _set_if_empty(result, "rating", str(rating))
                    elif isinstance(rating, dict):
                         _set_if_empty(
                             result,
                             "rating",
                             str(rating.get('value', rating.get('score', rating.get('val', '')))),
                         )
                elif 'score' in data:
                    _set_if_empty(result, "rating", str(data['score']))
                
                # Support modularPin rating (Yandex Update)
                if 'modularPin' in data and isinstance(data['modularPin'], dict):
                    hints = data['modularPin'].get('subtitleHints', [])
                    for hint in hints:
                        if hint.get('type') == 'RATING':
                             result['rating'] = str(hint.get('text', ''))
                             break
                
                if 'reviewsCount' in data or 'reviews_count' in data:
                    try:
                        _set_if_empty(
                            result,
                            "reviews_count",
                            int(data.get('reviewsCount') or data.get('reviews_count', 0)),
                        )
                    except (TypeError, ValueError):
                        pass
                
                if 'phones' in data:
                    phones = data['phones']
                    if isinstance(phones, list) and phones:
                        result['phone'] = phones[0].get('formatted', '') or phones[0].get('number', '')
                    elif isinstance(phones, dict):
                        result['phone'] = phones.get('formatted', '') or phones.get('number', '')
                
                if 'site' in data or 'website' in data:
                    result['site'] = data.get('site') or data.get('website', '')
                
                if 'description' in data or 'about' in data:
                    result['description'] = data.get('description') or data.get('about', '')
                
                # Категории / рубрики
                if 'rubrics' in data and isinstance(data['rubrics'], list):
                    names = []
                    for r in data['rubrics']:
                        if isinstance(r, dict):
                            n = r.get('name') or r.get('label')
                            if n:
                                names.append(str(n))
                    if names:
                        _extend_unique(result, 'categories', names)
                elif 'categories' in data:
                    cats = data['categories']
                    if isinstance(cats, list) and cats:
                        _extend_unique(result, 'categories', cats)
                    elif isinstance(cats, dict) and cats:
                        _extend_unique(result, 'categories', [cats])
                elif 'rubric' in data:
                    rub = data['rubric']
                    if isinstance(rub, str) and rub.strip():
                        _extend_unique(result, 'categories', [rub.strip()])
                    elif isinstance(rub, dict):
                        n = rub.get('name') or rub.get('label')
                        if n:
                            _extend_unique(result, 'categories', [str(n)])
                
                # Рекурсивно обходим вложенные объекты
                for key, value in data.items():
                    extract_nested(value, f"{path}.{key}")
            
            elif isinstance(data, list):
                for item in data:
                    extract_nested(item, path)
        
        extract_nested(json_data)

        # Fallback по наиболее частым путям (payload.company.*)
        try:
            addr_nested = (
                _get_nested(json_data, "payload.company.address.formatted")
                or _get_nested(json_data, "payload.company.address_name")
                or _get_nested(json_data, "payload.company.fullAddress")
            )
            _set_if_empty(result, "address", addr_nested)
        except Exception:
            pass

        try:
            rating_nested = (
                _get_nested(json_data, "payload.company.ratingData.rating")
                or _get_nested(json_data, "payload.company.ratingData.score")
            )
            _set_if_empty(result, "rating", rating_nested)
        except Exception:
            pass

        try:
            cnt = _get_nested(json_data, "payload.company.ratingData.count")
            if isinstance(cnt, (int, float, str)):
                try:
                    cnt_int = int(cnt)
                    _set_if_empty(result, "reviews_count", cnt_int)
                except ValueError:
                    pass
        except Exception:
            pass

        try:
            rubrics = _get_nested(json_data, "payload.company.rubrics") or []
            names = []
            if isinstance(rubrics, list):
                for r in rubrics:
                    if isinstance(r, dict):
                        n = r.get("name") or r.get("label")
                        if n:
                            names.append(str(n))
            if names:
                _extend_unique(result, "categories", names)
        except Exception:
            pass

        return result
    
    def _is_reviews_data(self, json_data: Any) -> bool:
        """Проверяет, содержит ли JSON данные об отзывах"""
        if not isinstance(json_data, dict):
            return False
        
        review_fields = ['reviews', 'items', 'feedback', 'comments']
        return any(field in json_data for field in review_fields) or \
               (isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], dict) and 
                any(k in json_data[0] for k in ['text', 'comment', 'rating', 'author']))
    
    def _extract_reviews_from_api(self, json_data: Any, url: str) -> List[Dict[str, Any]]:
        """Извлекает отзывы из API запроса fetchReviews (специфичная структура Яндекс.Карт)"""
        reviews = []
        
        def extract_review_item(item: dict) -> Optional[Dict[str, Any]]:
            """Извлекает один отзыв из структуры API"""
            if not isinstance(item, dict):
                return None
            
            # Извлекаем автора
            author_name = ''
            if 'author' in item:
                author = item['author']
                if isinstance(author, dict):
                    author_name = author.get('name') or author.get('displayName') or author.get('username', '')
                else:
                    author_name = str(author)
            else:
                author_name = item.get('authorName', item.get('author_name', ''))
            
            # Извлекаем рейтинг (может быть числом или строкой)
            rating = item.get('rating') or item.get('score') or item.get('grade') or item.get('stars')
            if rating:
                # Если это число, преобразуем в строку
                if isinstance(rating, (int, float)):
                    rating = str(rating)
                else:
                    rating = str(rating)
            else:
                rating = ''
            
            # Извлекаем текст
            text = item.get('text') or item.get('comment') or item.get('message') or item.get('content', '')
            
            # Извлекаем дату (может быть в разных форматах)
            date_fields = [
                'date', 'publishedAt', 'published_at', 'createdAt', 'created_at',
                'time', 'timestamp', 'created', 'published',
                'dateCreated', 'datePublished', 'reviewDate', 'review_date',
                'updatedTime'
            ]
            date_raw = next((item.get(field) for field in date_fields if item.get(field)), None)

            date = ''
            if date_raw:
                # Если это timestamp (число)
                if isinstance(date_raw, (int, float)):
                    try:
                        from datetime import datetime
                        # Проверяем, в миллисекундах или секундах
                        if date_raw > 1e10:  # Вероятно миллисекунды
                            date = datetime.fromtimestamp(date_raw / 1000.0).isoformat()
                        else:  # Секунды
                            date = datetime.fromtimestamp(date_raw).isoformat()
                    except Exception as e:
                        print(f"⚠️ Ошибка парсинга timestamp {date_raw}: {e}")
                        date = str(date_raw)
                # Если это строка ISO формата
                elif isinstance(date_raw, str):
                    # Пробуем распарсить как ISO
                    try:
                        from datetime import datetime
                        # Убираем Z и заменяем на +00:00
                        date_clean = date_raw.replace('Z', '+00:00')
                        datetime.fromisoformat(date_clean)  # Проверяем валидность
                        date = date_clean
                    except:
                        # Если не ISO, оставляем как есть (будет парситься в worker.py)
                        date = date_raw
                else:
                    date = str(date_raw)
            
            # Логируем дату отзыва (только для первых 5 отзывов)
            if date and len(reviews) < 5:
                print(f"📅 Дата отзыва извлечена: {date}")
            elif not date and len(reviews) < 5:
                print(f"⚠️ Дата отзыва не найдена. Доступные поля: {list(item.keys())}")
            
            # Извлекаем ответ организации (проверяем все возможные варианты)
            response_text = None
            response_date = None
            owner_comment = (
                item.get('businessComment') or
                item.get('business_comment') or
                item.get('ownerComment') or 
                item.get('owner_comment') or 
                item.get('response') or 
                item.get('reply') or
                item.get('organizationResponse') or
                item.get('organization_response') or
                item.get('companyResponse') or
                item.get('company_response') or
                item.get('ownerResponse') or
                item.get('owner_response') or
                item.get('answer') or
                item.get('answers')  # Может быть массив
            )
            
            if owner_comment:
                if isinstance(owner_comment, list) and len(owner_comment) > 0:
                    # Если это массив, берем первый непустой элемент
                    first_non_empty = None
                    for candidate in owner_comment:
                        if not candidate:
                            continue
                        if isinstance(candidate, dict):
                            if any(candidate.get(k) for k in ("text", "comment", "message", "content")):
                                first_non_empty = candidate
                                break
                        else:
                            candidate_text = str(candidate).strip()
                            if candidate_text and candidate_text.lower() not in ("none", "null"):
                                first_non_empty = candidate
                                break
                    owner_comment = first_non_empty if first_non_empty is not None else owner_comment[0]
                
                if isinstance(owner_comment, dict):
                    response_text = (
                        owner_comment.get('text') or 
                        owner_comment.get('comment') or 
                        owner_comment.get('message') or
                        owner_comment.get('content') or
                        str(owner_comment)
                    )
                    response_date = (
                        owner_comment.get('date') or 
                        owner_comment.get('createdAt') or
                        owner_comment.get('created_at') or
                        owner_comment.get('publishedAt') or
                        owner_comment.get('published_at')
                    )
                    if response_text:
                        print(f"✅ Извлечен ответ организации: {response_text[:100]}...")
                else:
                    response_text = str(owner_comment)
                    if response_text:
                        print(f"✅ Извлечен ответ организации (строка): {response_text[:100]}...")
            
            # Логируем дату отзыва
            if date:
                print(f"📅 Дата отзыва: {date}")
            
            if text:
                review_id = (
                    item.get('id') or
                    item.get('reviewId') or
                    item.get('review_id') or
                    item.get('uuid')
                )
                review_data = {
                    'id': str(review_id) if review_id is not None else None,
                    'author': author_name or 'Анонимный пользователь',
                    'rating': rating,
                    'text': text,
                    'date': date,
                    'org_reply': response_text,  # Маппинг на org_reply для совместимости с worker.py
                    'response_text': response_text,  # Оставляем для обратной совместимости
                    'response_date': response_date,
                    'has_response': bool(response_text)
                }
                if response_text:
                    print(f"✅ Отзыв с ответом: автор={author_name}, рейтинг={rating}, ответ={response_text[:50]}...")
                return review_data
            return None
        
        # Пытаемся найти массив отзывов в разных структурах
        if isinstance(json_data, dict):
            # Вариант 1: прямой массив в ключе reviews
            if 'reviews' in json_data and isinstance(json_data['reviews'], list):
                for item in json_data['reviews']:
                    review = extract_review_item(item)
                    if review:
                        reviews.append(review)
            
            # Вариант 2: в data.reviews
            elif 'data' in json_data and isinstance(json_data['data'], dict):
                if 'reviews' in json_data['data'] and isinstance(json_data['data']['reviews'], list):
                    for item in json_data['data']['reviews']:
                        review = extract_review_item(item)
                        if review:
                            reviews.append(review)
            
            # Вариант 3: в result.reviews
            elif 'result' in json_data and isinstance(json_data['result'], dict):
                if 'reviews' in json_data['result'] and isinstance(json_data['result']['reviews'], list):
                    for item in json_data['result']['reviews']:
                        review = extract_review_item(item)
                        if review:
                            reviews.append(review)
            
            # Вариант 4: в items
            elif 'items' in json_data and isinstance(json_data['items'], list):
                for item in json_data['items']:
                    review = extract_review_item(item)
                    if review:
                        reviews.append(review)
            
            # Вариант 5: рекурсивный поиск
            else:
                for key, value in json_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict) and any(k in value[0] for k in ['text', 'comment', 'rating', 'author']):
                            for item in value:
                                review = extract_review_item(item)
                                if review:
                                    reviews.append(review)
        
        elif isinstance(json_data, list):
            # Если сам JSON - это массив отзывов
            for item in json_data:
                review = extract_review_item(item)
                if review:
                    reviews.append(review)
        
        return reviews
    
    def _extract_reviews(self, json_data: Any) -> List[Dict[str, Any]]:
        """Извлекает отзывы из JSON (общий метод)"""
        reviews = []
        
        def find_reviews(data):
            if isinstance(data, dict):
                # Ищем массив отзывов
                for key in ['reviews', 'items', 'feedback', 'comments']:
                    if key in data and isinstance(data[key], list):
                        for item in data[key]:
                            if isinstance(item, dict):
                                review = {
                                    'author': item.get('author', {}).get('name', '') if isinstance(item.get('author'), dict) else item.get('author', ''),
                                    'rating': str(item.get('rating', item.get('score', ''))),
                                    'text': item.get('text', item.get('comment', item.get('message', ''))),
                                    'date': item.get('date', item.get('createdAt', ''))
                                }
                                if review['text']:
                                    reviews.append(review)
                
                # Рекурсивно ищем вложенные объекты
                for value in data.values():
                    find_reviews(value)
            
            elif isinstance(data, list):
                for item in data:
                    find_reviews(item)
        
        find_reviews(json_data)
        return reviews
    
    def _is_posts_data(self, json_data: Any) -> bool:
        """Проверяет, содержит ли JSON данные о постах/новостях (getPosts: data.items)"""
        if not isinstance(json_data, dict):
            return False
        post_fields = ['posts', 'publications', 'news', 'items']
        if any(field in json_data for field in post_fields):
            return True
        # getPosts: {"data": {"count": 7, "items": [...]}}
        inner = json_data.get("data")
        if isinstance(inner, dict) and any(f in inner for f in post_fields):
            return True
        return False
    
    def _extract_posts(self, json_data: Any) -> List[Dict[str, Any]]:
        """Извлекает посты/новости из JSON"""
        posts = []
        
        def find_posts(data):
            if isinstance(data, dict):
                for key in ['posts', 'publications', 'news', 'items']:
                    if key in data and isinstance(data[key], list):
                        # LOGGING STRUCTURE
                        if len(data[key]) > 0:
                            item0 = data[key][0]
                            if isinstance(item0, dict):
                                print(f"🔍 DEBUG POSTS: Found list in '{key}', Item keys: {list(item0.keys())}")

                        for item in data[key]:
                            if isinstance(item, dict):
                                # Извлекаем дату (может быть в разных форматах)
                                date_fields = [
                                    'date', 'publishedAt', 'published_at', 'createdAt', 'created_at',
                                    'publicationTime', 'time', 'timestamp', 'created', 'published',
                                    'dateCreated', 'datePublished', 'updatedTime'
                                ]
                                
                                date_raw = None
                                for field in date_fields:
                                    val = item.get(field)
                                    if val:
                                        date_raw = val
                                        break
                                
                                # Fallback: check for nested date object (e.g. date: { value: ... })
                                if not date_raw and isinstance(item.get('date'), dict):
                                    date_raw = item.get('date').get('value')

                                date = ''
                                if date_raw:
                                    # Если это timestamp (число)
                                    if isinstance(date_raw, (int, float)):
                                        try:
                                            from datetime import datetime
                                            # Проверяем, в миллисекундах или секундах
                                            if date_raw > 1e10:  # Вероятно миллисекунды
                                                date = datetime.fromtimestamp(date_raw / 1000.0).isoformat()
                                            else:  # Секунды
                                                date = datetime.fromtimestamp(date_raw).isoformat()
                                        except Exception as e:
                                            print(f"⚠️ Error parsing timestamp {date_raw}: {e}")
                                    # Если это строка ISO формата
                                    elif isinstance(date_raw, str):
                                        try:
                                            # Убираем Z и заменяем на +00:00
                                            date_clean = date_raw.replace('Z', '+00:00')
                                            date = date_clean
                                        except:
                                            date = date_raw
                                
                                if not date:
                                    print(f"⚠️ DEBUG POSTS: No date found for item. Keys: {list(item.keys())}")
                                    if 'date' in item:
                                        print(f"   Date field content: {item['date']}")

                                post = {
                                    'title': item.get('title', ''),
                                    'text': item.get('text', item.get('content', item.get('message', ''))),
                                    'date': date,
                                    'url': item.get('url', '')
                                }
                                if post['text'] or post['title']:
                                    posts.append(post)
                
                for value in data.values():
                    find_posts(value)
            
            elif isinstance(data, list):
                for item in data:
                    find_posts(item)
        
        find_posts(json_data)
        if posts:
            print(f"✅ Извлечено {len(posts)} новостей/постов")
            # Логируем первую новость для отладки
            print(f"📰 Пример новости: {posts[0].get('title', '')[:50]}... ({posts[0].get('date', 'нет даты')})")
        return posts

    def _extract_photos_from_api(self, json_data: Any) -> List[Dict[str, Any]]:
        """Извлекает фото из getByBusinessId: {"data": [{url, id, ...}, ...]}"""
        photos = []
        arr = json_data.get("data") if isinstance(json_data, dict) else None
        if not isinstance(arr, list):
            return photos
        for item in arr:
            if not isinstance(item, dict):
                continue
            url_val = item.get("url") or item.get("urlTemplate") or item.get("href")
            if url_val:
                photos.append({"url": str(url_val), "id": item.get("id", "")})
        return photos

    def _extract_products_from_api(self, json_data: Any) -> List[Dict[str, Any]]:
        """Извлекает товары/услуги из API"""
        products = []
        
        def find_products(data):
            if isinstance(data, dict):
                # LOGGING: Print all keys if we suspect this dictates products but we missed it
                if any(k in data for k in ['data', 'result', 'search', 'goods', 'items']):
                    # Too verbose to print everything, just keys
                    pass 

                # Ищем список товаров
                # Ищем список товаров
                # Убрали 'features' (это свойства карты) и 'items' (слишком общее, часто это организации)
                # 'items' оставим, но с жесткой проверкой
                target_keys = ['goods', 'products', 'prices', 'searchResult', 'results', 'catalog', 'menu', 'services', 'items', 'categoryItems']
                
                for key in target_keys:
                    if key in data and isinstance(data[key], list):
                         if len(data[key]) > 0:
                            item0 = data[key][0]
                            if isinstance(item0, dict):
                                 # Debug log
                                 if any(k in item0 for k in ['name', 'title', 'price', 'text']):
                                     pass # print(f"🔍 DEBUG PRODUCTS: Found list in '{key}'...")
                        
                         for item in data[key]:
                            if isinstance(item, dict):
                                # 1. ПРОВЕРКА: Это товар или организация/фича?
                                # Организации обычно имеют ratingData, workingTime, geoId
                                if any(k in item for k in ['ratingData', 'workingTime', 'geoId', 'rubricId', 'stops']):
                                    continue
                                
                                # Фичи карты (features) часто имеют 'id', 'value', 'type', но не имеют price
                                if 'type' in item and 'value' in item and 'price' not in item:
                                    continue
                                
                                # Check if it's a product
                                name = item.get('name', item.get('title', ''))
                                
                                # Deep search for name if not found at top level
                                if not name and 'name' in item.get('data', {}):
                                    name = item.get('data', {}).get('name')

                                if not name:
                                    text_val = item.get('text', '')
                                    if text_val and len(text_val) < 100: 
                                         name = text_val
                                
                                if not name:
                                    continue
                                
                                # --- SEMI-STRICT PRICE CHECK ---
                                # Relaxed Rule (2026-01-30): Allow items without price IF they are not obvious map features.
                                # Previously we required price for 'items', 'searchResult', etc. to avoid "Toilets", "Entrances".
                                # Now we use a blacklist and name length check.
                                
                                has_price = False
                                price_val = ''
                                
                                price_obj = item.get('minPrice', {}) or item.get('price', {})
                                if isinstance(price_obj, dict):
                                     val = price_obj.get('value')
                                     text = price_obj.get('text')
                                     if val or text:
                                         has_price = True
                                         price_val = text or str(val)
                                elif 'price' in item:
                                     val = item['price']
                                     if val:
                                         has_price = True
                                         price_val = str(val)
                                
                                if key in ['items', 'searchResult', 'results', 'categoryItems'] and not has_price:
                                    # Check blacklist for common map features
                                    junk_terms = ['вход', 'туалет', 'парковка', 'банкомат', 'оплата', 'entrance', 'toilet', 'parking', 'atm', 'wc', 'этаж']
                                    name_lower = name.lower()
                                    
                                    # If name matches junk or is very short (likely not a service), skip
                                    is_junk = any(term in name_lower for term in junk_terms)
                                    if is_junk or len(name) < 3:
                                         continue
                                    
                                    # Otherwise, allow it (Oliver has services without prices)
                                    pass
                                
                                # Категория
                                category = ''
                                if isinstance(item.get('category'), dict):
                                    category = item.get('category').get('name', '')
                                else:
                                    category = str(item.get('category', ''))
                                
                                # Описание
                                description = item.get('description', '')
                                
                                # Фото
                                photo = ''
                                if isinstance(item.get('image'), dict):
                                    photo = item.get('image').get('url', '')
                                elif isinstance(item.get('photos'), list) and len(item['photos']) > 0:
                                     photo = item['photos'][0].get('urlTemplate', '')

                                products.append({
                                    'name': name,
                                    'price': price_val,
                                    'description': description,
                                    'category': category,
                                    'photo': photo
                                })
                
                # Рекурсивный поиск
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        find_products(value)
            
            elif isinstance(data, list):
                for item in data:
                    find_products(item)
                    
        find_products(json_data)
        if len(products) > 0:
            print(f"📦 DEBUG PRODUCTS: Extracted {len(products)} total items")
        return products
    
    def _fallback_html_parsing(self, page, url: str) -> Dict[str, Any]:
        """Fallback на HTML парсинг, если API не сработал"""
        print("🔄 Используем fallback HTML парсинг...")
        
        # Импортируем функции из оригинального парсера
        try:
            from yandex_maps_scraper import parse_overview_data, parse_reviews, parse_news, parse_photos, get_photos_count, parse_features, parse_competitors, parse_products
            
            data = parse_overview_data(page)
            data['url'] = url
            
            reviews_data = parse_reviews(page)
            data['reviews'] = reviews_data.get('items', [])
            data['news'] = parse_news(page)
            data['photos_count'] = get_photos_count(page)
            data['photos'] = parse_photos(page)
            data['features_full'] = parse_features(page)
            data['competitors'] = parse_competitors(page)
            data['products'] = parse_products(page)
            
            overview_keys = [
                'title', 'address', 'phone', 'site', 'description',
                'rubric', 'categories', 'hours', 'hours_full', 'rating', 
                'ratings_count', 'reviews_count', 'social_links'
            ]
            data['overview'] = {k: data.get(k, '') for k in overview_keys}
            data['overview']['reviews_count'] = data.get('reviews_count', '')
            
            return data
        except Exception as e:
            print(f"❌ Ошибка при fallback парсинге: {e}")
            return {'error': str(e), 'url': url}


def parse_yandex_card(
    url: str,
    keep_open_on_captcha: bool = False,
    session_registry: Optional[Dict[str, BrowserSession]] = None,
    session_id: Optional[str] = None,
    debug_bundle_id: Optional[str] = None,
    **session_kwargs: Any,
) -> Dict[str, Any]:
    """
    Оркестратор для парсинга Яндекс.Карт c поддержкой human-in-the-loop.

    - управляет жизненным циклом BrowserSession через BrowserSessionManager
    - сам парсер работает только с готовой сессией (session.page/session.context)
    """
    manager = BrowserSessionManager()
    session: Optional[BrowserSession] = None

    # Валидация разрешённых kwargs для сессии
    unknown = set(session_kwargs.keys()) - ALLOWED_SESSION_KWARGS
    if unknown:
        msg = f"Unknown session kwargs in parse_yandex_card: {unknown}"
        env = os.getenv("FLASK_ENV", "").lower()
        is_debug_env = env in ("development", "dev", "debug", "test", "testing")
        if is_debug_env:
            raise ValueError(msg)
        else:
            print(f"⚠️ {msg}")
            # В production — просто отбрасываем неизвестные ключи
            for k in list(unknown):
                session_kwargs.pop(k, None)

    # 1. Режим resume: берём сессию из registry по session_id
    if session_id and session_registry is not None:
        session = manager.get(session_registry, session_id)
        if session is None:
            return {
                "error": "captcha_session_lost",
                "captcha_session_id": session_id,
            }
    else:
        # 2. Первый заход: открываем новую сессию
        session = manager.open_session(
            headless=session_kwargs.get("headless", True),
            cookies=session_kwargs.get("cookies"),
            user_agent=session_kwargs.get("user_agent"),
            viewport=session_kwargs.get("viewport"),
            locale=session_kwargs.get("locale", "ru-RU"),
            timezone_id=session_kwargs.get("timezone_id", "Europe/Moscow"),
            proxy=session_kwargs.get("proxy"),
            launch_args=session_kwargs.get("launch_args"),
            init_scripts=session_kwargs.get("init_scripts"),
            keep_open=keep_open_on_captcha,
            geolocation=session_kwargs.get("geolocation"),
        )

    parser = YandexMapsInterceptionParser(debug_bundle_id=debug_bundle_id)

    result: Dict[str, Any]
    try:
        result = parser.parse_yandex_card(url, session=session)
    except Exception:
        # При любой ошибке — всегда закрываем сессию (она больше не пригодна)
        if session:
            manager.close_session(session)
            if session_registry is not None and session_id:
                session_registry.pop(session_id, None)
        raise

    # Капча + human-in-the-loop
    if isinstance(result, dict) and result.get("error") == "captcha_detected":
        # Если можно держать сессию открытой и есть registry — паркуем
        if keep_open_on_captcha and session_registry is not None and session:
            parked_id = manager.park(session_registry, session)
            result["captcha_session_id"] = parked_id
            result["captcha_needs_human"] = True
            return result

        # Иначе: некуда парковать — закрываем сессию, но помечаем, что нужен человек
        if session:
            manager.close_session(session)
            if session_registry is not None and session_id:
                session_registry.pop(session_id, None)
        result["captcha_needs_human"] = True
        return result

    # Обычный кейс: сессию всегда закрываем
    if session:
        manager.close_session(session)
        # Если это resume — чистим registry
        if session_registry is not None and session_id:
            session_registry.pop(session_id, None)

    return result


if __name__ == "__main__":
    # Тестирование
    test_url = "https://yandex.ru/maps/org/gagarin/180566191872/"
    result = parse_yandex_card(test_url)
    print("\n📊 Результат парсинга:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
