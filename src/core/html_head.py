"""Safe helpers for rendering dynamic values into the SPA document head."""

from __future__ import annotations

import re


def replace_or_insert_tag(html_text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(
        pattern,
        lambda _match: replacement,
        html_text,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if count:
        return updated
    return html_text.replace("</head>", f"  {replacement}\n</head>", 1)
