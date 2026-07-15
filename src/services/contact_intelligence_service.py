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
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from psycopg2.extras import Json, RealDictCursor

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
        parsed = urlparse(raw)
        host = parsed.netloc.lower().removeprefix("www.")
        path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/")
        return f"https://{host}{path}" + (f"?{parsed.query}" if parsed.query else "")
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
    host = urlparse(candidate).netloc.lower().removeprefix("www.")
    return SOCIAL_HOST_TYPES.get(host)


def _public_http_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw if re.match(r"^https?://", raw, re.I) else "https://" + raw.lstrip("/")
    parsed = urlparse(candidate)
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
        except requests.RequestException:
            warnings.append(f"Не удалось проверить {page_url}")
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for contact in contacts:
        key = (str(contact.get("contact_type")), str(contact.get("normalized_value")))
        unique[key] = contact
    return list(unique.values()), warnings


def legacy_contact_candidates(lead: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add(contact_type: str, value: Any, confidence: float = 0.62) -> None:
        normalized = normalize_contact_value(contact_type, value)
        if normalized:
            candidates.append(
                {
                    "contact_type": contact_type,
                    "value": str(value or "").strip(),
                    "normalized_value": normalized,
                    "source_url": lead.get("source_url"),
                    "source_type": "map_card",
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
    return candidates


def upsert_contact_points(cursor, lead_id: str, contacts: list[dict[str, Any]]) -> int:
    saved = 0
    for contact in contacts:
        contact_type = str(contact.get("contact_type") or "").strip().lower()
        normalized = normalize_contact_value(contact_type, contact.get("normalized_value") or contact.get("value"))
        if contact_type not in CONTACT_TYPES or not normalized:
            continue
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
                str(uuid.uuid4()), lead_id, contact_type, str(contact.get("value") or normalized), normalized,
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


def build_message_brief(
    lead: dict[str, Any],
    workstream: dict[str, Any],
    research: dict[str, Any] | None,
    contact: dict[str, Any] | None,
    sender: dict[str, Any] | None,
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
    proof = str(stored_brief.get("proof") or "").strip()
    if verified_cases:
        case = verified_cases[0]
        proof = proof or str(case.get("summary") if isinstance(case, dict) else case).strip()
    elif proof_points and not proof:
        item = proof_points[0]
        proof = str(item.get("text") if isinstance(item, dict) else item).strip()
    elif sources and not proof:
        item = sources[0]
        proof = str(item.get("title") if isinstance(item, dict) else item).strip()
    numeric_proof_verified = any(
        bool(item.get("numeric_verified"))
        for item in verified_cases
        if isinstance(item, dict)
    )

    brief: dict[str, Any] = {
        "segment": str(stored_brief.get("segment") or category).strip(),
        "buyer_persona": str(stored_brief.get("buyer_persona") or (contact or {}).get("role_title") or "").strip(),
        "recipient_name": str((contact or {}).get("person_name") or "").strip(),
        "contact_type": (contact or {}).get("contact_type"),
        "kpi": str(stored_brief.get("kpi") or "").strip(),
        "pain": str(stored_brief.get("pain") or "").strip(),
        "pain_strength": str(stored_brief.get("pain_strength") or ("confirmed" if signal else "unknown")),
        "awareness": str(stored_brief.get("awareness") or ("problem_aware" if signal else "unknown")),
        "signal": signal,
        "result": str(stored_brief.get("result") or "").strip(),
        "proof": proof,
        "proof_verified_numeric": numeric_proof_verified,
        "angle": str(stored_brief.get("angle") or "").strip(),
        "cta": str(stored_brief.get("cta") or "Обсудить короткий безопасный тест?").strip(),
        "limitations": (research or {}).get("limitations_json") or [],
        "source_urls": [item.get("url") for item in sources if isinstance(item, dict) and item.get("url")],
    }
    missing: list[str] = []
    if not sender or not sender.get("confirmed_at"):
        missing.append("Подтвердите профиль отправителя")
    if not contact:
        missing.append("Выберите подходящий контакт")
    if workstream_type == "localos_sales":
        if not brief["segment"]:
            missing.append("Укажите узкий сегмент компании")
        if not brief["buyer_persona"]:
            missing.append("Найдите роль получателя")
        if not signal:
            missing.append("Добавьте публичный сигнал «почему сейчас»")
        if not brief["pain"]:
            missing.append("Добавьте подтверждённую проблему")
        if not brief["result"]:
            missing.append("Укажите один конкретный результ первого шага")
        if not proof:
            missing.append("Добавьте проверенное доказательство или кейс")
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
            missing.append("Подтвердите категорию потенциального партнёра")
        if workstream.get("service_compatibility_score") is None and not signal:
            missing.append("Подтвердите совместимость услуг или общий контекст")
    readiness = {
        "code": "ready" if not missing else ("needs_contact" if not contact else "needs_facts"),
        "label": "Готово к проверке" if not missing else ("Нужен контакт" if not contact else "Нужны факты"),
        "missing": missing,
    }
    return brief, readiness


def _clean_sentence(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" .")
    return text[:limit].rstrip(" ,;:")


def build_first_message(
    lead: dict[str, Any],
    workstream: dict[str, Any],
    brief: dict[str, Any],
    sender: dict[str, Any],
    contact: dict[str, Any],
) -> str:
    recipient_name = _clean_sentence(contact.get("person_name"), 60)
    hello = f"{recipient_name}, здравствуйте!" if recipient_name else "Здравствуйте!"
    sender_intro = f"Я {_clean_sentence(sender.get('display_name'), 80)}, {_clean_sentence(sender.get('role_title'), 100)} в {_clean_sentence(sender.get('company_name'), 100)}."
    company_name = _clean_sentence(lead.get("name"), 120)
    signal = _clean_sentence(brief.get("signal"), 200).replace("?", "")
    result = _clean_sentence(brief.get("result"), 220).replace("?", "")
    proof = _clean_sentence(brief.get("proof"), 180).replace("?", "")
    if workstream.get("workstream_type") == "client_partnership":
        client_name = _clean_sentence(brief.get("client_business_name"), 120)
        context = signal or f"У {company_name} и {client_name} пересекается локальная аудитория"
        context_line = f"Пишу от {client_name}: {context}."
        pain_line = ""
    else:
        context_line = f"Пишу по {company_name}: {signal}."
        pain = _clean_sentence(brief.get("pain"), 180).replace("?", "")
        pain_line = f"Вижу задачу: {pain}." if pain else ""
    offer = f"Предлагаю начать с {result}."
    proof_line = f"Основание: {proof}." if proof else ""
    cta = _clean_sentence(brief.get("cta"), 140).replace("?", "").rstrip(" .") + "?"
    body = " ".join(part for part in (hello, sender_intro, context_line, pain_line, offer, proof_line) if part)
    body_words = body.split()
    cta_words = cta.split()
    available_body_words = max(1, 90 - len(cta_words))
    if len(body_words) > available_body_words:
        body = " ".join(body_words[:available_body_words]).rstrip(" ,;:") + "."
    return f"{body} {cta}".strip()


def evaluate_first_message(text: str, brief: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    word_count = len(str(text or "").split())
    if word_count > 90:
        failures.append("Письмо длиннее 90 слов")
    if str(text or "").count("?") != 1:
        failures.append("В письме должен быть один простой вопрос")
    if any(pattern.search(str(text or "")) for pattern in UNSUPPORTED_PROMISE_PATTERNS):
        failures.append("Найдено неподтверждённое обещание")
    if re.search(r"\d+\s*%", str(text or "")) and not bool(brief.get("proof_verified_numeric")):
        failures.append("Процент не подтверждён доказательством")
    if not str(brief.get("result") or "").strip():
        failures.append("Не указан один конкретный результат")
    return {"passed": not failures, "failures": failures, "word_count": word_count}


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
    contacts_saved = upsert_contact_points(cursor, lead_id, legacy_contact_candidates(lead))
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
        ORDER BY job.next_attempt_at ASC, job.created_at ASC
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
               lead.messenger_links_json, lead.pipeline_status,
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
        )
    }
    lead["id"] = combined.get("lead_id")
    workstream = dict(combined)

    cursor.execute("UPDATE lead_enrichment_jobs SET status = 'collecting', current_phase = 'collecting', updated_at = NOW() WHERE id = %s", (job.get("id"),))
    contacts = legacy_contact_candidates(lead)
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
    cursor.execute(
        """
        SELECT * FROM lead_workstream_research
        WHERE workstream_id = %s
        ORDER BY researched_at DESC, created_at DESC
        LIMIT 1
        """,
        (workstream.get("id"),),
    )
    research_row = cursor.fetchone()
    research = dict(research_row) if research_row else None
    sender = _load_sender_profile(cursor, workstream)
    brief, readiness = build_message_brief(lead, workstream, research, best_contact, sender)
    if research:
        cursor.execute(
            """
            UPDATE lead_workstream_research
            SET message_brief_json = %s, message_readiness_json = %s
            WHERE id = %s
            """,
            (Json(brief), Json(readiness), research.get("id")),
        )

    cursor.execute("UPDATE lead_enrichment_jobs SET status = 'drafting', current_phase = 'drafting', message_brief_json = %s, readiness_json = %s, updated_at = NOW() WHERE id = %s", (Json(brief), Json(readiness), job.get("id")))
    draft_id = None
    quality: dict[str, Any] = {"passed": False, "failures": readiness.get("missing") or []}
    if readiness.get("code") == "ready" and sender and best_contact:
        message = build_first_message(lead, workstream, brief, sender, best_contact)
        quality = evaluate_first_message(message, brief)
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
                    job.get("id"), Json(brief), Json(quality),
                ),
            )
    final_status = "ready" if quality.get("passed") else "needs_input"
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
    return dict(cursor.fetchone())


def provider_error_is_retryable(error: Exception) -> bool:
    response = error.response if isinstance(error, requests.HTTPError) else None
    status_code = int(response.status_code or 0) if response is not None else 0
    return isinstance(error, (requests.Timeout, requests.ConnectionError)) or status_code in {408, 425, 429, 500, 502, 503, 504}


def fail_enrichment_job(cursor, job: dict[str, Any], error: Exception) -> dict[str, Any]:
    attempt_count = int(job.get("attempt_count") or 0)
    max_attempts = int(job.get("max_attempts") or 2)
    retryable = provider_error_is_retryable(error)
    status = "retry_wait" if retryable and attempt_count < max_attempts else "failed"
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
            status, status, status, status, error.__class__.__name__,
            str(error)[:1000], job.get("id"),
        ),
    )
    return dict(cursor.fetchone())


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
