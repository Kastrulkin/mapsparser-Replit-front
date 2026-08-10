from datetime import datetime, timezone
from pathlib import Path

from src.services import founder_content_editorial


def test_editorial_diff_preserves_before_after_and_edit_ratio():
    result = founder_content_editorial.build_editorial_diff(
        "LocalOS подготовил большой и сложный текст. Это второй абзац?",
        "LocalOS подготовил короткий текст.\n\nЭто второй абзац.",
    )

    assert 0 < result["edit_ratio"] < 1
    assert result["changes"]
    assert result["final_paragraphs"] > result["draft_paragraphs"]
    assert result["final_questions"] < result["draft_questions"]


def test_founder_post_review_reuses_human_language_gate_and_blocks_copy_overlap():
    copied = "один два три четыре пять шесть семь восемь девять десять"
    text = (
        "LocalOS обновил поиск партнёров и теперь проверяет компанию до подготовки письма. "
        + copied
        + "\n\nТак команда видит причину выбора и подтверждения до ручного запуска. "
        + "Это помогает разбирать решения, а не принимать готовый список вслепую. " * 4
    )
    result = founder_content_editorial.review_founder_post(
        text,
        [{"excerpt": f"Начало источника {copied} окончание источника"}],
    )

    assert result["passed"] is False
    assert "SOURCE_WORDING_OVERLAP" in result["reason_codes"]
    assert result["manual_publication_only"] is True


def test_morning_window_is_timezone_aware(monkeypatch):
    monkeypatch.setenv("FOUNDER_CONTENT_MORNING_HOUR", "9")
    monkeypatch.setenv("FOUNDER_CONTENT_MORNING_MINUTE", "30")

    assert founder_content_editorial.founder_content_window_is_due(
        datetime(2026, 8, 9, 6, 35, tzinfo=timezone.utc)
    )
    assert not founder_content_editorial.founder_content_window_is_due(
        datetime(2026, 8, 9, 4, 0, tzinfo=timezone.utc)
    )


def test_telegram_proposal_explicitly_keeps_publication_manual():
    message = founder_content_editorial.format_founder_content_telegram_message(
        {
            "brief_title": "Поиск партнёров",
            "generated_text": "LocalOS сначала проверяет факты, а затем готовит черновик.",
        }
    )

    assert "Ответьте на это сообщение" in message
    assert "автоматически не происходит" in message


class CorrectionCursor:
    def __init__(self):
        self.current = None
        self.rowcount = 0
        self.commands = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split())
        self.commands.append((normalized, params))
        self.rowcount = 0
        if "FROM founder_content_drafts draft" in normalized:
            self.current = {
                "id": "draft-1",
                "brief_id": "brief-1",
                "user_id": "11111111-1111-1111-1111-111111111111",
                "generated_text": "Черновик LocalOS. " * 20,
                "brief_title": "Партнёрства",
            }
        elif "FROM userexamples" in normalized:
            self.current = None
        elif normalized.startswith("UPDATE founder_content_drafts"):
            self.current = None
            self.rowcount = 1
        else:
            self.current = None

    def fetchone(self):
        return self.current

    def close(self):
        return None


class CorrectionConnection:
    def __init__(self):
        self.cursor_value = CorrectionCursor()

    def cursor(self, **_kwargs):
        return self.cursor_value


def test_reply_captures_correction_diff_and_learning_pair(monkeypatch):
    learning = []
    monkeypatch.setattr(
        founder_content_editorial,
        "record_ai_learning_event",
        lambda **kwargs: learning.append(kwargs) or True,
    )
    connection = CorrectionConnection()

    result = founder_content_editorial.capture_founder_content_correction(
        connection,
        telegram_id="12345",
        reply_to_message_id=777,
        corrected_text="Исправленная авторская версия LocalOS. " * 14,
    )

    assert result["captured"] is True
    assert result["manual_publication_only"] is True
    assert learning[0]["capability"] == "founder_content.post"
    assert learning[0]["draft_text"] != learning[0]["final_text"]
    assert any("INSERT INTO userexamples" in query for query, _params in connection.cursor_value.commands)


def test_migration_keeps_drafts_separate_from_publication():
    migration = Path("alembic_migrations/versions/20260810_add_founder_content_editorial_loop.py").read_text(encoding="utf-8")

    assert "founder_content_briefs" in migration
    assert "founder_content_drafts" in migration
    assert "telegram_message_id" in migration
    assert "published" not in migration


def test_b2b_retrieval_has_mandatory_corpus_filter():
    source = Path("src/services/founder_content_editorial.py").read_text(encoding="utf-8")

    assert "metadata_json->>'corpus_tag' = 'telegram_b2b'" in source
    assert "len(documents) >= 3 and len(sources) >= 2" in source
