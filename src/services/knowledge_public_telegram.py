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
    preview_url = _public_preview_url(canonical_url)
    if not preview_url:
        raise ValueError("Only public Telegram channels can be collected automatically")
    http_request = request.Request(
        preview_url,
        headers={"User-Agent": "LocalOS-Knowledge-Collector/1.0 (+https://localos.pro)"},
    )
    with request.urlopen(http_request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
    return parse_public_channel_html(html)


def run_public_telegram_monitor(conn, *, limit_sources: int = 10) -> dict[str, Any]:
    if not _monitor_enabled():
        return {"status": "disabled", "sources_checked": 0, "documents_seen": 0}
    interval_seconds = max(3600, int(os.getenv("KNOWLEDGE_TELEGRAM_MONITOR_INTERVAL_SEC", "604800")))
    run_id = str(uuid.uuid4())
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT * FROM knowledge_sources
        WHERE source_type = 'telegram'
          AND status = 'active'
          AND visibility = 'public'
          AND canonical_url LIKE 'https://t.me/%'
          AND (last_collected_at IS NULL OR last_collected_at < NOW() - (%s * INTERVAL '1 second'))
        ORDER BY last_collected_at ASC NULLS FIRST, updated_at ASC
        LIMIT %s
        """,
        (interval_seconds, max(1, min(limit_sources, 50))),
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
            messages = collect_public_channel(str(source.get("canonical_url") or ""))
            max_external_id = ""
            for message in messages:
                _, inserted = upsert_document(
                    conn,
                    source_id=str(source["id"]),
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
                    updated_at = NOW()
                WHERE id = %s
                """,
                (Json({"last_message_id": max_external_id, "checked_at": datetime.now(timezone.utc).isoformat()}), source["id"]),
            )
            cursor.close()
        except Exception as error:
            errors.append({"source_id": str(source.get("id") or ""), "message": str(error)[:300]})

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
