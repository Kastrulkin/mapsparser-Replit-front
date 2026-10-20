import hashlib
from services.content_reference_research import get_research


class Cursor:
    def __init__(self, report, rows=None):
        self.report = report
        self.rows = rows or []
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((sql, params))

    def fetchone(self):
        return {'metadata_json': {'report': self.report}} if self.report else None

    def fetchall(self):
        return self.rows


def report():
    return {'schema_version': 1, 'business_id': 'business', 'posts': [
        {'post_id': 'post', 'title': 'Old title', 'text_sha256': hashlib.sha256(b'Original').hexdigest()}]}


def test_private_research_has_explicit_business_and_type_scope():
    cursor = Cursor(report(), [{'id': 'post', 'draft_text': 'Original', 'theme': 'Old title'}])
    assert get_research(cursor, 'business')['stale_post_ids'] == []
    assert all(params == ('business',) for _, params in cursor.queries)
    assert "example_type='editorial_source_research'" in cursor.queries[0][0]
    assert all('SELECT' in sql and 'UPDATE' not in sql for sql, _ in cursor.queries)


def test_misplaced_report_never_exposes_another_business():
    cursor = Cursor({**report(), 'business_id': 'other'})
    assert get_research(cursor, 'business') is None
    assert len(cursor.queries) == 1


def test_missing_research_is_not_fabricated():
    assert get_research(Cursor(None), 'business') is None


def test_changed_or_deleted_post_keeps_evidence_but_marks_it_stale():
    for rows in [[], [{'id': 'post', 'draft_text': 'Changed', 'theme': 'Old title'}],
                 [{'id': 'post', 'draft_text': 'Original', 'theme': 'New title'}]]:
        original = report()
        result = get_research(Cursor(original, rows), 'business')
        assert result['stale_post_ids'] == ['post']
        assert 'stale_post_ids' not in original
        assert result['posts'] == original['posts']


def test_unsupported_schema_not_interpreted():
    assert get_research(Cursor({**report(), 'schema_version': 2}), 'business') is None


def test_source_study_does_not_depend_on_existing_posts():
    cursor = Cursor({**report(), 'purpose': 'pre_plan_source_research', 'posts': []})
    result = get_research(cursor, 'business')
    assert result['stale_post_ids'] == []
    assert len(cursor.queries) == 1
    assert all('contentplanitems' not in sql for sql, _ in cursor.queries)
