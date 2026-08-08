from __future__ import annotations

from pathlib import Path

from services.outreach_pain_library_service import (
    PAIN_LIBRARY_PATTERN_KEY,
    classify_owner_language,
    compile_pain_library_draft,
    load_approved_pain_library,
)
from services.outreach_founder_led_copy import founder_led_localos_text


ROOT = Path(__file__).resolve().parents[1]


class PatternCursor:
    def __init__(self, latest=None, approved=None):
        self.latest = latest
        self.approved = approved
        self.current = None
        self.executions = []

    def execute(self, query, params=None):
        self.executions.append((query, params))
        if "status = 'approved'" in query and query.lstrip().startswith("SELECT"):
            self.current = self.approved
        elif query.lstrip().startswith("SELECT"):
            self.current = self.latest
        else:
            self.current = None

    def fetchone(self):
        return self.current


def test_pain_language_is_classified_with_exact_source_provenance():
    library = classify_owner_language([
        {
            "id": "doc-1",
            "source_id": "source-1",
            "source_title": "Чат владельцев",
            "permalink": "https://t.me/example/1",
            "published_at": "2026-08-05T10:00:00+00:00",
            "content": "Клиентов нет от слова совсем. Работаю за администратора и бухгалтера.",
        }
    ])
    marketing = library["marketing_and_clients"][0]
    operations = library["operations_and_burnout"][0]
    assert marketing["text"] == "Клиентов нет от слова совсем."
    assert marketing["document_id"] == "doc-1"
    assert marketing["permalink"] == "https://t.me/example/1"
    assert marketing["status"] == "segment_hypothesis_only"
    assert operations["source_id"] == "source-1"


def test_pain_language_rejects_editorial_keyword_matches():
    library = classify_owner_language([
        {
            "id": "doc-2",
            "source_id": "source-2",
            "content": (
                "Всё равно зарегистрируйтесь в боте, там будет запись конференции. "
                "Компания работает с корпоративными клиентами по всей стране. "
                "Обороты росли: 8,6 млн, 43 млн и 76 млн."
            ),
        }
    ])
    assert all(not phrases for phrases in library.values())


def test_compiler_creates_draft_and_never_activates_raw_channel_language():
    cursor = PatternCursor()
    documents = [
        {"id": "1", "source_id": "a", "content": "Клиентов нет, реклама не помогает."},
        {"id": "2", "source_id": "b", "content": "Работы много, а средний чек маленький."},
        {"id": "3", "source_id": "b", "content": "Работаю за администратора и бухгалтера."},
    ]
    result = compile_pain_library_draft(cursor, documents, user_id="superadmin")
    insert_query, _params = cursor.executions[-1]
    assert result["status"] == "draft"
    assert result["unchanged"] is False
    assert "'pain', 'draft'" in insert_query
    assert "approved" not in insert_query


def test_runtime_uses_only_approved_version_and_keeps_hypothesis_boundary():
    cursor = PatternCursor(approved={
        "id": "pattern-7",
        "version": 7,
        "message_rule_json": {
            "library_version": "pain-library-v7",
            "pains": [{"key": "operations_and_burnout", "candidate_source_phrases": []}],
        },
        "source_refs_json": [{"document_id": "doc-1"}],
    })
    guidance = load_approved_pain_library(cursor)
    assert guidance["version"] == "pain-library-v7"
    assert guidance["pattern_id"] == "pattern-7"
    assert guidance["pain_language_status"] == "segment_hypothesis_only"
    assert guidance["source_refs"] == [{"document_id": "doc-1"}]
    assert guidance["pain_signal_library_version"] == "beauty_pain_signals_v4"
    assert len(guidance["pain_signal_hypotheses"]) == 12


def test_pain_library_uses_existing_pattern_and_outreach_surfaces():
    migration = (ROOT / "alembic_migrations/versions/20260805_add_outreach_pain_pattern_type.py").read_text(encoding="utf-8")
    api = (ROOT / "src/api/outreach_campaign_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "src/worker.py").read_text(encoding="utf-8")
    assert "outreach_knowledge_patterns" in migration
    assert "'pain'" in migration
    assert PAIN_LIBRARY_PATTERN_KEY == "beauty_owner_pain_library"
    assert "/api/outreach/knowledge-patterns/pain-library/refresh" in api
    assert "_refresh_outreach_pain_library_if_due()" in worker
    assert "outreachsendqueue" not in (ROOT / "src/services/outreach_pain_library_service.py").read_text(encoding="utf-8")


def test_approved_owner_language_is_used_as_segment_language_not_recipient_fact():
    text = founder_led_localos_text("founder_story", {
        "sender_mode": "localos",
        "recipient": "Салон",
        "recipient_segment": "beauty_team",
        "outreach_playbook": {
            "pain_library": [{
                "key": "operations_and_burnout",
                "candidate_source_phrases": [{"text": "Работаю за администратора и бухгалтера"}],
            }],
        },
    }, None)
    assert text is not None
    assert "Работаю за администратора и бухгалтера" not in text
    assert "карточек, контента и отзывов" in text
    assert "вы работаете за администратора" not in text.lower()


def test_audience_description_does_not_replace_owner_voice():
    text = founder_led_localos_text("founder_story", {
        "sender_mode": "localos",
        "recipient": "Салон",
        "recipient_segment": "beauty_team",
        "outreach_playbook": {
            "pain_library": [{
                "key": "operations_and_burnout",
                "candidate_source_phrases": [{
                    "text": "Предпринимателю, который устал тащить всё сам и хочет построить систему",
                }],
                "approved_seed_phrases": ["Если не я, то никто"],
            }],
        },
    }, None)

    assert text is not None
    assert "Если не я, то никто" not in text
    assert "карточек, контента и отзывов" in text
    assert "Предпринимателю, который" not in text
