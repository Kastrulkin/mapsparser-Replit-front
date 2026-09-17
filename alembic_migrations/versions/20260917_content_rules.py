"""Versioned content rule history on the existing business profile."""
from alembic import op
revision = '20260917_content_rules'
down_revision = '20260915_storage_oauth'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS content_rule_history (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
        rule_id TEXT NOT NULL, actor_id TEXT NOT NULL REFERENCES users(id),
        request_id TEXT NOT NULL, request_hash TEXT NOT NULL, version INTEGER NOT NULL,
        snapshot JSONB NOT NULL, event_type TEXT NOT NULL DEFAULT 'changed', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(business_id, actor_id, request_id))''')
    op.execute("ALTER TABLE content_rule_history ADD COLUMN IF NOT EXISTS event_type TEXT NOT NULL DEFAULT 'changed'")
    op.execute('CREATE INDEX IF NOT EXISTS content_rule_history_lookup ON content_rule_history(business_id,rule_id,created_at)')

    # Only the explicitly approved rule; never reinterpret other editorial notes.
    op.execute("""DO $$
    DECLARE p JSONB; note JSONB; rule JSONB;
    BEGIN
      SELECT preferences_json INTO p FROM content_voice_profiles
        WHERE business_id='cb674174-8b3d-41a3-8277-525c849935f2' FOR UPDATE;
      SELECT value INTO note FROM jsonb_array_elements(COALESCE(p->'editorial_notes','[]'::jsonb))
        WHERE value->>'id'='813836d8-be46-46aa-8ea0-d40e13e74861';
      IF note IS NOT NULL AND NOT EXISTS(SELECT 1 FROM content_rule_history
          WHERE id='7fd6c9fe-1a8b-4ca7-9130-5557e100497a') THEN
        rule=jsonb_build_object('id','7fd6c9fe-1a8b-4ca7-9130-5557e100497a',
          'business_id','cb674174-8b3d-41a3-8277-525c849935f2','text',note->>'text',
          'original_text',note->>'text','author_id',note->>'actor_id','source','approved_legacy_rule',
          'version',1,'status','active','updated_at',NOW());
        INSERT INTO content_rule_history(id,business_id,rule_id,actor_id,request_id,request_hash,version,snapshot)
          VALUES ('7fd6c9fe-1a8b-4ca7-9130-5557e100497a','cb674174-8b3d-41a3-8277-525c849935f2',
          rule->>'id',note->>'actor_id','migrate-approved-cartoon-rule',md5(note::text),1,rule);
        UPDATE content_voice_profiles SET preferences_json=jsonb_set(
          jsonb_set(p,'{content_rules}',COALESCE(p->'content_rules','[]'::jsonb)||jsonb_build_array(rule)),
          '{editorial_notes}',COALESCE((SELECT jsonb_agg(value) FROM jsonb_array_elements(p->'editorial_notes')
            WHERE value->>'id'!='813836d8-be46-46aa-8ea0-d40e13e74861'),'[]'::jsonb)),
          version=version+1,updated_at=NOW()
          WHERE business_id='cb674174-8b3d-41a3-8277-525c849935f2';
      END IF;
    END $$""")


def downgrade():
    pass  # Keep user rules and audit history during application rollback.
