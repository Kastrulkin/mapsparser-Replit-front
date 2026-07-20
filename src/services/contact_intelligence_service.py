"""Public contact collection and grounded first-message preparation for leads."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from psycopg2.extras import Json, RealDictCursor
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from services.outreach_campaign_service import build_evidence_ledger, build_personalization_candidates
from services.outreach_personalization_ai import (
    ai_personalization_enabled,
    generate_personalized_sequence,
)
from services.outreach_sender_profile_service import evaluate_sender_profile_completeness
from services.discovered_telegram_source_service import discovered_telegram_signals

try:
    import dns.resolver
except ImportError:
    dns = None

try:
    import phonenumbers
except ImportError:
    phonenumbers = None


CONTACT_TYPES = {
    "phone", "email", "telegram", "whatsapp", "vk", "instagram",
    "max", "website_form", "website", "other",
}
VERIFIED_STATUSES = {"confirmed_source", "verified"}
ACTIVE_JOB_STATUSES = {
    "queued", "collecting", "verifying", "researching", "drafting", "retry_wait",
}
SOCIAL_HOST_TYPES = {
    "t.me": "telegram",
    "telegram.me": "telegram",
    "wa.me": "whatsapp",
    "api.whatsapp.com": "whatsapp",
    "vk.com": "vk",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "max.ru": "max",
}
CONTACT_PAGE_HINTS = (
    "contact", "contacts", "kontakt", "контакт", "about", "о-компании", "about-us", "team", "команда",
)
EMAIL_PATTERN = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{8,}\d)")
UNSUPPORTED_PROMISE_PATTERNS = (
    re.compile(r"\+\s*\d+\s*[–—-]\s*\d+\s*%", re.I),
    re.compile(r"недополуча(?:ете|ют) клиент", re.I),
    re.compile(r"внедрим под ключ", re.I),
)


class PersonalizationGenerationError(RuntimeError):
    """Retryable failure while LocalOS prepares an evidence-bound AI draft."""

    retryable = True

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class MessageQualityError(RuntimeError):
    """Non-retryable draft failure that needs a human-visible correction."""

    retryable = False

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def normalize_phone(value: Any) -> str:
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not raw.startswith("+") and len(digits) not in {10, 11}:
        return ""
    if phonenumbers is not None:
        try:
            parsed = phonenumbers.parse(raw, "RU")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            pass
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) not in {10, 11} and not (raw.startswith("+") and 10 <= len(digits) <= 15):
        return ""
    return "+" + digits


def normalize_contact_value(contact_type: str, value: Any) -> str:
    normalized_type = str(contact_type or "").strip().lower()
    raw = unescape(str(value or "")).strip()
    if not raw:
        return ""
    if normalized_type == "phone":
        return normalize_phone(raw)
    if normalized_type == "email":
        return raw.lower()
    if normalized_type in {"telegram", "whatsapp", "vk", "instagram", "max", "website_form", "website"}:
        if raw.startswith("//"):
            raw = "https:" + raw
        if not re.match(r"^https?://", raw, re.I):
            raw = "https://" + raw.lstrip("/")
        try:
            parsed = urlparse(raw)
        except ValueError:
            return ""
        host = parsed.netloc.lower().removeprefix("www.")
        path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/")
        keep_query = normalized_type in {"website_form", "website"}
        query = f"?{parsed.query}" if keep_query and parsed.query else ""
        return f"https://{host}{path}{query}"
    return raw.lower()


def contact_type_from_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.lower().startswith("mailto:"):
        return "email"
    if raw.lower().startswith("tel:"):
        return "phone"
    candidate = raw if re.match(r"^https?://", raw, re.I) else "https://" + raw.lstrip("/")
    try:
        host = urlparse(candidate).netloc.lower().removeprefix("www.")
    except ValueError:
        return None
    return SOCIAL_HOST_TYPES.get(host)


def _public_http_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw if re.match(r"^https?://", raw, re.I) else "https://" + raw.lstrip("/")
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError:
        return None
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return None
    return candidate


def extract_contacts_from_html(html: str, page_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html or "", "html.parser")
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(
        contact_type: str,
        value: Any,
        source_type: str = "official_website",
        owner_type: str = "company",
        person_name: str = "",
        role_title: str = "",
    ) -> None:
        normalized = normalize_contact_value(contact_type, value)
        key = (contact_type, normalized)
        if contact_type not in CONTACT_TYPES or not normalized or key in seen:
            return
        seen.add(key)
        found.append(
            {
                "contact_type": contact_type,
                "value": str(value or "").strip(),
                "normalized_value": normalized,
                "source_url": page_url,
                "source_type": source_type,
                "owner_type": owner_type,
                "person_name": person_name,
                "role_title": role_title,
                "confidence": 0.86 if contact_type in {"phone", "email"} else 0.8,
                "verification_status": "confirmed_source",
            }
        )

    text = soup.get_text(" ", strip=True)
    for email in EMAIL_PATTERN.findall(text):
        add("email", email)
    for phone in PHONE_PATTERN.findall(text):
        add("phone", phone)
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href") or "").strip()
        if href.lower().startswith("mailto:"):
            add("email", href.split(":", 1)[1].split("?", 1)[0])
        elif href.lower().startswith("tel:"):
            add("phone", href.split(":", 1)[1])
        else:
            absolute = urljoin(page_url, href)
            contact_type = contact_type_from_url(absolute)
            if contact_type:
                add(contact_type, absolute)
    for form in soup.select("form"):
        action = urljoin(page_url, str(form.get("action") or page_url))
        add("website_form", action)

    def walk_structured_data(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk_structured_data(item)
            return
        if not isinstance(node, dict):
            return
        node_type = str(node.get("@type") or "").lower()
        person_name = str(node.get("name") or "").strip() if node_type == "person" else ""
        role_title = str(node.get("jobTitle") or node.get("contactType") or "").strip()
        owner_type = "person" if node_type == "person" and person_name else "company"
        for field, contact_type in (("email", "email"), ("telephone", "phone")):
            if node.get(field):
                add(contact_type, node.get(field), owner_type=owner_type, person_name=person_name, role_title=role_title)
        same_as = node.get("sameAs")
        values = same_as if isinstance(same_as, list) else [same_as]
        for value in values:
            contact_type = contact_type_from_url(value)
            if contact_type:
                add(contact_type, value, owner_type=owner_type, person_name=person_name, role_title=role_title)
        for value in node.values():
            if isinstance(value, (dict, list)):
                walk_structured_data(value)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            walk_structured_data(json.loads(script.string or script.get_text() or "{}"))
        except (TypeError, ValueError):
            continue
    return found


def _contact_pages(html: str, website_url: str, limit: int = 5) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    base_host = urlparse(website_url).netloc.lower().removeprefix("www.")
    pages: list[str] = []
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href") or "").strip()
        text = str(anchor.get_text(" ", strip=True) or "").lower()
        absolute = urljoin(website_url, href)
        parsed = urlparse(absolute)
        host = parsed.netloc.lower().removeprefix("www.")
        haystack = f"{text} {parsed.path.lower()}"
        if host == base_host and any(hint in haystack for hint in CONTACT_PAGE_HINTS):
            clean = absolute.split("#", 1)[0]
            if clean not in pages:
                pages.append(clean)
        if len(pages) >= limit:
            break
    return pages


def collect_public_website_contacts(website: Any) -> tuple[list[dict[str, Any]], list[str]]:
    safe_url = _public_http_url(website)
    if not safe_url:
        return [], ["Официальный сайт не указан или недоступен для безопасной проверки"]
    headers = {"User-Agent": "LocalOS Contact Intelligence/1.0 (+https://localos.pro)"}
    contacts: list[dict[str, Any]] = []
    warnings: list[str] = []
    queue = [safe_url]
    visited: set[str] = set()
    while queue and len(visited) < 6:
        page_url = queue.pop(0)
        if page_url in visited:
            continue
        visited.add(page_url)
        try:
            response = requests.get(page_url, headers=headers, timeout=8, allow_redirects=False, stream=True)
            if response.is_redirect:
                redirect_url = _public_http_url(urljoin(page_url, str(response.headers.get("location") or "")))
                if redirect_url and redirect_url not in visited:
                    queue.insert(0, redirect_url)
                continue
            response.raise_for_status()
            if "text/html" not in str(response.headers.get("content-type") or "").lower():
                continue
            body = response.raw.read(1_000_001, decode_content=True)
            if len(body) > 1_000_000:
                warnings.append(f"Страница {page_url} слишком большая и пропущена")
                continue
            html = body.decode(response.encoding or "utf-8", errors="replace")
            contacts.extend(extract_contacts_from_html(html, response.url))
            if len(visited) == 1:
                queue.extend(_contact_pages(html, response.url))
        except (requests.RequestException, Urllib3HTTPError):
            warnings.append(f"Не удалось проверить {page_url}")
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for contact in contacts:
        key = (str(contact.get("contact_type")), str(contact.get("normalized_value")))
        unique[key] = contact
    return list(unique.values()), warnings


def legacy_contact_candidates(lead: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add(
        contact_type: str,
        value: Any,
        confidence: float = 0.62,
        source_type: str = "map_card",
    ) -> None:
        normalized = normalize_contact_value(contact_type, value)
        if normalized:
            candidates.append(
                {
                    "contact_type": contact_type,
                    "value": str(value or "").strip(),
                    "normalized_value": normalized,
                    "source_url": lead.get("source_url"),
                    "source_type": source_type,
                    "confidence": confidence,
                    "verification_status": "found",
                }
            )

    add("phone", lead.get("phone"))
    add("email", lead.get("email"))
    add("telegram", lead.get("telegram_url"))
    add("whatsapp", lead.get("whatsapp_url"))
    add("website", lead.get("website"), 0.74)
    links = lead.get("messenger_links_json")
    if isinstance(links, list):
        for item in links:
            value = item.get("url") if isinstance(item, dict) else item
            contact_type = contact_type_from_url(value)
            if contact_type:
                add(contact_type, value)

    key_types = {
        "email": "email", "emails": "email", "mail": "email",
        "phone": "phone", "phones": "phone", "telephone": "phone", "tel": "phone",
        "telegram": "telegram", "telegram_url": "telegram", "tg": "telegram",
        "whatsapp": "whatsapp", "whatsapp_url": "whatsapp", "wa": "whatsapp",
        "vk": "vk", "vkontakte": "vk", "instagram": "instagram", "max": "max",
    }
    visited = 0

    def walk(value: Any, key_hint: str = "", depth: int = 0) -> None:
        nonlocal visited
        if depth > 5 or visited >= 500:
            return
        visited += 1
        if isinstance(value, dict):
            for key, item in value.items():
                clean_key = str(key or "").strip().lower().replace("-", "_")
                walk(item, clean_key, depth + 1)
            return
        if isinstance(value, list):
            for item in value:
                walk(item, key_hint, depth + 1)
            return
        raw = str(value or "").strip()
        if not raw:
            return
        contact_type = key_types.get(key_hint)
        if contact_type:
            add(contact_type, raw, 0.58, "map_payload")
            return
        detected_type = contact_type_from_url(raw)
        if detected_type:
            add(detected_type, raw, 0.58, "map_payload")

    for payload_key in ("raw_payload_json", "enrich_payload_json"):
        walk(lead.get(payload_key))
    return candidates


def exclude_public_channel_contacts(
    cursor: Any,
    lead_id: str,
    contacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """A verified public channel is evidence, not a direct-message recipient."""
    cursor.execute(
        """
        SELECT DISTINCT source.canonical_url
        FROM lead_workstreams workstream
        JOIN lead_signal_links link
          ON link.workstream_id = workstream.id
         AND link.source_type = 'telegram_knowledge_source'
         AND link.status = 'selected'
        JOIN knowledge_sources source
          ON source.id::text = link.source_id
        WHERE workstream.lead_id = %s
          AND source.status = 'active'
          AND source.metadata_json->>'telegram_reference_type' = 'public_channel'
        """,
        (lead_id,),
    )
    channel_urls = {
        normalize_contact_value("telegram", row.get("canonical_url") if isinstance(row, dict) else row[0])
        for row in cursor.fetchall() or []
    }
    if not channel_urls:
        return contacts
    return [
        contact
        for contact in contacts
        if not (
            str(contact.get("contact_type") or "") == "telegram"
            and normalize_contact_value("telegram", contact.get("normalized_value") or contact.get("value")) in channel_urls
        )
    ]


def upsert_contact_points(cursor, lead_id: str, contacts: list[dict[str, Any]]) -> int:
    saved = 0
    for contact in contacts:
        contact_type = str(contact.get("contact_type") or "").strip().lower()
        normalized = normalize_contact_value(contact_type, contact.get("normalized_value") or contact.get("value"))
        if contact_type not in CONTACT_TYPES or not normalized:
            continue
        display_value = (
            normalized
            if contact_type in {"telegram", "whatsapp", "vk", "instagram", "max"}
            else str(contact.get("value") or normalized)
        )
        cursor.execute(
            """
            INSERT INTO lead_contact_points (
                id, lead_id, contact_type, value, normalized_value, owner_type,
                person_name, role_title, source_url, source_type, provider,
                confidence, verification_status, observed_at, verified_at,
                stale_after, metadata_json, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, NULLIF(%s, ''), NULLIF(%s, ''), NULLIF(%s, ''),
                %s, %s, %s, %s, NOW(),
                CASE WHEN %s IN ('confirmed_source', 'verified') THEN NOW() ELSE NULL END,
                NOW() + INTERVAL '180 days', %s, NOW(), NOW()
            )
            ON CONFLICT (lead_id, contact_type, normalized_value) DO UPDATE SET
                value = EXCLUDED.value,
                owner_type = CASE
                    WHEN lead_contact_points.owner_type = 'person' THEN lead_contact_points.owner_type
                    ELSE EXCLUDED.owner_type
                END,
                person_name = COALESCE(lead_contact_points.person_name, EXCLUDED.person_name),
                role_title = COALESCE(lead_contact_points.role_title, EXCLUDED.role_title),
                source_url = CASE
                    WHEN EXCLUDED.confidence >= lead_contact_points.confidence THEN EXCLUDED.source_url
                    ELSE lead_contact_points.source_url
                END,
                source_type = CASE
                    WHEN EXCLUDED.confidence >= lead_contact_points.confidence THEN EXCLUDED.source_type
                    ELSE lead_contact_points.source_type
                END,
                provider = CASE
                    WHEN EXCLUDED.confidence >= lead_contact_points.confidence THEN EXCLUDED.provider
                    ELSE lead_contact_points.provider
                END,
                confidence = GREATEST(lead_contact_points.confidence, EXCLUDED.confidence),
                verification_status = CASE
                    WHEN EXCLUDED.confidence >= lead_contact_points.confidence THEN EXCLUDED.verification_status
                    ELSE lead_contact_points.verification_status
                END,
                observed_at = NOW(),
                verified_at = COALESCE(EXCLUDED.verified_at, lead_contact_points.verified_at),
                stale_after = GREATEST(lead_contact_points.stale_after, EXCLUDED.stale_after),
                metadata_json = lead_contact_points.metadata_json || EXCLUDED.metadata_json,
                updated_at = NOW()
            """,
            (
                str(uuid.uuid4()), lead_id, contact_type, display_value, normalized,
                str(contact.get("owner_type") or "company"), str(contact.get("person_name") or ""),
                str(contact.get("role_title") or ""), str(contact.get("source_url") or ""),
                str(contact.get("source_type") or "public"), str(contact.get("provider") or "public"),
                max(0.0, min(float(contact.get("confidence") or 0), 1.0)),
                str(contact.get("verification_status") or "found"),
                str(contact.get("verification_status") or "found"), Json(contact.get("metadata") or {}),
            ),
        )
        saved += 1
    return saved


def verify_contact_points(cursor, lead_id: str, website: Any) -> None:
    official_host = urlparse(normalize_contact_value("website", website)).netloc.lower().removeprefix("www.") if website else ""
    cursor.execute("SELECT * FROM lead_contact_points WHERE lead_id = %s", (lead_id,))
    for row in cursor.fetchall() or []:
        contact = dict(row)
        status = str(contact.get("verification_status") or "found")
        normalized = str(contact.get("normalized_value") or "")
        if status in VERIFIED_STATUSES or status == "invalid":
            continue
        if contact.get("contact_type") == "email":
            match = EMAIL_PATTERN.fullmatch(normalized)
            domain = normalized.rsplit("@", 1)[-1] if match else ""
            if not match:
                status = "invalid"
            elif official_host and (domain == official_host or official_host.endswith("." + domain)):
                status = "confirmed_source"
            else:
                if dns is not None:
                    try:
                        dns.resolver.resolve(domain, "MX", lifetime=4)
                        status = "valid_format"
                    except Exception:
                        status = "unknown"
                else:
                    try:
                        socket.getaddrinfo(domain, 25, type=socket.SOCK_STREAM)
                        status = "valid_format"
                    except OSError:
                        status = "unknown"
        elif contact.get("contact_type") == "phone":
            status = "valid_format" if normalize_phone(normalized) else "invalid"
        elif contact.get("contact_type") in {"telegram", "whatsapp", "vk", "instagram", "max", "website_form"}:
            status = "confirmed_source" if contact.get("source_type") == "official_website" else "found"
        cursor.execute(
            """
            UPDATE lead_contact_points
            SET verification_status = %s,
                verified_at = CASE WHEN %s IN ('confirmed_source', 'verified') THEN NOW() ELSE verified_at END,
                updated_at = NOW()
            WHERE id = %s
            """,
            (status, status, contact.get("id")),
        )


def _load_sender_profile(cursor, workstream: dict[str, Any]) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT * FROM outreach_sender_profiles
        WHERE workstream_type = %s
          AND COALESCE(client_business_id, '') = COALESCE(%s, '')
          AND is_active = TRUE
        ORDER BY confirmed_at DESC NULLS LAST, updated_at DESC
        LIMIT 1
        """,
        (workstream.get("workstream_type"), workstream.get("client_business_id")),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _select_best_contact(cursor, workstream: dict[str, Any]) -> dict[str, Any] | None:
    selected_id = workstream.get("selected_contact_point_id")
    cursor.execute(
        """
        SELECT * FROM lead_contact_points
        WHERE lead_id = %s
          AND contact_type <> 'website'
          AND verification_status <> 'invalid'
          AND (stale_after IS NULL OR stale_after > NOW())
        ORDER BY
          CASE WHEN id = %s THEN 0 ELSE 1 END,
          CASE WHEN owner_type = 'person' THEN 0 ELSE 1 END,
          CASE verification_status
            WHEN 'verified' THEN 0 WHEN 'confirmed_source' THEN 1
            WHEN 'valid_format' THEN 2 WHEN 'accept_all' THEN 3 ELSE 4 END,
          confidence DESC,
          CASE contact_type WHEN 'email' THEN 0 WHEN 'telegram' THEN 1 WHEN 'phone' THEN 2 ELSE 3 END,
          updated_at DESC
        LIMIT 1
        """,
        (workstream.get("lead_id"), selected_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def public_audit_artifact_from_row(row: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize one LocalOS public-audit row into native research evidence."""
    source = dict(row or {})
    if not source or not bool(source.get("is_active", True)):
        return {}
    page_json: dict[str, Any] = {}
    for key in ("published_json", "page_json", "generated_json"):
        candidate = source.get(key)
        if isinstance(candidate, dict) and candidate:
            page_json = candidate
            break
    audit = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
    slug = str(source.get("slug") or page_json.get("slug") or "").strip().strip("/")
    if not audit or not slug:
        return {}
    frontend_base = str(os.getenv("FRONTEND_BASE_URL") or "https://localos.pro").strip().rstrip("/")
    return {
        "audit_json": audit,
        "audit_source_url": f"{frontend_base}/{slug}",
        "audit_source_type": str(source.get("source_type") or "admin_prospecting_public_audit"),
        "audit_source_date": source.get("published_at") or source.get("updated_at"),
        "audit_edit_status": str(source.get("edit_status") or "generated"),
    }


def load_localos_sales_audit_artifact(cursor, lead_id: str) -> dict[str, Any]:
    """Load the current public audit for a LocalOS sales lead, if one exists."""
    cursor.execute(
        """
        SELECT slug, is_active, source_type, edit_status,
               page_json, generated_json, published_json,
               published_at, updated_at
        FROM adminprospectingleadpublicoffers
        WHERE lead_id = %s AND is_active = TRUE
        LIMIT 1
        """,
        (lead_id,),
    )
    row = cursor.fetchone()
    return public_audit_artifact_from_row(dict(row) if row else None)


def merge_research_briefs(
    existing_brief: dict[str, Any] | None,
    native_brief: dict[str, Any] | None,
    *,
    existing_score: int,
    native_score: int,
) -> tuple[dict[str, Any], bool]:
    """Keep the stronger sourced angle while preserving non-conflicting context."""
    existing = dict(existing_brief or {})
    native = dict(native_brief or {})
    native_has_signal = bool(str(native.get("signal") or "").strip())
    existing_has_signal = bool(str(existing.get("signal") or "").strip())
    native_wins = native_has_signal and (not existing_has_signal or native_score > existing_score)
    primary = native if native_wins else existing
    secondary = existing if native_wins else native
    merged = {
        key: value
        for key, value in secondary.items()
        if value is not None and value != "" and value != [] and value != {}
    }
    merged.update({
        key: value
        for key, value in primary.items()
        if value is not None and value != "" and value != [] and value != {}
    })
    return merged, native_wins


def build_native_research_payload(
    lead: dict[str, Any],
    workstream: dict[str, Any],
    partnership_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build conservative evidence from LocalOS-owned public snapshots."""
    artifact = partnership_artifact if isinstance(partnership_artifact, dict) else {}
    match = artifact.get("match_json") if isinstance(artifact.get("match_json"), dict) else {}
    audit = artifact.get("audit_json") if isinstance(artifact.get("audit_json"), dict) else {}
    source_url = str(lead.get("source_url") or lead.get("website") or "").strip()
    audit_source_url = str(artifact.get("audit_source_url") or source_url).strip()
    audit_source_date = artifact.get("audit_source_date")
    audit_source_type = str(artifact.get("audit_source_type") or "admin_prospecting_public_audit").strip()
    researched_at = datetime.now(timezone.utc).isoformat()
    signals: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    limitations: list[str] = []

    def add_signal(
        kind: str,
        fact: str,
        relevance: str,
        *,
        url: str | None = None,
        confidence: float = 0.8,
        published_at: Any = None,
        source_type: str | None = None,
        hypothesis: str | None = None,
    ) -> None:
        clean_fact = re.sub(r"\s+", " ", str(fact or "")).strip()
        clean_url = str(url or source_url or "").strip()
        if not clean_fact or not clean_url:
            return
        freshness = "current_snapshot"
        freshness_ok = True
        if published_at:
            freshness = "dated_source"
            try:
                published_text = str(published_at).strip().replace("Z", "+00:00")
                published_date = datetime.fromisoformat(published_text)
                if published_date.tzinfo is None:
                    published_date = published_date.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - published_date.astimezone(timezone.utc)).days
                freshness = "fresh" if age_days <= 180 else "stale"
                freshness_ok = age_days <= 180
            except (TypeError, ValueError):
                freshness = "unknown_dated_source"
                freshness_ok = False
        source_ok = bool(re.match(r"^https?://", clean_url, re.I))
        specificity_ok = len(clean_fact) >= 20
        relevance_ok = bool(re.sub(r"\s+", " ", str(relevance or "")).strip())
        usable_for_outreach = source_ok and specificity_ok and relevance_ok and freshness_ok
        rejected_reasons = []
        if not source_ok:
            rejected_reasons.append("source_url_invalid")
        if not specificity_ok:
            rejected_reasons.append("signal_not_specific")
        if not relevance_ok:
            rejected_reasons.append("offer_relevance_missing")
        if not freshness_ok:
            rejected_reasons.append("signal_stale_or_undated")
        evidence_id = "evidence:" + hashlib.sha256(
            f"{kind}|{clean_fact}|{clean_url}|{published_at or ''}".encode("utf-8")
        ).hexdigest()[:20]
        signal = {
            "evidence_id": evidence_id,
            "kind": kind,
            "observed_fact": clean_fact,
            "fact": clean_fact,
            "hypothesis": re.sub(r"\s+", " ", str(hypothesis or "")).strip() or None,
            "relevance": relevance,
            "source_url": clean_url,
            "source_type": source_type or (
                "official_website" if clean_url == str(lead.get("website") or "").strip() else "map_or_audit"
            ),
            "published_at": published_at,
            "researched_at": researched_at,
            "freshness": freshness,
            "confidence": max(0.0, min(float(confidence), 1.0)),
            "author_or_organization": str(lead.get("name") or "").strip() or None,
            "usable_for_outreach": usable_for_outreach,
            "rejected_reason": ",".join(rejected_reasons) or None,
        }
        signals.append(signal)
        if not any(item.get("url") == clean_url for item in sources):
            sources.append({
                "title": str(lead.get("name") or "Публичный источник"),
                "url": clean_url,
                "source_type": signal["source_type"],
                "observed_at": researched_at,
            })

    def add_hypothesis(
        kind: str,
        hypothesis: str,
        relevance: str,
        *,
        url: str | None = None,
        published_at: Any = None,
        source_type: str | None = None,
    ) -> None:
        clean_hypothesis = re.sub(r"\s+", " ", str(hypothesis or "")).strip()
        clean_url = str(url or audit_source_url or source_url).strip()
        if not clean_hypothesis:
            return
        evidence_id = "evidence:" + hashlib.sha256(
            f"{kind}|hypothesis|{clean_hypothesis}|{clean_url}".encode("utf-8")
        ).hexdigest()[:20]
        signals.append({
            "evidence_id": evidence_id,
            "kind": kind,
            "observed_fact": "",
            "fact": "",
            "hypothesis": clean_hypothesis,
            "relevance": relevance,
            "source_url": clean_url or None,
            "source_type": source_type or audit_source_type,
            "published_at": published_at,
            "researched_at": researched_at,
            "freshness": "not_applicable",
            "confidence": 0.5,
            "author_or_organization": "LocalOS",
            "usable_for_outreach": False,
            "rejected_reason": "observation_missing_hypothesis_only",
        })

    rating = lead.get("rating")
    try:
        rating_value = float(rating) if rating not in {None, ""} else None
    except (TypeError, ValueError):
        rating_value = None
    reviews_count = int(lead.get("reviews_count") or 0)
    def observation_requires_manual_check(value: Any) -> bool:
        normalized = re.sub(r"\s+", " ", str(value or "")).strip().lower()
        return any(
            phrase in normalized
            for phrase in (
                "требует ручной проверки",
                "нужно проверить",
                "важно проверить",
                "важно убедиться",
                "стоит проверить",
                "необходимо проверить",
            )
        )

    if workstream.get("workstream_type") == "localos_sales":
        if rating_value is not None and 0 < rating_value < 4.5:
            add_signal(
                "map_issue",
                f"В публичной карточке указан рейтинг {rating_value:.1f} при {reviews_count} отзывах.",
                "Есть конкретная точка для проверки карточки и работы с отзывами.",
                confidence=0.95,
            )
        elif reviews_count > 0 and reviews_count <= 5:
            add_signal(
                "map_issue",
                f"В публичной карточке сейчас {reviews_count} отзывов.",
                "Можно проверить, достаточно ли карточка раскрывает доверие и опыт клиентов.",
                confidence=0.9,
            )
        if not str(lead.get("website") or "").strip() and source_url:
            add_signal(
                "map_issue",
                "В сохранённом публичном снимке карточки официальный сайт не указан.",
                "Это конкретный элемент присутствия компании, который можно проверить в коротком аудите.",
                confidence=0.8,
            )
        reviews = lead.get("reviews_json") if isinstance(lead.get("reviews_json"), list) else []
        for review in reviews[:20]:
            if not isinstance(review, dict):
                continue
            try:
                review_rating = float(review.get("rating") or review.get("stars") or 0)
            except (TypeError, ValueError):
                review_rating = 0
            review_text = re.sub(r"\s+", " ", str(review.get("text") or review.get("review_text") or "")).strip()
            if review_rating and review_rating <= 3 and review_text:
                excerpt = review_text[:180].rstrip(" ,;:")
                add_signal(
                    "review",
                    f"В публичном отзыве с оценкой {review_rating:.0f} отмечено: «{excerpt}».",
                    "Отзыв даёт проверяемую тему для полезного разбора без приписывания бизнесу скрытой проблемы.",
                    url=str(review.get("source_url") or source_url),
                    confidence=0.9,
                    published_at=review.get("published_at") or review.get("date"),
                )
                break
        current_state = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
        services_count = current_state.get("services_count")
        priced_services_count = current_state.get("services_with_price_count")
        if services_count not in {None, ""} and priced_services_count not in {None, ""}:
            try:
                services_value = max(0, int(services_count))
                priced_value = max(0, int(priced_services_count))
            except (TypeError, ValueError):
                services_value = 0
                priced_value = 0
            price_coverage = priced_value / services_value if services_value > 0 else 1.0
            if services_value > 0 and priced_value < services_value and price_coverage <= 0.8:
                add_signal(
                    "map_issue",
                    f"По данным аудита карточки: всего услуг - {services_value}; с ценой - {priced_value}.",
                    "Можно предметно проверить, для каких услуг клиент видит цену прямо в карточке.",
                    url=audit_source_url,
                    confidence=0.95,
                    published_at=audit_source_date,
                    source_type=audit_source_type,
                )
            elif services_value > 0 and priced_value < services_value:
                add_hypothesis(
                    "map_issue",
                    "В карточке есть отдельные услуги без цены, но покрытие ценами выше 80%; "
                    "этого недостаточно как самостоятельного повода для холодного обращения.",
                    "Нужен более сильный публичный сигнал.",
                    url=audit_source_url,
                    published_at=audit_source_date,
                    source_type=audit_source_type,
                )
        parse_context = audit.get("parse_context") if isinstance(audit.get("parse_context"), dict) else {}
        if parse_context.get("description_present") is False:
            add_signal(
                "map_issue",
                "В аудите публичной карточки описание бизнеса не найдено.",
                "Можно проверить, понятно ли карточка объясняет услуги до перехода на сайт.",
                url=audit_source_url,
                confidence=0.9,
                published_at=audit_source_date,
                source_type=audit_source_type,
            )
        top_issues = audit.get("top_3_issues") if isinstance(audit.get("top_3_issues"), list) else (
            audit.get("top_issues") if isinstance(audit.get("top_issues"), list) else []
        )
        for issue in top_issues[:2]:
            if isinstance(issue, dict):
                fact = issue.get("observed_fact") or issue.get("evidence") or issue.get("fact")
                hypothesis = issue.get("problem") or issue.get("impact") or issue.get("title")
                issue_url = issue.get("source_url") or audit_source_url
            else:
                fact = ""
                hypothesis = issue
                issue_url = audit_source_url
            if fact and not observation_requires_manual_check(fact):
                add_signal(
                    "map_issue",
                    str(fact),
                    "Аудит публичной карточки выделяет конкретный элемент для проверки.",
                    url=str(issue_url or ""),
                    confidence=0.85,
                    published_at=audit_source_date,
                    source_type=audit_source_type,
                    hypothesis=str(hypothesis or ""),
                )
            elif fact or hypothesis:
                add_hypothesis(
                    "map_issue",
                    str(hypothesis or fact),
                    "Вывод аудита нельзя использовать в сообщении без отдельного наблюдаемого факта.",
                    url=str(issue_url or ""),
                    published_at=audit_source_date,
                    source_type=audit_source_type,
                )
    else:
        match_fact = str(
            match.get("recipient_observation")
            or ""
        ).strip()
        if match_fact and float(match.get("match_score") or 0) >= 40:
            add_signal(
                "service_compatibility",
                match_fact,
                str(match.get("relevance_bridge") or "").strip()
                or "Есть фактическое основание проверить один безопасный партнёрский тест.",
                confidence=min(1.0, float(match.get("match_score") or 70) / 100),
                hypothesis=str(match.get("compatibility_hypothesis") or "").strip(),
            )

    radar_signals = artifact.get("radar_signals") if isinstance(artifact.get("radar_signals"), list) else []
    for radar_signal in radar_signals[:3]:
        if not isinstance(radar_signal, dict):
            continue
        message_text = re.sub(r"\s+", " ", str(radar_signal.get("message_text") or "")).strip()
        chat_title = re.sub(r"\s+", " ", str(radar_signal.get("chat_title") or "Telegram")).strip()
        if not message_text or not radar_signal.get("message_link"):
            continue
        excerpt = message_text[:180].rstrip(" ,;:")
        auto_discovered = bool(radar_signal.get("auto_discovered"))
        add_signal(
            "telegram_post",
            f"В публичном Telegram-источнике «{chat_title}» опубликовано: «{excerpt}».",
            (
                "Telegram-канал найден в публичной карточке этого лида; публикация прошла проверки публичности, свежести и специфичности."
                if auto_discovered
                else "Сигнал вручную связан с этим лидом и прошёл проверку публичности и свежести."
            ),
            url=str(radar_signal.get("message_link")),
            confidence=min(0.95, max(0.6, float(radar_signal.get("relevance_score") or 60) / 100)),
            published_at=radar_signal.get("message_date"),
            source_type="telegram_public",
        )

    usable_signals = [item for item in signals if item.get("usable_for_outreach")]

    def signal_priority(item: dict[str, Any]) -> int:
        fact = str(item.get("observed_fact") or "").lower()
        if (
            "услуг, цена указана" in fact
            or "по данным аудита, услуг в карточке" in fact
            or "по данным аудита карточки: всего услуг" in fact
            or "описание бизнеса не найдено" in fact
        ):
            return 0
        if "указан рейтинг" in fact:
            return 1
        if "официальный сайт не указан" in fact:
            return 2
        if "сейчас" in fact and "отзыв" in fact:
            return 3
        if item.get("kind") == "review":
            return 5
        return 4

    usable_signals.sort(key=signal_priority)
    if not usable_signals:
        limitations.append("Не найден публичный специфичный сигнал, пригодный для персонализации")
    category = str(lead.get("category") or "").strip()
    signal_text = str(usable_signals[0].get("observed_fact") if usable_signals else "").strip()
    if workstream.get("workstream_type") == "client_partnership":
        client_name = str(workstream.get("client_business_name") or "бизнеса").strip()
        brief = {
            "segment": category,
            "buyer_persona": "владелец или менеджер партнёрств",
            "kpi": "полезное предложение для общей локальной аудитории",
            "pain": "",
            "pain_strength": "not_required",
            "awareness": "fit_aware" if signal_text else "unknown",
            "signal": signal_text,
            "result": f"проверить совместную механику с {client_name} на одном безопасном тесте",
            "angle": "совместимость аудитории и услуг",
            "cta": "Обсудить один безопасный тест?",
        }
    else:
        brief = {
            "segment": category,
            "buyer_persona": "",
            "kpi": "качество локального присутствия и обращений",
            "pain": signal_text,
            "pain_strength": "observed" if signal_text else "unknown",
            "awareness": "unknown",
            "signal": signal_text,
            "result": "короткого аудита карточки с одной проверяемой рекомендацией",
            "angle": "публичный сигнал и практический следующий шаг",
            "cta": "Прислать короткий разбор?",
        }
    contact_summary = artifact.get("contact_summary") if isinstance(artifact.get("contact_summary"), dict) else {}
    match_score = max(0, min(int(match.get("match_score") or 0), 100))
    raw_payload = lead.get("raw_payload_json") if isinstance(lead.get("raw_payload_json"), dict) else {}
    enrich_payload = lead.get("enrich_payload_json") if isinstance(lead.get("enrich_payload_json"), dict) else {}
    payload_text = json.dumps({"raw": raw_payload, "enrich": enrich_payload}, ensure_ascii=False).lower()
    disqualifiers = []
    if any(token in payload_text for token in ('"permanently_closed": true', '"isclosed": true', '"business_status": "closed"')):
        disqualifiers.append("business_closed")
    if workstream.get("workstream_type") == "client_partnership" and (
        bool(match.get("direct_competitor"))
        or str(match.get("competition_level") or "").lower() == "direct"
    ):
        disqualifiers.append("direct_competitor")
    average_confidence = (
        sum(float(item.get("confidence") or 0) for item in usable_signals) / len(usable_signals)
        if usable_signals else 0.0
    )
    evidence_quality = min(20, int(round(average_confidence * 15)) + min(5, len(sources) * 2))
    reachability = 15 if int(contact_summary.get("verified") or 0) > 0 else (
        8 if int(contact_summary.get("found") or 0) > 0 else 0
    )
    icp_fit = 15 if category else 5
    timing = min(15, sum(8 for item in usable_signals if item.get("freshness") == "fresh"))
    if workstream.get("workstream_type") == "client_partnership":
        service_compatibility = min(25, int(round(match_score * 0.25))) if match_fact else 0
        problem_strength = 0
        score = icp_fit + service_compatibility + timing + evidence_quality + reachability
    else:
        service_compatibility = 0
        problem_strength = min(
            35,
            sum(18 if item.get("kind") in {"map_issue", "review"} else 8 for item in usable_signals),
        )
        score = icp_fit + problem_strength + timing + evidence_quality + reachability
    if disqualifiers:
        score = 0
        # Qualification stage describes the strongest supported evidence tier.
        # Readiness and lifecycle decisions (for example needs_evidence or
        # not_relevant) are stored separately and are not valid research stages.
        qualification_stage = "potential_fit"
    elif usable_signals and score >= 60:
        qualification_stage = "trigger_present"
    elif score >= 35:
        qualification_stage = "potential_fit"
    else:
        qualification_stage = "potential_fit"
    signal_label = "reason_to_check" if usable_signals else "fit_only"
    score_breakdown = {
        "icp_fit": icp_fit,
        "problem_strength": problem_strength,
        "timing": timing,
        "evidence_quality": evidence_quality,
        "public_reachability": reachability,
        "service_compatibility": service_compatibility,
        "disqualifiers": disqualifiers,
    }
    evidence = [
        {
            "id": signal.get("evidence_id") or f"native-{index + 1}",
            "kind": signal["kind"],
            "fact": signal["observed_fact"],
            "status": "observed",
            "source_url": signal["source_url"],
            "observed_at": signal.get("published_at") or researched_at,
            "freshness": signal["freshness"],
            "confidence": signal["confidence"],
            "hypothesis": signal.get("hypothesis"),
            "relevance": signal["relevance"],
        }
        for index, signal in enumerate(usable_signals)
    ]
    report_hash = hashlib.sha256(
        json.dumps(
            {
                "workstream_id": str(workstream.get("id") or ""),
                "signals": [
                    {
                        "kind": item.get("kind"),
                        "observed_fact": item.get("observed_fact"),
                        "source_url": item.get("source_url"),
                        "published_at": item.get("published_at"),
                    }
                    for item in signals
                ],
                "brief": brief,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return json_safe({
        "score": score,
        "qualification_stage": qualification_stage,
        "signal_label": signal_label,
        "score_breakdown": score_breakdown,
        "why_now": signal_text,
        "signals_json": signals,
        "sources_json": sources,
        "contact_evidence_json": (
            artifact.get("contact_evidence")
            if isinstance(artifact.get("contact_evidence"), list)
            else []
        ),
        "limitations_json": limitations,
        "message_brief_json": brief,
        "message_readiness_json": {},
        "evidence_json": evidence,
        "personalization_candidates_json": [],
        "report_hash": report_hash,
        "researched_at": researched_at,
    })


def upsert_native_research(
    cursor,
    lead: dict[str, Any],
    workstream: dict[str, Any],
) -> dict[str, Any]:
    artifact: dict[str, Any] = {}
    cursor.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE contact_type <> 'website' AND verification_status <> 'invalid') AS found,
            COUNT(*) FILTER (
                WHERE contact_type <> 'website'
                  AND verification_status IN ('verified', 'confirmed_source')
            ) AS verified
        FROM lead_contact_points
        WHERE lead_id = %s
        """,
        (lead.get("id"),),
    )
    contact_summary_row = cursor.fetchone()
    artifact["contact_summary"] = dict(contact_summary_row) if contact_summary_row else {}
    cursor.execute(
        """
        SELECT id, contact_type, owner_type, person_name, role_title,
               source_url, source_type, provider, confidence,
               verification_status, observed_at, verified_at, stale_after
        FROM lead_contact_points
        WHERE lead_id = %s AND contact_type <> 'website'
        ORDER BY confidence DESC, updated_at DESC
        """,
        (lead.get("id"),),
    )
    artifact["contact_evidence"] = [
        json_safe({**dict(row), "id": str(dict(row).get("id"))})
        for row in cursor.fetchall() or []
    ]
    artifact["radar_signals"] = discovered_telegram_signals(cursor, lead, workstream, limit=3)
    if workstream.get("workstream_type") == "localos_sales":
        artifact.update(load_localos_sales_audit_artifact(cursor, str(lead.get("id") or "")))
    elif workstream.get("workstream_type") == "client_partnership":
        cursor.execute(
            "SELECT audit_json, match_json FROM partnershipleadartifacts WHERE lead_id = %s",
            (lead.get("id"),),
        )
        artifact_row = cursor.fetchone()
        if artifact_row:
            artifact = {**artifact, **dict(artifact_row)}
        cursor.execute(
            """
            SELECT opportunity.message_text, opportunity.message_link,
                   opportunity.message_date, opportunity.chat_title,
                   opportunity.relevance_score
            FROM lead_signal_links link
            JOIN telegram_opportunities opportunity
              ON opportunity.id = link.source_id
             AND link.source_type = 'telegram_opportunity'
            JOIN telegram_opportunity_sources radar_source ON radar_source.id = opportunity.source_id
            JOIN knowledge_sources knowledge_source ON knowledge_source.id = radar_source.knowledge_source_id
            JOIN telegram_account_permissions permission ON permission.account_id = opportunity.account_id
            WHERE link.workstream_id = %s
              AND link.status = 'selected'
              AND opportunity.business_id = %s
              AND knowledge_source.visibility = 'public'
              AND knowledge_source.status = 'active'
              AND permission.radar_enabled = TRUE
              AND opportunity.message_link IS NOT NULL
              AND opportunity.message_date >= NOW() - INTERVAL '180 days'
              AND COALESCE(opportunity.relevance_score, opportunity.score, 0) >= 40
            ORDER BY opportunity.message_date DESC
            LIMIT 3
            """,
            (workstream.get("id"), workstream.get("client_business_id")),
        )
        manual_radar_signals = [dict(row) for row in cursor.fetchall() or []]
        artifact["radar_signals"] = (artifact.get("radar_signals") or []) + manual_radar_signals
    payload = build_native_research_payload(lead, workstream, artifact)
    cursor.execute(
        """
        SELECT * FROM lead_workstream_research
        WHERE workstream_id = %s
        ORDER BY researched_at DESC, created_at DESC
        LIMIT 1
        """,
        (workstream.get("id"),),
    )
    existing_row = cursor.fetchone()
    existing = dict(existing_row) if existing_row else {}
    if existing:
        def merged_list(existing_items: Any, native_items: Any, identity_keys: tuple[str, ...]) -> list[Any]:
            result: list[Any] = []
            seen: set[str] = set()
            for item in list(existing_items or []) + list(native_items or []):
                if isinstance(item, dict):
                    identity = "|".join(str(item.get(key) or "") for key in identity_keys)
                else:
                    identity = str(item)
                if identity in seen:
                    continue
                seen.add(identity)
                result.append(item)
            return result

        existing_brief = existing.get("message_brief_json") if isinstance(existing.get("message_brief_json"), dict) else {}
        merged_brief, native_wins = merge_research_briefs(
            existing_brief,
            payload["message_brief_json"],
            existing_score=int(existing.get("score") or 0),
            native_score=int(payload["score"] or 0),
        )
        merged_signals = merged_list(existing.get("signals_json"), payload["signals_json"], ("source_url", "observed_fact", "fact"))
        merged_sources = merged_list(existing.get("sources_json"), payload["sources_json"], ("url", "source_url"))
        merged_evidence = merged_list(existing.get("evidence_json"), payload["evidence_json"], ("source_url", "fact"))
        merged_limitations = merged_list(existing.get("limitations_json"), payload["limitations_json"], tuple())
        if payload["why_now"]:
            merged_limitations = [
                item for item in merged_limitations
                if "не найден публичный специфичный сигнал" not in str(item).lower()
            ]
        cursor.execute(
            """
            UPDATE lead_workstream_research
            SET score = GREATEST(score, %s),
                qualification_stage = CASE WHEN %s > score THEN %s ELSE qualification_stage END,
                signal_label = CASE WHEN %s > score THEN %s ELSE signal_label END,
                why_now = CASE WHEN %s THEN NULLIF(%s, '') ELSE COALESCE(NULLIF(why_now, ''), NULLIF(%s, '')) END,
                score_breakdown = CASE WHEN %s THEN score_breakdown || %s ELSE score_breakdown END,
                signals_json = %s, sources_json = %s,
                contact_evidence_json = %s,
                limitations_json = %s, message_brief_json = %s,
                evidence_json = %s, researched_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (
                payload["score"], payload["score"], payload["qualification_stage"],
                payload["score"], payload["signal_label"], native_wins, payload["why_now"], payload["why_now"],
                native_wins, Json(payload["score_breakdown"]), Json(merged_signals), Json(merged_sources),
                Json(payload["contact_evidence_json"]), Json(merged_limitations),
                Json(merged_brief), Json(merged_evidence), existing.get("id"),
            ),
        )
        return dict(cursor.fetchone())
    research_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO lead_workstream_research (
            id, workstream_id, score, qualification_stage, signal_label,
            score_breakdown, why_now, signals_json, sources_json,
            contact_evidence_json, limitations_json, message_brief_json,
            message_readiness_json, evidence_json, personalization_candidates_json,
            report_hash, researched_at, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, NULLIF(%s, ''), %s, %s,
            %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
        )
        ON CONFLICT (workstream_id, report_hash) DO UPDATE SET
            score = EXCLUDED.score,
            qualification_stage = EXCLUDED.qualification_stage,
            signal_label = EXCLUDED.signal_label,
            score_breakdown = EXCLUDED.score_breakdown,
            why_now = EXCLUDED.why_now,
            signals_json = EXCLUDED.signals_json,
            sources_json = EXCLUDED.sources_json,
            contact_evidence_json = EXCLUDED.contact_evidence_json,
            limitations_json = EXCLUDED.limitations_json,
            message_brief_json = EXCLUDED.message_brief_json,
            evidence_json = EXCLUDED.evidence_json,
            researched_at = NOW()
        RETURNING *
        """,
        (
            research_id, workstream.get("id"), payload["score"], payload["qualification_stage"],
            payload["signal_label"], Json(payload["score_breakdown"]), payload["why_now"],
            Json(payload["signals_json"]), Json(payload["sources_json"]),
            Json(payload["contact_evidence_json"]), Json(payload["limitations_json"]),
            Json(payload["message_brief_json"]), Json(payload["message_readiness_json"]),
            Json(payload["evidence_json"]), Json(payload["personalization_candidates_json"]),
            payload["report_hash"],
        ),
    )
    return dict(cursor.fetchone())


def build_message_brief(
    lead: dict[str, Any],
    workstream: dict[str, Any],
    research: dict[str, Any] | None,
    contact: dict[str, Any] | None,
    sender: dict[str, Any] | None,
    suppressed: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    workstream_type = str(workstream.get("workstream_type") or "")
    category = str(lead.get("category") or "").strip()
    stored_brief = (research or {}).get("message_brief_json") or {}
    if not isinstance(stored_brief, dict):
        stored_brief = {}
    signal = str(stored_brief.get("signal") or (research or {}).get("why_now") or "").strip()
    sources = (research or {}).get("sources_json") or []
    proof_points = (sender or {}).get("proof_points_json") or []
    verified_cases = (sender or {}).get("verified_cases_json") or []
    sender_context = (
        (sender or {}).get("outreach_context_json")
        if isinstance((sender or {}).get("outreach_context_json"), dict)
        else {}
    )
    competence_status = str(sender_context.get("competence_story_status") or "approved").strip().lower()
    founder_story = (
        str((sender or {}).get("competence_story") or "").strip()
        if competence_status in {"approved", "observed"}
        else ""
    )

    def approved_fact(item: Any) -> str:
        if not isinstance(item, dict):
            return str(item or "").strip()
        status = str(item.get("status") or "approved").strip().lower()
        if status not in {"approved", "observed"}:
            return ""
        return str(
            item.get("fact") or item.get("text") or item.get("summary")
            or item.get("result") or item.get("title") or ""
        ).strip()

    proof = str(stored_brief.get("proof") or "").strip()
    approved_cases = [approved_fact(item) for item in verified_cases]
    approved_points = [approved_fact(item) for item in proof_points]
    approved_cases = [item for item in approved_cases if item]
    approved_points = [item for item in approved_points if item]
    if approved_cases:
        proof = proof or approved_cases[0]
    elif approved_points and not proof:
        proof = approved_points[0]
    elif founder_story and not proof:
        proof = founder_story
    numeric_proof_verified = any(
        bool(item.get("numeric_verified"))
        for item in verified_cases
        if isinstance(item, dict)
    )

    context_segments = sender_context.get("segments") if isinstance(sender_context.get("segments"), list) else []
    context_roles = sender_context.get("recipient_roles") if isinstance(sender_context.get("recipient_roles"), list) else []
    context_ctas = sender_context.get("allowed_ctas") if isinstance(sender_context.get("allowed_ctas"), list) else []
    context_result = str(sender_context.get("product_outcome") or "").strip()
    brief: dict[str, Any] = {
        "segment": str(stored_brief.get("segment") or category or (context_segments[0] if context_segments else "")).strip(),
        "lead_name": str(lead.get("name") or "").strip(),
        "buyer_persona": str(stored_brief.get("buyer_persona") or (contact or {}).get("role_title") or (context_roles[0] if context_roles else "")).strip(),
        "recipient_name": str((contact or {}).get("person_name") or "").strip(),
        "contact_type": (contact or {}).get("contact_type"),
        "kpi": str(stored_brief.get("kpi") or "").strip(),
        "pain": str(stored_brief.get("pain") or "").strip(),
        "pain_strength": str(stored_brief.get("pain_strength") or ("confirmed" if signal else "unknown")),
        "awareness": str(stored_brief.get("awareness") or ("problem_aware" if signal else "unknown")),
        "signal": signal,
        "result": str(stored_brief.get("result") or context_result).strip(),
        "proof": proof,
        "founder_story": founder_story,
        "proof_verified_numeric": numeric_proof_verified,
        "angle": str(stored_brief.get("angle") or "").strip(),
        "cta": str(stored_brief.get("cta") or (context_ctas[0] if context_ctas else "Обсудить короткий безопасный тест?")).strip(),
        "strategy_context": {
            "services": sender_context.get("services") or [],
            "audience": sender_context.get("audience") or "",
            "segments": context_segments,
            "geography": sender_context.get("geography") or "",
            "recipient_roles": context_roles,
            "desired_partner_types": sender_context.get("desired_partner_types") or [],
            "disqualifiers": sender_context.get("disqualifiers") or [],
        },
        "limitations": (research or {}).get("limitations_json") or [],
        "source_urls": [item.get("url") for item in sources if isinstance(item, dict) and item.get("url")],
        "evidence_ids": [
            str(item.get("id"))
            for item in ((research or {}).get("evidence_json") or [])
            if isinstance(item, dict) and item.get("id")
        ],
        "evidence_fresh": all(
            str(item.get("freshness") or "") not in {"stale", "unknown_dated_source"}
            for item in ((research or {}).get("evidence_json") or [])
            if isinstance(item, dict)
        ),
        "suppression_safe": not suppressed,
    }
    missing: list[str] = []
    missing_items: list[dict[str, str]] = []

    def add_missing(code: str, label: str) -> None:
        missing.append(label)
        missing_items.append({"code": code, "label": label})

    profile_completeness = evaluate_sender_profile_completeness(
        sender,
        workstream_type=workstream_type,
        business_service_count=workstream.get("business_service_count"),
    )
    if not sender:
        add_missing("sender_profile", "Добавьте факты об отправителе")
    else:
        for item in profile_completeness["missing_items"]:
            add_missing(str(item["code"]), str(item["label"]))
        if not sender.get("confirmed_at") and profile_completeness["ready"]:
            add_missing("sender_confirmation", "Подтвердите заполненный профиль отправителя")
    if not contact:
        add_missing("recipient_contact", "Выберите подходящий контакт")
    if workstream_type == "localos_sales":
        if not brief["segment"]:
            add_missing("lead_segment", "Укажите узкий сегмент компании")
        if not brief["buyer_persona"]:
            add_missing("recipient_role", "Найдите роль получателя")
        if not signal:
            add_missing("timing_signal", "Добавьте публичный сигнал «почему сейчас»")
        if not brief["pain"]:
            add_missing("confirmed_problem", "Добавьте подтверждённую проблему")
        if not brief["result"]:
            add_missing("first_step_result", "Укажите один конкретный результат первого шага")
        if not proof:
            add_missing("sender_proof", "Добавьте проверенное доказательство или кейс")
    else:
        client_name = str(workstream.get("client_business_name") or "клиент").strip()
        brief.update(
            {
                "buyer_persona": brief["buyer_persona"] or "владелец или менеджер партнёрств",
                "kpi": brief["kpi"] or "полезное предложение для общей локальной аудитории",
                "pain": "",
                "pain_strength": "not_required",
                "result": brief["result"] or f"проверить совместную механику с {client_name} на одном безопасном тесте",
                "angle": brief["angle"] or "совместимость аудитории и услуг",
                "client_business_name": client_name,
            }
        )
        if not category:
            add_missing("partner_category", "Подтвердите категорию потенциального партнёра")
        if workstream.get("service_compatibility_score") is None and not signal:
            add_missing(
                "partner_compatibility",
                "Подтвердите, чем бизнес отправителя и потенциальный партнёр полезны друг другу",
            )
    if suppressed:
        add_missing("suppression", "Получатель находится в stop-list")
    readiness_code = (
        "suppressed" if suppressed else (
            "ready" if not missing else ("needs_contact" if not contact else "needs_evidence")
        )
    )
    readiness = {
        "code": readiness_code,
        "label": (
            "Получатель в stop-list" if suppressed else (
                "Готово к проверке" if not missing else (
                    "Нужен контакт" if not contact else "Нужны факты"
                )
            )
        ),
        "missing": missing,
        "missing_items": missing_items,
    }
    return brief, readiness


def _clean_sentence(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" .")
    if len(text) <= limit:
        return text.rstrip(" ,;:")
    clipped = text[:limit + 1]
    if not clipped[-1].isspace():
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.rstrip(" ,;:")


def _normalized_message_fragment(value: Any) -> str:
    return " ".join(re.findall(r"[a-zа-яё0-9]+", str(value or "").lower()))


def _substantially_same_fragment(left: Any, right: Any) -> bool:
    left_normalized = _normalized_message_fragment(left)
    right_normalized = _normalized_message_fragment(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized in right_normalized or right_normalized in left_normalized:
        return True
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    if min(len(left_tokens), len(right_tokens)) < 4:
        return False
    overlap = len(left_tokens.intersection(right_tokens))
    return overlap / min(len(left_tokens), len(right_tokens)) >= 0.8


def _sentence(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.endswith((".", "!", "?", "…")) else text + "."


def _compact_approved_excerpt(value: Any, max_words: int) -> str:
    """Shorten a sourced fact without inventing a replacement claim."""

    text = str(value or "").strip()
    words = text.split()
    if not text or len(words) <= max_words:
        return text
    first_sentence = re.split(r"(?<=[.!?…])\s+", text, maxsplit=1)[0].strip()
    if 4 <= len(first_sentence.split()) <= max_words:
        return first_sentence
    first_clause = re.split(r"[:;]", first_sentence, maxsplit=1)[0].strip(" ,;:.")
    if 4 <= len(first_clause.split()) <= max_words:
        return _sentence(first_clause)
    return _sentence(" ".join(words[:max_words]).rstrip(" ,;:."))


def _lowercase_sentence_start(value: str) -> str:
    if value and re.match(r"[А-ЯЁ]", value[0]):
        return value[0].lower() + value[1:]
    return value


def _message_has_duplicate_claims(text: str) -> bool:
    fragments = [
        _normalized_message_fragment(item)
        for item in re.split(r"[.!?…]+", str(text or ""))
    ]
    meaningful = [item for item in fragments if len(item.split()) >= 5]
    return any(
        _substantially_same_fragment(left, right)
        for index, left in enumerate(meaningful)
        for right in meaningful[index + 1:]
    )


def build_first_message(
    lead: dict[str, Any],
    workstream: dict[str, Any],
    brief: dict[str, Any],
    sender: dict[str, Any],
    contact: dict[str, Any],
) -> str:
    recipient_name = _clean_sentence(contact.get("person_name"), 60)
    hello = f"{recipient_name}, здравствуйте!" if recipient_name else "Здравствуйте!"
    sender_name = _clean_sentence(sender.get("display_name"), 80)
    sender_role = _clean_sentence(sender.get("role_title"), 100)
    sender_company = _clean_sentence(sender.get("company_name"), 100)
    sender_identity = sender_role
    if sender_company and sender_company.lower() not in sender_role.lower():
        sender_identity = f"{sender_role} {sender_company}" if sender_role else sender_company
    sender_intro = _sentence(
        f"Я {sender_name}, {sender_identity}" if sender_identity else f"Я {sender_name}"
    )
    company_name = _clean_sentence(lead.get("name"), 120)
    signal = _clean_sentence(brief.get("signal"), 200).replace("?", "")
    result = _clean_sentence(brief.get("result"), 220).replace("?", "")
    founder_story = _clean_sentence(brief.get("founder_story"), 220).replace("?", "")
    if workstream.get("workstream_type") == "client_partnership":
        client_name = _clean_sentence(brief.get("client_business_name"), 120)
        context = signal or f"У {company_name} и {client_name} пересекается локальная аудитория"
        context_line = _sentence(f"Пишу от {client_name}: {context}")
        pain_line = ""
    else:
        context_line = _sentence(
            f"Обратил внимание на {company_name}: {_lowercase_sentence_start(signal)}"
        )
        pain = _clean_sentence(brief.get("pain"), 180).replace("?", "")
        pain_line = (
            _sentence(f"Отдельно стоит проверить: {pain}")
            if pain and not _substantially_same_fragment(pain, signal)
            else ""
        )
    offer = _sentence(f"В качестве первого шага могу подготовить {result}")
    founder_line = _sentence(founder_story) if founder_story else ""
    cta = _clean_sentence(brief.get("cta"), 140).replace("?", "").rstrip(" .") + "?"
    required_parts = [hello, sender_intro, context_line, founder_line, offer]
    # Proof is deliberately saved for the next angle in a multichannel chain.
    # The first touch stays focused on one signal, one founder story and one step.
    optional_parts = [pain_line]
    parts = [part for part in required_parts if part]
    cta_word_count = len(cta.split())
    for part in optional_parts:
        if part and len(" ".join(parts + [part]).split()) + cta_word_count <= 90:
            parts.append(part)
    while len(" ".join(parts).split()) + cta_word_count > 90 and len(parts) > 4:
        parts.pop()
    message = f"{' '.join(parts)} {cta}".strip()
    if len(message.split()) > 90:
        # This is a final safety net for unusually long approved facts. It keeps
        # whole words and makes the truncation explicit instead of cutting a word.
        allowed = max(1, 89 - cta_word_count)
        body_words = " ".join(parts).split()
        message = f"{' '.join(body_words[:allowed]).rstrip(' ,;:.')}… {cta}".strip()
    return message


def evaluate_first_message(text: str, brief: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    word_count = len(str(text or "").split())
    if word_count > 90:
        failures.append("Письмо длиннее 90 слов")
    if str(text or "").count("?") != 1:
        failures.append("В письме должен быть один простой вопрос")
    if any(pattern.search(str(text or "")) for pattern in UNSUPPORTED_PROMISE_PATTERNS):
        failures.append("Найдено неподтверждённое обещание")
    numeric_claim_text = str(text or "")
    for approved_field in ("lead_name", "signal", "founder_story", "proof", "result"):
        approved_value = str(brief.get(approved_field) or "").strip(" .!?…")
        if approved_value:
            numeric_claim_text = re.sub(
                re.escape(approved_value),
                "",
                numeric_claim_text,
                flags=re.I,
            )
    if (
        re.search(r"\d+(?:[.,]\d+)?\s*%", numeric_claim_text)
        and not bool(brief.get("proof_verified_numeric"))
    ):
        failures.append("Процент не подтверждён доказательством")
    if not str(brief.get("result") or "").strip():
        failures.append("Не указан один конкретный результат")
    message = str(text or "")
    signal = str(brief.get("signal") or "").strip(" .")
    pain = str(brief.get("pain") or "").strip(" .")
    lead_name = str(brief.get("lead_name") or "").strip()
    founder_story = str(brief.get("founder_story") or "").strip(" .")
    normalized_message = _normalized_message_fragment(message)
    normalized_signal = _normalized_message_fragment(signal)
    normalized_lead = _normalized_message_fragment(lead_name)
    normalized_story = _normalized_message_fragment(founder_story)
    signal_present = bool(normalized_signal and normalized_signal in normalized_message)
    lead_present = bool(normalized_lead and normalized_lead in normalized_message)
    story_present = bool(normalized_story and normalized_story in normalized_message)
    if pain and signal and _substantially_same_fragment(pain, signal):
        normalized_signal = _normalized_message_fragment(signal)
        normalized_message = _normalized_message_fragment(message)
        if normalized_signal and normalized_message.count(normalized_signal) > 1:
            failures.append("Один и тот же факт нельзя повторять как сигнал и проблему")
    if _message_has_duplicate_claims(message):
        failures.append("В письме повторяется один и тот же тезис")
    if len(re.findall(r"(?:Пишу не случайно|Вижу задачу|Из практики):", message, re.I)) >= 2:
        failures.append("Письмо звучит как набор служебных шаблонов")
    checks = {
        "removal": signal_present and lead_present,
        "bridge": signal_present and story_present,
        "fact": bool(brief.get("source_urls") and brief.get("evidence_ids")),
        "freshness": bool(brief.get("evidence_fresh")),
        "specificity": lead_present,
        "proof_integrity": bool(founder_story or brief.get("proof")),
        "channel_fit": word_count <= 90,
        "single_cta": message.count("?") == 1,
        "suppression_safety": bool(brief.get("suppression_safe")),
    }
    score = sum(2 for passed in checks.values() if passed)
    blocking_reasons = []
    if not checks["fact"]:
        blocking_reasons.append("unverified_or_unsourced_fact")
    if not checks["removal"]:
        blocking_reasons.append("decorative_personalization")
    if not checks["suppression_safety"]:
        blocking_reasons.append("recipient_suppressed")
    verdict = "approve" if score >= 15 and not failures and not blocking_reasons else (
        "reject" if blocking_reasons else "revise"
    )
    return {
        "passed": verdict == "approve",
        "verdict": verdict,
        "score": score,
        "max_score": 18,
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "failures": failures,
        "word_count": word_count,
    }


def _approved_profile_texts(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []
    approved: list[str] = []
    for item in items:
        if isinstance(item, dict):
            if str(item.get("status") or "approved").strip().lower() not in {"approved", "observed"}:
                continue
            text = str(
                item.get("text") or item.get("message") or item.get("example")
                or item.get("fact") or item.get("claim") or ""
            ).strip()
        else:
            text = str(item or "").strip()
        if text:
            approved.append(text)
    return approved


def prepare_first_message(
    lead: dict[str, Any],
    workstream: dict[str, Any],
    brief: dict[str, Any],
    sender: dict[str, Any],
    contact: dict[str, Any],
    personalization_candidate: dict[str, Any] | None,
    *,
    use_ai: bool | None = None,
    generator: Any = None,
    reviewer: Any = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Prepare one reviewed draft using the same native AI contract as campaigns."""

    deterministic_message = build_first_message(lead, workstream, brief, sender, contact)
    draft_brief = dict(brief)
    ai_enabled = ai_personalization_enabled() if use_ai is None else bool(use_ai)
    generation: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "disabled",
        "source": "deterministic",
        "prompt_version": None,
        "review_prompt_version": None,
    }
    message = deterministic_message
    semantic_review: dict[str, Any] | None = None
    if ai_enabled:
        candidate = dict(personalization_candidate or {})
        if not candidate.get("observed_fact") or not (
            candidate.get("source_url") or (brief.get("source_urls") or [None])[0]
        ):
            raise MessageQualityError(
                "missing_personalization_evidence",
                "Нельзя подготовить AI-письмо без выбранного факта и ссылки на источник",
            )
        candidate["source_url"] = candidate.get("source_url") or (brief.get("source_urls") or [None])[0]
        candidate["evidence_ids"] = list(
            candidate.get("evidence_ids")
            or ([candidate.get("evidence_id")] if candidate.get("evidence_id") else brief.get("evidence_ids") or [])
        )
        candidate["evidence_id"] = candidate.get("evidence_id") or (
            candidate["evidence_ids"][0] if candidate["evidence_ids"] else ""
        )
        candidate["founder_story"] = candidate.get("founder_story") or brief.get("founder_story")
        candidate["founder_proof"] = candidate.get("founder_proof") or brief.get("proof")
        candidate["sender"] = candidate.get("sender") or sender.get("display_name")
        candidate["sender_role"] = candidate.get("sender_role") or sender.get("role_title")
        candidate["sender_company"] = candidate.get("sender_company") or sender.get("company_name")
        candidate["next_step"] = candidate.get("next_step") or brief.get("result")
        # The evidence ledger keeps the full source text. The actual first touch
        # uses sentence-safe excerpts so long approved facts cannot turn a valid
        # enrichment job into a terminal quality failure solely on word count.
        candidate["observed_fact"] = _compact_approved_excerpt(
            candidate.get("observed_fact"), 28
        )
        candidate["founder_story"] = _compact_approved_excerpt(
            candidate.get("founder_story"), 22
        )
        candidate["founder_proof"] = _compact_approved_excerpt(
            candidate.get("founder_proof"), 18
        )
        compact_bridge = _compact_approved_excerpt(
            candidate.get("relevance_to_offer") or candidate.get("bridge"), 18
        )
        candidate["bridge"] = compact_bridge
        candidate["relevance_to_offer"] = compact_bridge
        candidate["next_step"] = _compact_approved_excerpt(candidate.get("next_step"), 16)

        draft_brief.update({
            "signal": candidate.get("observed_fact"),
            "founder_story": candidate.get("founder_story"),
            "proof": candidate.get("founder_proof") or brief.get("proof"),
            "source_urls": [candidate.get("source_url")],
            "evidence_ids": candidate["evidence_ids"],
            "evidence_fresh": str(candidate.get("freshness") or "") not in {
                "stale", "unknown_dated_source",
            },
            "selected_personalization_id": candidate.get("id"),
        })
        channel = str(contact.get("contact_type") or "manual").strip().lower()
        if channel not in {"telegram", "email", "whatsapp", "max", "vk", "sms", "manual"}:
            channel = "manual"
        generation = generate_personalized_sequence(
            motion=str(workstream.get("workstream_type") or ""),
            identity={
                "company_name": str(lead.get("name") or ""),
                "contact_name": str(contact.get("person_name") or ""),
                "contact_role": str(contact.get("role_title") or ""),
            },
            candidate=candidate,
            founder_story={
                "story": candidate.get("founder_story"),
                "proof": candidate.get("founder_proof"),
                "offer": candidate.get("next_step"),
                "forbidden_claims": _approved_profile_texts(sender.get("forbidden_claims_json")),
            },
            sequence=[{
                "sequence_index": 0,
                "channel": channel,
                "angle": "founder_story",
                "day_offset": 0,
                "text": deterministic_message,
                "subject": None,
            }],
            voice_examples=_approved_profile_texts(sender.get("voice_examples_json")),
            business_id=str(workstream.get("client_business_id") or ""),
            user_id=str(sender.get("created_by") or workstream.get("created_by") or ""),
            generator=generator,
            reviewer=reviewer,
        )
        if generation.get("status") != "ready":
            raise PersonalizationGenerationError(
                str(generation.get("error_code") or "ai_generation_failed"),
                str(generation.get("error") or "AI не вернул проверяемый персонализированный текст"),
            )
        touches = generation.get("touches") or []
        reviews = generation.get("semantic_reviews") or []
        if not touches or not reviews:
            raise PersonalizationGenerationError(
                "ai_generation_incomplete",
                "AI не вернул текст и независимую семантическую проверку",
            )
        semantic_review = dict(reviews[0])
        if not semantic_review.get("passed"):
            reason_codes = ", ".join(semantic_review.get("reason_codes") or [])
            raise PersonalizationGenerationError(
                "semantic_review_failed",
                reason_codes or "AI-текст не прошёл независимую семантическую проверку",
            )
        message = str(touches[0].get("text") or "").strip()

    quality = evaluate_first_message(message, draft_brief)
    quality["generation"] = {
        "schema_version": generation.get("schema_version"),
        "status": generation.get("status"),
        "source": generation.get("source"),
        "prompt_version": generation.get("prompt_version"),
        "review_prompt_version": generation.get("review_prompt_version"),
    }
    if semantic_review is not None:
        quality["semantic_review"] = semantic_review
    if not quality.get("passed"):
        raise MessageQualityError(
            "message_quality_failed",
            "; ".join(quality.get("failures") or quality.get("blocking_reasons") or [
                "Текст не прошёл quality gate",
            ]),
        )
    return message, quality, draft_brief


def enqueue_enrichment_job(
    cursor,
    workstream_id: str,
    force: bool = False,
    allow_paid_enrichment: bool = False,
) -> dict[str, Any]:
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s))",
        (f"lead-enrichment:{workstream_id}",),
    )
    cursor.execute(
        """
        SELECT * FROM lead_enrichment_jobs
        WHERE workstream_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (workstream_id,),
    )
    latest = cursor.fetchone()
    if latest and str(latest.get("status") if isinstance(latest, dict) else latest[2]) in ACTIVE_JOB_STATUSES:
        payload = dict(latest)
        if allow_paid_enrichment and not bool(payload.get("allow_paid_enrichment")):
            cursor.execute(
                """
                UPDATE lead_enrichment_jobs
                SET allow_paid_enrichment = TRUE, updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (payload.get("id"),),
            )
            payload = dict(cursor.fetchone())
        payload["reused"] = True
        return payload
    if latest and not force:
        payload = dict(latest)
        payload["reused"] = True
        return payload
    job_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO lead_enrichment_jobs (
            id, workstream_id, status, current_phase, attempt_count,
            max_attempts, next_attempt_at, allow_paid_enrichment, created_at, updated_at
        ) VALUES (%s, %s, 'queued', 'collecting', 0, 2, NOW(), %s, NOW(), NOW())
        RETURNING *
        """,
        (job_id, workstream_id, allow_paid_enrichment),
    )
    payload = dict(cursor.fetchone())
    payload["reused"] = False
    return payload


def sync_parsed_lead_contacts(cursor, lead: dict[str, Any]) -> dict[str, int]:
    lead_id = str(lead.get("id") or "").strip()
    if not lead_id:
        return {"contacts_saved": 0, "jobs_queued": 0}
    contacts = exclude_public_channel_contacts(cursor, lead_id, legacy_contact_candidates(lead))
    contacts_saved = upsert_contact_points(cursor, lead_id, contacts)
    cursor.execute("SELECT id FROM lead_workstreams WHERE lead_id = %s", (lead_id,))
    workstream_rows = cursor.fetchall() or []
    jobs_queued = 0
    for row in workstream_rows:
        workstream_id = row.get("id") if isinstance(row, dict) else row[0]
        job = enqueue_enrichment_job(cursor, str(workstream_id), force=True)
        if not job.get("reused"):
            jobs_queued += 1
    return {"contacts_saved": contacts_saved, "jobs_queued": jobs_queued}


def claim_next_enrichment_job(cursor) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT job.id
        FROM lead_enrichment_jobs job
        WHERE job.status IN ('queued', 'retry_wait')
          AND job.next_attempt_at <= NOW()
        ORDER BY CASE WHEN job.status = 'retry_wait' THEN 0 ELSE 1 END,
                 job.next_attempt_at ASC, job.created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    if not row:
        return None
    job_id = row.get("id") if isinstance(row, dict) else row[0]
    cursor.execute(
        """
        UPDATE lead_enrichment_jobs
        SET status = 'collecting', current_phase = 'collecting',
            started_at = COALESCE(started_at, NOW()), attempt_count = attempt_count + 1,
            error_code = NULL, error_message = NULL, updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (job_id,),
    )
    return dict(cursor.fetchone())


