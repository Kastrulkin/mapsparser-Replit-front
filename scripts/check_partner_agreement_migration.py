"""Exercise upgrade twice and downgrade using TEMP tables; never touches production."""
import importlib.util
from pathlib import Path
import subprocess

path = Path(__file__).resolve().parents[1] / 'alembic_migrations/versions/20260911_partner_agreements.py'
spec = importlib.util.spec_from_file_location('agreement_migration', path)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
statements = []
class Capture:
    def execute(self, sql):
        statements.append(sql + ';')
migration.op = Capture()
migration.upgrade()
migration.upgrade()
checks = """
DO $$ BEGIN
IF (SELECT agreement_json->>'status' FROM lead_workstreams LIMIT 1) <> 'needs_confirmation' THEN
RAISE EXCEPTION 'Legacy terms must not auto-confirm'; END IF;
IF (SELECT agreement_json->'terms'->>'details' FROM lead_workstreams LIMIT 1) <> 'Real terms' THEN
RAISE EXCEPTION 'Terms lost'; END IF;
END $$;
"""
statements.append(checks)
migration.downgrade()
sql = """BEGIN;
CREATE TEMP TABLE lead_workstreams (id uuid, workstream_type text);
CREATE TEMP TABLE journey_actions (entity_id text, id uuid, payload_json jsonb, user_id text, completed_at timestamptz, flow_type text, entity_type text, action_type text, status text);
INSERT INTO lead_workstreams VALUES ('00000000-0000-4000-8000-000000000001','client_partnership');
INSERT INTO journey_actions VALUES ('00000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000002','{"details":"Real terms"}','owner',NOW(),'partnership','lead_workstream','define_terms','completed');
""" + '\n'.join(statements) + '\nROLLBACK;'
subprocess.run(['docker', 'exec', '-i', 'seo-postgres-1', 'sh', '-c', 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'], input=sql, text=True, check=True)
