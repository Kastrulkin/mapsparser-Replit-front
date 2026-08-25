from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from html import unescape
from typing import Any
from urllib.parse import urlsplit

import requests
from psycopg2.extras import Json, RealDictCursor


USER_AGENT = "LocalOSCreatorVerification/1.0 (+https://localos.pro)"
TITLE_PATTERNS = (
    re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', re.IGNORECASE),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', re.IGNORECASE),
    re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL),
)
DESCRIPTION_PATTERNS = (
    re.compile(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)', re.IGNORECASE),
    re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', re.IGNORECASE),
)
STOPWORDS = {"the", "and", "для", "или", "это", "как", "что", "канал", "блог", "official", "instagram", "telegram"}


def _json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _clean_html_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", unescape(str(value or "")))
    return re.sub(r"\s+", " ", text).strip()[:1000]


def _first_match(html: str, patterns: tuple[re.Pattern[str], ...]) -> str:
    for pattern in patterns:
        match = pattern.search(html)
        if match:
            return _clean_html_text(match.group(1))
    return ""


def _tokens(value: Any) -> set[str]:
    normalized = str(value or "").casefold().replace("ё", "е")
    return {
        token
        for token in re.findall(r"[a-zа-я0-9]{3,}", normalized)
        if token not in STOPWORDS
    }


def compare_creator_identity(expected_title: Any, expected_description: Any, observed_title: Any, observed_description: Any) -> dict[str, Any]:
    expected = _clean_html_text(f"{expected_title or ''} {expected_description or ''}")
    observed = _clean_html_text(f"{observed_title or ''} {observed_description or ''}")
    expected_tokens = _tokens(expected)
    observed_tokens = _tokens(observed)
    token_overlap = len(expected_tokens.intersection(observed_tokens)) / max(1, len(expected_tokens))
    title_similarity = SequenceMatcher(
        None,
        _clean_html_text(expected_title).casefold(),
        _clean_html_text(observed_title).casefold(),
    ).ratio()
    enough_identity = len(expected_tokens) >= 2 and len(observed_tokens) >= 2
    mismatch = enough_identity and token_overlap < 0.15 and title_similarity < 0.22
    return {
        "mismatch": mismatch,
        "title_similarity": round(title_similarity, 4),
        "token_overlap": round(token_overlap, 4),
        "expected_tokens": sorted(expected_tokens)[:30],
        "observed_tokens": sorted(observed_tokens)[:30],
    }


def _validate_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("Недопустимая публичная ссылка")
    hostname = parts.hostname.casefold()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise ValueError("Локальные адреса запрещены")
    addresses = socket.getaddrinfo(hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Непубличный сетевой адрес запрещён")


def fetch_public_identity(url: str, timeout_seconds: int = 12) -> dict[str, Any]:
    _validate_public_url(url)
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=max(3, min(timeout_seconds, 30)),
        allow_redirects=True,
    )
    response.raise_for_status()
    _validate_public_url(response.url)
    content_type = str(response.headers.get("content-type") or "").casefold()
    if "html" not in content_type:
        raise ValueError("Источник не вернул публичную HTML-страницу")
    html = response.text[:1_000_000]
    return {
        "url": response.url,
        "title": _first_match(html, TITLE_PATTERNS),
        "description": _first_match(html, DESCRIPTION_PATTERNS),
        "http_status": response.status_code,
    }


def _apply_exclusion(cursor: Any, profile_id: str, note: str) -> None:
    cursor.execute(
        """
        SELECT COUNT(*)::INT AS healthy_channels
        FROM creator_channels
        WHERE creator_profile_id = %s
          AND verification_status NOT IN ('mismatch', 'inaccessible', 'excluded')
        """,
        (profile_id,),
    )
    row = cursor.fetchone()
    healthy_channels = int((row["healthy_channels"] if hasattr(row, "keys") else row[0]) or 0)
    if healthy_channels:
        return
    cursor.execute(
        """
        UPDATE creator_search_results SET
            result_group = 'excluded', shortlist_status = 'rejected',
            gates_json = gates_json || %s, reasons_json = reasons_json || %s,
            updated_at = NOW()
        WHERE creator_profile_id = %s
        """,
        (Json({"source_identity_current": False}), Json([note]), profile_id),
    )
    cursor.execute(
        """
        UPDATE creator_campaign_candidates candidate SET status = 'removed', updated_at = NOW()
        FROM creator_campaigns campaign
        WHERE candidate.campaign_id = campaign.id
          AND candidate.creator_profile_id = %s
          AND candidate.status IN ('shortlisted', 'invitation_ready')
          AND campaign.status IN ('draft', 'needs_review')
        """,
        (profile_id,),
    )


