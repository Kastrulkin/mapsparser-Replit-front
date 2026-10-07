from services import media_file_storage


def test_media_delivery_url_is_signed_and_stable(monkeypatch):
    monkeypatch.setenv("EXTERNAL_AUTH_SECRET_KEY", "test-secret-with-enough-entropy")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://localos.example")

    url = media_file_storage.build_media_delivery_url(
        asset_id="asset-1",
        content_hash="abc123",
    )

    assert url.startswith("https://localos.example/api/media-intelligence/public/photos/asset-1/file?")
    token = url.rsplit("token=", 1)[-1]
    assert media_file_storage.verify_media_delivery_token(
        asset_id="asset-1",
        content_hash="abc123",
        variant="original",
        token=token,
    ) is True


def test_media_delivery_token_rejects_changed_asset(monkeypatch):
    monkeypatch.setenv("EXTERNAL_AUTH_SECRET_KEY", "test-secret-with-enough-entropy")
    url = media_file_storage.build_media_delivery_url(
        asset_id="asset-1",
        content_hash="abc123",
    )
    token = url.rsplit("token=", 1)[-1]

    assert media_file_storage.verify_media_delivery_token(
        asset_id="asset-1",
        content_hash="changed",
        variant="original",
        token=token,
    ) is False
