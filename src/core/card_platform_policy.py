"""Versioned, provider-specific rules for managed map-card growth."""
from __future__ import annotations

from typing import Any


POLICY_VERSION = "2026-09-11.1"
POLICY_VERIFIED_AT = "2026-09-11"
PROVIDERS = ("google", "yandex", "2gis")
FACT_STATES = {"observed", "missing", "unknown", "not_applicable", "blocked"}


PLATFORM_RULES: dict[str, tuple[dict[str, Any], ...]] = {
    "google": (
        {"rule_id": "google.access", "gate": 0, "fact": "access", "influence": "eligibility", "impact": 100, "url": "https://support.google.com/business/answer/7091"},
        {"rule_id": "google.verified", "gate": 1, "fact": "verified", "influence": "eligibility", "impact": 98, "url": "https://support.google.com/business/answer/7107242"},
        {"rule_id": "google.duplicate", "gate": 1, "fact": "duplicate", "influence": "eligibility", "impact": 97, "url": "https://support.google.com/business/answer/12756178"},
        {"rule_id": "google.category", "gate": 1, "fact": "category", "influence": "ranking", "impact": 96, "url": "https://support.google.com/business/answer/7249669"},
        {"rule_id": "google.contacts", "gate": 2, "fact": "contacts", "influence": "conversion", "impact": 92, "url": "https://support.google.com/business/answer/7091"},
        {"rule_id": "google.schedule", "gate": 2, "fact": "schedule", "influence": "conversion", "impact": 90, "url": "https://support.google.com/business/answer/15300403"},
        {"rule_id": "google.action_path", "gate": 2, "fact": "action_path", "influence": "conversion", "impact": 94, "url": "https://support.google.com/business/answer/6218037"},
        {"rule_id": "google.services", "gate": 3, "fact": "services", "influence": "relevance", "impact": 80, "url": "https://support.google.com/business/answer/9455399"},
        {"rule_id": "google.prices", "gate": 3, "fact": "prices", "influence": "conversion", "impact": 76, "url": "https://support.google.com/business/answer/9455399"},
        {"rule_id": "google.reviews", "gate": 4, "fact": "reviews", "influence": "prominence", "impact": 76, "url": "https://support.google.com/business/answer/3474122"},
        {"rule_id": "google.review_responses", "gate": 4, "fact": "review_responses", "influence": "trust", "impact": 78, "url": "https://support.google.com/business/answer/7091"},
        {"rule_id": "google.photos", "gate": 5, "fact": "photos", "influence": "conversion", "impact": 62, "url": "https://support.google.com/business/answer/6103862"},
        {"rule_id": "google.publications", "gate": 6, "fact": "publications", "influence": "conversion", "impact": 42, "url": "https://support.google.com/business/answer/7342169"},
    ),
    "yandex": (
        {"rule_id": "yandex.access", "gate": 0, "fact": "access", "influence": "eligibility", "impact": 100, "url": "https://yandex.ru/support/business-priority/ru/add-company"},
        {"rule_id": "yandex.verified", "gate": 1, "fact": "verified", "influence": "trust", "impact": 92, "url": "https://yandex.ru/support/business-priority/ru/manage/verified"},
        {"rule_id": "yandex.duplicate", "gate": 1, "fact": "duplicate", "influence": "eligibility", "impact": 97, "url": "https://yandex.ru/support/business-priority/ru/branches/branches-xml"},
        {"rule_id": "yandex.category", "gate": 1, "fact": "category", "influence": "ranking", "impact": 96, "url": "https://yandex.ru/support/business-priority/ru/add-company/rules-rubric"},
        {"rule_id": "yandex.contacts", "gate": 2, "fact": "contacts", "influence": "conversion", "impact": 92, "url": "https://yandex.ru/support/business-priority/ru/manage/company-info"},
        {"rule_id": "yandex.schedule", "gate": 2, "fact": "schedule", "influence": "conversion", "impact": 90, "url": "https://yandex.ru/support/business-priority/ru/manage/company-info"},
        {"rule_id": "yandex.action_path", "gate": 2, "fact": "action_path", "influence": "conversion", "impact": 94, "url": "https://yandex.ru/support/business-priority/ru/manage/company-info"},
        {"rule_id": "yandex.services", "gate": 3, "fact": "services", "influence": "relevance", "impact": 82, "url": "https://yandex.ru/support/business-priority/ru/manage/price-list"},
        {"rule_id": "yandex.prices", "gate": 3, "fact": "prices", "influence": "conversion", "impact": 78, "url": "https://yandex.ru/support/business-priority/ru/manage/price-list"},
        {"rule_id": "yandex.reviews", "gate": 4, "fact": "reviews", "influence": "ranking", "impact": 76, "url": "https://yandex.ru/support/business-priority/ru/reviews/rating"},
        {"rule_id": "yandex.review_responses", "gate": 4, "fact": "review_responses", "influence": "trust", "impact": 78, "url": "https://yandex.ru/support/business-priority/ru/reviews/get-and-promote"},
        {"rule_id": "yandex.photos", "gate": 5, "fact": "photos", "influence": "conversion", "impact": 64, "url": "https://yandex.ru/support/business-priority/ru/manage/photos"},
        {"rule_id": "yandex.publications", "gate": 6, "fact": "publications", "influence": "conversion_only", "impact": 38, "url": "https://yandex.ru/support/business-priority/ru/manage/publications"},
    ),
    "2gis": (
        {"rule_id": "2gis.access", "gate": 0, "fact": "access", "influence": "eligibility", "impact": 100, "url": "https://help.2gis.ru/question/kak-vnesti-izmeneniya-vnbspkartochku-kompanii"},
        {"rule_id": "2gis.duplicate", "gate": 1, "fact": "duplicate", "influence": "eligibility", "impact": 97, "url": "https://help.2gis.ru/question/kak-vnesti-izmeneniya-vnbspkartochku-kompanii"},
        {"rule_id": "2gis.category", "gate": 1, "fact": "category", "influence": "ranking", "impact": 94, "url": "https://help.2gis.ru/question/kak-vnesti-izmeneniya-vnbspkartochku-kompanii"},
        {"rule_id": "2gis.contacts", "gate": 2, "fact": "contacts", "influence": "conversion", "impact": 90, "url": "https://help.2gis.ru/question/kak-vnesti-izmeneniya-vnbspkartochku-kompanii"},
        {"rule_id": "2gis.schedule", "gate": 2, "fact": "schedule", "influence": "conversion", "impact": 88, "url": "https://help.2gis.ru/question/kak-vnesti-izmeneniya-vnbspkartochku-kompanii"},
        {"rule_id": "2gis.action_path", "gate": 2, "fact": "action_path", "influence": "conversion", "impact": 92, "url": "https://help.2gis.ru/question/kak-obshchatsya-sklientami-spomoshchyu-chata-2gis-instrukciya-dlya-kompaniy"},
        {"rule_id": "2gis.services", "gate": 3, "fact": "services", "influence": "relevance", "impact": 80, "url": "https://help.2gis.ru/question/upload-menu-and-prices/"},
        {"rule_id": "2gis.prices", "gate": 3, "fact": "prices", "influence": "conversion", "impact": 78, "url": "https://help.2gis.ru/question/upload-menu-and-prices/"},
        {"rule_id": "2gis.reviews", "gate": 4, "fact": "reviews", "influence": "ranking", "impact": 78, "url": "https://help.2gis.ru/question/kak-rabotat-s-otzyvami-klientov-instrukciya-dlya-kompaniy"},
        {"rule_id": "2gis.review_responses", "gate": 4, "fact": "review_responses", "influence": "trust", "impact": 78, "url": "https://help.2gis.ru/question/kak-rabotat-s-otzyvami-klientov-instrukciya-dlya-kompaniy"},
        {"rule_id": "2gis.photos", "gate": 5, "fact": "photos", "influence": "conversion", "impact": 62, "url": "https://help.2gis.ru/question/kak-zagruzit-horoshee-foto"},
        {"rule_id": "2gis.publications", "gate": 6, "fact": "publications", "influence": "not_applicable", "impact": 0, "url": "https://help.2gis.ru/"},
    ),
}


def provider_rules(provider: str) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            **item,
            "provider": provider,
            "applicability": "unsupported" if provider == "2gis" and item["fact"] == "publications" else "provider_listing",
            "verified_at": POLICY_VERIFIED_AT,
            "official_source": True,
        }
        for item in PLATFORM_RULES.get(provider, ())
    )


def rule_for(provider: str, fact: str) -> dict[str, Any] | None:
    return next((item for item in provider_rules(provider) if item["fact"] == fact), None)
