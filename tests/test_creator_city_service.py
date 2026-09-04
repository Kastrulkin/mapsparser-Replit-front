from services.creator_city_service import (
    available_creator_cities,
    canonicalize_city,
    canonicalize_geography,
    city_matches,
)


class CityCursor:
    def __init__(self):
        self.executed = False

    def execute(self, _query):
        self.executed = True

    def fetchall(self):
        return [
            {"city": "Санкт-Петербург", "profiles": 80},
            {"city": "СПб", "profiles": 15},
            {"city": "Пеьтербург", "profiles": 3},
            {"city": "Москва", "profiles": 20},
        ]


def test_city_aliases_and_common_typos_have_one_canonical_name():
    for value in ("Петербург", "Санкт Петербург", "СПб", "Пеьтербург", "saint petersburg"):
        assert canonicalize_city(value) == "Санкт-Петербург"
    assert canonicalize_city("Мосвка") == "Москва"
    assert canonicalize_city("Твреь", ["Тверь"]) == "Тверь"


def test_city_match_accepts_alias_inside_geography_description():
    assert city_matches("Санкт-Петербург, Выборгский район", "Питер") is True
    assert city_matches("Москва", "СПб") is False


def test_available_cities_group_aliases_and_typos():
    cursor = CityCursor()

    result = available_creator_cities(cursor)

    assert cursor.executed is True
    assert result[0]["name"] == "Санкт-Петербург"
    assert result[0]["count"] == 98
    assert result[1]["name"] == "Москва"


def test_campaign_geography_is_canonical_and_deduplicated():
    result = canonicalize_geography({"city": "спб", "cities": ["Питер", "Санкт Петербург"]})

    assert result == {"city": "Санкт-Петербург", "cities": ["Санкт-Петербург"]}
