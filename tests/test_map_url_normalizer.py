from core.map_url_normalizer import is_google_map_url, normalize_map_url
import pytest


@pytest.mark.parametrize("value", [
    "https://maps.google.com/?cid=3265699317834998350%29",
    " https://maps.google.com/?cid=3265699317834998350) ",
    '<https://maps.google.com/?cid=3265699317834998350>',
    '[Riderra](https://maps.google.com/?cid=3265699317834998350)',
    'maps.google.com/?cid=3265699317834998350',
    '//maps.google.com/?cid=3265699317834998350',
])
def test_pasted_google_cid(value):
    expected = 'https://maps.google.com/?cid=3265699317834998350'
    assert normalize_map_url(value) == expected
    assert normalize_map_url(normalize_map_url(value)) == expected
    assert is_google_map_url(value)


def test_preserves_parentheses_in_google_query():
    value = 'https://www.google.com/maps?q=Riderra+%28Tallinn%29'
    assert normalize_map_url(value) == value


def test_does_not_guess_broken_cid():
    value = 'https://maps.google.com/?cid=123abc%29'
    assert normalize_map_url(value) == value


def test_pasted_yandex_link():
    assert normalize_map_url('yandex.ru/maps/org/test/123/reviews)') == 'https://yandex.ru/maps/org/test/123'


def test_normalize_yandex_reviews_url_to_business_card_url():
    assert (
        normalize_map_url("https://yandex.com/maps/org/ryad/205932220769/reviews?z=16&utm_source=telegram")
        == "https://yandex.com/maps/org/ryad/205932220769"
    )


def test_normalize_yandex_photos_url_to_business_card_url():
    assert (
        normalize_map_url("https://yandex.ru/maps/org/dom_krasoty/123/photos")
        == "https://yandex.ru/maps/org/dom_krasoty/123"
    )


def test_normalize_2gis_reviews_tail_to_business_card_url():
    assert (
        normalize_map_url("https://2gis.ru/spb/firm/70000001000000000/reviews")
        == "https://2gis.ru/spb/firm/70000001000000000"
    )


def test_google_search_business_panel_is_google_map_url():
    url = "https://www.google.com/search?q=Intellectum+Space+and+School&stick=H4sIAAAAAAAA"

    assert is_google_map_url(url) is True
    assert (
        normalize_map_url(url)
        == "https://www.google.com/search?q=Intellectum+Space+and+School&stick=H4sIAAAAAAAA"
    )


def test_maps_google_cid_url_is_google_map_url():
    url = "https://maps.google.com/?cid=demo-roga-i-kopyta-network"

    assert is_google_map_url(url) is True
    assert normalize_map_url(url) == url


def test_google_search_without_business_entity_is_not_map_url():
    assert is_google_map_url("https://www.google.com/search?q=how+to+write+content") is False
