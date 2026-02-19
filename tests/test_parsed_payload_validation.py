import pytest

from parsed_payload_validation import (
    validate_parsed_payload,
    _has_content,
    _resolve_categories,
    FIELDS_HARD,
    FIELDS_CRITICAL,
)


def test_has_content_basic_cases():
    assert _has_content(0) is True
    assert _has_content(1) is True
    assert _has_content(None) is False
    assert _has_content("") is False
    assert _has_content("  ") is False
    assert _has_content("x") is True
    assert _has_content([]) is False
    assert _has_content([1]) is True
    assert _has_content({}) is False
    assert _has_content({"k": "v"}) is True


@pytest.mark.parametrize(
    "data,overview,expected_missing",
    [
        ({"categories": []}, {}, True),
        ({"categories": [{"id": 1}]}, {}, False),
        ({"categories": {}}, {"rubric": {"id": "123"}}, False),
        ({}, {"rubric": "Салон"}, False),
        ({}, {"rubric": ""}, True),
    ],
)
def test_resolve_categories_scenarios(data, overview, expected_missing):
    value = _resolve_categories(data, overview)
    is_missing = value is None
    assert is_missing == expected_missing


def test_reviews_count_zero_is_found_not_missing():
    parsed = {
        "title": "Test",
        "reviews_count": 0,
    }
    res = validate_parsed_payload(parsed)
    assert "reviews_count" in res["found_fields"]
    assert "reviews_count" not in res["missing_fields"]
    assert "missing_in_source:reviews_count" not in res["warnings"]


def test_rating_zero_is_found():
    parsed = {
        "title": "Test",
        "rating": 0,
    }
    res = validate_parsed_payload(parsed)
    assert "rating" in res["found_fields"]
    assert "rating" not in res["missing_fields"]


def test_rating_none_is_missing_with_warning():
    parsed = {
        "title": "Test",
        "rating": None,
    }
    res = validate_parsed_payload(parsed)
    assert "rating" in res["missing_fields"]
    assert "missing_in_source:rating" in res["warnings"]


def test_title_or_name_from_overview_title():
    parsed = {
        "overview": {"title": "Название только в overview"},
    }
    res = validate_parsed_payload(parsed)

    # HARD группа должна считаться найденной
    assert "title_or_name" in res["found_fields"]
    assert "title_or_name" not in res["hard_missing"]


def test_categories_and_rubric_empty_is_missing():
    parsed = {
        "title": "Test",
        "categories": [],
        "rubric": "",
    }
    res = validate_parsed_payload(parsed)

    assert "categories" in res["missing_fields"]
    assert "missing_in_source:categories" in res["warnings"]


@pytest.mark.parametrize(
    "rubric_value",
    [
        {"id": "123", "name": "Салон"},
        "Салон",
    ],
)
def test_categories_found_when_rubric_is_meaningful(rubric_value):
    parsed = {
        "title": "Test",
        "categories": [],  # пустой список, но rubric «спасает» поле
        "rubric": rubric_value,
    }
    res = validate_parsed_payload(parsed)

    assert "categories" not in res["missing_fields"]
    assert "missing_in_source:categories" not in res["warnings"]


def test_quality_score_full_coverage_is_one():
    # Все обязательные поля (HARD + CRITICAL) найдены
    parsed = {
        "title": "Test",
        "address": "Адрес",
        "rating": 5,
        "reviews_count": 10,
        "categories": ["cat"],
    }
    res = validate_parsed_payload(parsed)

    required = set(FIELDS_HARD + FIELDS_CRITICAL)
    for field in required:
        assert field in res["found_fields"]

    assert res["quality_score"] == 1.0


def test_quality_score_partial_coverage_three_of_five():
    # Найдены только 3 из 5 обязательных полей
    parsed = {
        "title": "Test",          # title_or_name OK
        "address": "Адрес",       # address OK
        "reviews_count": 0,       # reviews_count OK
        # rating отсутствует
        # categories/rubric отсутствуют
    }
    res = validate_parsed_payload(parsed)

    # Проверяем ожидаемую долю: 3 из 5 → 0.6
    assert res["quality_score"] == pytest.approx(0.6, rel=1e-9)