def recover_interrupted_enrichment_jobs(cursor, *, minimum_age_seconds: int = 30) -> list[str]:
    """Return jobs abandoned by a stopped worker to the retry queue."""
    minimum_age = max(1, int(minimum_age_seconds))
    cursor.execute(
        """
        UPDATE lead_enrichment_jobs
        SET status = 'retry_wait',
            current_phase = 'collecting',
            next_attempt_at = NOW(),
            error_code = 'worker_interrupted',
            error_message = 'Worker stopped before enrichment completed',
            updated_at = NOW()
        WHERE status IN ('collecting', 'verifying', 'researching', 'drafting')
          AND updated_at <= NOW() - (%s * INTERVAL '1 second')
        RETURNING id
        """,
        (minimum_age,),
    )
    return [
        str(row.get("id") if isinstance(row, dict) else row[0])
        for row in cursor.fetchall() or []
    ]


def _hunter_contacts(
    cursor,
    lead: dict[str, Any],
    workstream: dict[str, Any],
    allow_paid_enrichment: bool,
) -> tuple[list[dict[str, Any]], int]:
    enabled = str(os.getenv("PROSPECTING_HUNTER_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on"}
    api_key = str(os.getenv("HUNTER_API_KEY") or "").strip()
    qualification_states = {
        str(workstream.get("status") or ""),
        str(workstream.get("pipeline_status") or ""),
        str(workstream.get("legacy_lead_status") or ""),
    }
    if not allow_paid_enrichment or not enabled or not api_key or not qualification_states.intersection({"qualified", "selected_for_outreach", "converted"}):
        return [], 0
    website = normalize_contact_value("website", lead.get("website"))
    domain = urlparse(website).netloc.lower().removeprefix("www.") if website else ""
    if not domain:
        return [], 0
    limit = max(1, min(int(os.getenv("PROSPECTING_HUNTER_CANDIDATE_LIMIT", "3")), 10))
    daily_budget = max(0, int(os.getenv("PROSPECTING_HUNTER_DAILY_REQUEST_LIMIT", "20")))
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext('prospecting-hunter-daily-budget'))")
    cursor.execute(
        """
        SELECT COALESCE(SUM(hunter_requests_used), 0)::INT AS used
        FROM lead_enrichment_jobs
        WHERE created_at >= CURRENT_DATE
        """
    )
    budget_row = cursor.fetchone()
    used_today = int((budget_row.get("used") if isinstance(budget_row, dict) else budget_row[0]) or 0)
    remaining = max(0, daily_budget - used_today)
    if remaining < 1:
        return [], 0
    if remaining > 1:
        limit = min(limit, remaining - 1)
    response = requests.get(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "limit": limit, "api_key": api_key},
        timeout=12,
    )
    response.raise_for_status()
    requests_used = 1
    contacts: list[dict[str, Any]] = []
    for item in ((response.json().get("data") or {}).get("emails") or [])[:limit]:
        email = str(item.get("value") or "").strip()
        normalized = normalize_contact_value("email", email)
        if not normalized:
            continue
        person_name = " ".join(part for part in (item.get("first_name"), item.get("last_name")) if part).strip()
        verifier_status = "unknown"
        if requests_used < remaining:
            verify_response = requests.get(
                "https://api.hunter.io/v2/email-verifier",
                params={"email": email, "api_key": api_key},
                timeout=12,
            )
            verify_response.raise_for_status()
            requests_used += 1
            verifier_payload = verify_response.json().get("data") or {}
            raw_status = str(verifier_payload.get("status") or "unknown").lower()
            verifier_status = {
                "valid": "verified",
                "accept_all": "accept_all",
                "invalid": "invalid",
            }.get(raw_status, "unknown")
        contacts.append(
            {
                "contact_type": "email",
                "value": email,
                "normalized_value": normalized,
                "owner_type": "person" if person_name else "company",
                "person_name": person_name,
                "role_title": str(item.get("position") or "").strip(),
                "source_url": str(item.get("sources", [{}])[0].get("uri") if item.get("sources") else "") or None,
                "source_type": "hunter_public_sources",
                "provider": "hunter",
                "confidence": max(0.0, min(float(item.get("confidence") or 0) / 100.0, 1.0)),
                "verification_status": verifier_status,
                "metadata": {
                    "hunter_sources": item.get("sources") or [],
                    "hunter_confidence": item.get("confidence"),
                },
            }
        )
    return contacts, requests_used


