import pytest

from services.creator_portal_service import _creator_channel_url


@pytest.mark.parametrize(
    ("platform", "value", "expected"),
    [
        ("telegram", "@anna_spb", "https://t.me/anna_spb"),
        ("instagram", "anna_places", "https://instagram.com/anna_places"),
        ("threads", "threads.net/@anna", "https://threads.net/@anna"),
        ("youtube", "https://www.youtube.com/@anna/?view=1", "https://youtube.com/@anna"),
    ],
)
def test_creator_channel_url_accepts_username_and_public_link(platform, value, expected):
    assert _creator_channel_url(platform, value) == expected


def test_creator_channel_url_rejects_unknown_platform():
    with pytest.raises(ValueError, match="поддерживаемую площадку"):
        _creator_channel_url("unknown", "anna")


def test_creator_channel_url_rejects_link_from_another_platform():
    with pytest.raises(ValueError, match="не соответствует"):
        _creator_channel_url("telegram", "instagram.com/anna")
