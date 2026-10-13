"""The worker's cursor scope must retain wrapping and never manage transactions."""
import ast
from pathlib import Path
from unittest.mock import Mock
import pytest


def wrapper_type():
    path=Path(__file__).resolve().parents[1]/'src/database_manager.py'
    nodes=[n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name in {'HybridRow','DBCursorWrapper'}]
    ns={}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns['DBCursorWrapper']


def test_context_keeps_wrapper_and_closes_underlying_cursor():
    raw=Mock();raw.__exit__=Mock(return_value=False);raw.fetchone.return_value={'id':'queue'}
    wrapped=wrapper_type()(raw)
    with wrapped as cursor:
        assert cursor is wrapped
        assert cursor.fetchone()[0]=='queue'
        cursor.execute('SELECT 1')
    raw.execute.assert_called_once_with('SELECT 1',None)
    raw.__exit__.assert_called_once_with(None,None,None)
    raw.commit.assert_not_called();raw.rollback.assert_not_called()


def test_context_exception_is_not_suppressed():
    raw=Mock();raw.__exit__=Mock(return_value=False)
    with pytest.raises(ValueError,match='preflight_failed'):
        with wrapper_type()(raw):
            raise ValueError('preflight_failed')
    assert raw.__exit__.call_args.args[0] is ValueError
    raw.commit.assert_not_called();raw.rollback.assert_not_called()
