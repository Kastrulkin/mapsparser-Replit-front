"""Enforce manual-chat review identity without merging provider snapshots.

Provider review rows may contain historical snapshots with repeated source IDs.
Only the manual-chat upsert contract is constrained by this revision.
"""
from alembic import op
from sqlalchemy import text

revision = '20261102_manual_review_identity'
down_revision = '20261030_client_agent_scope'
branch_labels = None
depends_on = None

INDEX = 'uq_manual_chat_review_identity'


def upgrade():
    connection = op.get_bind()
    duplicates = connection.execute(text("""SELECT COUNT(*) FROM (
        SELECT 1 FROM externalbusinessreviews
        WHERE source='manual_chat' AND business_id IS NOT NULL AND external_review_id IS NOT NULL
        GROUP BY business_id,source,external_review_id HAVING COUNT(*)>1
    ) duplicate_groups""")).scalar()
    if duplicates:
        raise RuntimeError('Manual review identity duplicates exist; no rows were changed. Resolve explicitly before migrating.')
    # Never adopt or silently drop an invalid/differently defined existing index.
    existing = connection.execute(text("""SELECT i.indisvalid,i.indisunique,
        pg_get_indexdef(i.indexrelid) definition,pg_get_expr(i.indpred,i.indrelid) predicate,
        i.indrelid='externalbusinessreviews'::regclass correct_table,i.indnkeyatts FROM pg_index i
        WHERE i.indexrelid=to_regclass(:name)"""), {'name': INDEX}).mappings().first()
    if existing:
        definition = existing['definition']
        if (not existing['indisvalid'] or not existing['indisunique'] or not existing['correct_table']
                or existing['indnkeyatts'] != 3 or '(business_id, source, external_review_id)' not in definition
                or (existing['predicate'] or '').replace(' ', '') not in {"(source='manual_chat'::text)", "((source)::text='manual_chat'::text)"}):
            raise RuntimeError('Manual identity index exists with an unexpected or invalid definition; inspect before retrying.')
        return
    # Autocommit is required for CONCURRENTLY; existing provider writes continue.
    with op.get_context().autocommit_block():
        op.execute("SET lock_timeout='5s'")
        op.execute("SET statement_timeout='120s'")
        try:
            op.execute("""CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_manual_chat_review_identity
                ON externalbusinessreviews(business_id,source,external_review_id)
                WHERE source='manual_chat'""")
        finally:
            op.execute('RESET lock_timeout')
            op.execute('RESET statement_timeout')


def downgrade():
    with op.get_context().autocommit_block():
        op.execute('DROP INDEX CONCURRENTLY IF EXISTS uq_manual_chat_review_identity')
