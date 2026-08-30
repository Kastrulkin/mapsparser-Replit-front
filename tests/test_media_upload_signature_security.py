import io
import zipfile

import pytest

from core.upload_security import upload_content_matches_type
from services import media_intelligence


class _PhotoCursor:
    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return {
            "id": "asset-1",
            "business_id": "business-1",
            "source": "upload",
            "versions_json": {},
            "metadata_json": {},
        }


def test_photo_upload_rejects_fake_jpeg_before_storage(monkeypatch):
    storage_calls = []

    def record_storage(**kwargs):
        storage_calls.append(kwargs)
        return {
            "storage_path": "/tmp/asset-1.jpg",
            "storage_key": "businesses/business-1/media/original/asset-1.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": len(kwargs["content"]),
        }

    monkeypatch.setattr(media_intelligence, "store_media_file", record_storage)

    with pytest.raises(ValueError, match="содержим"):
        media_intelligence.create_uploaded_photo_asset(
            _PhotoCursor(),
            business_id="business-1",
            user_id="user-1",
            content=b"<html><script>alert('not an image')</script></html>",
            original_name="photo.jpg",
            mime_type="image/jpeg",
        )

    assert storage_calls == []


def test_photo_upload_accepts_matching_jpeg_signature(monkeypatch):
    storage_calls = []

    def record_storage(**kwargs):
        storage_calls.append(kwargs)
        return {
            "storage_path": "/tmp/asset-1.jpg",
            "storage_key": "businesses/business-1/media/original/asset-1.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": len(kwargs["content"]),
        }

    monkeypatch.setattr(media_intelligence, "store_media_file", record_storage)
    result = media_intelligence.create_uploaded_photo_asset(
        _PhotoCursor(),
        business_id="business-1",
        user_id="user-1",
        content=b"\xff\xd8\xff\xe0valid-jpeg-payload",
        original_name="photo.jpg",
        mime_type="image/jpeg",
    )

    assert result["id"] == "asset-1"
    assert len(storage_calls) == 1


def _office_archive(prefix):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(f"{prefix}/document.xml", "<document />")
    return output.getvalue()


@pytest.mark.parametrize(
    ("extension", "mime_type", "content"),
    [
        ("jpg", "image/jpeg", b"\xff\xd8\xff\xe0jpeg"),
        ("png", "image/png", b"\x89PNG\r\n\x1a\npng"),
        ("webp", "image/webp", b"RIFF\x04\x00\x00\x00WEBPdata"),
        ("pdf", "application/pdf", b"%PDF-1.7\nbody"),
        ("doc", "application/msword", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1doc"),
        ("xls", "application/vnd.ms-excel", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1xls"),
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", _office_archive("word")),
        ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _office_archive("xl")),
        ("csv", "text/csv", "name,value\nтест,1".encode("utf-8")),
        ("txt", "text/plain", "обычный текст".encode("utf-8")),
    ],
)
def test_upload_signature_accepts_supported_content(extension, mime_type, content):
    assert upload_content_matches_type(extension=extension, mime_type=mime_type, content=content) is True


def test_upload_signature_rejects_mime_mismatch():
    assert upload_content_matches_type(
        extension="jpg",
        mime_type="text/html",
        content=b"\xff\xd8\xff\xe0jpeg",
    ) is False
