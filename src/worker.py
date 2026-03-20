import time
import uuid
import json
import re
import os
import traceback
from datetime import datetime, timedelta
import signal
import sys
import multiprocessing
import asyncio
import random
from typing import Dict, List, Any, Optional
from urllib import request as urllib_request, error as urllib_error
from dotenv import load_dotenv

from browser_session import BrowserSession, BrowserSessionManager
from parser_config_cookies import get_yandex_cookies

load_dotenv()

# New imports
from database_manager import DatabaseManager
from parsequeue_status import (
    STATUS_CAPTCHA,
    STATUS_COMPLETED,
    STATUS_ERROR,
    STATUS_PENDING,
    STATUS_PAUSED,
    STATUS_PROCESSING,
)
from yandex_business_sync_worker import YandexBusinessSyncWorker
from external_sources import ExternalReview, ExternalSource, ExternalPost, ExternalStatsPoint, make_stats_id
from dateutil import parser as date_parser
from parsed_payload_validation import (
    build_parsing_meta,
    FIELDS_CRITICAL,
    SOURCE_YANDEX_BUSINESS,
)
from parsing_failure_taxonomy import with_reason_code_prefix
from core.action_orchestrator import ActionOrchestrator
from yookassa_integration import run_due_renewals
from api.admin_prospecting import dispatch_due_outreach_queue

# Реестр активных Playwright-сессий для human-in-the-loop
ACTIVE_CAPTCHA_SESSIONS: Dict[str, BrowserSession] = {}
BROWSER_SESSION_MANAGER = BrowserSessionManager()
CAPTCHA_TTL_MINUTES = 30
CALLBACK_DISPATCH_ORCHESTRATOR = ActionOrchestrator(handlers={})
_LAST_CALLBACK_DISPATCH_AT = 0.0
_LAST_BILLING_RECONCILE_AT = 0.0
_LAST_BILLING_ALERT_BY_TENANT: Dict[str, float] = {}
_LAST_CALLBACK_ALERT_BY_TENANT: Dict[str, float] = {}
_LAST_CALLBACK_ALERT_SCAN_AT = 0.0
_LAST_YOOKASSA_RENEWALS_AT = 0.0
_LAST_OUTREACH_DISPATCH_AT = 0.0

_EDITORIAL_SERVICE_PATTERNS = (
    "хорошее место",
    "где можно",
    "выбрали места",
    "рассказываем про",
    "собрали в одном месте",
    "собрали в одном месте салоны",
    "собрали в одном месте бары",
    "подборка",
    "популярных салонов красоты",
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

_SERVICE_NOISE_TERMS = (
    "вход",
    "туалет",
    "парковка",
    "банкомат",
    "этаж",
    "лифт",
    "остановка",
    "подъезд",
    "navigation",
    "entrance",
    "toilet",
    "parking",
    "atm",
    "wc",
    "floor",
)

_GENERIC_SERVICE_CATEGORIES = {
    "другое",
    "разное",
    "other",
    "общие услуги",
    "без категории",
    "услуги",
    "товары",
    "категория",
}

_HUMAN_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
)

_HUMAN_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
try { delete navigator.__proto__.webdriver; } catch (e) {}
Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US'] });
Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
window.chrome = window.chrome || { runtime: {} };
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters && parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : originalQuery(parameters)
  );
}
"""


def _captcha_retry_attempt_from_error(error_message: Any) -> int:
    text = str(error_message or "")
    match = re.search(r"captcha_auto_retry_attempt=(\d+)", text)
    if not match:
        return 0
    try:
        return max(0, int(match.group(1)))
    except (TypeError, ValueError):
        return 0


def _captcha_next_retry_delay(attempt_no: int) -> timedelta:
    base_minutes = max(1, int(os.getenv("CAPTCHA_AUTO_RETRY_BASE_MINUTES", "5")))
    max_minutes = max(base_minutes, int(os.getenv("CAPTCHA_AUTO_RETRY_MAX_MINUTES", "45")))
    jitter_seconds = max(0, int(os.getenv("CAPTCHA_AUTO_RETRY_JITTER_SECONDS", "45")))
    exp_minutes = min(max_minutes, base_minutes * (2 ** max(0, attempt_no - 1)))
    jitter = random.randint(0, jitter_seconds) if jitter_seconds else 0
    return timedelta(minutes=exp_minutes, seconds=jitter)


def _is_mass_network_task(queue_dict: Dict[str, Any]) -> bool:
    batch_id = str(queue_dict.get("batch_id") or "").strip()
    batch_kind = str(queue_dict.get("batch_kind") or "").strip().lower()
    return bool(batch_id and batch_kind == "network_sync")


def _captcha_retry_delay_for_task(queue_dict: Dict[str, Any], attempt_no: int) -> timedelta:
    if _is_mass_network_task(queue_dict):
        pause_minutes = max(5, int(os.getenv("CAPTCHA_BATCH_PAUSE_MINUTES", "30")))
        return timedelta(minutes=pause_minutes)
    return _captcha_next_retry_delay(attempt_no)


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _task_age_hours(queue_dict: Dict[str, Any]) -> float:
    created_at_dt = _to_datetime(queue_dict.get("created_at"))
    if not created_at_dt:
        return 0.0
    age_seconds = (datetime.now() - created_at_dt).total_seconds()
    if age_seconds <= 0:
        return 0.0
    return age_seconds / 3600.0


def _move_task_to_dlq(task_id: str, dlq_reason: str, details: str, *, clear_captcha_fields: bool = False) -> None:
    base_message = f"dlq_reason={dlq_reason}; {details}"
    normalized_message = with_reason_code_prefix(STATUS_ERROR, base_message)
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if clear_captcha_fields:
            cursor.execute(
                """
                UPDATE parsequeue
                SET status = %s,
                    error_message = %s,
                    retry_after = NULL,
                    captcha_required = 0,
                    captcha_url = NULL,
                    captcha_session_id = NULL,
                    captcha_started_at = NULL,
                    resume_requested = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (STATUS_ERROR, normalized_message, task_id),
            )
        else:
            cursor.execute(
                """
                UPDATE parsequeue
                SET status = %s,
                    error_message = %s,
                    retry_after = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (STATUS_ERROR, normalized_message, task_id),
            )
        conn.commit()
    except Exception as e:
        print(f"⚠️ Не удалось перевести задачу {task_id} в DLQ: {e}", flush=True)
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _build_human_browser_profile() -> Dict[str, Any]:
    width = random.randint(1366, 1920)
    height = random.randint(768, 1200)
    return {
        "user_agent": random.choice(_HUMAN_USER_AGENTS),
        "viewport": {"width": width, "height": height},
        "launch_args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
            "--ignore-certificate-errors",
            "--allow-insecure-localhost",
            "--lang=ru-RU,ru",
            "--window-position=0,0",
        ],
        "init_scripts": [_HUMAN_INIT_SCRIPT],
    }


def _pick_proxy_country_code() -> str:
    """
    Возвращает 2-буквенный country-код для BrightData (или '' для base режима).
    Приоритет:
      1) PROXY_COUNTRY_ROTATION (CSV: kz,am,ge,base)
      2) PROXY_FORCE_COUNTRY
    """
    raw_rotation = str(os.getenv("PROXY_COUNTRY_ROTATION", "") or "").strip()
    if raw_rotation:
        items = [str(x).strip().lower() for x in raw_rotation.split(",")]
        normalized: List[str] = []
        for item in items:
            if not item:
                continue
            if item in ("base", "none", "off", "auto"):
                normalized.append("")
                continue
            if len(item) == 2 and item.isalpha():
                normalized.append(item)
        if normalized:
            return random.choice(normalized)

    forced_country = str(os.getenv("PROXY_FORCE_COUNTRY", "") or "").strip().lower()
    if len(forced_country) == 2 and forced_country.isalpha():
        return forced_country
    return ""


def _get_next_proxy_for_playwright() -> Optional[Dict[str, Any]]:
    """
    Возвращает активный рабочий прокси в формате Playwright:
    {"id": "...", "host": "...", "port": 33335, "proxy": {"server": "...", "username": "...", "password": "..."}}
    """
    conn = None
    cursor = None
    try:
        if not _env_bool("PARSING_USE_PROXY_POOL", True):
            return None
        min_health_score_raw = os.getenv("PROXY_MIN_HEALTH_SCORE", "0.25")
        try:
            min_health_score = float(min_health_score_raw)
        except (TypeError, ValueError):
            min_health_score = 0.25
        min_health_score = max(0.0, min(0.99, min_health_score))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, proxy_type, host, port, username, password
            FROM proxyservers
            WHERE is_active = TRUE AND is_working = TRUE
              AND (
                    (COALESCE(success_count, 0) + COALESCE(failure_count, 0)) < 8
                 OR ((COALESCE(success_count, 0) + 1.0) / (COALESCE(success_count, 0) + COALESCE(failure_count, 0) + 2.0)) >= %s
              )
            ORDER BY
                ((COALESCE(success_count, 0) + 1.0) / (COALESCE(success_count, 0) + COALESCE(failure_count, 0) + 2.0)) DESC,
                COALESCE(success_count, 0) DESC,
                CASE WHEN last_checked_at IS NULL THEN 1 ELSE 0 END,
                last_checked_at DESC,
                CASE WHEN last_used_at IS NULL THEN 0 ELSE 1 END,
                last_used_at ASC,
                RANDOM()
            LIMIT 1
            """,
            (min_health_score,),
        )
        row = cursor.fetchone()
        if not row:
            # Self-healing fallback: если нет "рабочих", пробуем активный прокси
            # (часто помогает при ротируемых residential зонах).
            cursor.execute(
                """
                SELECT id, proxy_type, host, port, username, password
                FROM proxyservers
                WHERE is_active = TRUE
                  AND (
                        (COALESCE(success_count, 0) + COALESCE(failure_count, 0)) < 8
                     OR ((COALESCE(success_count, 0) + 1.0) / (COALESCE(success_count, 0) + COALESCE(failure_count, 0) + 2.0)) >= %s
                  )
                ORDER BY
                    ((COALESCE(success_count, 0) + 1.0) / (COALESCE(success_count, 0) + COALESCE(failure_count, 0) + 2.0)) DESC,
                    COALESCE(success_count, 0) DESC,
                    CASE WHEN last_checked_at IS NULL THEN 1 ELSE 0 END,
                    last_checked_at DESC,
                    CASE WHEN last_used_at IS NULL THEN 0 ELSE 1 END,
                    last_used_at ASC,
                    RANDOM()
                LIMIT 1
                """,
                (min_health_score,),
            )
            row = cursor.fetchone()
        if not row:
            # Последний fallback: если health-gate отфильтровал всех,
            # берём любой активный прокси, чтобы не останавливать пайплайн.
            cursor.execute(
                """
                SELECT id, proxy_type, host, port, username, password
                FROM proxyservers
                WHERE is_active = TRUE
                ORDER BY
                    CASE WHEN last_used_at IS NULL THEN 0 ELSE 1 END,
                    last_used_at ASC,
                    RANDOM()
                LIMIT 1
                """
            )
            row = cursor.fetchone()
        if not row:
            return None

        if isinstance(row, dict):
            proxy_id = str(row.get("id") or "").strip()
            proxy_type = str(row.get("proxy_type") or "http").strip().lower() or "http"
            host = str(row.get("host") or "").strip()
            port = int(row.get("port") or 0)
            username = str(row.get("username") or "").strip()
            password = str(row.get("password") or "").strip()
        else:
            proxy_id, proxy_type, host, port, username, password = row
            proxy_id = str(proxy_id or "").strip()
            proxy_type = str(proxy_type or "http").strip().lower() or "http"
            host = str(host or "").strip()
            port = int(port or 0)
            username = str(username or "").strip()
            password = str(password or "").strip()

        if not proxy_id or not host or not port:
            return None

        cursor.execute(
            """
            UPDATE proxyservers
            SET last_used_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (proxy_id,),
        )
        conn.commit()

        proxy_payload: Dict[str, Any] = {"server": f"{proxy_type}://{host}:{port}"}
        selected_country_code = ""
        if username and password:
            username_effective = username
            # BrightData: добавляем ротацию сессии, чтобы снизить CAPTCHA/блокировки
            # и не залипать на одном egress-IP.
            if "brd-customer-" in username and "-session-" not in username:
                session_suffix = f"{int(time.time())}{random.randint(100000, 999999)}"
                username_effective = f"{username}-session-{session_suffix}"
                country_code = _pick_proxy_country_code()
                if country_code and f"-country-{country_code}" not in username_effective:
                    username_effective = f"{username_effective}-country-{country_code}"
                    selected_country_code = country_code
                else:
                    selected_country_code = ""

            proxy_payload["username"] = username_effective
            proxy_payload["password"] = password

        return {
            "id": proxy_id,
            "host": host,
            "port": port,
            "proxy": proxy_payload,
            "country_code": selected_country_code,
        }
    except Exception as e:
        print(f"⚠️ Не удалось получить прокси из proxyservers: {e}", flush=True)
        return None
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _mark_proxy_result(proxy_id: Optional[str], *, success: bool, reason: str = "") -> None:
    if not proxy_id:
        return
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if success:
            cursor.execute(
                """
                UPDATE proxyservers
                SET success_count = COALESCE(success_count, 0) + 1,
                    is_working = TRUE,
                    last_checked_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (proxy_id,),
            )
        else:
            reason_lc = str(reason or "").lower()
            fatal_proxy_reason = any(
                token in reason_lc
                for token in (
                    "err_cert_authority_invalid",
                    "proxy authentication",
                    "net::err_tunnel_connection_failed",
                    "net::err_proxy_connection_failed",
                    "timeout 30000ms exceeded",
                    "navigation timeout",
                    "err_timed_out",
                    "407",
                    "forbidden",
                )
            )
            cursor.execute(
                """
                UPDATE proxyservers
                SET failure_count = COALESCE(failure_count, 0) + 1,
                    is_working = CASE
                        WHEN %s THEN FALSE
                        ELSE is_working
                    END,
                    last_checked_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (fatal_proxy_reason, proxy_id),
            )
        conn.commit()
    except Exception as e:
        print(f"⚠️ Не удалось обновить статистику прокси {proxy_id}: {e}; reason={reason}", flush=True)
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _parse_retry_after(value: Any) -> Optional[datetime]:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _is_proxy_transport_error(message: str) -> bool:
    text = str(message or "").lower()
    return any(
        token in text
        for token in (
            "err_cert_authority_invalid",
            "err_tunnel_connection_failed",
            "err_proxy_connection_failed",
            "proxy authentication",
            "proxyerror",
            "proxy connection",
            "certificate",
            "ssl",
            "tls",
        )
    )


def _is_empty_payload_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _first_nested_non_empty(node: Any, keys: List[str], max_depth: int = 6) -> Any:
    if max_depth < 0:
        return None

    if isinstance(node, dict):
        for key in keys:
            value = node.get(key)
            if not _is_empty_payload_value(value):
                return value
        for value in node.values():
            nested = _first_nested_non_empty(value, keys, max_depth - 1)
            if not _is_empty_payload_value(nested):
                return nested
        return None

    if isinstance(node, list):
        for value in node:
            nested = _first_nested_non_empty(value, keys, max_depth - 1)
            if not _is_empty_payload_value(nested):
                return nested
        return None

    return None


def _promote_nested_card_payload(card_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(card_data, dict):
        return card_data

    source_nodes: List[Dict[str, Any]] = []
    for key in ("data", "payload", "result"):
        value = card_data.get(key)
        if isinstance(value, dict):
            source_nodes.append(value)

    for root in list(source_nodes):
        for nested_key in ("data", "payload", "result", "company", "organization", "org", "card"):
            nested = root.get(nested_key)
            if isinstance(nested, dict):
                source_nodes.append(nested)

    promoted_fields = (
        "title",
        "name",
        "address",
        "phone",
        "site",
        "website",
        "description",
        "rating",
        "ratings_count",
        "reviews_count",
        "categories",
        "rubric",
        "hours",
        "hours_full",
        "reviews",
        "products",
        "news",
        "photos",
        "page_title",
        "og_title",
    )

    for source in source_nodes:
        for field in promoted_fields:
            if _is_empty_payload_value(card_data.get(field)) and not _is_empty_payload_value(source.get(field)):
                card_data[field] = source.get(field)

    overview = card_data.get("overview")
    if not isinstance(overview, dict):
        overview = {}
    for source in source_nodes:
        source_overview = source.get("overview")
        if isinstance(source_overview, dict):
            for key, value in source_overview.items():
                if _is_empty_payload_value(overview.get(key)) and not _is_empty_payload_value(value):
                    overview[key] = value
    if overview:
        card_data["overview"] = overview

    if _is_empty_payload_value(card_data.get("title")):
        card_data["title"] = _first_nested_non_empty(card_data, ["title", "name", "organizationName", "companyName"])
    if _is_empty_payload_value(card_data.get("address")):
        card_data["address"] = _first_nested_non_empty(
            card_data,
            ["address", "address_name", "fullAddress", "full_address", "formattedAddress"],
        )
    if _is_empty_payload_value(card_data.get("rating")):
        card_data["rating"] = _first_nested_non_empty(card_data, ["rating", "score", "value"])
    if _is_empty_payload_value(card_data.get("reviews_count")):
        card_data["reviews_count"] = _first_nested_non_empty(
            card_data,
            ["reviews_count", "reviewsCount", "ratings_count", "ratingCount", "count"],
        )
    if _is_empty_payload_value(card_data.get("categories")):
        card_data["categories"] = _first_nested_non_empty(
            card_data,
            ["categories", "rubrics", "rubric", "category", "category_name"],
        )

    if _is_empty_payload_value(card_data.get("title_or_name")):
        og_raw = str(card_data.get("og_title") or "").strip()
        og_clean = ""
        if og_raw:
            og_clean = (
                og_raw.replace(" — Яндекс Карты", "")
                .replace(" - Яндекс Карты", "")
                .split("|")[0]
                .split(",")[0]
                .strip()
            )

        overview_title = ""
        if isinstance(card_data.get("overview"), dict):
            overview_title = str(card_data.get("overview", {}).get("title") or "").strip()

        page_title = str(card_data.get("page_title") or "").strip()
        if page_title:
            page_title = (
                page_title.replace(" — Яндекс Карты", "")
                .replace(" - Яндекс Карты", "")
                .split("|")[0]
                .strip()
            )

        for candidate in (
            str(card_data.get("title") or "").strip(),
            str(card_data.get("name") or "").strip(),
            overview_title,
            page_title,
            og_clean,
            str(_first_nested_non_empty(card_data, ["title", "name", "organizationName", "companyName"]) or "").strip(),
        ):
            if candidate:
                card_data["title_or_name"] = candidate
                if _is_empty_payload_value(card_data.get("title")):
                    card_data["title"] = candidate
                if isinstance(card_data.get("overview"), dict) and _is_empty_payload_value(card_data["overview"].get("title")):
                    card_data["overview"]["title"] = candidate
                break

    return card_data


def _apply_business_identity_fallback(
    card_data: Dict[str, Any],
    *,
    business_name: str,
    business_address: str,
) -> bool:
    if not isinstance(card_data, dict):
        return False

    used = False
    title_candidate = str(business_name or "").strip()
    address_candidate = str(business_address or "").strip()

    if _is_empty_payload_value(card_data.get("title_or_name")) and title_candidate:
        card_data["title_or_name"] = title_candidate
        used = True

    if _is_empty_payload_value(card_data.get("title")) and title_candidate:
        card_data["title"] = title_candidate
        used = True

    if _is_empty_payload_value(card_data.get("address")) and address_candidate:
        card_data["address"] = address_candidate
        used = True

    if used:
        warnings = card_data.get("warnings")
        if not isinstance(warnings, list):
            warnings = []
            card_data["warnings"] = warnings
        marker = "identity_fallback:business_record"
        if marker not in warnings:
            warnings.append(marker)

    return used


def _load_business_identity_for_fallback(business_id: Any) -> Dict[str, str]:
    business_id_text = str(business_id or "").strip()
    if not business_id_text:
        return {"name": "", "address": ""}

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, address FROM businesses WHERE id = %s", (business_id_text,))
        row = cursor.fetchone()
        if not row:
            return {"name": "", "address": ""}
        if isinstance(row, (list, tuple)):
            return {"name": str(row[0] or "").strip(), "address": str(row[1] or "").strip()}
        return {"name": str(row.get("name") or "").strip(), "address": str(row.get("address") or "").strip()}
    except Exception as e:
        print(f"⚠️ Не удалось загрузить fallback identity для business_id={business_id_text}: {e}", flush=True)
        return {"name": "", "address": ""}
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _parse_yandex_card_subprocess_entry(result_queue: Any, url: str, kwargs: Dict[str, Any]) -> None:
    """Изолированный запуск sync Playwright в отдельном процессе."""
    try:
        from parser_config import parse_yandex_card as subprocess_parse_yandex_card

        result = subprocess_parse_yandex_card(url, **kwargs)
        if result is None:
            result_queue.put({"error": "parser_returned_none", "url": url})
        elif not isinstance(result, dict):
            result_queue.put({"error": f"parser_returned_{type(result).__name__}", "url": url})
        else:
            result_queue.put(result)
    except Exception as exc:
        result_queue.put(
            {
                "error": "parser_subprocess_exception",
                "message": str(exc),
                "traceback": traceback.format_exc(),
                "url": url,
            }
        )


def _is_playwright_sync_in_async_error(message: str) -> bool:
    msg = (message or "").strip().lower()
    return "playwright sync api inside the asyncio loop" in msg


def _normalize_yandex_org_url(raw_url: str) -> str:
    text = str(raw_url or "").strip()
    if not text:
        return text
    match = re.search(r"/org/(?:[^/]+/)?(\d+)", text)
    if not match:
        return text
    org_id = match.group(1)
    # Канонический URL парсинга: ru-домен + org/<id>, без лишних query параметров.
    return f"https://yandex.ru/maps/org/{org_id}/"


def _detect_map_source(queue_dict: Dict[str, Any], url: str) -> str:
    source_hint = str(queue_dict.get("source") or "").strip().lower()
    if source_hint in {"2gis", "two_gis"}:
        return "2gis"
    url_lower = str(url or "").strip().lower()
    if "2gis.ru/" in url_lower or "2gis.com/" in url_lower:
        return "2gis"
    return "yandex_maps"


def _has_running_asyncio_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _parse_yandex_card_with_playwright_fallback(
    url: str,
    *,
    keep_open_on_captcha: bool,
    session_registry: Optional[Dict[str, BrowserSession]] = None,
    session_id: Optional[str] = None,
    timeout_sec: int = 600,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Основной вызов парсера.

    Если sync Playwright падает из-за активного asyncio loop, повторяем парсинг
    в отдельном процессе. Для subprocess fallback не паркуем живую CAPTCHA-сессию.
    """
    force_subprocess = False
    # По умолчанию сначала пробуем обычный sync путь.
    # Subprocess fallback используем только при реальной ошибке sync-in-async
    # (или при явном флаге окружения).
    if _env_bool("PLAYWRIGHT_FORCE_SUBPROCESS_ON_ASYNC_LOOP", False) and _has_running_asyncio_loop():
        force_subprocess = True
        if keep_open_on_captcha:
            # parked session нельзя перенести между процессами.
            keep_open_on_captcha = False
            session_registry = None
            session_id = None

    try:
        if force_subprocess:
            raise RuntimeError("Playwright Sync API inside the asyncio loop (pre-detected)")
        return parse_yandex_card(
            url,
            keep_open_on_captcha=keep_open_on_captcha,
            session_registry=session_registry,
            session_id=session_id,
            **kwargs,
        )
    except Exception as exc:
        msg = str(exc)
        if not _is_playwright_sync_in_async_error(msg):
            raise

        if session_id:
            # Resume по существующей parked session должен выполняться в обычном path.
            # Если сюда дошли — это уже другой сбой, подменять path нельзя.
            raise

        subprocess_kwargs = dict(kwargs)
        ctx = multiprocessing.get_context("fork")
        result_queue = ctx.Queue(maxsize=1)
        proc = ctx.Process(
            target=_parse_yandex_card_subprocess_entry,
            args=(result_queue, url, subprocess_kwargs),
            daemon=True,
        )
        proc.start()
        proc.join(timeout_sec)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            return {
                "error": "parser_subprocess_timeout",
                "message": f"parse_yandex_card subprocess timeout after {timeout_sec}s",
                "url": url,
            }

        if result_queue.empty():
            return {
                "error": "parser_subprocess_no_result",
                "message": "parse_yandex_card subprocess finished without payload",
                "url": url,
            }

        result = result_queue.get()
        if isinstance(result, dict):
            result.setdefault("_playwright_fallback", "subprocess")
            return result
        return {"error": "parser_subprocess_invalid_result", "url": url}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _run_yookassa_renewals_if_due() -> None:
    global _LAST_YOOKASSA_RENEWALS_AT
    if not _env_bool("YOOKASSA_RENEWALS_ENABLED", False):
        return

    now = time.time()
    interval_sec = max(30, int(os.getenv("YOOKASSA_RENEWALS_INTERVAL_SEC", "300")))
    if now - _LAST_YOOKASSA_RENEWALS_AT < interval_sec:
        return

    _LAST_YOOKASSA_RENEWALS_AT = now
    try:
        batch_size = max(1, min(int(os.getenv("YOOKASSA_RENEWALS_BATCH_SIZE", "25")), 200))
        result = run_due_renewals(batch_size=batch_size)
        if result.get("success") and int(result.get("scheduled") or 0) > 0:
            print(
                f"[YOOKASSA_RENEWALS] processed={result.get('processed')} "
                f"scheduled={result.get('scheduled')} errors={result.get('errors')}",
                flush=True,
            )
        elif not result.get("success"):
            print(f"[YOOKASSA_RENEWALS] error: {result.get('error')}", flush=True)
    except Exception as e:
        print(f"[YOOKASSA_RENEWALS] unexpected error: {e}", flush=True)


def _dispatch_outreach_queue_if_due() -> None:
    global _LAST_OUTREACH_DISPATCH_AT
    if not _env_bool("OUTREACH_DISPATCH_ENABLED", True):
        return

    now = time.time()
    interval_sec = max(5, int(os.getenv("OUTREACH_DISPATCH_INTERVAL_SEC", "30")))
    if now - _LAST_OUTREACH_DISPATCH_AT < interval_sec:
        return

    _LAST_OUTREACH_DISPATCH_AT = now
    try:
        batch_size = max(1, min(int(os.getenv("OUTREACH_DISPATCH_BATCH_SIZE", "20")), 200))
        result = dispatch_due_outreach_queue(batch_size=batch_size)
        picked = int(result.get("picked") or 0)
        if picked > 0:
            print(
                "[OUTREACH_DISPATCH] "
                f"picked={picked} sent={int(result.get('sent') or 0)} "
                f"delivered={int(result.get('delivered') or 0)} "
                f"retry={int(result.get('retry') or 0)} dlq={int(result.get('dlq') or 0)} "
                f"failed={int(result.get('failed') or 0)}",
                flush=True,
            )
    except Exception as e:
        print(f"[OUTREACH_DISPATCH] error: {e}", flush=True)


def _dispatch_openclaw_callback_outbox_if_due() -> None:
    global _LAST_CALLBACK_DISPATCH_AT
    if not _env_bool("OPENCLAW_CALLBACK_DISPATCH_ENABLED", True):
        return

    now = time.time()
    interval_sec = max(1, int(os.getenv("OPENCLAW_CALLBACK_DISPATCH_INTERVAL_SEC", "15")))
    if now - _LAST_CALLBACK_DISPATCH_AT < interval_sec:
        return

    batch_size = max(1, min(int(os.getenv("OPENCLAW_CALLBACK_DISPATCH_BATCH_SIZE", "50")), 500))
    _LAST_CALLBACK_DISPATCH_AT = now
    try:
        result = CALLBACK_DISPATCH_ORCHESTRATOR.dispatch_callback_outbox(batch_size=batch_size)
        if int(result.get("picked") or 0) > 0 or int(result.get("retried") or 0) > 0 or int(result.get("dlq") or 0) > 0:
            print(
                f"[CALLBACK_DISPATCH] picked={result.get('picked')} sent={result.get('sent')} retried={result.get('retried')} dlq={result.get('dlq')}",
                flush=True,
            )
    except Exception as e:
        print(f"[CALLBACK_DISPATCH] error: {e}", flush=True)


def _send_telegram_plain_message(chat_id: str, text: str) -> bool:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = str(chat_id or "").strip()
    if not token or not chat_id:
        return False
    try:
        payload = json.dumps(
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        req = urllib_request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=10) as resp:
            return 200 <= int(getattr(resp, "status", 500)) < 300
    except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError) as e:
        print(f"[BILLING_RECONCILE] telegram send failed chat_id={chat_id}: {e}", flush=True)
        return False
    except Exception as e:
        print(f"[BILLING_RECONCILE] telegram unexpected error chat_id={chat_id}: {e}", flush=True)
        return False


