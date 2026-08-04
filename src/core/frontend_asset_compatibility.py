from __future__ import annotations

import os
import re


_LAZY_CHUNK_PATTERN = re.compile(
    r"^(?P<stem>[A-Z][A-Za-z0-9]*)-[A-Za-z0-9_-]{8,}\.js$"
)
_ENTRY_ASSET_PATTERN = re.compile(
    r'''(?:src|href)=["']/assets/(?P<filename>index-[A-Za-z0-9_-]{8,}\.js)["']'''
)


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as source_file:
            return source_file.read()
    except (OSError, UnicodeError):
        return ""


def resolve_current_lazy_chunk(frontend_dist_dir: str, requested_filename: str) -> str | None:
    """Resolve a missing old Vite route chunk to the matching chunk in the current build."""
    clean_filename = str(requested_filename or "").strip()
    if not clean_filename or os.path.basename(clean_filename) != clean_filename:
        return None

    requested_match = _LAZY_CHUNK_PATTERN.fullmatch(clean_filename)
    if not requested_match:
        return None

    index_text = _read_text(os.path.join(frontend_dist_dir, "index.html"))
    entry_match = _ENTRY_ASSET_PATTERN.search(index_text)
    if not entry_match:
        return None

    assets_dir = os.path.join(frontend_dist_dir, "assets")
    entry_text = _read_text(os.path.join(assets_dir, entry_match.group("filename")))
    if not entry_text:
        return None

    stem = requested_match.group("stem")
    current_pattern = re.compile(
        rf"(?<![A-Za-z0-9_-])({re.escape(stem)}-[A-Za-z0-9_-]{{8,}}\.js)"
    )
    for candidate in current_pattern.findall(entry_text):
        if os.path.isfile(os.path.join(assets_dir, candidate)):
            return candidate
    return None