def _sync_legacy_best_contact(cursor, lead_id: str) -> None:
    mapping = {
        "phone": "phone",
        "email": "email",
        "telegram": "telegram_url",
        "whatsapp": "whatsapp_url",
    }
    updates: dict[str, str] = {}
    for contact_type, column in mapping.items():
        cursor.execute(
            """
            SELECT value FROM lead_contact_points
            WHERE lead_id = %s AND contact_type = %s AND verification_status <> 'invalid'
            ORDER BY
              CASE verification_status WHEN 'verified' THEN 0 WHEN 'confirmed_source' THEN 1 ELSE 2 END,
              confidence DESC, updated_at DESC
            LIMIT 1
            """,
            (lead_id, contact_type),
        )
        row = cursor.fetchone()
        if row:
            updates[column] = str(row.get("value") if isinstance(row, dict) else row[0])
    if not updates:
        return
    assignments = ", ".join(f"{column} = %s" for column in updates)
    cursor.execute(
        f"UPDATE prospectingleads SET {assignments}, updated_at = NOW() WHERE id = %s",
        tuple(updates.values()) + (lead_id,),
    )


def process_enrichment_job(cursor, job: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT ws.*, client.name AS client_business_name,
               lead.name, lead.category, lead.city, lead.address, lead.phone, lead.email,
               lead.telegram_url, lead.whatsapp_url, lead.website, lead.source_url,
               lead.messenger_links_json, lead.pipeline_status, lead.rating,
               lead.reviews_count, lead.reviews_json, lead.services_json,
               lead.description, lead.raw_payload_json, lead.enrich_payload_json,
               lead.status AS legacy_lead_status
        FROM lead_workstreams ws
        JOIN prospectingleads lead ON lead.id = ws.lead_id
        LEFT JOIN businesses client ON client.id = ws.client_business_id
        WHERE ws.id = %s
        """,
        (job.get("workstream_id"),),
    )
    row = cursor.fetchone()
    if not row:
        raise LookupError("Lead workstream not found")
    combined = dict(row)
    lead = {
        key: combined.get(key)
        for key in (
            "lead_id", "name", "category", "city", "address", "phone", "email",
            "telegram_url", "whatsapp_url", "website", "source_url", "messenger_links_json",
            "rating", "reviews_count", "reviews_json", "services_json", "description",
            "raw_payload_json", "enrich_payload_json",
        )
    }
    lead["id"] = combined.get("lead_id")
    workstream = dict(combined)
    if workstream.get("workstream_type") == "client_partnership":
        cursor.execute(
            """
            SELECT COUNT(*) AS service_count
            FROM userservices
            WHERE business_id = %s AND COALESCE(is_active, TRUE) = TRUE
            """,
            (workstream.get("client_business_id"),),
        )
        service_row = cursor.fetchone()
        workstream["business_service_count"] = int(
            (service_row.get("service_count") if isinstance(service_row, dict) else service_row[0]) or 0
        )

    cursor.execute("UPDATE lead_enrichment_jobs SET status = 'collecting', current_phase = 'collecting', updated_at = NOW() WHERE id = %s", (job.get("id"),))
    contacts = exclude_public_channel_contacts(cursor, str(lead["id"]), legacy_contact_candidates(lead))
    website_contacts, warnings = collect_public_website_contacts(lead.get("website"))
    contacts.extend(website_contacts)
    upsert_contact_points(cursor, str(lead["id"]), contacts)

    cursor.execute("UPDATE lead_enrichment_jobs SET status = 'verifying', current_phase = 'verifying', updated_at = NOW() WHERE id = %s", (job.get("id"),))
    verify_contact_points(cursor, str(lead["id"]), lead.get("website"))
    best_contact = _select_best_contact(cursor, workstream)
    hunter_used = 0
    if not best_contact or best_contact.get("owner_type") != "person" or best_contact.get("verification_status") not in VERIFIED_STATUSES:
        hunter_contacts, hunter_used = _hunter_contacts(
            cursor,
            lead,
            workstream,
            bool(job.get("allow_paid_enrichment")),
        )
        upsert_contact_points(cursor, str(lead["id"]), hunter_contacts)
        best_contact = _select_best_contact(cursor, workstream)
    if best_contact and not workstream.get("selected_contact_point_id"):
        cursor.execute(
            """
            UPDATE lead_workstreams
            SET selected_contact_point_id = %s, updated_at = NOW()
            WHERE id = %s AND selected_contact_point_id IS NULL
            """,
            (best_contact.get("id"), workstream.get("id")),
        )
        workstream["selected_contact_point_id"] = best_contact.get("id")
    _sync_legacy_best_contact(cursor, str(lead["id"]))

    cursor.execute("UPDATE lead_enrichment_jobs SET status = 'researching', current_phase = 'researching', updated_at = NOW() WHERE id = %s", (job.get("id"),))
    research = upsert_native_research(cursor, lead, workstream)
    sender = _load_sender_profile(cursor, workstream)
    scope_type = "platform" if workstream.get("workstream_type") == "localos_sales" else "business"
    suppression_business_id = None if scope_type == "platform" else workstream.get("client_business_id")
    cursor.execute(
        """
        SELECT reason_code
        FROM outreach_suppressions
        WHERE (expires_at IS NULL OR expires_at > NOW())
          AND lead_id = %s
          AND (
              scope_type = 'platform_safety'
              OR (scope_type = %s AND COALESCE(business_id, '') = COALESCE(%s, ''))
          )
        LIMIT 1
        """,
        (lead.get("id"), scope_type, suppression_business_id),
    )
    suppression_row = cursor.fetchone()
    suppressed = bool(suppression_row)
    brief, readiness = build_message_brief(
        lead, workstream, research, best_contact, sender, suppressed=suppressed,
    )
    brief = json_safe(brief)
    readiness = json_safe(readiness)
    personalization_context = {
        **workstream,
        "lead_name": lead.get("name"),
        "rating": lead.get("rating"),
        "reviews_count": lead.get("reviews_count"),
        "website": lead.get("website"),
        "source_url": lead.get("source_url"),
        "research": research,
        "sender_profile": sender or {},
    }
    evidence = json_safe(build_evidence_ledger(personalization_context))
    personalization_candidates = json_safe(
        build_personalization_candidates(personalization_context, evidence)
    )
    if research:
        cursor.execute(
            """
            UPDATE lead_workstream_research
            SET message_brief_json = %s, message_readiness_json = %s,
                evidence_json = %s, personalization_candidates_json = %s,
                selected_personalization_id = %s
            WHERE id = %s
            """,
            (
                Json(brief), Json(readiness), Json(evidence), Json(personalization_candidates),
                personalization_candidates[0]["id"] if personalization_candidates else None,
                research.get("id"),
            ),
        )

    cursor.execute("UPDATE lead_enrichment_jobs SET status = 'drafting', current_phase = 'drafting', message_brief_json = %s, readiness_json = %s, updated_at = NOW() WHERE id = %s", (Json(brief), Json(readiness), job.get("id")))
    draft_id = None
    draft_brief = brief
    quality: dict[str, Any] = {"passed": False, "failures": readiness.get("missing") or []}
    if readiness.get("code") == "ready" and sender and best_contact:
        selected_candidate = personalization_candidates[0] if personalization_candidates else None
        message, quality, draft_brief = prepare_first_message(
            lead,
            workstream,
            brief,
            sender,
            best_contact,
            selected_candidate,
        )
        if quality.get("passed"):
            draft_hash = hashlib.sha256(
                json.dumps(
                    {"workstream_id": str(workstream.get("id")), "brief": brief, "contact_id": str(best_contact.get("id"))},
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()[:24]
            draft_id = f"contact-intel-{draft_hash}"
            cursor.execute(
                """
                INSERT INTO outreachmessagedrafts (
                    id, lead_id, workstream_id, channel, angle_type, tone, status,
                    generated_text, created_by, research_id, contact_point_id,
                    sender_profile_id, enrichment_job_id, message_brief_json,
                    quality_gate_json, include_room_link, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, 'evidence_based', 'human', 'generated',
                    %s, 'contact_intelligence', %s, %s, %s, %s, %s, %s, FALSE, NOW(), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    generated_text = EXCLUDED.generated_text,
                    research_id = EXCLUDED.research_id,
                    contact_point_id = EXCLUDED.contact_point_id,
                    sender_profile_id = EXCLUDED.sender_profile_id,
                    enrichment_job_id = EXCLUDED.enrichment_job_id,
                    message_brief_json = EXCLUDED.message_brief_json,
                    quality_gate_json = EXCLUDED.quality_gate_json,
                    updated_at = NOW()
                """,
                (
                    draft_id, lead.get("id"), workstream.get("id"), best_contact.get("contact_type"),
                    message, (research or {}).get("id"), best_contact.get("id"), sender.get("id"),
                    job.get("id"), Json(draft_brief), Json(quality),
                ),
            )
    if readiness.get("code") == "ready" and not quality.get("passed"):
        raise MessageQualityError(
            "message_not_prepared",
            "Фактов достаточно, но проверяемый персонализированный текст не подготовлен",
        )
    final_status = "ready" if quality.get("passed") else str(readiness.get("code") or "needs_evidence")
    if final_status not in {"ready", "needs_contact", "needs_evidence", "suppressed"}:
        final_status = "needs_evidence"
    result = {
        "lead_id": str(lead.get("id")),
        "workstream_id": str(workstream.get("id")),
        "workstream_type": workstream.get("workstream_type"),
        "client_business_id": workstream.get("client_business_id"),
        "selected_channel": workstream.get("selected_channel") or (best_contact or {}).get("contact_type") or "manual",
        "actor_id": str((sender or {}).get("created_by") or workstream.get("created_by") or ""),
        "contacts_collected": len(contacts),
        "selected_contact_point_id": str(best_contact.get("id")) if best_contact else None,
        "draft_id": draft_id,
        "warnings": warnings,
    }
    cursor.execute(
        """
        UPDATE lead_enrichment_jobs
        SET status = %s, current_phase = %s, completed_at = NOW(),
            hunter_requests_used = hunter_requests_used + %s,
            message_brief_json = %s, readiness_json = %s, result_json = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (final_status, final_status, hunter_used, Json(brief), Json(readiness), Json(result), job.get("id")),
    )
    updated_job = dict(cursor.fetchone())
    lifecycle_status = "ready_for_draft" if final_status == "ready" else final_status
    cursor.execute(
        """
        UPDATE lead_workstreams
        SET lifecycle_status = %s,
            status_reason = %s,
            next_step = %s,
            state_changed_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            lifecycle_status,
            None if final_status == "ready" else ", ".join(readiness.get("missing") or []),
            "Проверить персонализированную цепочку" if final_status == "ready" else (
                "Не писать: получатель в stop-list" if final_status == "suppressed" else (
                    "Найти контакт получателя" if final_status == "needs_contact" else "Добавить подтверждённые факты"
                )
            ),
            workstream.get("id"),
        ),
    )
    return updated_job


def provider_error_is_retryable(error: Exception) -> bool:
    response = error.response if isinstance(error, requests.HTTPError) else None
    status_code = int(response.status_code or 0) if response is not None else 0
    return bool(getattr(error, "retryable", False)) or isinstance(
        error, (requests.Timeout, requests.ConnectionError)
    ) or status_code in {408, 425, 429, 500, 502, 503, 504}


def fail_enrichment_job(cursor, job: dict[str, Any], error: Exception) -> dict[str, Any]:
    attempt_count = int(job.get("attempt_count") or 0)
    max_attempts = int(job.get("max_attempts") or 2)
    retryable = provider_error_is_retryable(error)
    status = "retry_wait" if retryable and attempt_count < max_attempts else "failed"
    error_code = str(getattr(error, "code", "") or error.__class__.__name__)
    error_message = str(error)[:1000]
    cursor.execute(
        """
        UPDATE lead_enrichment_jobs
        SET status = %s, current_phase = %s,
            next_attempt_at = CASE WHEN %s = 'retry_wait' THEN NOW() + INTERVAL '10 minutes' ELSE next_attempt_at END,
            completed_at = CASE WHEN %s = 'failed' THEN NOW() ELSE NULL END,
            error_code = %s, error_message = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            status, status, status, status, error_code,
            error_message, job.get("id"),
        ),
    )
    updated_job = dict(cursor.fetchone())
    cursor.execute(
        """
        UPDATE lead_workstreams workstream
        SET lifecycle_status = CASE WHEN %s = 'retry_wait' THEN 'enriching' ELSE 'needs_attention' END,
            status_reason = %s,
            next_step = CASE
                WHEN %s = 'retry_wait' THEN 'LocalOS повторит enrichment автоматически'
                ELSE 'Проверьте ошибку enrichment и запустите повторную обработку'
            END,
            state_changed_at = NOW(),
            updated_at = NOW()
        FROM lead_enrichment_jobs job
        WHERE job.id = %s
          AND workstream.id = job.workstream_id
        """,
        (status, error_message, status, job.get("id")),
    )
    return updated_job


def serialize_contact_point(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id")),
        "type": row.get("contact_type"),
        "value": row.get("value"),
        "owner_type": row.get("owner_type"),
        "person_name": row.get("person_name"),
        "role_title": row.get("role_title"),
        "source_url": row.get("source_url"),
        "source_type": row.get("source_type"),
        "provider": row.get("provider"),
        "confidence": float(row.get("confidence") or 0),
        "verification_status": row.get("verification_status"),
        "observed_at": row.get("observed_at"),
        "verified_at": row.get("verified_at"),
        "stale_after": row.get("stale_after"),
    }