def _incident_snapshot_lines(snapshot: Dict[str, Any]) -> List[str]:
    if not snapshot or not snapshot.get("success"):
        return []

    action_id = str(snapshot.get("action_id") or "")
    capability = str(snapshot.get("capability") or "-")
    status = str(snapshot.get("status") or "-")
    overview = dict(snapshot.get("overview") or {})
    lifecycle = dict((snapshot.get("lifecycle_summary") or {}).get("lifecycle") or {})
    recent = list(snapshot.get("recent_timeline") or [])

    lines = [
        f"Action: {action_id[:8] if action_id else '-'}",
        f"Capability/status: {capability} / {status}",
        (
            "Attempts: "
            f"{int(overview.get('callback_attempts_total') or 0)} total, "
            f"{int(overview.get('callback_attempts_failed') or 0)} failed"
        ),
        (
            "Lifecycle: "
            f"pending={int((lifecycle.get('pending_human') or {}).get('count') or 0)}, "
            f"approved={int((lifecycle.get('approved') or {}).get('count') or 0)}, "
            f"completed={int((lifecycle.get('completed') or {}).get('count') or 0)}"
        ),
    ]
    if recent:
        last_event = dict(recent[-1] or {})
        lines.append(
            "Last event: "
            f"{str(last_event.get('source') or '-')}/"
            f"{str(last_event.get('event_type') or '-')}/"
            f"{str(last_event.get('status') or '-')}"
        )
    return lines


def _load_incident_snapshots_for_actions(action_ids: List[str]) -> List[Dict[str, Any]]:
    snapshots: List[Dict[str, Any]] = []
    seen: set[str] = set()
    max_items = max(1, min(int(os.getenv("OPENCLAW_TELEGRAM_ALERT_SNAPSHOT_LIMIT", "2")), 5))
    for action_id in action_ids:
        normalized = str(action_id or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        try:
            result = CALLBACK_DISPATCH_ORCHESTRATOR.get_action_incident_snapshot(
                normalized,
                {"user_id": "system-worker", "is_superadmin": True},
            )
            if result.get("success"):
                snapshots.append(result)
        except Exception as e:
            print(f"[OPENCLAW_ALERTS] incident snapshot load failed action={normalized}: {e}", flush=True)
        if len(snapshots) >= max_items:
            break
    return snapshots


def _load_problematic_action_ids_for_tenant(tenant_id: str, *, limit: int = 2) -> List[str]:
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT action_id
            FROM action_callback_outbox
            WHERE tenant_id = %s
              AND status IN ('dlq', 'retry')
            ORDER BY
              CASE WHEN status = 'dlq' THEN 0 ELSE 1 END,
              updated_at DESC,
              created_at DESC
            LIMIT %s
            """,
            (str(tenant_id), max(1, min(int(limit or 2), 5))),
        )
        rows = cursor.fetchall() or []
        action_ids: List[str] = []
        for row in rows:
            if isinstance(row, dict):
                value = row.get("action_id")
            else:
                value = row[0] if len(row) > 0 else None
            if value:
                action_ids.append(str(value))
        return action_ids
    except Exception as e:
        print(f"[CALLBACK_ALERTS] problematic action scan failed tenant={tenant_id}: {e}", flush=True)
        return []
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _build_support_bundle_digest_lines(
    tenant_id: str,
    *,
    callback_metrics: Optional[Dict[str, Any]] = None,
    alerts: Optional[List[Dict[str, Any]]] = None,
    billing_summary: Optional[Dict[str, Any]] = None,
    action_ids: Optional[List[str]] = None,
) -> List[str]:
    metrics_payload: Dict[str, Any] = {}
    if callback_metrics:
        metrics_payload = {"success": True, "metrics": callback_metrics, "alerts": alerts or []}
    else:
        try:
            metrics_payload = CALLBACK_DISPATCH_ORCHESTRATOR.get_callback_metrics(
                {"user_id": "system-worker", "is_superadmin": True},
                tenant_id=str(tenant_id),
                window_minutes=60,
            )
        except Exception as e:
            print(f"[OPENCLAW_ALERTS] support bundle callback metrics failed tenant={tenant_id}: {e}", flush=True)
            metrics_payload = {"success": False, "metrics": {}, "alerts": []}

    metrics = dict(metrics_payload.get("metrics") or {})
    resolved_alerts = list(alerts or metrics_payload.get("alerts") or [])
    sample_action_ids = list(action_ids or [])
    if not sample_action_ids:
        sample_action_ids = _load_problematic_action_ids_for_tenant(tenant_id, limit=2)
    sample_snapshots = _load_incident_snapshots_for_actions(sample_action_ids)

    lines = [
        "Support bundle:",
        (
            "Queue: "
            f"sent={int(metrics.get('sent') or 0)}, "
            f"retry={int(metrics.get('retry') or 0)}, "
            f"dlq={int(metrics.get('dlq') or 0)}, "
            f"pending={int(metrics.get('pending') or 0)}"
        ),
        (
            "Success rate / stuck: "
            f"{float(metrics.get('delivery_success_rate') or 0.0)}% / "
            f"{int(metrics.get('stuck_retry') or 0)}"
        ),
    ]
    if billing_summary:
        lines.append(
            "Billing: "
            f"checked={int(billing_summary.get('actions_checked') or 0)}, "
            f"with_issues={int(billing_summary.get('actions_with_issues') or 0)}, "
            f"issue_count={int(billing_summary.get('issue_count') or 0)}, "
            f"token_delta={int(billing_summary.get('tokenusage_minus_settled') or 0)}"
        )
    if resolved_alerts:
        lines.append(
            "Alerts: "
            + "; ".join(
                f"{str(item.get('code') or 'UNKNOWN')}: {str(item.get('message') or '').strip()}"
                for item in resolved_alerts[:5]
            )
        )
    else:
        lines.append("Alerts: none")

    if sample_action_ids:
        lines.append(f"Sample action_ids: {', '.join(sample_action_ids[:5])}")
    if sample_snapshots:
        lines.append("Action snapshots:")
        for snapshot in sample_snapshots:
            lines.extend([f"  {line}" for line in _incident_snapshot_lines(snapshot)])

    return lines


def _notify_superadmins_billing_reconcile(
    tenant_id: str,
    *,
    actions_with_issues: int,
    issue_count: int,
    actions_checked: int,
    sample_action_ids: List[str],
) -> None:
    if not _env_bool("OPENCLAW_BILLING_RECONCILE_ALERT_ENABLED", True):
        return
    interval_sec = max(60, int(os.getenv("OPENCLAW_BILLING_RECONCILE_ALERT_INTERVAL_SEC", "1800")))
    now = time.time()
    last_at = _LAST_BILLING_ALERT_BY_TENANT.get(str(tenant_id), 0.0)
    if now - last_at < interval_sec:
        return

    conn = None
    cursor = None
    try:
        def _val(row: Any, idx: int, key: str, default: Any = None) -> Any:
            if row is None:
                return default
            if isinstance(row, dict):
                return row.get(key, default)
            try:
                return row[idx]
            except Exception:
                return default

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users'
            """
        )
        raw_cols = cursor.fetchall() or []
        user_cols = {
            str(_val(r, 0, "column_name", "")).lower()
            for r in raw_cols
            if str(_val(r, 0, "column_name", "")).strip()
        }
        env_ids = {
            x.strip()
            for x in str(os.getenv("OPENCLAW_SUPERADMIN_TELEGRAM_IDS", "")).split(",")
            if x.strip()
        }

        cursor.execute(
            """
            SELECT COALESCE(name, ''), COALESCE(email, '')
            FROM businesses
            WHERE id = %s
            LIMIT 1
            """,
            (str(tenant_id),),
        )
        business_row = cursor.fetchone()
        business_name = str((_val(business_row, 0, "name", "") or "")).strip()

        db_ids: set[str] = set()
        if "telegram_id" in user_cols:
            cursor.execute(
                """
                SELECT telegram_id
                FROM users
                WHERE is_superadmin = TRUE
                  AND telegram_id IS NOT NULL
                  AND NULLIF(TRIM(telegram_id), '') IS NOT NULL
                ORDER BY created_at ASC
                """
            )
            admin_rows = cursor.fetchall() or []
            for row in admin_rows:
                telegram_id = str(_val(row, 0, "telegram_id", "") or "").strip()
                if telegram_id:
                    db_ids.add(telegram_id)

        target_ids = sorted(db_ids.union(env_ids))
        if not target_ids:
            return

        lines = [
            "🚨 OpenClaw billing reconcile alert",
            f"Tenant: {tenant_id}",
            f"Business: {business_name or '-'}",
            f"Actions checked: {actions_checked}",
            f"Actions with issues: {actions_with_issues}",
            f"Issue count: {issue_count}",
        ]
        lines.extend(
            _build_support_bundle_digest_lines(
                tenant_id,
                billing_summary={
                    "actions_checked": actions_checked,
                    "actions_with_issues": actions_with_issues,
                    "issue_count": issue_count,
                },
                action_ids=sample_action_ids or [],
            )
        )
        message = "\n".join(lines)
        sent_any = False
        for telegram_id in target_ids:
            if _send_telegram_plain_message(telegram_id, message):
                sent_any = True

        if sent_any:
            _LAST_BILLING_ALERT_BY_TENANT[str(tenant_id)] = now
    except Exception as e:
        print(f"[BILLING_RECONCILE] notify superadmin error tenant={tenant_id}: {e}", flush=True)
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _notify_superadmins_callback_alerts(
    tenant_id: str,
    *,
    metrics: Dict[str, Any],
    alerts: List[Dict[str, Any]],
    window_minutes: int,
) -> None:
    interval_sec = max(60, int(os.getenv("OPENCLAW_CALLBACK_ALERT_NOTIFY_INTERVAL_SEC", "900")))
    now = time.time()
    last_at = _LAST_CALLBACK_ALERT_BY_TENANT.get(str(tenant_id), 0.0)
    if now - last_at < interval_sec:
        return

    conn = None
    cursor = None
    try:
        def _val(row: Any, idx: int, key: str, default: Any = None) -> Any:
            if row is None:
                return default
            if isinstance(row, dict):
                return row.get(key, default)
            try:
                return row[idx]
            except Exception:
                return default

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users'
            """
        )
        raw_cols = cursor.fetchall() or []
        user_cols = {
            str(_val(r, 0, "column_name", "")).lower()
            for r in raw_cols
            if str(_val(r, 0, "column_name", "")).strip()
        }
        env_ids = {
            x.strip()
            for x in str(os.getenv("OPENCLAW_SUPERADMIN_TELEGRAM_IDS", "")).split(",")
            if x and x.strip()
        }

        cursor.execute(
            """
            SELECT COALESCE(name, '')
            FROM businesses
            WHERE id = %s
            LIMIT 1
            """,
            (str(tenant_id),),
        )
        business_row = cursor.fetchone()
        business_name = str((_val(business_row, 0, "name", "") or "")).strip()

        db_ids: set[str] = set()
        if "telegram_id" in user_cols:
            cursor.execute(
                """
                SELECT telegram_id
                FROM users
                WHERE is_superadmin = TRUE
                  AND telegram_id IS NOT NULL
                  AND NULLIF(TRIM(telegram_id), '') IS NOT NULL
                ORDER BY created_at ASC
                """
            )
            admin_rows = cursor.fetchall() or []
            for row in admin_rows:
                telegram_id = str(_val(row, 0, "telegram_id", "") or "").strip()
                if telegram_id:
                    db_ids.add(telegram_id)

        target_ids = sorted(db_ids.union(env_ids))
        if not target_ids:
            return

        alert_lines = [f"- {a.get('code')}: {a.get('message')}" for a in (alerts or []) if a.get("code")]
        lines = [
            "🚨 OpenClaw callback delivery alert",
            f"Tenant: {tenant_id}",
            f"Business: {business_name or '-'}",
            f"Window (minutes): {window_minutes}",
            f"Sent: {int(metrics.get('sent') or 0)}",
            f"Retry: {int(metrics.get('retry') or 0)}",
            f"DLQ: {int(metrics.get('dlq') or 0)}",
            f"Stuck retry: {int(metrics.get('stuck_retry') or 0)}",
            f"Success rate: {float(metrics.get('delivery_success_rate') or 0.0)}%",
            "Alerts:",
        ] + (alert_lines or ["- unknown"])
        lines.extend(
            _build_support_bundle_digest_lines(
                tenant_id,
                callback_metrics=metrics,
                alerts=alerts,
            )
        )
        message = "\n".join(lines)

        sent_any = False
        for telegram_id in target_ids:
            if _send_telegram_plain_message(telegram_id, message):
                sent_any = True

        if sent_any:
            _LAST_CALLBACK_ALERT_BY_TENANT[str(tenant_id)] = now
    except Exception as e:
        print(f"[CALLBACK_ALERTS] notify superadmin error tenant={tenant_id}: {e}", flush=True)
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _check_openclaw_callback_alerts_if_due() -> None:
    global _LAST_CALLBACK_ALERT_SCAN_AT
    if not _env_bool("OPENCLAW_CALLBACK_ALERT_NOTIFY_ENABLED", True):
        return

    now = time.time()
    scan_interval_sec = max(30, int(os.getenv("OPENCLAW_CALLBACK_ALERT_SCAN_INTERVAL_SEC", "180")))
    if now - _LAST_CALLBACK_ALERT_SCAN_AT < scan_interval_sec:
        return
    _LAST_CALLBACK_ALERT_SCAN_AT = now

    window_minutes = max(5, min(int(os.getenv("OPENCLAW_CALLBACK_ALERT_NOTIFY_WINDOW_MINUTES", "60")), 7 * 24 * 60))
    max_tenants = max(1, min(int(os.getenv("OPENCLAW_CALLBACK_ALERT_NOTIFY_MAX_TENANTS", "100")), 1000))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT tenant_id
            FROM action_callback_outbox
            WHERE tenant_id IS NOT NULL
              AND created_at >= (CURRENT_TIMESTAMP - (%s || ' minutes')::interval)
            ORDER BY tenant_id
            LIMIT %s
            """,
            (window_minutes, max_tenants),
        )
        tenant_rows = cursor.fetchall() or []
        tenant_ids = []
        for row in tenant_rows:
            if isinstance(row, dict):
                value = row.get("tenant_id")
            else:
                value = row[0] if len(row) > 0 else None
            if value:
                tenant_ids.append(str(value))
    except Exception as e:
        print(f"[CALLBACK_ALERTS] tenant scan error: {e}", flush=True)
        return
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass

    for tenant_id in tenant_ids:
        try:
            metrics_payload = CALLBACK_DISPATCH_ORCHESTRATOR.get_callback_metrics(
                {"user_id": "system-worker", "is_superadmin": True},
                tenant_id=tenant_id,
                window_minutes=window_minutes,
            )
            if not metrics_payload.get("success"):
                continue
            alerts = metrics_payload.get("alerts") or []
            if not alerts:
                continue
            metrics = metrics_payload.get("metrics") or {}
            print(
                f"[CALLBACK_ALERTS] tenant={tenant_id} alerts={len(alerts)} dlq={metrics.get('dlq')} stuck_retry={metrics.get('stuck_retry')} success_rate={metrics.get('delivery_success_rate')}",
                flush=True,
            )
            _notify_superadmins_callback_alerts(
                tenant_id,
                metrics=metrics,
                alerts=alerts,
                window_minutes=window_minutes,
            )
        except Exception as e:
            print(f"[CALLBACK_ALERTS] tenant={tenant_id} exception: {e}", flush=True)


