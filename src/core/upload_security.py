"""Content-level checks for user-uploaded files."""

import io
import zipfile


GENERIC_MIME_TYPES = {"", "application/octet-stream"}
MIME_TYPES_BY_EXTENSION = {
    "jpg": {"image/jpeg", "image/jpg"},
    "jpeg": {"image/jpeg", "image/jpg"},
    "png": {"image/png"},
    "webp": {"image/webp"},
    "pdf": {"application/pdf"},
    "doc": {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xls": {"application/vnd.ms-excel"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"},
    "txt": {"text/plain"},
}


def upload_content_matches_type(*, extension: str, mime_type: str, content: bytes) -> bool:
    normalized_extension = str(extension or "").strip().lower().lstrip(".")
    normalized_mime = str(mime_type or "").split(";", 1)[0].strip().lower()
    allowed_mimes = MIME_TYPES_BY_EXTENSION.get(normalized_extension)
    if not allowed_mimes or normalized_mime not in allowed_mimes | GENERIC_MIME_TYPES:
        return False
    if not content:
        return False
    if normalized_extension in {"jpg", "jpeg"}:
        return len(content) >= 4 and content.startswith(b"\xff\xd8\xff")
    if normalized_extension == "png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if normalized_extension == "webp":
        return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    if normalized_extension == "pdf":
        return content.startswith(b"%PDF-")
    if normalized_extension in {"doc", "xls"}:
        return content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if normalized_extension in {"docx", "xlsx"}:
        return _office_archive_matches_type(content, normalized_extension)
    if normalized_extension in {"csv", "txt"}:
        return b"\x00" not in content
    return False


def _office_archive_matches_type(content: bytes, extension: str) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
    except (OSError, ValueError, zipfile.BadZipFile):
        return False
    if len(names) > 2000 or "[Content_Types].xml" not in names:
        return False
    required_prefix = "word/" if extension == "docx" else "xl/"
    return any(name.startswith(required_prefix) for name in names)
