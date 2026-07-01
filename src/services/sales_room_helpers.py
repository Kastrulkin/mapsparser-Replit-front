"""Small shared helpers for sales-room flows."""
from __future__ import annotations

import os
import re
import uuid
from typing import Any


def make_sales_room_url(slug: str) -> str:
    frontend_base = str(os.environ.get("FRONTEND_BASE_URL") or "").strip().rstrip("/")
    if not frontend_base:
        frontend_base = "https://localos.pro"
    return f"{frontend_base}/room/{slug}"


def append_sales_room_link_to_outreach_text(text: str, room_url: str) -> str:
    cleaned = str(text or "").strip()
    url = str(room_url or "").strip()
    if not cleaned or not url or "/room/" in cleaned:
        return cleaned
    return (
        f"{cleaned}\n\n"
        "Для удобства подготовил общую цифровую комнату, где можно обсуждать идеи, "
        "приглашать коллег и обмениваться материалами:\n\n"
        f"{url}"
    )


def normalize_sales_room_data_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "audited":
        return "audited"
    return "template"


def clean_sales_room_filename(filename: str) -> str:
    raw = str(filename or "file").strip().replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[^A-Za-z0-9А-Яа-яЁё._ -]+", "-", raw).strip(" .-")
    return cleaned or "file"


def sales_room_file_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].strip().lower()


def is_uuid_string(value: str) -> bool:
    try:
        uuid.UUID(str(value or "").strip())
        return True
    except ValueError:
        return False
