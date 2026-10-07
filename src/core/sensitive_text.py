"""Redact credentials before diagnostic text is persisted or logged."""

from __future__ import annotations

import re
from typing import Any


_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:token|api_token|access_token|key|api_key)=)([^&#\s]+)"
)
_HEADER_SECRET = re.compile(
    r"(?i)((?:authorization|proxy-authorization)\s*[:=]\s*(?:bearer|basic)?\s*)([^,;\s]+)"
)
_JSON_SECRET = re.compile(
    r'''(?i)(["'](?:token|api_token|access_token|api_key|password)["']\s*:\s*["'])([^"']+)(["'])'''
)


def redact_sensitive_text(value: Any, *, limit: int = 4000) -> str:
    text = str(value or "")
    text = _QUERY_SECRET.sub(r"\1[REDACTED]", text)
    text = _HEADER_SECRET.sub(r"\1[REDACTED]", text)
    text = _JSON_SECRET.sub(r"\1[REDACTED]\3", text)
    return text[: max(0, int(limit))]
