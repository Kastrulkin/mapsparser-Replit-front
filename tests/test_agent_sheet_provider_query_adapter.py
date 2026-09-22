from database_manager import DBCursorWrapper
from services.agent_sheet_provider_executor import claim_next_sheet_provider_request


class _RecordingCursor:
    rowcount = 0

    def __init__(self):
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return None


def test_sheet_provider_claim_does_not_confuse_jsonb_operator_with_placeholder():
    raw_cursor = _RecordingCursor()
    cursor = DBCursorWrapper(raw_cursor)

    assert claim_next_sheet_provider_request(cursor, business_id="") is None
    assert len(raw_cursor.queries) == 3