def _reconcile_openclaw_billing_if_due() -> None:
    global _LAST_BILLING_RECONCILE_AT
    if not _env_bool("OPENCLAW_BILLING_RECONCILE_ENABLED", True):
        return

    now = time.time()
    interval_sec = max(30, int(os.getenv("OPENCLAW_BILLING_RECONCILE_INTERVAL_SEC", "900")))
    if now - _LAST_BILLING_RECONCILE_AT < interval_sec:
        return
    _LAST_BILLING_RECONCILE_AT = now

    window_minutes = max(5, min(int(os.getenv("OPENCLAW_BILLING_RECONCILE_WINDOW_MINUTES", "120")), 30 * 24 * 60))
    limit = max(10, min(int(os.getenv("OPENCLAW_BILLING_RECONCILE_LIMIT", "200")), 1000))
    max_tenants = max(1, min(int(os.getenv("OPENCLAW_BILLING_RECONCILE_MAX_TENANTS", "100")), 1000))
    min_alert_issues = max(1, int(os.getenv("OPENCLAW_BILLING_RECONCILE_ALERT_MIN_ISSUES", "1")))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT tenant_id
            FROM action_requests
            WHERE tenant_id IS NOT NULL
              AND created_at >= (CURRENT_TIMESTAMP - (%s || ' minutes')::interval)
            ORDER BY tenant_id
            LIMIT %s
            """,
            (window_minutes, max_tenants),
        )
        tenant_rows = cursor.fetchall() or []
        tenant_ids = [str(r[0]) if not isinstance(r, dict) else str(r.get("tenant_id")) for r in tenant_rows if (r[0] if not isinstance(r, dict) else r.get("tenant_id"))]
    except Exception as e:
        print(f"[BILLING_RECONCILE] tenant scan error: {e}", flush=True)
        return
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass

    if not tenant_ids:
        return

    total_actions_checked = 0
    total_actions_with_issues = 0
    total_issue_count = 0
    for tenant_id in tenant_ids:
        try:
            result = CALLBACK_DISPATCH_ORCHESTRATOR.reconcile_billing(
                {"user_id": "system-worker", "is_superadmin": True},
                tenant_id=tenant_id,
                window_minutes=window_minutes,
                limit=limit,
            )
            if not result.get("success"):
                print(
                    f"[BILLING_RECONCILE] tenant={tenant_id} error={result.get('error')}",
                    flush=True,
                )
                continue

            summary = result.get("summary") or {}
            actions_checked = int(summary.get("actions_checked") or 0)
            actions_with_issues = int(summary.get("actions_with_issues") or 0)
            issue_count = int(summary.get("issue_count") or 0)
            total_actions_checked += actions_checked
            total_actions_with_issues += actions_with_issues
            total_issue_count += issue_count
            if actions_with_issues > 0:
                print(
                    f"[BILLING_RECONCILE] ALERT tenant={tenant_id} actions_with_issues={actions_with_issues} issue_count={issue_count}",
                    flush=True,
                )
                if issue_count >= min_alert_issues:
                    items = result.get("items") or []
                    sample_action_ids = [str(it.get("action_id") or "") for it in items if it.get("issues")]
                    _notify_superadmins_billing_reconcile(
                        tenant_id,
                        actions_with_issues=actions_with_issues,
                        issue_count=issue_count,
                        actions_checked=actions_checked,
                        sample_action_ids=sample_action_ids,
                    )
        except Exception as e:
            print(f"[BILLING_RECONCILE] tenant={tenant_id} exception: {e}", flush=True)

    if total_actions_checked > 0:
        print(
            f"[BILLING_RECONCILE] checked={total_actions_checked} actions_with_issues={total_actions_with_issues} issue_count={total_issue_count} tenants={len(tenant_ids)}",
            flush=True,
        )


def get_db_connection():
    """Runtime worker всегда использует PostgreSQL через pg_db_utils."""
    from pg_db_utils import get_db_connection as _get_pg_connection

    return _get_pg_connection()

def _handle_worker_error(queue_id: str, error_msg: str):
    """Обновить статус задачи на error с сообщением"""
    try:
        normalized_error = with_reason_code_prefix(STATUS_ERROR, error_msg)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE parsequeue
            SET status = %s,
                error_message = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (STATUS_ERROR, normalized_error, queue_id),
        )
        if _env_bool("PAUSE_NETWORK_BATCH_ON_ERROR", False):
            try:
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'parsequeue'
                    """
                )
                parsequeue_columns = {
                    str(row.get("column_name") if hasattr(row, "get") else row[0])
                    for row in (cursor.fetchall() or [])
                    if (row.get("column_name") if hasattr(row, "get") else (row[0] if row else None))
                }
                if {"batch_id", "batch_kind", "paused_reason"}.issubset(parsequeue_columns):
                    cursor.execute(
                        """
                        SELECT batch_id
                        FROM parsequeue
                        WHERE id = %s
                        LIMIT 1
                        """,
                        (queue_id,),
                    )
                    row = cursor.fetchone()
                    batch_id = str((row.get("batch_id") if hasattr(row, "get") else (row[0] if row else "")) or "").strip()
                    if batch_id:
                        cursor.execute(
                            """
                            UPDATE parsequeue
                            SET status = %s,
                                paused_reason = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE batch_id = %s
                              AND batch_kind = 'network_sync'
                              AND status IN (%s)
                              AND id <> %s
                            """,
                            (STATUS_PAUSED, f"network_batch_paused_after_error:{normalized_error[:400]}", batch_id, STATUS_PENDING, queue_id),
                        )
            except Exception as pause_ex:
                print(f"⚠️ Не удалось применить pause-on-error для batch задачи {queue_id}: {pause_ex}")
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as ex:
        print(f"❌ Не удалось обновить статус ошибки для {queue_id}: {ex}")


