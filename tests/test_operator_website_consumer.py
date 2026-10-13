from concurrent.futures import Future
from unittest.mock import Mock

import operator_worker as worker


def test_running_site_read_does_not_block_pause_or_chat(monkeypatch):
    future = Future()
    executor = Mock()
    command = Mock(return_value={'status': 'paused'})
    monkeypatch.setattr(worker, 'website_research_enabled', lambda: True)
    monkeypatch.setattr(worker, 'process_next_operator_async_job', command)
    result, retained = worker.poll_once(executor, future)
    assert result['status'] == 'paused'
    assert retained is future
    executor.submit.assert_not_called()
    command.assert_called_once_with()


def test_consumption_requires_both_feature_flags(monkeypatch):
    monkeypatch.setenv('OPENCLAW_WEBSITE_RESEARCH_ENABLED', 'true')
    monkeypatch.delenv('PROSPECTING_CONTACT_INTELLIGENCE_ENABLED', raising=False)
    assert not worker.website_research_enabled()
    monkeypatch.setenv('PROSPECTING_CONTACT_INTELLIGENCE_ENABLED', 'true')
    assert worker.website_research_enabled()


def test_only_approved_source_queue_is_claimed_and_claim_is_committed(monkeypatch):
    db = Mock()
    cursor = db.conn.cursor.return_value
    claim = Mock(return_value={'id': 'job'})
    def process(selected_cursor, job):
        db.conn.commit.assert_called_once_with()
        assert selected_cursor is cursor and job['id'] == 'job'
        return {'status': 'ready'}
    monkeypatch.setattr(worker, 'DatabaseManager', Mock(return_value=db))
    monkeypatch.setattr(worker, 'claim_next_enrichment_job', claim)
    monkeypatch.setattr(worker, 'process_enrichment_job', process)
    assert worker.process_reviewed_website_job()
    claim.assert_called_once_with(cursor, reviewed_sources_only=True)
    assert db.conn.commit.call_count == 2
    db.close.assert_called_once_with()


def test_failed_read_uses_existing_failure_state_and_releases_connection(monkeypatch):
    db = Mock()
    monkeypatch.setattr(worker, 'DatabaseManager', Mock(return_value=db))
    monkeypatch.setattr(worker, 'claim_next_enrichment_job', Mock(return_value={'id': 'job'}))
    monkeypatch.setattr(worker, 'process_enrichment_job', Mock(side_effect=ValueError('synthetic')))
    failed = Mock(return_value={'status': 'failed'})
    monkeypatch.setattr(worker, 'fail_enrichment_job', failed)
    assert worker.process_reviewed_website_job()
    db.conn.rollback.assert_called_once_with()
    failed.assert_called_once()
    db.close.assert_called_once_with()
