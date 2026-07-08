from main import (
    _extract_review_reply_from_model_result,
    _format_template_with_literal_json_fallback,
    _normalize_review_reply_output,
)


def test_extract_review_reply_never_returns_markdown_json_wrapper() -> None:
    raw = '''```json
{"reply": "Спасибо за ваш отзыв! Мы ценим, что вам понравилась аккуратность нашего мастера и удобство записи." Обращайтесь, будем рады видеть вас снова."}
```'''

    reply, malformed = _extract_review_reply_from_model_result(raw)
    cleaned = _normalize_review_reply_output(
        reply,
        "DEMO Яндекс Карты: отзыв о груминге, аккуратности мастера и удобстве записи.",
        malformed_model_output=malformed,
        language="ru",
    )

    assert "```" not in cleaned
    assert '{"reply"' not in cleaned
    assert "аккуратность мастера" in cleaned
    assert "удобство записи" in cleaned


def test_generic_review_reply_is_replaced_with_pattern_based_detail_reply() -> None:
    cleaned = _normalize_review_reply_output(
        "Спасибо за отзыв, будем рады видеть вас снова.",
        "Отзыв о груминге, аккуратности мастера и удобстве записи.",
        language="ru",
    )

    assert cleaned == "Спасибо за отзыв. Рады, что вы отметили аккуратность мастера и удобство записи. Будем ждать вас снова."


def test_review_reply_prompt_template_keeps_literal_json_example() -> None:
    template = 'Верни JSON: {"reply": "текст"}. Тон: {tone}. Отзыв: {review_text}'

    formatted = _format_template_with_literal_json_fallback(
        template,
        {
            "tone": "профессиональный",
            "review_text": "Отличный сервис",
        },
    )

    assert '{"reply": "текст"}' in formatted
    assert "профессиональный" in formatted
    assert "Отличный сервис" in formatted
