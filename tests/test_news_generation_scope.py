from main import (
    _clean_generated_news_text,
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


def test_clean_generated_news_text_removes_only_outer_broken_quote() -> None:
    raw = 'Сеть зоосалонов "Рога и копыта" приглашает на груминг-услуги."'

    cleaned = _clean_generated_news_text(raw)

    assert cleaned == 'Сеть зоосалонов "Рога и копыта" приглашает на груминг-услуги.'


def test_clean_generated_news_text_extracts_broken_json_with_business_quotes() -> None:
    raw = (
        '{"news": "Рада приветствовать вас в нашей материнской точке сети груминга домашних животных '
        '"Рога и копыта"! Мы предлагаем профессиональные уходовые процедуры для ваших любимцев. '
        'Приходите лично познакомиться с атмосферой нашего салона." }'
    )

    cleaned = _clean_generated_news_text(raw)

    assert '{"news"' not in cleaned
    assert "}" not in cleaned
    assert '"Рога и копыта"' in cleaned
    assert "Приходите лично" in cleaned
    assert 'любимцев." Приходите' not in cleaned
    assert cleaned.count('"') == 2