def _pause_network_batch_for_captcha(queue_id: str, captcha_comment: str, delay: timedelta):
    """Поставить оставшиеся pending-задачи network batch на паузу и авто-возобновить после delay."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT batch_id
            FROM parsequeue
            WHERE id = %s
            LIMIT 1
            """,
            (queue_id,),
        )
        row = cursor.fetchone()
        batch_id = str((row.get("batch_id") if hasattr(row, "get") else (row[0] if row else "")) or "").strip()
        if not batch_id:
            conn.commit()
            return
        resume_at = datetime.now() + delay
        cursor.execute(
            """
            UPDATE parsequeue
            SET status = %s,
                paused_reason = %s,
                retry_after = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE batch_id = %s
              AND batch_kind = 'network_sync'
              AND status IN (%s)
              AND id <> %s
            """,
            (
                STATUS_PAUSED,
                f"network_batch_paused_after_captcha_auto:{captcha_comment[:240]}",
                resume_at.isoformat(),
                batch_id,
                STATUS_PENDING,
                queue_id,
            ),
        )
        paused_rows = int(cursor.rowcount or 0)
        if paused_rows == 0:
            # Fallback: если batch_kind по какой-то причине не совпал/пустой,
            # всё равно ставим pending задачи этого batch на паузу.
            cursor.execute(
                """
                UPDATE parsequeue
                SET status = %s,
                    paused_reason = %s,
                    retry_after = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE batch_id = %s
                  AND status = %s
                  AND id <> %s
                """,
                (
                    STATUS_PAUSED,
                    f"network_batch_paused_after_captcha_auto:{captcha_comment[:240]}",
                    resume_at.isoformat(),
                    batch_id,
                    STATUS_PENDING,
                    queue_id,
                ),
            )
            paused_rows = int(cursor.rowcount or 0)
        print(
            f"⏸️ CAPTCHA pause applied for batch {batch_id}: paused_rows={paused_rows} "
            f"source_queue_id={queue_id} resume_at={resume_at.isoformat()}",
            flush=True,
        )
        conn.commit()
    except Exception as ex:
        print(f"⚠️ Не удалось применить pause-on-captcha для batch задачи {queue_id}: {ex}")
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _resume_network_batch_after_captcha(queue_id: str):
    """После успешного CAPTCHA-resume вернуть в pending только те задачи batch, что были paused из-за CAPTCHA."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT batch_id
            FROM parsequeue
            WHERE id = %s
            LIMIT 1
            """,
            (queue_id,),
        )
        row = cursor.fetchone()
        batch_id = str((row.get("batch_id") if hasattr(row, "get") else (row[0] if row else "")) or "").strip()
        if not batch_id:
            conn.commit()
            return
        cursor.execute(
            """
            UPDATE parsequeue
            SET status = %s,
                paused_reason = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE batch_id = %s
              AND batch_kind = 'network_sync'
              AND status = %s
              AND (
                paused_reason LIKE 'network_batch_paused_after_captcha:%'
                OR paused_reason LIKE 'network_batch_paused_after_captcha_auto:%'
              )
            """,
            (STATUS_PENDING, batch_id, STATUS_PAUSED),
        )
        print(
            f"▶️ CAPTCHA pause released for batch {batch_id}: resumed_rows={cursor.rowcount} source_queue_id={queue_id}",
            flush=True,
        )
        conn.commit()
    except Exception as ex:
        print(f"⚠️ Не удалось снять captcha-pause для batch задачи {queue_id}: {ex}")
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _upsert_map_parse_from_card(
    conn,
    business_id: str,
    *,
    url: str = "",
    map_type: str = "yandex",
    rating: float | None = None,
    reviews_count: int = 0,
    photos_count: int = 0,
    news_count: int = 0,
    products: list | None = None,
    competitors: list | None = None,
):
    """Записать срез в MapParseResults для обратной совместимости с Progress/growth_api."""
    import uuid as _uuid
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'mapparseresults'
        """)
        cols = {r[0] for r in cursor.fetchall()}
        # Таблица отсутствует/не видна в схеме — silently skip для совместимости окружений.
        if not cols:
            return
        pid = str(_uuid.uuid4())
        default_url = "https://2gis.ru/" if str(map_type or "").strip().lower() == "2gis" else "https://yandex.ru/maps/"
        url_val = url or default_url
        fields = ["id", "business_id", "url", "map_type", "rating", "reviews_count", "news_count", "photos_count", "created_at"]
        values = [pid, business_id, url_val, map_type or "yandex", str(rating) if rating else None, reviews_count, news_count, photos_count]
        if "services_count" in cols and products:
            s_count = sum(len(c.get("items") or []) for c in products if isinstance(c, dict))
            fields.append("services_count")
            values.append(s_count)
        if "products" in cols and products:
            fields.append("products")
            values.append(json.dumps(products, ensure_ascii=False) if products else None)
        if "competitors" in cols and competitors:
            fields.append("competitors")
            values.append(json.dumps(competitors, ensure_ascii=False) if competitors else None)
        placeholders = ", ".join(["%s"] * len(values))
        cursor.execute(
            f"INSERT INTO mapparseresults ({', '.join(fields)}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
    finally:
        cursor.close()


def _extract_date_from_review(review: dict) -> str | int | float | None:
    """Извлечь дату из отзыва, проверяя различные поля"""
    date_fields = ['date', 'published_at', 'publishedAt', 'created_at', 'createdAt', 'time', 'timestamp']
    date_value = review.get('date')
    
    if date_value:
        if isinstance(date_value, str):
            return date_value.strip()
        return date_value
    
    # Пробуем другие поля
    for field in date_fields[1:]:
        date_value = review.get(field)
        if date_value:
            if isinstance(date_value, str):
                return date_value.strip()
            return date_value
    
    return None

def _parse_timestamp_to_datetime(timestamp: int | float) -> datetime | None:
    """Парсить timestamp в datetime (миллисекунды или секунды)"""
    try:
        if timestamp > 1e10:  # Миллисекунды
            return datetime.fromtimestamp(timestamp / 1000.0)
        return datetime.fromtimestamp(timestamp)  # Секунды
    except Exception:
        return None

def _parse_relative_date(date_str: str) -> datetime | None:
    """Парсить относительные даты: 'сегодня', 'вчера', '2 дня назад' и т.д."""
    date_lower = date_str.lower()
    
    if 'сегодня' in date_lower or 'today' in date_lower:
        return datetime.now()
    if 'вчера' in date_lower or 'yesterday' in date_lower:
        return datetime.now() - timedelta(days=1)
    
    # Дни назад
    if any(word in date_str for word in ['дня', 'день', 'дней']):
        days_match = re.search(r'(\d+)', date_str)
        if days_match:
            return datetime.now() - timedelta(days=int(days_match.group(1)))
    
    # Недели назад
    if any(word in date_str for word in ['неделю', 'недели', 'недель']):
        weeks_match = re.search(r'(\d+)', date_str)
        weeks_ago = int(weeks_match.group(1)) if weeks_match else 1
        return datetime.now() - timedelta(weeks=weeks_ago)
    
    # Месяцы назад
    if any(word in date_str for word in ['месяц', 'месяца', 'месяцев']):
        months_match = re.search(r'(\d+)', date_str)
        months_ago = int(months_match.group(1)) if months_match else 1
        return datetime.now() - timedelta(days=months_ago * 30)
    
    # Годы назад
    if any(word in date_str for word in ['год', 'года', 'лет']):
        years_match = re.search(r'(\d+)', date_str)
        years_ago = int(years_match.group(1)) if years_match else 1
        return datetime.now() - timedelta(days=years_ago * 365)
    
    return None

def _parse_russian_date(date_str: str) -> datetime | None:
    try:
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
            'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
            'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
        }
        
        parts = date_str.lower().split()
        if len(parts) >= 2:
            day_str = parts[0]
            month_str = parts[1]
            year_str = parts[2] if len(parts) > 2 else str(datetime.now().year)
            
            # Очистка от лишних символов
            day_str = re.sub(r'\D', '', day_str)
            year_str = re.sub(r'\D', '', year_str)
            # Очищаем месяц от знаков препинания (запятые, точки)
            month_str = re.sub(r'[^\w\s]', '', month_str, flags=re.UNICODE) 
            
            if not day_str or not month_str:
                return None
                
            day = int(day_str)
            month = months.get(month_str)
            year = int(year_str)
            
            if month:
                return datetime(year, month, day)
                
    except Exception:
        pass
    return None

def _parse_date_string(date_str: str) -> datetime | None:
    """Парсить строку даты в datetime"""
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    if not date_str:
        return None
    
    # Пробуем относительные даты
    relative = _parse_relative_date(date_str)
    if relative:
        return relative
    
    # Пробуем русские даты (27 января 2026)
    russian_date = _parse_russian_date(date_str)
    if russian_date:
        return russian_date
    
    # Пробуем ISO формат
    try:
        if 'T' in date_str or 'Z' in date_str or date_str.count('-') >= 2:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        pass
    
    # Пробуем dateutil для других форматов
    try:
        return date_parser.parse(date_str, fuzzy=True)
    except Exception:
        return None

def _validate_parsing_result(card_data: dict, source: str = SOURCE_YANDEX_BUSINESS) -> tuple:
    """
    Проверяет результат парсинга по ключевым полям. Без подмешивания из БД —
    только то, что реально пришло из источника (Яндекс).
    Returns:
        (is_successful: bool, reason: str, validation_result: dict | None)
    """
    from parsed_payload_validation import validate_parsed_payload

    if card_data.get("error") == "captcha_detected":
        return False, "captcha_detected", None
    if card_data.get("error"):
        error_name = str(card_data.get("error") or "").strip()
        detail = str(card_data.get("message") or "").strip()
        if detail:
            detail = detail.replace("\n", " ")[:220]
            return False, f"error: {error_name} detail={detail}", None
        return False, f"error: {error_name}", None

    validation = validate_parsed_payload(card_data, source=source or SOURCE_YANDEX_BUSINESS)
    hard_missing = validation.get("hard_missing") or []
    quality_score = validation.get("quality_score", 0.0)

    if hard_missing:
        return False, "missing_in_source:" + ",".join(hard_missing), validation

    # Низкое качество: есть заголовок, но критичные поля почти все отсутствуют.
    # Не считаем такой результат успешным парсингом.
    missing_fields = set(validation.get("missing_fields") or [])
    critical_list = []
    for field in ("address", "rating", "reviews_count", "categories"):
        if field in missing_fields:
            critical_list.append(field)

    # Порог 0.5: при 0.4 парсер часто отдаёт только title (редирект на /prices/, капча и т.д.)
    if quality_score < 0.5:
        reason = f"low_quality_payload:quality_score={quality_score}"
        if critical_list:
            reason = f"{reason} missing={','.join(critical_list)}"
        return False, reason, validation

    return True, "success", validation


def _parse_transient_retry_attempt(error_message: Any) -> int:
    text = str(error_message or "")
    match = re.search(r"transient_retry_attempt=(\d+)", text)
    if not match:
        return 0
    try:
        value = int(match.group(1))
    except Exception:
        return 0
    return value if value > 0 else 0


def _transient_retry_delay_for_task(queue_dict: dict, attempt_no: int) -> timedelta:
    attempt = max(int(attempt_no or 1), 1)
    if _is_mass_network_task(queue_dict):
        # Для массовой очереди держим быстрый цикл, чтобы не замораживать throughput.
        minutes = min(5 * attempt, 30)
    else:
        minutes = min(10 * attempt, 40)
    return timedelta(minutes=minutes)


def _queue_transient_parse_retry(queue_dict: dict, reason: str, card_data: Optional[dict]) -> bool:
    transient_errors = {
        "parser_subprocess_exception",
        "org_api_not_loaded",
        "parser_returned_none",
        "parser_returned_list",
        "parser_returned_tuple",
    }
    parser_error = ""
    if isinstance(card_data, dict):
        parser_error = str(card_data.get("error") or "").strip()
    parser_message = ""
    if isinstance(card_data, dict):
        parser_message = str(card_data.get("message") or "").strip().lower()

    is_2gis_timeout = (
        parser_error == "2gis_parse_failed"
        and (
            "err_timed_out" in parser_message
            or "timeout" in parser_message
            or "err_connection_reset" in parser_message
            or "err_connection_closed" in parser_message
            or "err_name_not_resolved" in parser_message
        )
    )

    if parser_error not in transient_errors and not is_2gis_timeout:
        return False

    prev_attempt = _parse_transient_retry_attempt(queue_dict.get("error_message"))
    attempt_no = prev_attempt + 1
    max_attempts = int(os.getenv("TRANSIENT_PARSE_MAX_ATTEMPTS", "8") or 8)
    if attempt_no > max_attempts:
        return False

    retry_delay = _transient_retry_delay_for_task(queue_dict, attempt_no)
    retry_after = datetime.now() + retry_delay
    detail = str(reason or "")[:220]
    comment = (
        f"transient_retry_attempt={attempt_no}; "
        f"transient_error={parser_error}; detail={detail}"
    )

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE parsequeue
            SET status = %s,
                retry_after = %s,
                error_message = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                STATUS_PENDING,
                retry_after.isoformat(),
                comment,
                queue_dict["id"],
            ),
        )
        conn.commit()
        print(
            f"🔁 Transient parse retry scheduled: queue_id={queue_dict.get('id')} "
            f"error={parser_error} attempt={attempt_no}/{max_attempts} "
            f"retry_after={retry_after.isoformat()}",
            flush=True,
        )
        return True
    except Exception as ex:
        print(f"⚠️ Не удалось поставить transient retry для {queue_dict.get('id')}: {ex}", flush=True)
        return False
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _has_existing_card_snapshot(business_id: str) -> bool:
    """Есть ли у бизнеса уже сохранённый snapshot в cards."""
    if not business_id:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT 1
            FROM cards
            WHERE business_id = %s
            LIMIT 1
            """,
            (business_id,),
        )
        return cursor.fetchone() is not None
    except Exception as e:
        print(f"⚠️ Не удалось проверить existing cards snapshot для {business_id}: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def _has_cabinet_account(business_id: str) -> tuple:
    """
    Проверяет, есть ли у бизнеса аккаунт в личном кабинете.
    
    Returns:
        (has_account: bool, account_id: str)
    """
    if not business_id:
        return False, None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id
            FROM externalbusinessaccounts
            WHERE business_id = %s AND source = 'yandex_business' AND is_active = TRUE
            LIMIT 1
        """, (business_id,))
        
        row = cursor.fetchone()
        if row:
            return True, row[0]
        return False, None
    finally:
        cursor.close()
        conn.close()

def _ensure_column_exists(cursor, conn, table_name, column_name, column_type="TEXT"):
    """Проверяет и добавляет колонку если её нет"""
    # Эта функция использовалась только для SQLite (PRAGMA, ALTER TABLE on the fly).
    # В PostgreSQL схема управляется через миграции (schema_postgres.sql),
    # поэтому в worker'е при DB_TYPE='postgres' просто выходим.
    if DB_TYPE == "postgres":
        return

    try:
        # PRAGMA не поддерживает параметризованные запросы, используем f-string с проверкой
        ALLOWED_TABLES = {"parsequeue", "cards"}
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Неразрешенная таблица: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]

        if column_name not in columns:
            print(f"📝 Добавляю поле {column_name} в {table_name}...")
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            conn.commit()
    except Exception as e:
        print(f"⚠️ Ошибка проверки колонки {column_name} в {table_name}: {e}")

# Используем parser_config для автоматического выбора парсера (interception или legacy)
from parser_config import parse_yandex_card
try:
    from two_gis_maps_scraper import parse_2gis_card
except ModuleNotFoundError:
    # В некоторых контейнерных сборках модуль доступен только как src.*
    from src.two_gis_maps_scraper import parse_2gis_card
from gigachat_analyzer import analyze_business_data

def process_queue():
    """Обрабатывает очередь парсинга из SQLite базы данных"""
    queue_dict = None
    
    # ШАГ 1: Получаем задачу из очереди и обновляем статус (закрываем соединение сразу)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Для PostgreSQL схема очереди уже задана в schema_postgres.sql,
        # поэтому проверки через sqlite_master / PRAGMA здесь не нужны.

        # Восстановление застрявших processing-задач (например, после падения worker/DB).
        # Такие задачи возвращаем в pending, чтобы очередь продолжила движение.
        try:
            stale_processing_minutes = max(3, int(os.getenv("PROCESSING_STALE_MINUTES", "10")))
            cursor.execute(
                """
                UPDATE parsequeue
                SET status = %s,
                    updated_at = CURRENT_TIMESTAMP,
                    error_message = COALESCE(
                        error_message || '; stale processing recovered',
                        'stale processing recovered'
                    )
                WHERE status = %s
                  AND updated_at < (CURRENT_TIMESTAMP - make_interval(mins => %s))
                """,
                (STATUS_PENDING, STATUS_PROCESSING, stale_processing_minutes),
            )
            if cursor.rowcount:
                print(f"♻️ Восстановлено stale processing задач: {cursor.rowcount}")
                conn.commit()
        except Exception as e:
            print(f"⚠️ Ошибка восстановления stale processing: {e}")

        # Global TTL guardrail: старые задачи уходят в DLQ, чтобы не зацикливать очередь.
        try:
            parse_task_ttl_hours = max(1, int(os.getenv("PARSE_TASK_TTL_HOURS", "48")))
            ttl_msg = with_reason_code_prefix(
                STATUS_ERROR,
                f"dlq_reason=task_ttl_exceeded; source=global_guard; ttl_hours={parse_task_ttl_hours}",
            )
            cursor.execute(
                """
                UPDATE parsequeue
                SET status = %s,
                    error_message = %s,
                    retry_after = NULL,
                    captcha_required = 0,
                    captcha_url = NULL,
                    captcha_session_id = NULL,
                    captcha_started_at = NULL,
                    resume_requested = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN (%s, %s, %s, %s)
                  AND created_at IS NOT NULL
                  AND created_at < (CURRENT_TIMESTAMP - make_interval(hours => %s))
                """,
                (
                    STATUS_ERROR,
                    ttl_msg,
                    STATUS_PENDING,
                    STATUS_CAPTCHA,
                    STATUS_PROCESSING,
                    STATUS_PAUSED,
                    parse_task_ttl_hours,
                ),
            )
            if cursor.rowcount:
                print(f"🛑 Global TTL guard moved to DLQ: {cursor.rowcount}", flush=True)
                conn.commit()
        except Exception as e:
            print(f"⚠️ Ошибка global TTL guardrail: {e}")

        # Global retry-attempt guard: капча попытки сверх лимита отправляем в DLQ.
        try:
            max_captcha_attempts = max(1, int(os.getenv("CAPTCHA_AUTO_RETRY_MAX_ATTEMPTS", "4")))
            cursor.execute(
                """
                SELECT id, status, error_message
                FROM parsequeue
                WHERE status IN (%s, %s)
                  AND error_message LIKE '%%captcha_auto_retry_attempt=%%'
                LIMIT 500
                """,
                (STATUS_PENDING, STATUS_CAPTCHA),
            )
            rows = cursor.fetchall() or []
            moved = 0
            for row in rows:
                row_id = str(row.get("id") if isinstance(row, dict) else row[0])
                row_status = row.get("status") if isinstance(row, dict) else row[1]
                row_error = row.get("error_message") if isinstance(row, dict) else row[2]
                attempt_no = _captcha_retry_attempt_from_error(row_error)
                if attempt_no < max_captcha_attempts:
                    continue
                dlq_message = with_reason_code_prefix(
                    STATUS_ERROR,
                    f"dlq_reason=captcha_retry_exhausted; source=global_guard; attempt={attempt_no}; max_attempts={max_captcha_attempts}",
                )
                cursor.execute(
                    """
                    UPDATE parsequeue
                    SET status = %s,
                        error_message = %s,
                        retry_after = NULL,
                        captcha_required = 0,
                        captcha_url = NULL,
                        captcha_session_id = NULL,
                        captcha_started_at = NULL,
                        resume_requested = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                      AND status = %s
                    """,
                    (STATUS_ERROR, dlq_message, row_id, row_status),
                )
                moved += int(cursor.rowcount or 0)
            if moved:
                print(f"🛑 Global captcha-attempt guard moved to DLQ: {moved}", flush=True)
                conn.commit()
        except Exception as e:
            print(f"⚠️ Ошибка global captcha-attempt guardrail: {e}")

        # Санитайзер "битых" captcha-записей: status='captcha' без корректного captcha_started_at
        try:
            cursor.execute(
                """
                UPDATE parsequeue
                SET status = %s,
                    captcha_status = 'expired',
                    captcha_required = 0,
                    captcha_url = NULL,
                    captcha_session_id = NULL,
                    captcha_started_at = NULL,
                    resume_requested = 0,
                    updated_at = CURRENT_TIMESTAMP,
                    error_message = COALESCE(
                        error_message || '; broken captcha record: missing captcha_started_at',
                        'broken captcha record: missing captcha_started_at'
                    )
                WHERE status = %s
                  AND captcha_started_at IS NULL
                """,
                (STATUS_PENDING, STATUS_CAPTCHA),
            )
            if cursor.rowcount:
                conn.commit()
        except Exception as e:
            print(f"⚠️ Ошибка санитации битых captcha-записей: {e}")

        # Разморозка paused-задач батча, если активной captcha в batch уже нет.
        # Это защищает от зависаний после старых сценариев pause-on-captcha.
        try:
            cursor.execute(
                """
                UPDATE parsequeue p
                SET status = %s,
                    paused_reason = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE p.status = %s
                  AND p.batch_kind = 'network_sync'
                  AND (
                    p.paused_reason LIKE 'network_batch_paused_after_captcha:%%'
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM parsequeue p2
                      WHERE p2.batch_id = p.batch_id
                        AND p2.status = %s
                  )
                """,
                (STATUS_PENDING, STATUS_PAUSED, STATUS_CAPTCHA),
            )
            if cursor.rowcount:
                print(f"▶️ Разморожено paused задач после captcha terminal state: {cursor.rowcount}", flush=True)
                conn.commit()
        except Exception as e:
            print(f"⚠️ Ошибка разморозки paused batch-задач: {e}")

        # Авто-возврат paused batch-задач после backoff окна (по retry_after),
        # даже если часть задач всё ещё в pending/captcha.
        try:
            now_iso = datetime.now().isoformat()
            cursor.execute(
                """
                UPDATE parsequeue
                SET status = %s,
                    paused_reason = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = %s
                  AND batch_kind = 'network_sync'
                  AND paused_reason LIKE 'network_batch_paused_after_captcha_auto:%%'
                  AND retry_after IS NOT NULL
                  AND retry_after <= %s
                """,
                (STATUS_PENDING, STATUS_PAUSED, now_iso),
            )
            if cursor.rowcount:
                print(f"▶️ Авто-возврат paused задач после captcha backoff: {cursor.rowcount}", flush=True)
                conn.commit()
        except Exception as e:
            print(f"⚠️ Ошибка авто-возврата paused batch-задач: {e}")
        
        # Получаем заявки из очереди (обрабатываем и parse_card, и sync задачи)
        now = datetime.now()
        now_iso = now.isoformat()
        ttl_cutoff_iso = (now - timedelta(minutes=CAPTCHA_TTL_MINUTES)).isoformat()
        cursor.execute(
            """
            WITH next_task AS (
                SELECT id, status AS selected_status
                FROM parsequeue
                WHERE
                    (
                        status = %s
                        AND (retry_after IS NULL OR retry_after <= %s)
                    )
                    OR (
                        status = %s
                        AND (
                            resume_requested = 1
                            OR (retry_after IS NULL OR retry_after <= %s)
                            OR (captcha_started_at <= %s)
                        )
                    )
                ORDER BY
                    CASE
                        WHEN status = %s THEN 1
                        WHEN status = %s THEN 2
                        ELSE 3
                    END,
                    created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE parsequeue q
            SET status = CASE WHEN next_task.selected_status = %s THEN %s ELSE q.status END,
                updated_at = CURRENT_TIMESTAMP
            FROM next_task
            WHERE q.id = next_task.id
            RETURNING q.*, next_task.selected_status
            """,
            (
                STATUS_PENDING,
                now_iso,
                STATUS_CAPTCHA,
                now_iso,
                ttl_cutoff_iso,
                STATUS_PENDING,
                STATUS_CAPTCHA,
                STATUS_PENDING,
                STATUS_PROCESSING,
            ),
        )
        queue_item = cursor.fetchone()
        
        if not queue_item:
            return
        
        conn.commit()

        # Преобразуем Row в словарь (RealDictCursor в pg_db_utils)
        queue_dict = dict(queue_item)
        selected_status = queue_dict.get("selected_status") or queue_dict.get("status") or STATUS_PENDING
        queue_dict["selected_status"] = selected_status
    finally:
        # ВАЖНО: Закрываем соединение перед долгим парсингом
        cursor.close()
        conn.close()
    
    if not queue_dict:
        return
    
    status = queue_dict.get("status") or "pending"
    task_type = queue_dict.get("task_type") or "parse_card"
    preparsed_card_data: Optional[Dict[str, Any]] = None

    task_age_h = _task_age_hours(queue_dict)
    task_age_warn_h = max(1, int(os.getenv("TASK_AGE_WARN_HOURS", "12")))
    task_ttl_h = max(task_age_warn_h, int(os.getenv("PARSE_TASK_TTL_HOURS", "48")))
    if task_age_h >= float(task_age_warn_h):
        print(
            f"⏱️ Task age warn: task_id={queue_dict.get('id')} age_hours={task_age_h:.2f} "
            f"status={status} ttl_hours={task_ttl_h}",
            flush=True,
        )
    if task_age_h > float(task_ttl_h):
        print(
            f"🛑 Task TTL exceeded: task_id={queue_dict.get('id')} age_hours={task_age_h:.2f} "
            f"ttl_hours={task_ttl_h}. Moving to DLQ.",
            flush=True,
        )
        _move_task_to_dlq(
            str(queue_dict.get("id")),
            "task_ttl_exceeded",
            f"task_age_hours={task_age_h:.2f}; ttl_hours={task_ttl_h}",
            clear_captcha_fields=True,
        )
        return
    
    print(f"Обрабатываю заявку: {queue_dict.get('id')}, тип: {task_type}, статус: {status}")
    
    # Если задача в статусе captcha — обрабатываем HITL-flow (resume/expired)
    if status == "captcha":
        task_id = queue_dict["id"]
        captcha_session_id = queue_dict.get("captcha_session_id")
        captcha_started_at = queue_dict.get("captcha_started_at")
        resume_requested = queue_dict.get("resume_requested")
        url = queue_dict.get("url")

        # 1) Проверка TTL (expired)
        try:
            if captcha_started_at:
                started_dt = datetime.fromisoformat(str(captcha_started_at))
                age_minutes = (datetime.now() - started_dt).total_seconds() / 60.0
            else:
                age_minutes = 0
        except Exception:
            age_minutes = 0

        if age_minutes > CAPTCHA_TTL_MINUTES:
            print(f"⏰ CAPTCHA TTL истёк для задачи {task_id}, помечаем как expired")
            session = BROWSER_SESSION_MANAGER.get(ACTIVE_CAPTCHA_SESSIONS, str(captcha_session_id)) if captcha_session_id else None
            if session:
                BROWSER_SESSION_MANAGER.close_session(session)
            if captcha_session_id:
                ACTIVE_CAPTCHA_SESSIONS.pop(str(captcha_session_id), None)

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE parsequeue
                    SET captcha_status = 'expired',
                        captcha_session_id = NULL,
                        captcha_required = 0,
                        captcha_url = NULL,
                        captcha_started_at = NULL,
                        resume_requested = 0,
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (STATUS_PENDING, task_id),
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            return

        # 2) Resume по запросу оператора
        if resume_requested and url:
            print(f"▶️ RESUME CAPTCHA для задачи {task_id}, session_id={captcha_session_id}")
            if captcha_session_id:
                card_data = _parse_yandex_card_with_playwright_fallback(
                    url,
                    keep_open_on_captcha=False,
                    session_registry=ACTIVE_CAPTCHA_SESSIONS,
                    session_id=str(captcha_session_id),
                )
            else:
                # Для старых/упрощённых CAPTCHA-задач без parked session даём fresh retry.
                browser_profile = _build_human_browser_profile()
                card_data = _parse_yandex_card_with_playwright_fallback(
                    url,
                    keep_open_on_captcha=False,
                    user_agent=browser_profile["user_agent"],
                    viewport=browser_profile["viewport"],
                    launch_args=browser_profile["launch_args"],
                    init_scripts=browser_profile["init_scripts"],
                )

            if card_data.get("error") == "captcha_session_lost":
                print(f"⚠️ CAPTCHA session lost для задачи {task_id}")
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    session_lost_msg = with_reason_code_prefix(STATUS_ERROR, "captcha session lost")
                    cursor.execute(
                        """
                        UPDATE parsequeue
                        SET captcha_status = 'expired',
                            captcha_session_id = NULL,
                            captcha_required = 0,
                            captcha_url = NULL,
                            captcha_started_at = NULL,
                            resume_requested = 0,
                            status = 'pending',
                            updated_at = CURRENT_TIMESTAMP,
                            error_message = %s
                        WHERE id = %s
                        """,
                        (session_lost_msg, task_id),
                    )
                    conn.commit()
                finally:
                    cursor.close()
                    conn.close()
                ACTIVE_CAPTCHA_SESSIONS.pop(str(captcha_session_id), None)
                return

            if card_data.get("error") == "captcha_detected":
                # Капча не решена или появилась заново — остаёмся в waiting с новым session_id (если есть)
                new_session_id = card_data.get("captcha_session_id") or captcha_session_id
                captcha_url = card_data.get("captcha_url") or url
                captcha_comment = f"captcha_required: откройте ссылку и пройдите капчу: {captcha_url}" if captcha_url else "captcha_required: пройдите капчу и нажмите продолжить"
                captcha_comment = with_reason_code_prefix(STATUS_CAPTCHA, captcha_comment)
                print(f"⚠️ Капча всё ещё активна для задачи {task_id}, session_id={new_session_id}")
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    retry_after = datetime.now() + timedelta(minutes=CAPTCHA_TTL_MINUTES)
                    cursor.execute(
                        """
                        UPDATE parsequeue
                        SET captcha_status = 'waiting',
                            retry_after = %s,
                            captcha_url = %s,
                            captcha_session_id = %s,
                            error_message = %s,
                            resume_requested = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (retry_after.isoformat(), captcha_url, str(new_session_id), captcha_comment, task_id),
                    )
                    conn.commit()
                finally:
                    cursor.close()
                    conn.close()
                if _is_mass_network_task(queue_dict):
                    _pause_network_batch_for_captcha(task_id, captcha_comment, timedelta(minutes=max(5, CAPTCHA_TTL_MINUTES)))
                return

            # Иначе — капча решена, продолжаем как обычный успешный парсинг
            print(f"✅ CAPTCHA решена для задачи {task_id}, продолжаем обработку")
            queue_dict["status"] = "processing"
            queue_dict["resume_requested"] = 0
            queue_dict["_resume_batch_after_captcha"] = True
            preparsed_card_data = card_data
            # Чистим captcha-поля
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE parsequeue
                    SET captcha_status = NULL,
                        captcha_required = 0,
                        captcha_url = NULL,
                        captcha_session_id = NULL,
                        captcha_started_at = NULL,
                        resume_requested = 0,
                        status = 'processing',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (task_id,),
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()

            # Убираем сессию из реестра на всякий случай (оркестратор уже её закрыл)
            ACTIVE_CAPTCHA_SESSIONS.pop(str(captcha_session_id), None)

            # card_data уже получен, можно использовать его дальше, минуя повторный вызов parse_yandex_card
            # Для простоты здесь можно пойти по "обычному" пути: переиспользуем card_data ниже.
        else:
            auto_retry_enabled = _env_bool("CAPTCHA_AUTO_RETRY_ENABLED", True)
            if not auto_retry_enabled or not url:
                print(f"⏳ Задача {queue_dict.get('id')} в статусе CAPTCHA/waiting, действий не требуется")
                return

            retry_after_dt = _parse_retry_after(queue_dict.get("retry_after"))
            now_dt = datetime.now()
            if retry_after_dt and retry_after_dt > now_dt:
                print(
                    f"⏳ CAPTCHA auto-retry ещё не наступил для {task_id}: "
                    f"retry_after={retry_after_dt.isoformat()}"
                )
                return

            attempt_no = _captcha_retry_attempt_from_error(queue_dict.get("error_message")) + 1
            max_captcha_attempts = max(1, int(os.getenv("CAPTCHA_AUTO_RETRY_MAX_ATTEMPTS", "4")))
            if attempt_no > max_captcha_attempts:
                print(
                    f"🛑 CAPTCHA retry exhausted in captcha-state: task_id={task_id} "
                    f"attempt={attempt_no} max={max_captcha_attempts}. Moving to DLQ.",
                    flush=True,
                )
                _move_task_to_dlq(
                    str(task_id),
                    "captcha_retry_exhausted",
                    f"attempt={attempt_no}; max_attempts={max_captcha_attempts}; source=captcha_status",
                    clear_captcha_fields=True,
                )
                return
            print(f"🔁 CAPTCHA auto-retry attempt={attempt_no} task_id={task_id}")
            browser_profile = _build_human_browser_profile()
            card_data = _parse_yandex_card_with_playwright_fallback(
                url,
                keep_open_on_captcha=False,
                user_agent=browser_profile["user_agent"],
                viewport=browser_profile["viewport"],
                launch_args=browser_profile["launch_args"],
                init_scripts=browser_profile["init_scripts"],
            )

            if card_data.get("error") == "captcha_detected":
                retry_delay = _captcha_retry_delay_for_task(queue_dict, attempt_no)
                next_retry = datetime.now() + retry_delay
                captcha_url = card_data.get("captcha_url") or url
                captcha_comment = (
                    f"captcha_auto_retry_attempt={attempt_no}; "
                    f"captcha_required: {captcha_url or 'retry_scheduled'}"
                )
                captcha_comment = with_reason_code_prefix(STATUS_CAPTCHA, captcha_comment)
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        """
                        UPDATE parsequeue
                        SET captcha_status = 'delayed_auto',
                            status = %s,
                            retry_after = %s,
                            captcha_url = %s,
                            captcha_session_id = NULL,
                            error_message = %s,
                            resume_requested = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (
                            STATUS_CAPTCHA,
                            next_retry.isoformat(),
                            captcha_url,
                            captcha_comment,
                            task_id,
                        ),
                    )
                    conn.commit()
                finally:
                    cursor.close()
                    conn.close()
                print(
                    f"⏱️ CAPTCHA auto-retry rescheduled task_id={task_id} "
                    f"next_retry={next_retry.isoformat()}",
                    flush=True,
                )
                if _is_mass_network_task(queue_dict):
                    _pause_network_batch_for_captcha(task_id, captcha_comment, retry_delay)
                return

            if card_data.get("error"):
                _handle_worker_error(task_id, f"captcha_auto_retry_failed:{card_data.get('error')}")
                return

            print(f"✅ CAPTCHA auto-retry succeeded for task_id={task_id}")
            queue_dict["status"] = "processing"
            queue_dict["resume_requested"] = 0
            queue_dict["_resume_batch_after_captcha"] = True
            preparsed_card_data = card_data
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE parsequeue
                    SET captcha_status = NULL,
                        captcha_required = 0,
                        captcha_url = NULL,
                        captcha_session_id = NULL,
                        captcha_started_at = NULL,
                        resume_requested = 0,
                        status = 'processing',
                        error_message = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (task_id,),
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()

    # Обрабатываем в зависимости от типа задачи
    if task_type == "sync_yandex_business":
        # Синхронизация Яндекс.Бизнес
        _process_sync_yandex_business_task(queue_dict)
        return
    elif task_type == "parse_cabinet_fallback":
        # Fallback парсинг через кабинет
        _process_cabinet_fallback_task(queue_dict)
        return
    elif task_type == "sync_2gis":
        # Синхронизация 2ГИС API
        _process_sync_2gis_task(queue_dict)
        return
    elif task_type == "sync_google_business":
        # Другие источники (будущее)
        print(f"⚠️ Тип задачи {task_type} пока не реализован")
        _handle_worker_error(queue_dict["id"], f"Тип задачи {task_type} пока не реализован")
        return
    
    # Обычный парсинг карт (task_type = 'parse_card' или NULL)
    # ШАГ 2: Парсим данные (БЕЗ открытого соединения с БД)
    # Устанавливаем таймаут 10 минут
    def timeout_handler(signum, frame):
        raise TimeoutError("Parsing task timed out after 10 minutes")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(600)
    
    try:
        if not queue_dict.get("url"):
            raise ValueError("URL не указан для задачи парсинга")

        url = queue_dict["url"]
        parsed_source = _detect_map_source(queue_dict, url)

        # --- АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ ССЫЛОК (SPRAV -> MAPS) ---
        if parsed_source == "yandex_maps" and '/sprav/' in url:
            import re
            # Ищем ID организации (цифры)
            sprav_match = re.search(r'/sprav/(\d+)', url)
            if sprav_match:
                org_id = sprav_match.group(1)
                # Конвертируем в публичную ссылку карт
                new_url = f"https://yandex.ru/maps/org/redirect/{org_id}"
                print(f"⚠️ ОБНАРУЖЕНА ССЫЛКА НА ЛИЧНЫЙ КАБИНЕТ: {url}")
                print(f"🔄 АВТОМАТИЧЕСКАЯ ЗАМЕНА НА: {new_url}")
                url = new_url
                queue_dict['url'] = new_url # Обновляем и в словаре

        # Нормализуем org URL, чтобы не получать региональные/редакционные вариации .com
        # и шумные query-параметры.
        if parsed_source == "yandex_maps":
            normalized_url = _normalize_yandex_org_url(url)
            if normalized_url and normalized_url != url:
                print(f"🔄 URL normalized: {url} -> {normalized_url}")
                url = normalized_url
                queue_dict["url"] = normalized_url

        cookies = get_yandex_cookies() if parsed_source == "yandex_maps" else None
        business_id = queue_dict.get("business_id")
        debug_dir_root = os.getenv("DEBUG_DIR", "/app/debug_data").rstrip("/")

        # Генерируем debug_bundle_id и bundle_dir для этого прогона (привязан к бизнесу и задаче)
        debug_bundle_id = None
        bundle_dir = None
        if business_id:
            ts_dbg = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_prefix = "yandex" if parsed_source == "yandex_maps" else "2gis"
            debug_bundle_id = f"{debug_prefix}_{business_id}_{queue_dict['id']}_{ts_dbg}"
            bundle_dir = os.path.join(debug_dir_root, debug_bundle_id)
            try:
                os.makedirs(bundle_dir, exist_ok=True)
            except Exception as e:
                print(f"⚠️ Не удалось создать debug bundle dir {bundle_dir}: {e}")
            else:
                print(f"[DEBUG_BUNDLE] {bundle_dir}")

        # Геолокация для стабилизации региона: только если у бизнеса есть координаты
        geolocation_kwarg = {}
        if business_id:
            try:
                conn_geo = get_db_connection()
                cur_geo = conn_geo.cursor()
                cur_geo.execute("SELECT geo_lat, geo_lon FROM businesses WHERE id = %s", (business_id,))
                row_geo = cur_geo.fetchone()
                cur_geo.close()
                conn_geo.close()
                geo_lat = None
                geo_lon = None
                if isinstance(row_geo, dict):
                    geo_lat = row_geo.get("geo_lat")
                    geo_lon = row_geo.get("geo_lon")
                elif row_geo:
                    geo_lat = row_geo[0]
                    geo_lon = row_geo[1]
                if geo_lat is not None and geo_lon is not None:
                    geolocation_kwarg = {"geolocation": {"latitude": float(geo_lat), "longitude": float(geo_lon)}}
            except Exception as e:
                print(f"⚠️ Не удалось загрузить geo для business_id={business_id}: {e}")

        # Основной вызов парсера с защитой от Playwright Sync-in-async краша
        active_proxy = _get_next_proxy_for_playwright()
        proxy_id = str((active_proxy or {}).get("id") or "").strip()
        if active_proxy:
            proxy_country = str((active_proxy or {}).get("country_code") or "base")
            print(
                f"🌐 Используем proxyservers прокси: {active_proxy.get('host')}:{active_proxy.get('port')} "
                f"(id={proxy_id}, country={proxy_country})",
                flush=True,
            )

        try:
            if preparsed_card_data is not None:
                card_data = preparsed_card_data
                print("♻️ Используем уже полученные данные из CAPTCHA flow", flush=True)
            else:
                browser_profile = _build_human_browser_profile()
                if parsed_source == "2gis":
                    card_data = parse_2gis_card(
                        url,
                        timeout_sec=60,
                        headless=True,
                        proxy=(active_proxy or {}).get("proxy"),
                    )
                else:
                    card_data = _parse_yandex_card_with_playwright_fallback(
                        url,
                        keep_open_on_captcha=True,
                        session_registry=ACTIVE_CAPTCHA_SESSIONS,
                        cookies=cookies,
                        user_agent=browser_profile["user_agent"],
                        viewport=browser_profile["viewport"],
                        launch_args=browser_profile["launch_args"],
                        init_scripts=browser_profile["init_scripts"],
                        locale="ru-RU",
                        timezone_id="Europe/Moscow",
                        proxy=(active_proxy or {}).get("proxy"),
                        headless=True,
                        debug_bundle_id=debug_bundle_id,
                        **geolocation_kwarg,
                    )

            # Защита от некорректного возврата парсера
            if card_data is None:
                print("[FATAL] parse_card вернул None", flush=True)
                card_data = {"error": "parser_returned_none", "url": url}
            elif not isinstance(card_data, dict):
                print(f"[FATAL] parse_card вернул {type(card_data)}", flush=True)
                card_data = {"error": f"parser_returned_{type(card_data).__name__}", "url": url}

            # Нормализация/распаковка payload до валидации:
            # - поднимаем nested data/payload/result/company/org в top-level
            # - заполняем title_or_name из доступных полей
            if isinstance(card_data, dict) and not card_data.get("error"):
                before_keys = set(card_data.keys())
                card_data = _promote_nested_card_payload(card_data)
                added_keys = sorted(list(set(card_data.keys()) - before_keys))
                if added_keys:
                    print(f"[WORKER_NORMALIZE] promoted keys: {', '.join(added_keys[:10])}", flush=True)
                if card_data.get("title_or_name"):
                    print(f"[WORKER_NORMALIZE] title_or_name='{str(card_data.get('title_or_name'))[:60]}'", flush=True)
                else:
                    print("[CRITICAL] Нет источников для title_or_name", flush=True)
                    identity = _load_business_identity_for_fallback(business_id)
                    if _apply_business_identity_fallback(
                        card_data,
                        business_name=identity.get("name") or "",
                        business_address=identity.get("address") or "",
                    ):
                        print(
                            f"[WORKER_NORMALIZE] title_or_name fallback from business record: "
                            f"'{str(card_data.get('title_or_name'))[:60]}'",
                            flush=True,
                        )
        except Exception as e:
            msg = str(e)
            recovered_without_proxy = False
            _mark_proxy_result(proxy_id, success=False, reason=msg[:240])
            if active_proxy and parsed_source == "yandex_maps":
                print(
                    f"⚠️ Ошибка при парсинге через прокси ({proxy_id}): {msg[:160]} | retry without proxy",
                    flush=True,
                )
                try:
                    browser_profile = _build_human_browser_profile()
                    card_data = _parse_yandex_card_with_playwright_fallback(
                        url,
                        keep_open_on_captcha=True,
                        session_registry=ACTIVE_CAPTCHA_SESSIONS,
                        cookies=cookies,
                        user_agent=browser_profile["user_agent"],
                        viewport=browser_profile["viewport"],
                        launch_args=browser_profile["launch_args"],
                        init_scripts=browser_profile["init_scripts"],
                        locale="ru-RU",
                        timezone_id="Europe/Moscow",
                        proxy=None,
                        headless=True,
                        debug_bundle_id=debug_bundle_id,
                        **geolocation_kwarg,
                    )
                    print("✅ Retry without proxy succeeded", flush=True)
                    recovered_without_proxy = True
                except Exception as retry_exc:
                    retry_msg = str(retry_exc)
                    print(f"❌ Retry without proxy failed: {retry_msg[:180]}", flush=True)
                    if _is_playwright_sync_in_async_error(retry_msg):
                        e = retry_exc
                        msg = retry_msg
                    else:
                        raise
            if recovered_without_proxy:
                pass
            elif _is_playwright_sync_in_async_error(msg):
                # Специальный кейс: крэш Playwright Sync внутри asyncio loop.
                # Пишем exception.txt в bundle (если можно) и помечаем задачу как error.
                bundle_path = None
                try:
                    if bundle_dir:
                        os.makedirs(bundle_dir, exist_ok=True)
                        bundle_path = bundle_dir
                        exc_path = os.path.join(bundle_dir, "exception.txt")
                        with open(exc_path, "w", encoding="utf-8") as f:
                            f.write("Playwright Sync-in-async crash\n\n")
                            f.write(repr(e) + "\n\n")
                            f.write(traceback.format_exc())
                except Exception as we:
                    print(f"⚠️ Не удалось сохранить exception.txt: {we}")

                err_msg = f"playwright_sync_in_async_loop exc={type(e).__name__}"
                if bundle_path:
                    err_msg = f"{err_msg} bundle={bundle_path}"

                try:
                    _handle_worker_error(queue_dict["id"], err_msg)
                except Exception as db_ex:
                    print(f"❌ Не удалось обновить parsequeue для playwright-sync ошибки: {db_ex}")
                return
            # Любая другая ошибка — пусть обрабатывается общей логикой ниже
            else:
                raise

        if isinstance(card_data, dict):
            card_error = str(card_data.get("error") or "").strip()
            if card_error == "parser_subprocess_exception":
                sub_msg = str(card_data.get("message") or "").strip()
                if sub_msg:
                    print(f"⚠️ parser_subprocess_exception: {sub_msg[:240]}", flush=True)
                sub_tb = str(card_data.get("traceback") or "").strip()
                if sub_tb:
                    tb_head = sub_tb.splitlines()[:5]
                    print("⚠️ traceback head: " + " | ".join(tb_head), flush=True)
                if active_proxy and parsed_source == "yandex_maps":
                    print(
                        f"⚠️ parser_subprocess_exception через proxy ({proxy_id}) -> retry without proxy",
                        flush=True,
                    )
                    try:
                        browser_profile = _build_human_browser_profile()
                        retry_card_data = _parse_yandex_card_with_playwright_fallback(
                            url,
                            keep_open_on_captcha=True,
                            session_registry=ACTIVE_CAPTCHA_SESSIONS,
                            cookies=cookies,
                            user_agent=browser_profile["user_agent"],
                            viewport=browser_profile["viewport"],
                            launch_args=browser_profile["launch_args"],
                            init_scripts=browser_profile["init_scripts"],
                            locale="ru-RU",
                            timezone_id="Europe/Moscow",
                            proxy=None,
                            headless=True,
                            debug_bundle_id=debug_bundle_id,
                            **geolocation_kwarg,
                        )
                        if isinstance(retry_card_data, dict) and not retry_card_data.get("error"):
                            card_data = retry_card_data
                            card_error = ""
                            print("✅ Retry without proxy succeeded after parser_subprocess_exception", flush=True)
                        else:
                            retry_err = str((retry_card_data or {}).get("error") or "unknown")
                            print(f"❌ Retry without proxy returned error: {retry_err[:140]}", flush=True)
                    except Exception as retry_exc:
                        print(f"❌ Retry without proxy failed: {str(retry_exc)[:180]}", flush=True)
            if not card_error:
                _mark_proxy_result(proxy_id, success=True, reason="parse_ok")
            elif "captcha" in card_error.lower():
                _mark_proxy_result(proxy_id, success=False, reason=f"captcha:{card_error[:80]}")
            else:
                _mark_proxy_result(proxy_id, success=False, reason=card_error[:120])
        
        # Проверяем успешность парсинга (валидация только по данным Яндекса, без fallback из БД)
        validation_source = "2gis" if parsed_source == "2gis" else SOURCE_YANDEX_BUSINESS
        is_successful, reason, validation_result = _validate_parsing_result(card_data, source=validation_source)

        # пишем validation.json в bundle (если он есть)
        if bundle_dir and validation_result:
            try:
                v_path = os.path.join(bundle_dir, "validation.json")
                val_warnings = list(validation_result.get("warnings") or [])
                parser_warnings = list(card_data.get("warnings") or []) if isinstance(card_data, dict) else []
                all_warnings = list(dict.fromkeys(val_warnings + parser_warnings))
                payload = {
                    "is_successful": bool(is_successful),
                    "reason": str(reason),
                    "quality_score": validation_result.get("quality_score"),
                    "hard_missing": validation_result.get("hard_missing") or [],
                    "missing_fields": validation_result.get("missing_fields") or [],
                    "found_fields": validation_result.get("found_fields") or [],
                    "warnings": all_warnings,
                }
                with open(v_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
            except Exception as ve:
                print(f"⚠️ Failed to write validation.json: {ve}")

        # Лог покрытия полей (coverage), если валидация отработала
        if validation_result:
            found_fields = validation_result.get("found_fields", []) or []
            missing_fields = validation_result.get("missing_fields", []) or []
            hard_missing = validation_result.get("hard_missing", []) or []
            quality_score = validation_result.get("quality_score", 0.0)
            print(
                f"📊 Parsing coverage: found={len(found_fields)} "
                f"missing={len(missing_fields)} hard_missing={hard_missing} "
                f"quality={quality_score}"
            )

            # Собираем _meta и прикрепляем к card_data для сохранения в cards
            meta = build_parsing_meta(card_data, validation_result, source=validation_source)
            card_data["_meta"] = meta

        if isinstance(card_data, dict) and not card_data.get("error"):
            normalized_service_rows = map_card_services(
                card_data,
                str(queue_dict.get("business_id") or "unknown_business"),
                str(queue_dict.get("user_id") or "unknown_user"),
                source=parsed_source,
            )
            card_data["_service_rows"] = normalized_service_rows
            card_data["products"] = _service_rows_to_grouped_products(normalized_service_rows)

        if not is_successful and business_id:
            print(f"⚠️ Парсинг неполный ({reason}). Автоматический fallback отключен.")
        
        if card_data.get("error") == "captcha_detected":
            captcha_session_id = card_data.get("captcha_session_id")
            captcha_url = card_data.get("captcha_url") or queue_dict.get("url")
            attempt_no = _captcha_retry_attempt_from_error(queue_dict.get("error_message")) + 1
            max_captcha_attempts = max(1, int(os.getenv("CAPTCHA_AUTO_RETRY_MAX_ATTEMPTS", "4")))
            if attempt_no > max_captcha_attempts:
                print(
                    f"🛑 CAPTCHA retry exhausted in parse flow: task_id={queue_dict.get('id')} "
                    f"attempt={attempt_no} max={max_captcha_attempts}. Moving to DLQ.",
                    flush=True,
                )
                _move_task_to_dlq(
                    str(queue_dict.get("id")),
                    "captcha_retry_exhausted",
                    f"attempt={attempt_no}; max_attempts={max_captcha_attempts}; source=parse_flow",
                    clear_captcha_fields=True,
                )
                return
            retry_delay = _captcha_retry_delay_for_task(queue_dict, attempt_no)
            retry_after = datetime.now() + retry_delay
            captcha_comment = (
                f"captcha_auto_retry_attempt={attempt_no}; "
                f"captcha_required: {captcha_url or 'retry_scheduled'}"
            )
            captcha_comment = with_reason_code_prefix(STATUS_CAPTCHA, captcha_comment)
            if captcha_session_id:
                print(f"⚠️ Капча обнаружена, session_id={captcha_session_id} (human-in-the-loop)")
            else:
                print("⚠️ Капча обнаружена, но session_id отсутствует (registry недоступен)")

            # Открываем новое соединение только для обновления статуса капчи и сохранения метаданных
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                now_iso = datetime.now().isoformat()
                cursor.execute(
                    """
                    UPDATE parsequeue
                    SET status = %s,
                        retry_after = %s,
                        captcha_required = 1,
                        captcha_url = %s,
                        captcha_session_id = %s,
                        captcha_started_at = %s,
                        captcha_status = 'delayed_auto',
                        error_message = %s,
                        resume_requested = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        STATUS_CAPTCHA,
                        retry_after.isoformat(),
                        captcha_url,
                        captcha_session_id,
                        now_iso,
                        captcha_comment,
                        queue_dict["id"],
                    ),
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            if _is_mass_network_task(queue_dict):
                # Для массовых очередей по умолчанию НЕ паузим весь batch из-за одной капчи.
                # Иначе throughput резко падает и KPI по сети недостижим.
                if _env_bool("CAPTCHA_PAUSE_NETWORK_BATCH_ON_MASS", False):
                    _pause_network_batch_for_captcha(queue_dict["id"], captcha_comment, retry_delay)
                else:
                    print(
                        "ℹ️ Массовый batch: глобальная пауза на CAPTCHA отключена "
                        "(CAPTCHA_PAUSE_NETWORK_BATCH_ON_MASS=false)",
                        flush=True,
                    )
            elif _env_bool("CAPTCHA_PAUSE_BATCH_ON_HUMAN", False):
                _pause_network_batch_for_captcha(queue_dict["id"], captcha_comment, retry_delay)
            return

        # ШАГ 3: Сохраняем результаты (открываем новое соединение)
        if not is_successful and card_data.get("error") != "captcha_detected":
            print(f"❌ Парсинг неуспешен: {reason}. Сохранение отменено.")

            if _queue_transient_parse_retry(queue_dict, reason, card_data):
                return

            # Базовая причина
            err_msg = str(reason)

            # Привязываем путь к debug bundle, если он был создан
            debug_dir = os.getenv("DEBUG_DIR", "/app/debug_data").rstrip("/")
            if debug_bundle_id:
                bundle_path = f"{debug_dir}/{debug_bundle_id}"
                err_msg = f"{err_msg} bundle={bundle_path}"

            business_id = queue_dict.get("business_id")
            preserve_existing_snapshot = (
                str(reason).startswith("low_quality_payload:")
                and bool(business_id)
                and _has_existing_card_snapshot(str(business_id))
            )

            if preserve_existing_snapshot:
                warning_msg = f"{err_msg} preserved_existing_snapshot=1"
                print(
                    f"⚠️ Слабый payload для business_id={business_id}; "
                    "существующий snapshot сохранён, задача помечена completed.",
                    flush=True,
                )
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE parsequeue
                    SET status = %s,
                        error_message = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (STATUS_COMPLETED, warning_msg, queue_dict["id"]),
                )
                conn.commit()
                cursor.close()
                conn.close()
                return

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE parsequeue
                SET status = %s,
                    error_message = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (STATUS_ERROR, err_msg, queue_dict["id"]),
            )
            conn.commit()
            cursor.close()
            conn.close()
            return

        business_id = queue_dict.get("business_id")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if business_id:
                # Сохраняем в cards (Postgres source of truth)
                print(f"📊 Сохраняю результаты в cards для business_id={business_id}")
                
                try:
                    analysis_data = {
                        'score': 50,
                        'recommendations': [],
                        'ai_analysis': {},
                    }
                    report_path = None
                    if _env_bool("WORKER_ENABLE_AI_ANALYSIS", False):
                        from gigachat_analyzer import analyze_business_data
                        from report import generate_html_report

                        print(f"🤖 Запускаем GigaChat анализ для {business_id}...")
                        analysis_result = analyze_business_data(card_data)
                        analysis_data = {
                            'score': analysis_result.get('score', 50),
                            'recommendations': analysis_result.get('recommendations', []),
                            'ai_analysis': analysis_result.get('analysis', {}),
                        }

                        report_path = generate_html_report(card_data, analysis_data, {})
                        print(f"📄 Отчет сгенерирован: {report_path}")
                    else:
                        print("⏭️ AI-анализ отключен (WORKER_ENABLE_AI_ANALYSIS=false)", flush=True)
                    
                    rating = card_data.get('overview', {}).get('rating', '') or ''
                    reviews_count = card_data.get('reviews_count') or card_data.get('overview', {}).get('reviews_count') or 0
                    reviews = card_data.get('reviews', [])
                    if isinstance(reviews, dict) and 'items' in reviews:
                        reviews_list = reviews['items']
                    elif isinstance(reviews, list):
                        reviews_list = reviews
                    else:
                        reviews_list = []
                    
                    parsed_reviews_count = len(reviews_list)
                    if parsed_reviews_count > int(reviews_count or 0):
                        reviews_count = parsed_reviews_count
                    
                    reviews_count = _normalize_reviews_count(reviews_count)
                    photos_count = card_data.get('photos_count') or 0
                    try:
                        photos_count = int(photos_count)
                    except (ValueError, TypeError):
                        photos_count = 0
                    
                    phone = card_data.get('phone', '') or ''
                    website = card_data.get('site', '') or card_data.get('website', '') or ''
                    hours_full = card_data.get('hours_full', [])
                    hours_struct = {'schedule': hours_full} if hours_full else None
                    competitors = card_data.get('competitors', [])
                    products = card_data.get('products', [])
                    news_list = card_data.get('news') or card_data.get('posts') or []
                    if not isinstance(news_list, list):
                        news_list = []
                    
                    rating_float = _normalize_rating_value(rating)
                    
                    # Готовим overview с метой парсинга
                    overview_payload = {
                        'photos_count': photos_count,
                        'news_count': len(news_list),
                        'snapshot_type': 'full',
                    }
                    if card_data.get("_meta"):
                        overview_payload["_meta"] = card_data["_meta"]

                    db_manager = DatabaseManager()
                    services_saved_count = 0
                    try:
                        _photos = card_data.get("photos") or []
                        if isinstance(_photos, int):
                            _photos = []
                        db_manager.save_new_card_version(
                            business_id,
                            url=queue_dict["url"],
                            title=(card_data.get('name') or card_data.get('title') or ''),
                            address=(card_data.get('address') or ''),
                            phone=phone or None,
                            site=website or None,
                            rating=rating_float,
                            reviews_count=reviews_count,
                            overview=overview_payload,
                            products=products or None,
                            news=news_list or None,
                            photos=_photos if _photos else None,
                            competitors=competitors or None,
                            hours=hours_struct,
                            hours_full=hours_full or None,
                            report_path=report_path,
                            ai_analysis=analysis_data.get('ai_analysis'),
                            # Сохраняем пустой список как [] (а не NULL), чтобы отличать
                            # "нет рекомендаций" от "поле отсутствует"
                            recommendations=analysis_data.get('recommendations', []),
                        )

                        # Синхронизируем агрегированные поля в businesses (rich model)
                        try:
                            sync_payload = {
                                "address": card_data.get("address"),
                                "phone": phone or None,
                                "site": website or None,
                                "rating": rating_float,
                                "reviews_count": reviews_count,
                                "categories": card_data.get("categories"),
                                "hours": hours_struct,
                                "hours_full": hours_full or None,
                                "description": card_data.get("description") or (card_data.get("overview") or {}).get("description"),
                                "industry": card_data.get("industry"),
                                "geo": card_data.get("geo"),
                                "external_ids": card_data.get("external_ids"),
                            }
                            db_manager.update_business_from_card(business_id, sync_payload)
                            # Услуги из карточки → userservices (для вкладки «Услуги и цены»)
                            owner_id = (db_manager.get_business_by_id(business_id) or {}).get("owner_id")
                            if owner_id and (card_data.get("products") or card_data.get("services")):
                                try:
                                    service_rows = card_data.get("_service_rows")
                                    if not isinstance(service_rows, list):
                                        service_rows = map_card_services(card_data, business_id, owner_id)
                                    if service_rows:
                                        services_saved_count = db_manager.upsert_parsed_services(business_id, owner_id, service_rows)
                                        print(f"[Services] Saved {services_saved_count} services")
                                    else:
                                        # Безопасный режим: если парсер вернул только редакционные подборки
                                        # или пустой список после фильтров, не скрываем ранее сохранённые услуги.
                                        print(
                                            f"[Services] Skip source deactivation for business_id={business_id}: "
                                            "no valid parsed service rows after normalization"
                                        )
                                except Exception as svc_e:
                                    print(f"⚠️ upsert_parsed_services failed for {business_id}: {svc_e}")
                        except Exception as sync_e:
                            print(f"⚠️ Failed to update businesses from card for {business_id}: {sync_e}")

                    except Exception as e:
                        # Помечаем задачу как ошибочной, чтобы не зависала в processing
                        err_text = f"save_failed:{e.__class__.__name__}:{e}"
                        _handle_worker_error(queue_dict["id"], err_text)
                        db_manager.close()
                        raise
                    else:
                        # MapParseResults для обратной совместимости (Progress, growth_api)
                        try:
                            mpr_fields = {
                                'rating': rating_float,
                                'reviews_count': reviews_count,
                                'photos_count': photos_count,
                                'news_count': len(news_list or []),
                            }
                            print(f"[METRICS_SAVE] {business_id} | rating={mpr_fields['rating']} | reviews={mpr_fields['reviews_count']} | photos={mpr_fields['photos_count']} | news={mpr_fields['news_count']}")
                            _upsert_map_parse_from_card(
                                db_manager.conn,
                                business_id,
                                url=queue_dict["url"],
                                map_type=("2gis" if parsed_source == "2gis" else "yandex"),
                                rating=mpr_fields['rating'],
                                reviews_count=mpr_fields['reviews_count'],
                                photos_count=mpr_fields['photos_count'],
                                news_count=mpr_fields['news_count'],
                                products=products if products else None,
                                competitors=competitors if competitors else None,
                            )
                        except Exception as mpr_e:
                            print(f"❌ [MapParseResults] Failed for {business_id}: {mpr_e}")
                            traceback.print_exc()
                        db_manager.close()

                    # Диагностический лог: одна строка, без секретов
                    title_snippet = (card_data.get('name') or card_data.get('title') or '')[:80]
                    _products = card_data.get("products") or []
                    _news = card_data.get("news") or []
                    _photos = card_data.get("photos") or []
                    if isinstance(_photos, int):
                        _photos = []
                    _competitors = card_data.get("competitors") or []
                    _hours_full = card_data.get("hours_full") or []
                    print(
                        f"[PARSE_DIAG] business_id={business_id} queue_id={queue_dict.get('id')} "
                        f"title={title_snippet!r} address_present={bool(card_data.get('address'))} "
                        f"rating={rating_float} reviews_count={reviews_count} "
                        f"products_len={len(_products) if isinstance(_products, list) else 0} "
                        f"news_len={len(_news) if isinstance(_news, list) else 0} "
                        f"photos_len={len(_photos) if isinstance(_photos, list) else 0} "
                        f"competitors_len={len(_competitors) if isinstance(_competitors, list) else 0} "
                        f"hours_full_len={len(_hours_full) if isinstance(_hours_full, list) else 0} "
                        f"services_saved_count={services_saved_count}"
                    )
                    print(f"✅ Результаты сохранены в cards для business_id={business_id}")
                    
                    # --- ИНИЦИАЛИЗАЦИЯ SyncWorker ДЛЯ СОХРАНЕНИЯ ДЕТАЛЬНЫХ ДАННЫХ ---
                    try:
                        import re
                        
                        db_manager = None
                        try:
                            # Используем DatabaseManager для работы с репозиториями
                            db_manager = DatabaseManager()
                            sync_worker = YandexBusinessSyncWorker()
                            external_source_value = (
                                ExternalSource.TWO_GIS
                                if parsed_source == "2gis"
                                else ExternalSource.YANDEX_MAPS
                            )
                            
                            # DEBUG LOGGING
                            try:
                                from worker_debug_helper import debug_log
                                from safe_db_utils import get_db_path
                                db_path_debug = get_db_path()
                                r_len = len(reviews_list) if reviews_list else 0
                                # Расчёт неотвеченных отзывов (если reviews_list определён)
                                if 'reviews_list' in locals() and reviews_list:
                                    unanswered_reviews_count = sum(
                                        1 for r in reviews_list
                                        if not r.get("org_reply")
                                    )
                                else:
                                    unanswered_reviews_count = 0
                                debug_log(f"Worker DB Path: {db_path_debug}")
                                debug_log(f"Reviews in list: {r_len}")
                                debug_log(f"Unanswered calc: {unanswered_reviews_count}")
                            except Exception as e:
                                print(f"Debug log fail: {e}")
                            
                            # 1. СОХРАНЕНИЕ ОТЗЫВОВ (С ДЕДУПЛИКАЦИЕЙ)
                            if reviews_list:
                                external_reviews = []
                                seen_review_ids = set()
                                
                                for review in reviews_list:
                                    if not review.get('text'):
                                        continue
                                    
                                    # Дедупликация: используем ID отзыва или хеш от текста+автора
                                    raw_id = review.get('id')
                                    if raw_id:
                                        unique_key = str(raw_id)
                                    else:
                                        author = review.get('author') or 'Anon'
                                        text_snippet = (review.get('text') or '')[:50]
                                        unique_key = f"{author}_{text_snippet}"
                                        
                                    if unique_key in seen_review_ids:
                                        continue
                                    seen_review_ids.add(unique_key)
                                    
                                    # Генерируем ID для нашей БД (детерминированный, чтобы избегать дублей)
                                    # Используем business_id + author + text snippet (без ответа, чтобы ответ обновлял запись, а не создавал новую)
                                    text_part = (review.get('text') or '').strip()
                                    unique_string = f"{business_id}_{review.get('author')}_{text_part}"
                                    review_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))
                                    external_review_id = raw_id or f"html_{review_id}"
                                    
                                    # Инициализация переменных
                                    published_at = None
                                    response_text = None
                                    response_at = None
                                    
                                    # Парсим дату
                                    date_value = _extract_date_from_review(review)
                                    
                                    if date_value:
                                        if isinstance(date_value, (int, float)):
                                            published_at = _parse_timestamp_to_datetime(date_value)
                                        elif isinstance(date_value, str):
                                            published_at = _parse_date_string(date_value)
                                    
                                    # Ответ организации
                                    response_text = review.get('org_reply') or review.get('response_text') or ''
                                    response_text = response_text.strip() if response_text else None
                                    response_at = None
                                    
                                    if review.get('response_date'):
                                        response_at = _parse_date_string(str(review.get('response_date')))
                                    
                                    # Рейтинг
                                    r_val = review.get('score') or review.get('rating')
                                    try:
                                        r_val = int(r_val) if r_val else None
                                    except:
                                        r_val = None
                                    
                                    external_review = ExternalReview(
                                        id=review_id,
                                        business_id=business_id,
                                        source=external_source_value,
                                        external_review_id=external_review_id,
                                        rating=r_val,
                                        author_name=review.get('author') or 'Анонимный пользователь',
                                        text=review.get('text'),
                                        published_at=published_at,
                                        response_text=response_text,
                                        response_at=response_at,
                                        raw_payload=review
                                    )
                                    external_reviews.append(external_review)
                                
                                if external_reviews:
                                    sync_worker._upsert_reviews(db_manager, external_reviews)
                                    db_manager.conn.commit()
                                    print(f"✅ Saved {len(external_reviews)} reviews to ExternalBusinessReviews")

                            # 2. СОХРАНЕНИЕ НОВОСТЕЙ (Posts)
                            news_items = card_data.get('news') or card_data.get('posts') or []
                            if news_items:
                                external_posts = []
                                for item in news_items:
                                    post_text = item.get('text')
                                    if not post_text:
                                        continue
                                        
                                    post_id = str(uuid.uuid4())
                                    # Пытаемся дату достать
                                    pub_at = None
                                    if item.get('date'):
                                        pub_at = _parse_date_string(item['date'])
                                        
                                    ext_post = ExternalPost(
                                        id=post_id,
                                        business_id=business_id,
                                        source=external_source_value,
                                        external_post_id=f"html_{post_id}", # Нет реального ID в HTML
                                        title=item.get('title') or (post_text[:30] + '...'),
                                        text=post_text,
                                        published_at=pub_at, # Keep None if not found, don't fake it with now()
                                        image_url=None, # HTML scraper rarely gets clean image URLs for news context
                                        raw_payload=item
                                    )
                                    external_posts.append(ext_post)
                                
                                if external_posts:
                                    try:
                                        sync_worker._upsert_posts(db_manager, external_posts)
                                        print(f"✅ Saved {len(external_posts)} posts to ExternalBusinessPosts")
                                    except Exception as posts_err:
                                        # Не блокируем синк услуг/статистики, если таблица постов ещё не мигрирована.
                                        print(f"⚠️ Skip posts sync (ExternalBusinessPosts unavailable): {posts_err}")

                            # 3. СОХРАНЕНИЕ УСЛУГ (Services)
                            products = card_data.get('products')
                            if products:
                                services_count = len(products)
                                # Fetch owner_id for service syncing
                                cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (business_id,))
                                owner_row = cursor.fetchone()
                                if owner_row:
                                    owner_id = owner_row[0] if isinstance(owner_row, (list, tuple)) else owner_row.get("owner_id")
                                    sync_worker._sync_services_to_db(db_manager.conn, business_id, products, owner_id)
                                    print(f"💾 Синхронизировано {services_count} услуг (owner_id={owner_id})")
                                else:
                                    print(f"⚠️ Cannot sync services: owner_id not found for business {business_id}")

                            # 4. СОХРАНЕНИЕ СТАТИСТИКИ (Rating History)
                            if rating and reviews_count is not None:
                                today = datetime.now().strftime('%Y-%m-%d')
                                stats_id = make_stats_id(business_id, external_source_value, today)
                                
                                try:
                                    rating_val = float(rating)
                                except:
                                    rating_val = 0.0
                                    
                                stat_point = ExternalStatsPoint(
                                    id=stats_id,
                                    business_id=business_id,
                                    source=external_source_value,
                                    date=today,
                                    rating=rating_val,
                                    reviews_total=reviews_count,
                                    # Остальные поля None, так как публичные карты их не дают
                                    views_total=None,
                                    actions_total=None
                                )
                                sync_worker._upsert_stats(db_manager, [stat_point])
                                print(f"💾 Сохранена статистика (Рейтинг: {rating_val}, Отзывов: {reviews_count})")

                            # Commit changes to External Data tables
                            if db_manager and db_manager.conn:
                                db_manager.conn.commit()
                                print("💾 Detailed data committed successfully")

                        finally:
                            if db_manager:
                                db_manager.close()
                                
                    except Exception as det_err:
                        print(f"⚠️ Ошибка сохранения детальных данных (reviews/posts/stats): {det_err}")
                        traceback.print_exc()

                except Exception as e:
                    print(f"⚠️ Ошибка сохранения в cards: {e}")
                    traceback.print_exc()
                    try:
                        from user_api import send_email
                        send_email(
                            "demyanovap@yandex.ru",
                            "Ошибка парсинга карты",
                            f"URL: {queue_dict['url']}\nBusiness ID: {business_id}\nОшибка: {e}"
                        )
                    except:
                        pass
                    raise
            else:
                # Старая логика: сохраняем в Cards
                card_id = str(uuid.uuid4())
                
                rating = card_data.get("rating")
                if rating == "" or rating is None:
                    rating = None
                else:
                    try:
                        rating = float(rating)
                    except (ValueError, TypeError):
                        rating = None
                        
                reviews_count = card_data.get("reviews_count")
                if reviews_count == "" or reviews_count is None:
                    reviews_count = None
                else:
                    try:
                        reviews_count = int(reviews_count)
                    except (ValueError, TypeError):
                        reviews_count = None
                
                cursor.execute("""
                    INSERT INTO cards (
                        id, user_id, url, title, address, phone, site, rating,
                        reviews_count, categories, overview, products, news,
                        photos, features_full, competitors, hours, hours_full,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    card_id,
                    queue_dict["user_id"],
                    queue_dict["url"],
                    card_data.get("title"),
                    card_data.get("address"),
                    card_data.get("phone"),
                    card_data.get("site"),
                    rating,
                    reviews_count,
                    json.dumps(card_data.get("categories", [])),
                    json.dumps(
                        {
                            **(card_data.get("overview") or {}),
                            **({"_meta": card_data["_meta"]} if card_data.get("_meta") else {}),
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(card_data.get("products", [])),
                    json.dumps(card_data.get("news") or card_data.get("posts") or []),
                    json.dumps(card_data.get("photos", [])),
                    json.dumps(card_data.get("features_full", {})),
                    json.dumps(card_data.get("competitors", [])),
                    card_data.get("hours"),
                    json.dumps(card_data.get("hours_full", [])),
                    datetime.now().isoformat()
                ))
                
                # Попытка синхронизации сервисов даже для старой схемы (если есть owner_id)
                # Но у нас нет business_id здесь, поэтому пропускаем
                pass
                
                if _env_bool("WORKER_ENABLE_AI_ANALYSIS", False):
                    print(f"Выполняем ИИ-анализ для карточки {card_id}...")

                    try:
                        analysis_result = analyze_business_data(card_data)

                        cursor.execute("""
                            UPDATE cards SET
                                ai_analysis = %s,
                                seo_score = %s,
                                recommendations = %s
                            WHERE id = %s
                        """, (
                            json.dumps(analysis_result.get('analysis', {})),
                            analysis_result.get('score', 50),
                            json.dumps(analysis_result.get('recommendations', [])),
                            card_id
                        ))

                        print(f"ИИ-анализ завершён для карточки {card_id}")

                        try:
                            from report import generate_html_report
                            analysis_data = {
                                'score': analysis_result.get('score', 50),
                                'recommendations': analysis_result.get('recommendations', []),
                                'ai_analysis': analysis_result.get('analysis', {})
                            }
                            report_path = generate_html_report(card_data, analysis_data)
                            print(f"HTML отчёт сгенерирован: {report_path}")
                            cursor.execute("UPDATE cards SET report_path = %s WHERE id = %s", (report_path, card_id))
                        except Exception as report_error:
                            print(f"Ошибка при генерации отчёта для карточки {card_id}: {report_error}")

                    except Exception as analysis_error:
                        print(f"Ошибка при ИИ-анализе карточки {card_id}: {analysis_error}")
                else:
                    print("⏭️ ИИ-анализ карточки пропущен (WORKER_ENABLE_AI_ANALYSIS=false)", flush=True)
            
            # Обновляем статус на "completed" (чтобы задача осталась в списке)
            warning_parts = []
            # Старое предупреждение про HTML fallback (если используется быстрый эндпоинт)
            if card_data.get('fallback_used'):
                warning_parts.append("⚠️ Fast Endpoint Outdated (Used HTML Fallback)")

            # Alert 2nd-level: парсер вернул products, но в userservices ничего не сохранилось.
            # Это сигнализирует о возможном дрейфе схемы/маппера и не должен оставаться незамеченным.
            try:
                products_len = len(products) if isinstance(products, list) else 0
            except Exception:
                products_len = 0
            if products_len > 0 and int(services_saved_count or 0) == 0:
                services_alert = (
                    f"services_upsert_zero:products_len={products_len},services_saved_count=0"
                )
                warning_parts.append(services_alert)
                print(
                    f"[SERVICES_ALERT] queue_id={queue_dict.get('id')} "
                    f"business_id={business_id} {services_alert}",
                    flush=True,
                )

            # Предупреждения по отсутствующим CRITICAL-полям в источнике
            if validation_result:
                missing_fields = set(validation_result.get("missing_fields", []) or [])
                critical_missing = [f for f in FIELDS_CRITICAL if f in missing_fields]
                if critical_missing:
                    warning_parts.append(
                        "warnings_missing_in_source:" + ",".join(critical_missing)
                    )

            warning_msg = " | ".join(warning_parts) if warning_parts else None

            # Обновляем completed: error_message = NULL, warnings — с безопасным fallback при UndefinedColumn
            try:
                cursor.execute(
                    "UPDATE parsequeue SET status = %s, error_message = NULL, warnings = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (STATUS_COMPLETED, warning_msg, queue_dict["id"]),
                )
            except Exception as upd_err:
                # Fallback только для PostgreSQL UndefinedColumn (pgcode 42703).
                if getattr(upd_err, "pgcode", None) == "42703":
                    # Колонки warnings нет — пишем предупреждения в error_message только в этом fallback
                    cursor.execute(
                        "UPDATE parsequeue SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (STATUS_COMPLETED, warning_msg, queue_dict["id"]),
                    )
                else:
                    raise
            conn.commit()

            if queue_dict.get("_resume_batch_after_captcha"):
                _resume_network_batch_after_captcha(queue_dict["id"])
            
            print(f"✅ Заявка {queue_dict['id']} обработана и удалена из очереди.")
            signal.alarm(0)  # Отключаем таймаут при успехе
            
        finally:
            try:
                if 'cursor' in locals() and cursor:
                    cursor.close()
            except:
                pass
            try:
                if 'conn' in locals() and conn:
                    conn.close()
            except:
                pass
            
    except Exception as e:
        signal.alarm(0)  # Отключаем таймаут при ошибке
        queue_id = queue_dict.get('id', 'unknown') if queue_dict else 'unknown'
        print(f"❌ Ошибка при обработке заявки {queue_id}: {e}")
        traceback.print_exc()
        
        _handle_worker_error(queue_id, str(e))
        print(f"⚠️ Заявка {queue_id} помечена как ошибка.")
        
        # Отправляем email (ошибка не критична)
        try:
            from user_api import send_email
            send_email(
                "demyanovap@yandex.ru",
                "Ошибка парсинга карты",
                f"URL: {queue_dict.get('url', 'unknown') if queue_dict else 'unknown'}\nОшибка: {e}"
            )
        except Exception as email_error:
            print(f"⚠️ Не удалось отправить email: {email_error}")

def map_card_services(
    card_data: Dict[str, Any],
    business_id: str,
    user_id: str,
    source: str = "yandex_maps",
) -> List[Dict[str, Any]]:
    """
    Чистый маппер: из card_data (products/services) в список строк для userservices.
    Поддерживает структуру: список категорий с items или плоский список элементов.
    """
    products = card_data.get("products") or card_data.get("services") or []
    print(f"[map_card_services] Found {len(products) if isinstance(products, list) else 0} product categories for {business_id}")
    if not products:
        print(f"[map_card_services] No products in card_data. Keys: {list(card_data.keys())}")
        return []
    if not isinstance(products, list):
        print(f"[map_card_services] No products in card_data. Keys: {list(card_data.keys())}")
        return []
    rows = []
    seen = set()
    normalized_source = str(source or "yandex_maps").strip().lower() or "yandex_maps"
    for cat_block in products:
        # cat_block может быть: dict (категория), list (вложенные items), или мусор
        if isinstance(cat_block, list):
            # Плоский список items без обёртки категории
            items = cat_block
            for item in items:
                if isinstance(item, dict) and item.get("name"):
                    row = _one_service_row(item, business_id, user_id, normalized_source)
                    if row:
                        item_category = _extract_service_category(item)
                        if item_category:
                            row["category"] = item_category
                        key = (
                            (row.get("source") or "").lower(),
                            (row.get("name") or "").strip().lower(),
                            (row.get("category") or "").strip().lower(),
                            str(row.get("price_from") or ""),
                            str(row.get("price_to") or ""),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append(row)
            continue

        if not isinstance(cat_block, dict):
            # Примитивы и неизвестные типы — пропускаем
            continue

        # Вариант: в products пришел плоский список услуг (без items)
        if cat_block.get("name") and not (cat_block.get("items") or cat_block.get("products")):
            row = _one_service_row(cat_block, business_id, user_id, normalized_source)
            if row:
                key = (
                    (row.get("source") or "").lower(),
                    (row.get("name") or "").strip().lower(),
                    (row.get("category") or "").strip().lower(),
                    str(row.get("price_from") or ""),
                    str(row.get("price_to") or ""),
                )
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
            continue

        # Стандартная структура: dict с category/group/name и items
        category_name = _extract_service_category(cat_block, allow_name_fallback=False) or ""
        items = cat_block.get("items") or cat_block.get("products") or []
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            row = _one_service_row(item, business_id, user_id, normalized_source)
            if row:
                item_category = _extract_service_category(item)
                inferred_category = _infer_service_category(str(row.get("name") or ""), str(row.get("description") or ""))
                effective_category = item_category or category_name or inferred_category or "Общие услуги"
                if _is_editorial_category_name(effective_category):
                    effective_category = inferred_category or "Общие услуги"
                row["category"] = effective_category
                key = (
                    (row.get("source") or "").lower(),
                    (row.get("name") or "").strip().lower(),
                    (row.get("category") or "").strip().lower(),
                    str(row.get("price_from") or ""),
                    str(row.get("price_to") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    return rows


def _one_service_row(item: Dict[str, Any], business_id: str, user_id: str, source: str) -> Dict[str, Any]:
    """Один элемент услуги в нормализованном виде для userservices."""
    name = re.sub(r"\s+", " ", str(item.get("name") or "")).strip() or None
    if not name:
        return {}
    if len(name) > 120 or len(name) < 2:
        return {}
    lower_name = name.lower()
    description = re.sub(r"\s+", " ", str(item.get("description") or "")).strip() or None
    if description and len(description) > 1000:
        description = description[:1000].rstrip()
    combined_text = f"{name} {description or ''}".lower()
    if any(pattern in combined_text for pattern in _EDITORIAL_SERVICE_PATTERNS):
        print(f"⚠️ [map_card_services] Skip editorial listing: {name}")
        return {}
    if any(term in lower_name for term in _SERVICE_NOISE_TERMS):
        return {}
    if "http://" in lower_name or "https://" in lower_name or "yandex." in lower_name:
        print(f"⚠️ [map_card_services] Skip URL-like service title: {name}")
        return {}
    if "|" in name and len(name.split()) >= 6:
        return {}
    if re.search(r"[✅❌🔥⭐✨💥]", name) and "₽" in name and " за " in lower_name:
        print(f"⚠️ [map_card_services] Skip promo-like noisy title: {name}")
        return {}
    if (
        (description or "").lower().startswith("рассказываем")
        or (description or "").lower().startswith("выбрали")
        or (description or "").lower().startswith("собрали")
    ):
        print(f"⚠️ [map_card_services] Skip non-service description: {name}")
        return {}
    external_id = item.get("id") or item.get("external_id")
    if external_id is not None:
        external_id = str(external_id).strip() or None
    raw_price = item.get("price") or item.get("price_from") or ""
    price_from, price_to = _parse_service_price(raw_price)
    if not price_from and not price_to:
        # Доп. защита от редакционных подборок, которые иногда попадают в products API
        # и не являются услугами конкретного бизнеса.
        if ":" in name or len(name.split()) >= 7 or "," in name:
            print(f"⚠️ [map_card_services] Skip long editorial-like title without price: {name}")
            return {}
    inferred_category = _extract_service_category(item) or _infer_service_category(name, description or "")
    return {
        "business_id": business_id,
        "user_id": user_id,
        "name": name,
        "description": description,
        "category": inferred_category or "Общие услуги",
        "source": source,
        "external_id": external_id,
        "price_from": price_from,
        "price_to": price_to,
        "raw": (dict(item) if isinstance(item, dict) else {"_error": "not_a_dict", "_type": type(item).__name__}),
        "duration_minutes": item.get("duration_minutes") or item.get("duration"),
    }


def _deactivate_parsed_service_source(conn, business_id: str, source: str) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE userservices
        SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
        WHERE business_id = %s
          AND source = %s
          AND raw IS NOT NULL
          AND COALESCE(is_active, TRUE) = TRUE
        """,
        (business_id, source),
    )
    conn.commit()
    return int(cursor.rowcount or 0)


