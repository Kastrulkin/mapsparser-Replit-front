from pathlib import Path


CONTENT_PAGE = Path("frontend/src/pages/dashboard/ContentPage.tsx")
AUDIENCE_INSIGHTS = Path("frontend/src/components/AudienceInsights.tsx")
CONTENT_WORKSPACE_COPY = Path("frontend/src/i18n/contentWorkspaceCopy.ts")
CONTENT_PLAN_SERVICE = Path("src/services/content_plan_service.py")


def test_content_setup_uses_three_plain_language_steps() -> None:
    source = CONTENT_PAGE.read_text(encoding="utf-8")

    assert "Настроить контент" in source
    assert "{ key: 'business', label: 'О бизнесе' }" in source
    assert "{ key: 'audience', label: 'О клиентах' }" in source
    assert "{ key: 'voice', label: 'Как писать' }" in source


def test_content_setup_values_are_saved_and_used_for_generation() -> None:
    page_source = CONTENT_PAGE.read_text(encoding="utf-8")
    service_source = CONTENT_PLAN_SERVICE.read_text(encoding="utf-8")

    assert "business_description: businessDescription.trim()" in page_source
    assert "audience_description: audienceDescription.trim()" in page_source
    assert 'voice_preferences.get("business_description")' in service_source
    assert 'voice_preferences.get("audience_description")' in service_source


def test_audience_insights_opens_source_selection_in_a_drawer() -> None:
    source = AUDIENCE_INSIGHTS.read_text(encoding="utf-8")
    copy_source = CONTENT_WORKSPACE_COPY.read_text(encoding="utf-8")

    assert "Настроить источники" in copy_source
    assert "Добавить канал конкурента" in copy_source
    assert '<TelegramResearchSetup businessId={businessId} mode="sources" />' in source
    assert '<Sheet open={sourcesOpen}' in source
