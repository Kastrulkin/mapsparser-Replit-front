import os
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib import request

from bs4 import BeautifulSoup
from psycopg2.extras import Json, RealDictCursor

from services.knowledge_graph_service import upsert_document


def _monitor_enabled() -> bool:
    return str(os.getenv("KNOWLEDGE_TELEGRAM_MONITOR_ENABLED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _public_preview_url(canonical_url: str) -> str | None:
    value = str(canonical_url or "").strip().rstrip("/")
    if not value.startswith("https://t.me/") or "+" in value or "joinchat" in value:
        return None
    username = value.rsplit("/", 1)[-1]
    if not username or username == "s":
        return None
    return f"https://t.me/s/{username}"


def parse_public_channel_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    messages: list[dict[str, Any]] = []
    for node in soup.select("div.tgme_widget_message[data-post]"):
        data_post = str(node.get("data-post") or "").strip()
        if "/" not in data_post:
            continue
        external_id = data_post.rsplit("/", 1)[-1]
        text_node = node.select_one("div.tgme_widget_message_text")
        if not text_node:
            continue
        content_text = text_node.get_text("\n", strip=True)
        if not content_text:
            continue
        time_node = node.select_one("time[datetime]")
        published_at = None
        if time_node:
            try:
                published_at = datetime.fromisoformat(str(time_node.get("datetime") or "").replace("Z", "+00:00"))
            except ValueError:
                published_at = None
        link_node = node.select_one("a.tgme_widget_message_date")
        messages.append(
            {
                "external_id": external_id,
                "content_text": content_text,
                "published_at": published_at,
                "permalink": str(link_node.get("href") or "").strip() if link_node else None,
            }
        )
    return messages


def collect_public_channel(canonical_url: str, *, timeout: int = 20) -> list[dict[str, Any]]:
    return inspect_public_channel(canonical_url, timeout=timeout)["messages"]


def inspect_public_channel(canonical_url: str, *, timeout: int = 20) -> dict[str, Any]:
    """Preflight a Telegram username without treating a personal profile as a channel."""
    preview_url = _public_preview_url(canonical_url)
    if not preview_url:
        raise ValueError("Only public Telegram channels can be collected automatically")
    http_request = request.Request(
        preview_url,
        headers={"User-Agent": "LocalOS-Knowledge-Collector/1.0 (+https://localos.pro)"},
    )
    proxy_url = str(os.getenv("TELEGRAM_HTTP_PROXY") or os.getenv("OUTBOUND_HTTP_PROXY") or "").strip()
    opener = request.build_opener(request.ProxyHandler({"http": proxy_url, "https": proxy_url})) if proxy_url else request.build_opener()
    with opener.open(http_request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
        geturl = getattr(response, "geturl", None)
        final_url = str(geturl() if callable(geturl) else preview_url)
    soup = BeautifulSoup(html, "html.parser")
    messages = parse_public_channel_html(html)
    channel_node = soup.select_one("div.tgme_channel_info")
    title_node = soup.select_one("div.tgme_channel_info_header_title")
    stayed_on_preview = "/s/" in final_url or final_url.rstrip("/") == preview_url.rstrip("/")
    is_public_channel = bool(channel_node or messages) and stayed_on_preview
    return {
        "is_public_channel": is_public_channel,
        "title": title_node.get_text(" ", strip=True) if title_node else "",
        "messages": messages,
        "final_url": final_url,
        "reason": "public_preview" if is_public_channel else "not_public_channel_or_unavailable",
    }


def run_public_telegram_monitor(conn, *, limit_sources: int = 10) -> dict[str, Any]:
    if not _monitor_enabled():
        return {"status": "disabled", "sources_checked": 0, "documents_seen": 0}
    interval_seconds = max(86400, int(os.getenv("KNOWLEDGE_TELEGRAM_MONITOR_INTERVAL_SEC", "86400")))
    run_id = str(uuid.uuid4())
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT source.* FROM knowledge_sources source
        JOIN telegram_account_permissions permission
          ON permission.account_id = source.account_id
         AND permission.radar_enabled = TRUE
        WHERE source.source_type = 'telegram'
          AND (
                source.status = 'active'
                OR (
                    source.status = 'candidate'
                    AND COALESCE((source.metadata_json->>'auto_discovered')::boolean, FALSE) = TRUE
                    AND source.sync_status = 'queued'
                )
              )
          AND source.sync_mode = 'public_preview'
          AND source.visibility = 'public'
          AND source.canonical_url LIKE %s
          AND (source.last_collected_at IS NULL OR source.last_collected_at < NOW() - (%s * INTERVAL '1 second'))
        ORDER BY source.last_collected_at ASC NULLS FIRST, source.updated_at ASC
        LIMIT %s
        """,
        ("https://t.me/%", interval_seconds, max(1, min(limit_sources, 50))),
    )
    sources = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        INSERT INTO knowledge_analysis_runs (
            id, run_type, analysis_version, status, document_count, metadata_json, started_at
        ) VALUES (%s, 'telegram_monitor', 'public-telegram-v1', 'running', 0, %s, NOW())
        """,
        (run_id, Json({"sources_selected": len(sources)})),
    )
    cursor.close()

    documents_seen = 0
    documents_imported = 0
    errors: list[dict[str, str]] = []
    for source in sources:
        try:
            inspection = inspect_public_channel(str(source.get("canonical_url") or ""))
            auto_discovered = bool((source.get("metadata_json") or {}).get("auto_discovered"))
            workstream_ids: list[str] = []
            if auto_discovered:
                from services.discovered_telegram_source_service import mark_discovered_source_classification

                workstream_ids = mark_discovered_source_classification(
                    conn,
                    source_id=str(source["id"]),
                    is_public_channel=bool(inspection.get("is_public_channel")),
                    title=str(inspection.get("title") or ""),
                    reason=str(inspection.get("reason") or ""),
                )
                if not inspection.get("is_public_channel"):
                    continue
            messages = list(inspection.get("messages") or [])
            max_external_id = ""
            for message in messages:
                _, inserted = upsert_document(
                    conn,
                    source_id=str(source["id"]),
                    business_id=str(source.get("business_id") or "").strip() or None,
                    external_id=message["external_id"],
                    document_type="telegram_message",
                    title=str(source.get("title") or "Telegram"),
                    content_text=message["content_text"],
                    permalink=message.get("permalink"),
                    published_at=message.get("published_at"),
                    sensitivity_class="public",
                    allowed_uses=list(source.get("allowed_uses") or []),
                    metadata={"collector": "public_telegram_preview"},
                )
                documents_seen += 1
                documents_imported += 1 if inserted else 0
                if message["external_id"].isdigit() and (
                    not max_external_id or int(message["external_id"]) > int(max_external_id)
                ):
                    max_external_id = message["external_id"]
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE knowledge_sources
                SET last_collected_at = NOW(),
                    cursor_json = cursor_json || %s,
                    sync_status = 'ready',
                    next_sync_at = NOW() + (%s * INTERVAL '1 second'),
                    last_sync_error = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    Json({"last_message_id": max_external_id, "checked_at": datetime.now(timezone.utc).isoformat()}),
                    interval_seconds,
                    source["id"],
                ),
            )
            cursor.close()
            if workstream_ids and messages:
                from services.contact_intelligence_service import enqueue_enrichment_job

                cursor = conn.cursor()
                for workstream_id in workstream_ids:
                    enqueue_enrichment_job(cursor, workstream_id, force=True)
                cursor.close()
        except Exception as error:
            errors.append({"source_id": str(source.get("id") or ""), "message": str(error)[:300]})
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE knowledge_sources
                SET sync_status = 'failed', last_sync_error = %s,
                    next_sync_at = NOW() + (%s * INTERVAL '1 second'), updated_at = NOW()
                WHERE id = %s
                """,
                (str(error)[:300], interval_seconds, source.get("id")),
            )
            cursor.close()

    status = "completed" if not errors else "partial"
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE knowledge_analysis_runs
        SET status = %s, document_count = %s, processed_count = %s,
            failed_count = %s, error_json = %s, completed_at = NOW()
        WHERE id = %s
        """,
        (status, documents_seen, documents_seen, len(errors), Json({"items": errors}), run_id),
    )
    cursor.close()
    return {
        "run_id": run_id,
        "status": status,
        "sources_checked": len(sources),
        "documents_seen": documents_seen,
        "documents_imported": documents_imported,
        "errors": errors,
    }
