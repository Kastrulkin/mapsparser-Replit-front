from main import (
    _news_text_has_demo_platform_drift,
    _news_text_has_service_anchor,
    _service_focused_news_fallback,
)


def test_news_generation_flags_localos_demo_drift_for_service_news() -> None:
    generated = (
        'Бизнес-сеть "Рога и копыта" приглашает вас ознакомиться с нашей материнской точкой сети. '
        "Здесь мы делимся опытом автоматизации бизнеса с использованием AI-инструментов LocalOS."
    )

    assert _news_text_has_demo_platform_drift(generated)
    assert not _news_text_has_service_anchor(generated, "Услуга: чистка ушей питомца. Описание: бережный уход")


def test_service_focused_news_fallback_keeps_pet_ear_cleaning_as_topic() -> None:
    text = _service_focused_news_fallback(
        business_name="Рога и копыта",
        service_context="Услуга: чистка ушей питомца. Описание: бережный уход",
        language_code="ru",
    )

    assert "чистка ушей питомца" in text
    assert "ушами питомца" in text
    assert "LocalOS" not in text
    assert "материнск" not in text.lower()
    assert "партнер" not in text.lower()
