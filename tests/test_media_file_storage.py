from services import media_file_storage


def test_local_media_storage_uses_business_media_path(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setenv("MEDIA_UPLOAD_DIR", str(tmp_path))

    stored = media_file_storage.store_media_file(
        business_id="biz-1",
        asset_id="asset-1",
        variant="original",
        extension="jpg",
        content=b"image-bytes",
        original_name="photo.jpg",
        mime_type="image/jpeg",
    )

    assert stored["backend"] == "local"
    assert stored["storage_key"] == "businesses/biz-1/media/original/asset-1.jpg"
    assert stored["mime_type"] == "image/jpeg"
    assert stored["size_bytes"] == len(b"image-bytes")
    assert media_file_storage.load_media_file(stored["storage_path"]) == b"image-bytes"


def test_local_media_storage_blocks_paths_outside_upload_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setenv("MEDIA_UPLOAD_DIR", str(tmp_path / "media"))
    outside_file = tmp_path / "outside.jpg"
    outside_file.write_bytes(b"nope")

    assert media_file_storage.load_media_file(str(outside_file)) is None
