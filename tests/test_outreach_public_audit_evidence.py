from services.outreach_campaign_service import build_evidence_ledger


def test_deepseek_public_audit_becomes_grounded_outreach_evidence() -> None:
    ledger = build_evidence_ledger({
        "workstream_type": "localos_sales",
        "lead_name": "Салон",
        "source_url": "https://yandex.ru/maps/org/123",
        "research": {},
        "public_audit": {
            "updated_at": "2026-08-03T10:00:00+00:00",
            "page_json": {
                "audit": {
                    "ai_enrichment": {"source": "deepseek"},
                    "current_state": {
                        "description_present": False,
                        "services_count": 20,
                        "services_with_price_count": 4,
                    },
                },
            },
        },
    })

    assert ledger[0]["id"] == "deepseek-public-audit"
    assert ledger[0]["analysis_source"] == "deepseek"
    assert ledger[0]["fact"] == 'В публичной карточке "Салон" не заполнено описание бизнеса.'
    assert ledger[0]["source_url"] == "https://yandex.ru/maps/org/123"


def test_deterministic_or_missing_ai_audit_is_not_mislabeled_as_deepseek() -> None:
    ledger = build_evidence_ledger({
        "workstream_type": "localos_sales",
        "lead_name": "Салон",
        "source_url": "https://yandex.ru/maps/org/123",
        "research": {},
        "public_audit": {
            "page_json": {
                "audit": {
                    "ai_enrichment": {"source": "deterministic"},
                    "current_state": {"description_present": False},
                },
            },
        },
    })

    assert all(item.get("id") != "deepseek-public-audit" for item in ledger)
