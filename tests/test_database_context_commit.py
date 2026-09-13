import pytest
from database_manager import DatabaseManager


def test_context_commit_failure_is_reported_and_connection_closed():
    class Connection:
        def __init__(self): self.rollbacks=0;self.closed=False
        def commit(self): raise RuntimeError('commit failed')
        def rollback(self): self.rollbacks+=1
        def close(self): self.closed=True
    manager=DatabaseManager.__new__(DatabaseManager)
    manager.conn=Connection();manager._closed=False
    with pytest.raises(RuntimeError,match='commit failed'):
        manager.__exit__(None,None,None)
    assert manager.conn.rollbacks==1
    assert manager.conn.closed
