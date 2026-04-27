from services import telegram_compare_flow


def test_compare_result_without_cached_cards_returns_audit_links(monkeypatch) -> None:
    monkeypatch.setattr(telegram_compare_flow, "_load_card_snapshot_by_url", lambda normalized_url: None)
    text = telegram_compare_flow.build_guest_compare_result(
        own_url="https://yandex.ru/maps/org/test/1",
        competitor_url="https://yandex.ru/maps/org/test/2",
        own_report_url="https://localos.pro/report-a",
        competitor_report_url="https://localos.pro/report-b",
    )
    assert "Я запустил аудит для обеих карточек" in text
    assert "https://localos.pro/report-a" in text
    assert "https://localos.pro/report-b" in text


def test_compare_result_with_gap_has_headline_and_next_step(monkeypatch) -> None:
    def fake_loader(normalized_url: str):
        if normalized_url.endswith("/1"):
            return {
                "title": "Мы",
                "rating": 4.2,
                "reviews_count": 12,
                "products_count": 1,
                "news_count": 0,
                "photos_count": 2,
            }
        return {
            "title": "Конкурент",
            "rating": 4.9,
            "reviews_count": 120,
            "products_count": 8,
            "news_count": 3,
            "photos_count": 18,
        }

    monkeypatch.setattr(telegram_compare_flow, "_load_card_snapshot_by_url", fake_loader)
    text = telegram_compare_flow.build_guest_compare_result(
        own_url="https://yandex.ru/maps/org/test/1",
        competitor_url="https://yandex.ru/maps/org/test/2",
        own_report_url="https://localos.pro/report-a",
        competitor_report_url="https://localos.pro/report-b",
    )
    assert "конкурент выглядит сильнее" in text.lower()
    assert "следующий шаг" in text.lower()
    assert "вернуть часть спроса себе" in text.lower()
