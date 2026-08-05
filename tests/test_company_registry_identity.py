from __future__ import annotations

from typing import Any

from services.company_registry_service import ensure_company_for_lead


class IdentityCursor:
    def __init__(self, *, weak_match_type: str):
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []
        self.query = ""
        self.params: tuple[Any, ...] | None = None
        self.weak_match_type = weak_match_type

    def execute(self, query, params=None):
        self.query = " ".join(str(query).split())
        self.params = params
        self.calls.append((self.query, params))

    def fetchone(self):
        if "SELECT company_id, company_location_id FROM prospectingleads" in self.query:
            return None
        if "FROM company_identity_keys" in self.query:
            key_type = str((self.params or ("",))[0])
            if key_type == self.weak_match_type:
                return {
                    "company_id": "existing-company",
                    "company_location_id": "existing-location",
                }
            return None
        return None

    def close(self):
        return None


class IdentityConnection:
    def __init__(self, *, weak_match_type: str):
        self.cursor_instance = IdentityCursor(weak_match_type=weak_match_type)

    def cursor(self, cursor_factory=None):
        return self.cursor_instance


def test_distinct_yandex_id_is_not_merged_by_shared_phone_and_address():
    connection = IdentityConnection(weak_match_type="phone_address")

    result = ensure_company_for_lead(
        connection,
        "new-lead",
        {
            "id": "new-lead",
            "name": "Дивный город",
            "address": "Санкт-Петербург, проспект Энгельса, 154",
            "city": "Санкт-Петербург",
            "phone": "+7 (812) 123-45-67",
            "source": "yandex_maps",
            "external_source_id": "1577567569",
            "source_url": "https://yandex.com/maps/org/divny_gorod/1577567569",
        },
    )

    assert result["company_id"] != "existing-company"


def test_distinct_yandex_id_is_not_merged_by_shared_developer_domain():
    connection = IdentityConnection(weak_match_type="domain_geo")

    result = ensure_company_for_lead(
        connection,
        "new-lead",
        {
            "id": "new-lead",
            "name": "Шекспир",
            "address": "Санкт-Петербург, улица Руднева",
            "city": "Санкт-Петербург",
            "website": "https://www.l1-stroy.ru/",
            "source": "yandex_maps",
            "external_source_id": "233925395012",
            "source_url": "https://yandex.com/maps/org/shekspir/233925395012",
        },
    )

    assert result["company_id"] != "existing-company"


def test_exact_provider_identity_still_resolves_existing_company():
    connection = IdentityConnection(weak_match_type="provider_id:apify_yandex")

    result = ensure_company_for_lead(
        connection,
        "existing-lead",
        {
            "id": "existing-lead",
            "name": "Дивный город",
            "source": "apify_yandex",
            "external_source_id": "1577567569",
            "source_url": "https://yandex.com/maps/org/divny_gorod/1577567569",
        },
    )

    assert result["company_id"] == "existing-company"


def test_weak_identity_still_resolves_when_map_identity_is_missing():
    connection = IdentityConnection(weak_match_type="phone_address")

    result = ensure_company_for_lead(
        connection,
        "legacy-lead",
        {
            "id": "legacy-lead",
            "name": "Компания без ID карты",
            "address": "Санкт-Петербург, Невский проспект, 1",
            "phone": "+7 (812) 123-45-67",
        },
    )

    assert result["company_id"] == "existing-company"
