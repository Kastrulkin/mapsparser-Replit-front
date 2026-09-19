import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "seed_journey_staging.py"


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((str(query), params))


class RecordingConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.commits = 0
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


@pytest.fixture
def journey_seed_module():
    specification = importlib.util.spec_from_file_location("journey_seed_contract", SCRIPT_PATH)
    module = importlib.util.module_from_spec(specification)
    assert specification.loader is not None
    specification.loader.exec_module(module)
    return module


def partnership_artifact_calls(cursor):
    return [
        (query, params)
        for query, params in cursor.calls
        if "INSERT INTO partnershipleadartifacts" in query
    ]


def test_partnership_journey_seeds_an_unconfirmed_overlap_without_outreach_artifacts(
    journey_seed_module,
    monkeypatch,
):
    cursor = RecordingCursor()
    connection = RecordingConnection(cursor)
    monkeypatch.setattr(journey_seed_module, "get_db_connection", lambda: connection)

    journey_seed_module.seed_journeys("owner-id", "business-id")

    artifact_calls = partnership_artifact_calls(cursor)
    assert len(artifact_calls) == 1
    query, params = artifact_calls[0]
    assert params[0] == journey_seed_module.fixture_id("lead:partnership")
    assert params[1].adapted == {
        "overlap": ["Локальная аудитория: жители Санкт-Петербурга, выбирающие услуги рядом."],
        "score_explanation": (
            "Синтетическая гипотеза для демо: у компаний может пересекаться "
            "локальная аудитория; требуется ручная проверка фактов."
        ),
        "readiness_code": "needs_evidence",
        "next_action": "Проверить публичные факты о партнёре вручную перед подготовкой предложения.",
    }
    assert "ON CONFLICT (lead_id) DO NOTHING" in query
    assert "offer_draft_json" not in query
    assert "contact" not in query.lower()
    assert "approval" not in query.lower()
    assert "send" not in query.lower()
    assert connection.commits == 1
    assert connection.closed is True


def test_partnership_overlap_seed_emits_same_key_and_conflict_do_nothing(
    journey_seed_module,
    monkeypatch,
):
    first_cursor = RecordingCursor()
    second_cursor = RecordingCursor()
    connections = [RecordingConnection(first_cursor), RecordingConnection(second_cursor)]
    monkeypatch.setattr(journey_seed_module, "get_db_connection", connections.pop)

    journey_seed_module.seed_journeys("owner-id", "business-id")
    journey_seed_module.seed_journeys("owner-id", "business-id")

    first_query, first_params = partnership_artifact_calls(first_cursor)[0]
    second_query, second_params = partnership_artifact_calls(second_cursor)[0]
    assert first_query == second_query
    assert first_params[0] == second_params[0]
    assert first_params[1].adapted == second_params[1].adapted
    assert "ON CONFLICT (lead_id) DO NOTHING" in first_query