def revalidate_creator_channels(cursor: Any, *, limit: int = 100, fetcher: Any = None) -> dict[str, Any]:
    identity_fetcher = fetcher or fetch_public_identity
    cursor.execute(
        """
        SELECT channel.*, profile.display_name, profile.description
        FROM creator_channels channel
        JOIN creator_profiles profile ON profile.id = channel.creator_profile_id
        WHERE channel.verification_status NOT IN ('excluded')
          AND (channel.next_check_at IS NULL OR channel.next_check_at <= NOW())
        ORDER BY channel.next_check_at NULLS FIRST, channel.updated_at
        FOR UPDATE SKIP LOCKED
        LIMIT %s
        """,
        (max(1, min(limit, 1000)),),
    )
    channels = [dict(row) for row in cursor.fetchall()]
    summary = {"selected": len(channels), "verified": 0, "stale": 0, "mismatch": 0, "inaccessible": 0, "excluded_profiles": 0}
    now = datetime.now(timezone.utc)
    for channel in channels:
        metadata = dict(_json(channel.get("metadata_json"), {}))
        history = dict(_json(metadata.get("identity_revalidation"), {}))
        expected = dict(_json(metadata.get("observed_identity"), {}))
        expected_title = expected.get("title") or channel.get("display_name")
        expected_description = expected.get("description") or channel.get("description")
        try:
            observed = identity_fetcher(str(channel.get("canonical_url") or ""))
            comparison = compare_creator_identity(
                expected_title,
                expected_description,
                observed.get("title"),
                observed.get("description"),
            )
            consecutive_mismatches = int(history.get("consecutive_mismatches") or 0)
            if comparison["mismatch"]:
                consecutive_mismatches += 1
                status = "mismatch" if consecutive_mismatches >= 2 else "stale"
                next_check_at = now + (timedelta(days=30) if status == "mismatch" else timedelta(days=1))
                note = "Публичный профиль дважды показал другое название и тематику" if status == "mismatch" else "Обнаружено возможное изменение профиля; назначена повторная проверка"
            else:
                consecutive_mismatches = 0
                status = "verified"
                next_check_at = now + timedelta(days=30)
                note = "Публичная идентичность подтверждена"
            history = {
                "checked_at": now.isoformat(),
                "consecutive_mismatches": consecutive_mismatches,
                "consecutive_failures": 0,
                "observed": observed,
                "comparison": comparison,
            }
        except Exception as exc:
            consecutive_failures = int(history.get("consecutive_failures") or 0) + 1
            status = "inaccessible" if consecutive_failures >= 3 else "stale"
            next_check_at = now + (timedelta(days=7) if status == "inaccessible" else timedelta(days=1))
            note = "Источник трижды недоступен" if status == "inaccessible" else "Источник временно недоступен; назначена повторная проверка"
            history = {
                "checked_at": now.isoformat(),
                "consecutive_mismatches": int(history.get("consecutive_mismatches") or 0),
                "consecutive_failures": consecutive_failures,
                "error": str(exc)[:500],
            }
        metadata["identity_revalidation"] = history
        cursor.execute(
            """
            UPDATE creator_channels SET verification_status = %s, verified_at = %s,
                next_check_at = %s, verification_note = %s, metadata_json = %s,
                last_observed_at = CASE WHEN %s = 'verified' THEN %s ELSE last_observed_at END,
                updated_at = NOW()
            WHERE id = %s
            """,
            (status, now if status == "verified" else channel.get("verified_at"), next_check_at, note, Json(metadata), status, now, channel["id"]),
        )
        summary[status] += 1
        if status in {"mismatch", "inaccessible"}:
            before = summary["excluded_profiles"]
            _apply_exclusion(cursor, str(channel["creator_profile_id"]), note)
            cursor.execute(
                "SELECT COUNT(*)::INT AS count FROM creator_search_results WHERE creator_profile_id = %s AND result_group = 'excluded'",
                (channel["creator_profile_id"],),
            )
            row = cursor.fetchone()
            if int((row["count"] if hasattr(row, "keys") else row[0]) or 0) > 0:
                summary["excluded_profiles"] = before + 1
    return summary


def process_creator_profile_revalidation_batch() -> dict[str, Any] | None:
    if str(os.getenv("INFLUENCER_PROFILE_REVALIDATION_ENABLED") or "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    from database_manager import DatabaseManager

    database = DatabaseManager()
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    try:
        result = revalidate_creator_channels(
            cursor,
            limit=max(1, min(int(os.getenv("INFLUENCER_PROFILE_REVALIDATION_BATCH_SIZE") or "50"), 1000)),
        )
        database.conn.commit()
        return result
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()