def _extract_service_category(payload: Dict[str, Any], *, allow_name_fallback: bool = False) -> str:
    """Извлекает категорию услуги из разных форматов ответа парсера."""
    if not isinstance(payload, dict):
        return ""
    raw = (
        payload.get("category")
        or payload.get("category_name")
        or payload.get("categoryName")
        or payload.get("group")
        or payload.get("group_name")
        or payload.get("groupName")
        or payload.get("section")
        or payload.get("section_name")
        or payload.get("sectionName")
    )
    if raw in (None, "") and allow_name_fallback:
        raw = payload.get("name") or payload.get("title")
    if isinstance(raw, dict):
        raw = raw.get("name") or raw.get("title") or raw.get("value")
    if raw is None:
        return ""
    category = str(raw).strip()
    if not category:
        return ""
    category_lower = category.lower()
    if "http://" in category.lower() or "https://" in category.lower() or "yandex." in category.lower():
        return ""
    if len(category) > 80:
        return ""
    if category_lower in _GENERIC_SERVICE_CATEGORIES:
        return ""
    if _is_editorial_category_name(category):
        return ""
    return category


def _is_editorial_category_name(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    if len(text) > 70:
        return True
    if any(pattern in text for pattern in _EDITORIAL_SERVICE_PATTERNS):
        return True
    if "с наградой" in text or "хорошее место" in text:
        return True
    if "суши" in text or "бар" in text or "паб" in text:
        return True
    if text.startswith("где ") or text.startswith("лучшие "):
        return True
    return False


def _infer_service_category(name: str, description: str = "") -> str:
    text = f"{name or ''} {description or ''}".lower()
    if not text.strip():
        return ""

    rules = (
        ("Косметология", ("косметолог", "чистк", "пилинг", "ботокс", "биорев", "мезотерап", "контурн", "филлер")),
        ("Инъекционные процедуры", ("инъекц", "биорев", "мезотерап", "ботокс", "диспорт", "филлер")),
        ("Эпиляция", ("эпиляц", "лазерн", "шугаринг", "воск")),
        ("Массаж", ("массаж", "лимфодренаж", "релакс", "спа")),
        ("Маникюр и педикюр", ("маникюр", "педикюр", "ногт", "гель", "шеллак")),
        ("Брови и ресницы", ("бров", "ресниц", "ламин", "микроблейд", "татуаж")),
        ("Парикмахерские услуги", ("стрижк", "окрашив", "укладк", "волос", "прическ", "барбер")),
        ("Консультации", ("консультац", "прием", "диагност", "осмотр")),
    )
    for category, tokens in rules:
        if any(token in text for token in tokens):
            return category
    return ""


def _parse_service_price(raw_price: Any) -> tuple[Optional[float], Optional[float]]:
    """Нормализует цену из строки Яндекс.Карт в рубли."""
    if raw_price is None:
        return None, None
    s = str(raw_price).strip()
    if not s:
        return None, None
    numbers = re.findall(r"\d+", s)
    if not numbers:
        return None, None
    try:
        # Явный диапазон: "1000-1500", "1000 – 1500", "от 1000 до 1500"
        if len(numbers) >= 2 and (re.search(r"[-–—]", s) or " до " in s.lower()):
            n1, n2 = int(numbers[0]), int(numbers[1])
            return float(min(n1, n2)), float(max(n1, n2))

        # Тысячные разделители: "1.650", "1,650", "1 650" => 1650
        if len(numbers) >= 2:
            compact = "".join(numbers[:2])
            if compact.isdigit():
                return float(int(compact)), float(int(compact))

        n = int(numbers[0])
        return float(n), float(n)
    except (ValueError, TypeError):
        return None, None


def _normalize_rating_value(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        rating = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if rating < 0 or rating > 5.0:
        return None
    return rating


def _normalize_reviews_count(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, count)


def _format_service_price_text(price_from: Optional[float], price_to: Optional[float], raw_payload: Dict[str, Any]) -> str:
    if isinstance(raw_payload, dict):
        raw_price = raw_payload.get("price")
        if isinstance(raw_price, str) and raw_price.strip():
            return raw_price.strip()
    if price_from and price_to and price_from != price_to:
        return f"{int(price_from)}-{int(price_to)} ₽"
    if price_from:
        return f"{int(price_from)} ₽"
    return ""


def _service_rows_to_grouped_products(service_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in service_rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        category = str(row.get("category") or "Общие услуги").strip() or "Общие услуги"
        raw_payload = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        item_payload = {
            "name": name,
            "price": _format_service_price_text(row.get("price_from"), row.get("price_to"), raw_payload),
            "description": str(row.get("description") or "").strip(),
            "category": category,
        }
        grouped.setdefault(category, []).append(item_payload)
    return [{"category": category, "items": items} for category, items in grouped.items() if items]


def _sync_parsed_services_to_db(business_id: str, products: list, conn, owner_id: str):
    """
    Синхронизирует распаршенные услуги в таблицу UserServices.
    Добавляет новые, обновляет цены существующих.
    """
    if not products:
        return

    # STRICT CHECK: owner_id required
    if not owner_id:
        print(f"⚠️ Service sync skipped: owner_id is missing for business {business_id}")
        # Raising error to fail fast as per plan, but let's confirm logic
        raise ValueError(f"owner_id (str) is required for service sync for business {business_id}")

    cursor = conn.cursor()
    
    # Старый путь синхронизации в таблицу UserServices использует SQLite-специфичные конструкции.
    # В PostgreSQL основной источник правды по услугам — YandexBusinessSyncWorker и связанные таблицы,
    # поэтому здесь просто выходим, чтобы не ломать worker.
    if DB_TYPE == "postgres":
        print(f"⚠️ Service sync via _sync_parsed_services_to_db пропущен для Postgres (business_id={business_id})")
        return

    # 1. Проверяем наличие таблицы UserServices и нужных колонок (SQLite)
    cursor.execute("SELECT to_regclass('public.userservices')")
    if not cursor.fetchone():
        # Если таблицы нет, создаём (должна быть, но на всякий случай)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS UserServices (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                price INTEGER, -- цена в копейках
                duration INTEGER DEFAULT 60,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
            )
        """
        )
    
    count_new = 0
    count_updated = 0
    
    print(f"👤 Syncing services for owner_id: {owner_id}")
    
    for category_data in products:


        category_name = category_data.get('category', 'Разное')
        items = category_data.get('items', [])
        
        for item in items:
            name = item.get('name')
            if not name:
                continue
                
            raw_price = item.get('price', '')
            description = item.get('description', '')
            
            # Парсинг цены
            price_cents = None
            if raw_price:
                # Удаляем все нецифровые символы кроме разделителей
                try:
                    # Ищем числа в строке
                    import re
                    # "от 1 500 ₽" -> "1500"
                    digits = re.sub(r'[^0-9]', '', str(raw_price))
                    if digits:
                        price_cents = int(digits) * 100 # В копейки
                except:
                    pass
            
            # Ищем существующую услугу по имени и business_id
            cursor.execute(
                """
                SELECT id FROM userservices
                WHERE business_id = %s AND name = %s
                """,
                (business_id, name),
            )
            row = cursor.fetchone()
            service_id = (row[0] if isinstance(row, (list, tuple)) else row.get("id")) if row else None

            if service_id:
                cursor.execute(
                    """
                    UPDATE userservices
                    SET price = %s, description = %s, category = %s, updated_at = CURRENT_TIMESTAMP, is_active = TRUE
                    WHERE id = %s
                    """,
                    (price_cents, description, category_name, service_id),
                )
                count_updated += 1
            else:
                service_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO userservices (id, business_id, user_id, name, description, category, price, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                    """,
                    (service_id, business_id, owner_id, name, description, category_name, price_cents),
                )
                count_new += 1
                
    conn.commit()
    print(f"📊 Синхронизация услуг завершена: {count_new} новых, {count_updated} обновлено.")

def _process_sync_yandex_business_task(queue_dict):
    """Обработка синхронизации Яндекс.Бизнес через кабинет"""
    import signal
    import sys
    
    # Устанавливаем таймаут 10 минут для задачи
    def timeout_handler(signum, frame):
        raise TimeoutError("Задача синхронизации превысила таймаут 10 минут")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(600)  # 10 минут
    
    try:
        business_id = queue_dict.get("business_id")
        account_id = queue_dict.get("account_id")
        
        if not business_id or not account_id:
            print(f"❌ Отсутствует business_id или account_id для задачи {queue_dict.get('id')}", flush=True)
            _handle_worker_error(queue_dict["id"], "Отсутствует business_id или account_id")
            signal.alarm(0)  # Отменяем таймаут
            return
        
        print(f"🔄 Синхронизация Яндекс.Бизнес для бизнеса {business_id}", flush=True)
        
        from yandex_business_parser import YandexBusinessParser
        from yandex_business_sync_worker import YandexBusinessSyncWorker
        from auth_encryption import decrypt_auth_data
        from database_manager import DatabaseManager
        import json
        
        # Получаем auth_data
        db = None  # Initialize to None for safe cleanup
        try:
            db = DatabaseManager()
            cursor = db.conn.cursor()
        

            cursor.execute("""
                SELECT auth_data_encrypted, external_id
                FROM externalbusinessaccounts
                WHERE id = %s AND business_id = %s
            """, (account_id, business_id))
            account_row = cursor.fetchone()
            if not account_row:
                raise Exception("Аккаунт не найден")
            if isinstance(account_row, (list, tuple)):
                auth_data_encrypted, external_id = account_row[0], (account_row[1] if len(account_row) > 1 else None)
            else:
                auth_data_encrypted = account_row.get("auth_data_encrypted")
                external_id = account_row.get("external_id")
            auth_data_plain = decrypt_auth_data(auth_data_encrypted)
            
            if not auth_data_plain:
                raise Exception("Не удалось расшифровать auth_data")
            
            # Парсим auth_data
            try:
                auth_data_dict = json.loads(auth_data_plain)
            except json.JSONDecodeError:
                auth_data_dict = {"cookies": auth_data_plain}
            
            # Создаем парсер
            parser = YandexBusinessParser(auth_data_dict)
            account_data = {
                "id": account_id,
                "business_id": business_id,
                "external_id": external_id
            }
            
            # Получаем данные из кабинета
            print(f"📥 Получение отзывов из кабинета...")
            reviews = parser.fetch_reviews(account_data)
            print(f"✅ Получено отзывов: {len(reviews)}")
            
            print(f"📥 Получение статистики из кабинета...")
            stats = parser.fetch_stats(account_data)
            print(f"✅ Получено точек статистики: {len(stats)}")
            
            print(f"📥 Получение публикаций из кабинета...")
            posts = parser.fetch_posts(account_data)
            print(f"✅ Получено публикаций: {len(posts)}")
            
            print(f"📥 Получение информации об организации из кабинета...")
            org_info = parser.fetch_organization_info(account_data)
            
            # Сохраняем отзывы и статистику
            worker = YandexBusinessSyncWorker()
            if reviews:
                worker._upsert_reviews(db, reviews)
                print(f"💾 Сохранено отзывов: {len(reviews)}")
            
            if stats:
                worker._upsert_stats(db, stats)
                print(f"💾 Сохранено точек статистики: {len(stats)}")
            
            if posts:
                worker._upsert_posts(db, posts)
                print(f"💾 Сохранено публикаций: {len(posts)}")
            
            # Существующие данные из cards (Postgres source of truth)
            cursor.execute("""
                SELECT rating, reviews_count, overview
                FROM cards
                WHERE business_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (business_id,))
            existing_row = cursor.fetchone()
            existing_data = None
            if existing_row:
                if isinstance(existing_row, (list, tuple)):
                    existing_data = {'rating': existing_row[0], 'reviews_count': existing_row[1], 'overview': existing_row[2] if len(existing_row) > 2 else None}
                else:
                    existing_data = dict(existing_row) if hasattr(existing_row, 'keys') else None

            current_reviews_count = len(reviews) if reviews else 0
            rating = org_info.get('rating')
            if not rating and existing_data and existing_data.get('rating') is not None:
                rating = existing_data['rating']
            if current_reviews_count == 0 and existing_data and (existing_data.get('reviews_count') or 0) > 0:
                reviews_count = existing_data['reviews_count']
            else:
                reviews_count = current_reviews_count
            reviews_without_response = sum(1 for r in reviews if not getattr(r, 'response_text', None)) if reviews else 0
            current_news = len(posts) if posts else 0
            news_count = current_news
            current_photos = org_info.get('photos_count', 0) if org_info else 0
            photos_count = current_photos

            # Сохраняем срез в cards, не затирая rich-поля предыдущей карточки.
            url = f"https://yandex.ru/sprav/{external_id or 'unknown'}"
            overview_payload = {
                "photos_count": photos_count,
                "news_count": news_count,
                "snapshot_type": "metrics_update",
            }
            try:
                # Берём последнюю актуальную карточку, чтобы унаследовать products/news/photos/...,
                # иначе новая версия будет пустой.
                existing_card = db.get_latest_card_by_business(business_id)
                inherit_fields = {}
                if existing_card:
                    for key in (
                        "products",
                        "news",
                        "photos",
                        "features_full",
                        "competitors",
                        "hours",
                        "hours_full",
                        "categories",
                        "description",
                        "industry",
                        "geo",
                        "external_ids",
                    ):
                        if key in existing_card and existing_card[key] is not None:
                            inherit_fields[key] = existing_card[key]

                # Safeguard: если совсем нет ни rich-полей, ни метрик — не плодим пустые версии.
                has_rich = bool(inherit_fields)
                has_metrics = (
                    rating is not None
                    or (reviews_count not in (None, 0))
                    or (photos_count not in (None, 0))
                    or (news_count not in (None, 0))
                )

                if has_rich or has_metrics:
                    db.save_new_card_version(
                        business_id,
                        url=url,
                        rating=float(rating) if rating is not None else None,
                        reviews_count=int(reviews_count or 0),
                        overview=overview_payload,
                        **inherit_fields,
                    )
                else:
                    # Не прерываем выполнение worker, но явно логируем ситуацию деградации.
                    print(
                        f"[CARDS_SYNC] Skip creating new card version for business_id={business_id}: "
                        f"no rich fields and no metrics"
                    )
            except Exception as card_err:
                print(f"⚠️ Ошибка сохранения в cards (sync): {card_err}")

            try:
                metric_history_id = str(uuid.uuid4())
                current_date = datetime.now().strftime('%Y-%m-%d')
                cursor.execute("""
                    SELECT id FROM businessmetricshistory
                    WHERE business_id = %s AND metric_date = %s AND source = 'parsing'
                """, (business_id, current_date))
                existing_metric = cursor.fetchone()
                mid = existing_metric[0] if isinstance(existing_metric, (list, tuple)) else (existing_metric.get("id") if existing_metric else None)
                if mid:
                    cursor.execute("""
                        UPDATE businessmetricshistory
                        SET rating = %s, reviews_count = %s, photos_count = %s, news_count = %s
                        WHERE id = %s
                    """, (rating, reviews_count, photos_count, news_count, mid))
                else:
                    cursor.execute("""
                        INSERT INTO businessmetricshistory (
                            id, business_id, metric_date, rating, reviews_count,
                            photos_count, news_count, source
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'parsing')
                    """, (
                        metric_history_id,
                        business_id,
                        current_date,
                        rating,
                        reviews_count,
                        photos_count,
                        news_count,
                    ))
            except Exception as e:
                print(f"Error saving metrics history: {e}")
            
            db.conn.commit()
            # Safely close db and connections
            try:
                if 'db' in locals() and db:
                    db.close()
            except Exception:
                pass
            
            # The cursor and conn here refer to the ones created within the try block
            # associated with the DatabaseManager instance.
            try:
                if 'cursor' in locals() and cursor and not cursor.closed:
                    cursor.close()
            except Exception:
                pass
            try:
                if 'conn' in locals() and conn and not conn.closed:
                    conn.close()
            except Exception:
                pass
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE parsequeue
                SET status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (STATUS_COMPLETED, queue_dict["id"]))
            conn.commit()
            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass
            try:
                if conn:
                    conn.close()
            except Exception:
                pass

            print(f"✅ Синхронизация завершена для бизнеса {business_id}", flush=True)
            signal.alarm(0)  # Отменяем таймаут при успехе
            
        except TimeoutError as e:
            print(f"⏱️ Таймаут синхронизации: {e}", flush=True)
            signal.alarm(0)
            _handle_worker_error(queue_dict["id"], str(e))
            
        except Exception as e:
            print(f"❌ Ошибка синхронизации: {e}", flush=True)
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
            signal.alarm(0)  # Отменяем таймаут при ошибке
            
            try:
                if 'db' in locals() and db:
                    db.close()
            except:
                pass
            
            _handle_worker_error(queue_dict["id"], str(e))
            
    except Exception as e:
        print(f"❌ Критическая ошибка синхронизации: {e}")
        traceback.print_exc()
        
        _handle_worker_error(queue_dict["id"], str(e))

def _process_cabinet_fallback_task(queue_dict):
    """Обработка fallback парсинга через кабинет"""
    business_id = queue_dict.get("business_id")
    account_id = queue_dict.get("account_id")
    
    if not business_id or not account_id:
        print(f"❌ Отсутствует business_id или account_id для задачи {queue_dict.get('id')}", flush=True)
        _handle_worker_error(queue_dict["id"], "Отсутствует business_id или account_id")
        return
    
    print(f"🔄 Fallback парсинг через кабинет для бизнеса {business_id}", flush=True)
    
    try:
        from yandex_business_sync_worker import YandexBusinessSyncWorker
        
        # Используем sync_account для получения данных из кабинета
        worker = YandexBusinessSyncWorker()
        worker.sync_account(account_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE parsequeue
            SET status = %s,
                updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """, (STATUS_COMPLETED, queue_dict["id"]))
        conn.commit()
        cursor.close()
        conn.close()

        print(f"✅ Fallback парсинг завершен для бизнеса {business_id}", flush=True)
        
    except Exception as e:
        print(f"❌ Ошибка fallback парсинга: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        _handle_worker_error(queue_dict["id"], str(e))

def _process_sync_2gis_task(queue_dict):
    """Обработка задачи синхронизации с 2ГИС через API"""
    business_id = queue_dict.get("business_id")
    target_url = queue_dict.get("url")
    user_id = queue_dict.get("user_id")
    
    print(f"🔄 Запуск синхронизации 2ГИС для бизнеса {business_id}...", flush=True)
    
    try:
        from services.two_gis_client import TwoGISClient
        from external_sources import ExternalSource, ExternalStatsPoint, make_stats_id
        
        # Инициализация клиента
        # TODO: Можно брать ключ из настроек бизнеса, если мы разрешаем клиентам свои ключи
        # Пока берем из ENV
        if not os.getenv("TWOGIS_API_KEY"):
            raise ValueError("TWOGIS_API_KEY не установлен в .env")

        client = TwoGISClient()
        
        org_data = None
        
        # 1. Если есть URL, пробуем извлечь ID или найти по нему
        if target_url:
            # Извлекаем ID из URL вида https://2gis.ru/city/firm/70000001007629561
            import re
            match = re.search(r'/firm/(\d+)', target_url)
            if match:
                org_id = match.group(1)
                print(f"🔍 Найден ID организации в URL: {org_id}")
                org_data = client.search_organization_by_id(org_id)
            else:
                # Если URL сложный, можно попробовать поискать по названию, но это неточно
                pass
        
        # 2. Если по URL не нашли (или его нет), ищем по названию/адресу из БД
        if not org_data:
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT name, address FROM businesses WHERE id = %s", (business_id,))
                row = cursor.fetchone()
                if row:
                    name = row[0] if isinstance(row, (list, tuple)) else row.get("name")
                    address = row[1] if isinstance(row, (list, tuple)) else row.get("address")
                    query = f"{name} {address}"
                    print(f"🔍 Поиск в 2ГИС по запросу: {query}")
                    items = client.search_organization_by_text(query)
                    if items:
                        # Берем первый результат. В идеале нужно сравнение адресов.
                        org_data = items[0]
                        print(f"✅ Найдена организация: {org_data.get('name')}")
            finally:
                cursor.close()
                conn.close()

        if not org_data:
            raise Exception("Не удалось найти организацию в 2ГИС по ID или названию")

        # 3. Сохраняем данные
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            reviews_data = org_data.get('reviews', {})
            rating = reviews_data.get('general_rating')
            reviews_count = reviews_data.get('general_review_count', 0)
            name = org_data.get('name')
            address = org_data.get('address_name') or (org_data.get('adm_div', [{}])[0].get('name') if org_data.get('adm_div') else None)
            contacts = org_data.get('contact_groups', [])
            phone = None
            website = None
            for group in contacts:
                for contact in group.get('contacts', []):
                    if contact.get('type') == 'phone_number':
                        phone = contact.get('value') or contact.get('text')
                    if contact.get('type') == 'website':
                        website = contact.get('value') or contact.get('text')
            schedule = org_data.get('schedule')
            schedule_json = json.dumps(schedule, ensure_ascii=False) if schedule else None

            # Сохраняем в cards (Postgres)
            db_2gis = DatabaseManager()
            try:
                db_2gis.save_new_card_version(
                    business_id,
                    url=target_url or "",
                    title=name or "",
                    address=address or "",
                    phone=phone,
                    site=website,
                    rating=float(rating) if rating is not None else None,
                    reviews_count=int(reviews_count or 0),
                    hours=schedule_json,
                )
            finally:
                db_2gis.close()

            if rating is not None:
                today = datetime.now().strftime('%Y-%m-%d')
                stats_id = make_stats_id(business_id, ExternalSource.TWO_GIS, today)
                cursor.execute("""
                    INSERT INTO externalbusinessstats
                    (id, business_id, source, date, rating, reviews_total, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                    rating = EXCLUDED.rating,
                    reviews_total = EXCLUDED.reviews_total,
                    updated_at = CURRENT_TIMESTAMP
                """, (stats_id, business_id, "2gis", today, float(rating), int(reviews_count)))
                print(f"✅ Статистика 2ГИС обновлена: Рейтинг {rating}, Отзывов {reviews_count}")

            cursor.execute("""
                UPDATE parsequeue
                SET status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (STATUS_COMPLETED, queue_dict["id"]))
            
            conn.commit()
            print(f"✅ Синхронизация с 2ГИС успешно завершена для {business_id}")
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"❌ Ошибка синхронизации 2ГИС: {e}", flush=True)
        # import traceback
        # traceback.print_exc()
        _handle_worker_error(queue_dict["id"], str(e))


if __name__ == "__main__":
    print("Worker запущен. Проверка очереди каждые 5 минут...")
    while True:
        try:
            process_queue()
            _dispatch_outreach_queue_if_due()
            _dispatch_openclaw_callback_outbox_if_due()
            _check_openclaw_callback_alerts_if_due()
            _reconcile_openclaw_billing_if_due()
            _run_yookassa_renewals_if_due()
        except Exception as e:
            print(f"❌ Критическая ошибка worker loop: {e}", flush=True)
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
        
        try:    
            time.sleep(10)  # 10 секунд
        except Exception as e:
             # Если sleep прерван сигналом или ошибкой, просто логируем и продолжаем
             print(f"⚠️ Sleep interrupted: {e}", flush=True)
