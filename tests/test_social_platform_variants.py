import json

from services.social_posts import platform_variants
from services.social_post_service import (
    _platform_variant_for_prepare,
    _platform_variant_needs_generation,
)


def test_build_platform_variants_uses_one_ai_response_for_all_channels(monkeypatch):
    calls = []

    def fake_analyze(prompt, **kwargs):
        calls.append({"prompt": prompt, "kwargs": kwargs})
        return json.dumps(
            {
                "variants": {
                    "telegram": "Рейс задержался.\n\nRiderra дождётся туриста после согласования ожидания.",
                    "vk": "Задержка рейса не должна срывать встречу.\n\nRiderra согласует ожидание водителя.",
                    "google_business": "При задержке рейса Riderra согласует дополнительное ожидание водителя.",
                }
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(platform_variants, "analyze_text_with_gigachat", fake_analyze)

    variants = platform_variants.build_platform_variants(
        "Рейс задержался. Riderra может согласовать дополнительное ожидание водителя.",
        ["telegram", "vk", "google_business"],
        {"business_id": "riderra", "theme": "Задержка рейса"},
    )

    assert len(calls) == 1
    assert variants["telegram"]["text"] != variants["vk"]["text"]
    assert variants["telegram"]["metadata"]["variant_source"] == "ai"
    assert variants["google_business"]["metadata"]["platform_rules_version"] == "v1"


def test_build_platform_variants_falls_back_per_channel(monkeypatch):
    monkeypatch.setattr(platform_variants, "analyze_text_with_gigachat", lambda *args, **kwargs: "not-json")

    variants = platform_variants.build_platform_variants(
        "Первое предложение. Второе предложение. Третье предложение.",
        ["telegram", "yandex_maps"],
        {},
    )

    assert variants["telegram"]["metadata"]["variant_source"] == "deterministic"
    assert "\n\n" in variants["telegram"]["text"]
    assert "\n\n" not in variants["yandex_maps"]["text"]


def test_max_variant_uses_channel_rules_and_limit(monkeypatch):
    prompts = []

    def fake_analyze(prompt, **kwargs):
        prompts.append(prompt)
        return json.dumps({"variants": {"max": "Первая строка.\n\nКороткий пост для MAX."}}, ensure_ascii=False)

    monkeypatch.setattr(platform_variants, "analyze_text_with_gigachat", fake_analyze)

    variants = platform_variants.build_platform_variants(
        "Подтверждённый текст публикации.",
        ["max"],
        {"business_id": "business-1", "theme": "История визита"},
    )

    assert "Компактный пост для канала MAX" in prompts[0]
    assert variants["max"]["text"] == "Первая строка.\n\nКороткий пост для MAX."
    assert platform_variants.PLATFORM_TEXT_LIMITS["max"] == 4000


def test_build_platform_variants_honors_channel_language(monkeypatch):
    prompts = []

    def fake_analyze(prompt, **kwargs):
        prompts.append(prompt)
        return json.dumps(
            {
                "variants": {
                    "google_business": "Tell us how many passengers and bags are travelling.",
                    "vk": "Укажите число пассажиров и объём багажа.",
                }
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(platform_variants, "analyze_text_with_gigachat", fake_analyze)

    platform_variants.build_platform_variants(
        "Укажите число пассажиров и весь нестандартный багаж.",
        ["google_business", "vk"],
        {
            "business_id": "riderra",
            "metadata_json": {
                "channel_languages": {
                    "google_business": "en",
                    "vk": "ru",
                }
            },
        },
    )

    assert len(prompts) == 1
    assert "google_business: write in English" in prompts[0]
    assert "vk: write in Russian" in prompts[0]


def test_configured_channel_language_never_falls_back_to_the_source_language(monkeypatch):
    monkeypatch.setattr(platform_variants, "analyze_text_with_gigachat", lambda *args, **kwargs: "not-json")

    variants = platform_variants.build_platform_variants(
        "Укажите число пассажиров и весь нестандартный багаж.",
        ["google_business"],
        {
            "metadata_json": {
                "channel_languages": {"google_business": "en"},
            },
        },
    )

    assert variants["google_business"]["text"] == ""
    assert variants["google_business"]["metadata"]["variant_source"] == "unavailable"
    assert variants["google_business"]["metadata"]["variant_status"] == "needs_regeneration"
    assert variants["google_business"]["metadata"]["channel_language"] == "en"


def test_current_variant_does_not_request_regeneration():
    base_text = "Подтверждённый общий текст."
    existing = {
        "status": "needs_review",
        "platform_text": "Версия Telegram.",
        "metadata_json": {
            "base_text_hash": platform_variants.platform_variant_base_hash(base_text),
            "variant_status": "current",
            "platform_rules_version": "v1",
            "manually_edited": False,
        },
    }

    assert _platform_variant_needs_generation(existing, base_text) is False
    assert _platform_variant_needs_generation(existing, base_text, True) is True


def test_manual_variant_becomes_stale_without_being_overwritten():
    old_base = "Старый общий текст."
    existing = {
        "status": "needs_review",
        "platform_text": "Моя ручная версия для VK.",
        "metadata_json": {
            "base_text_hash": platform_variants.platform_variant_base_hash(old_base),
            "variant_status": "current",
            "platform_rules_version": "v1",
            "variant_source": "manual",
            "manually_edited": True,
        },
    }

    prepared = _platform_variant_for_prepare(
        platform="vk",
        base_text="Новый общий текст.",
        existing=existing,
        generated=None,
    )

    assert prepared["text"] == "Моя ручная версия для VK."
    assert prepared["metadata"]["variant_status"] == "stale"
    assert prepared["metadata"]["variant_source"] == "manual"


def test_published_variant_never_requests_regeneration():
    existing = {
        "status": "published",
        "platform_text": "Уже опубликовано.",
        "metadata_json": {},
    }

    assert _platform_variant_needs_generation(existing, "Совсем новый общий текст.") is False
