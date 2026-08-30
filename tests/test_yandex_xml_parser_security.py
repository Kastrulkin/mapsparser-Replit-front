import pytest

from services.yandex_xml_parser import parse_yandex_network_xml, validate_xml


ENTITY_EXPANSION_XML = """<?xml version="1.0"?>
<!DOCTYPE companies [
  <!ENTITY a "1234567890">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
]>
<companies><company><name lang="ru">&c;</name></company></companies>
"""


def test_yandex_xml_rejects_dtd_and_entity_expansion():
    with pytest.raises(ValueError, match="небезопас"):
        parse_yandex_network_xml(ENTITY_EXPANSION_XML)

    is_valid, message = validate_xml(ENTITY_EXPANSION_XML)
    assert is_valid is False
    assert "небезопас" in message.lower()


def test_yandex_xml_rejects_oversized_payload_before_parsing():
    oversized_xml = "<companies>" + (" " * (11 * 1024 * 1024)) + "</companies>"

    with pytest.raises(ValueError, match="слишком большой"):
        parse_yandex_network_xml(oversized_xml)

    is_valid, message = validate_xml(oversized_xml)
    assert is_valid is False
    assert "слишком большой" in message.lower()
