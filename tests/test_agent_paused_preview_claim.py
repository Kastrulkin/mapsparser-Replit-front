import ast
import json
import sqlite3
from pathlib import Path
import pytest


def claim_visibility_predicate():
    source=ast.parse(Path('src/services/agent_run_queue.py').read_text())
    fn=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='claim_next_agent_run')
    query=next(n.value for n in ast.walk(fn) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'WITH next_run AS' in n.value)
    return query.split('AND EXISTS',1)[1].split('ORDER BY COALESCE',1)[0].strip()


@pytest.mark.parametrize('status,preview,claimable',[
    ('paused',True,True),('paused',False,False),('paused',None,False),
    ('active',False,True),('draft',True,True),('archived',True,False)])
def test_paused_automation_only_allows_explicit_preview(status,preview,claimable):
    db=sqlite3.connect(':memory:')
    db.executescript('CREATE TABLE agent_blueprints(id TEXT,status TEXT); CREATE TABLE agent_runs(id TEXT,blueprint_id TEXT,input_json TEXT);')
    db.execute('INSERT INTO agent_blueprints VALUES(?,?)',('blueprint',status))
    # PostgreSQL ->> returns textual booleans; keep that representation in the
    # local SQL evaluator so the production predicate itself is exercised.
    db.execute('INSERT INTO agent_runs VALUES(?,?,?)',('run','blueprint',json.dumps({'preview_mode':str(preview).lower()} if preview is not None else {})))
    rows=db.execute('SELECT id FROM agent_runs WHERE EXISTS '+claim_visibility_predicate()).fetchall()
    assert bool(rows) is claimable
    db.close()
