import pytest

from services.lead_registry_projection import (
    lead_matches_registry_filters,
    normalize_lead_for_registry,
)


@pytest.mark.parametrize(
    ("status", "pipeline_status"),
    [
        ("new", "unprocessed"),
        ("sent", "contacted"),
        ("responded", "replied"),
        ("qualified", "converted"),
        ("shortlist_approved", "in_progress"),
        ("rejected", "not_relevant"),
    ],
)
def test_registry_projection_preserves_legacy_pipeline_mapping(status, pipeline_status):
    normalized = normalize_lead_for_registry({"id": "lead", "name": "Clinic", "status": status})

    assert normalized is not None
    assert normalized["pipeline_status"] == pipeline_status


def test_registry_projection_normalizes_placeholders_and_languages():
    normalized = normalize_lead_for_registry(
        {
            "id": "lead",
            "name": "name",
            "company_name": "Real Clinic",
            "email": "email",
            "enabled_languages": '["ru", "en"]',
        }
    )

    assert normalized is not None
    assert normalized["name"] == "Real Clinic"
    assert normalized["email"] is None
    assert normalized["enabled_languages"] == ["ru", "en"]


def test_registry_projection_applies_numeric_contact_and_messenger_filters():
    lead = {
        "name": "Clinic",
        "category": "Dental clinic",
        "city": "Moscow",
        "rating": 4.7,
        "reviews_count": 120,
        "email": "owner@example.com",
        "messenger_links_json": '[{"type":"vk","url":"https://vk.com/clinic"}]',
    }

    assert lead_matches_registry_filters(
        lead,
        {
            "category": "dental",
            "city": "moscow",
            "min_rating": 4.6,
            "max_rating": 4.8,
            "min_reviews": 100,
            "max_reviews": 150,
            "has_email": True,
            "has_messengers": True,
        },
    )
    assert not lead_matches_registry_filters(lead, {"min_rating": 4.8})
