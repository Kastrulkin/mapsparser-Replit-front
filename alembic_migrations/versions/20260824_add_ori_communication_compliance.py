"""Add ORI communication evidence, outbox, retention and audit entities.

Revision ID: 20260824_001
Revises: 20260822_001
"""

from alembic import op


revision = "20260824_001"
down_revision = "20260822_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_files (
          id UUID PRIMARY KEY,
          room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
          message_id UUID REFERENCES sales_room_messages(id) ON DELETE SET NULL,
          original_name TEXT NOT NULL,
          mime_type TEXT,
          size_bytes INTEGER NOT NULL DEFAULT 0,
          storage_path TEXT NOT NULL,
          public_url TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_sales_room_files_room_created
          ON sales_room_files(room_id, created_at DESC);
        """
    )
    op.execute(
        """
        ALTER TABLE sales_room_participants
          ADD COLUMN IF NOT EXISTS access_token_hash TEXT,
          ADD COLUMN IF NOT EXISTS access_token_expires_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS access_token_revoked_at TIMESTAMPTZ;
        UPDATE sales_room_participants
           SET access_token_hash = encode(digest(access_token, 'sha256'), 'hex'),
               access_token_expires_at = COALESCE(updated_at, created_at, NOW()) + INTERVAL '30 days'
         WHERE access_token_hash IS NULL AND access_token IS NOT NULL;
        ALTER TABLE sales_room_participants ALTER COLUMN access_token DROP NOT NULL;
        UPDATE sales_room_participants SET access_token = NULL WHERE access_token IS NOT NULL;
        DROP INDEX IF EXISTS idx_sales_room_participants_access_token;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_room_participants_access_token_hash
          ON sales_room_participants(access_token_hash) WHERE access_token_hash IS NOT NULL;

        ALTER TABLE sales_room_messages
          ADD COLUMN IF NOT EXISTS participant_id UUID REFERENCES sales_room_participants(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS recipient_type TEXT,
          ADD COLUMN IF NOT EXISTS recipient_id TEXT,
          ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS content_sha256 TEXT,
          ADD COLUMN IF NOT EXISTS archive_status TEXT NOT NULL DEFAULT 'pending',
          ADD COLUMN IF NOT EXISTS content_retention_until TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS metadata_retention_until TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_room_message_idempotency
          ON sales_room_messages(room_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

        ALTER TABLE sales_room_files
          ADD COLUMN IF NOT EXISTS participant_id UUID REFERENCES sales_room_participants(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS sha256 TEXT,
          ADD COLUMN IF NOT EXISTS quarantine_status TEXT NOT NULL DEFAULT 'legacy_unscanned',
          ADD COLUMN IF NOT EXISTS archive_status TEXT NOT NULL DEFAULT 'pending',
          ADD COLUMN IF NOT EXISTS content_retention_until TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS metadata_retention_until TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_room_file_idempotency
          ON sales_room_files(room_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

        CREATE TABLE IF NOT EXISTS communication_identities (
          id UUID PRIMARY KEY,
          room_id UUID,
          identity_type TEXT NOT NULL,
          external_ref TEXT,
          display_name TEXT,
          contact TEXT,
          verified_at TIMESTAMPTZ,
          valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          valid_until TIMESTAMPTZ,
          snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_communication_identities_room ON communication_identities(room_id, created_at);

        CREATE TABLE IF NOT EXISTS communication_events (
          id UUID PRIMARY KEY,
          message_id UUID,
          room_id UUID NOT NULL,
          event_type TEXT NOT NULL,
          sender_identity_id UUID REFERENCES communication_identities(id) ON DELETE RESTRICT,
          recipient_identity_id UUID REFERENCES communication_identities(id) ON DELETE RESTRICT,
          sender_ref TEXT,
          recipient_ref TEXT,
          client_ip INET,
          client_port INTEGER,
          service_ip INET,
          service_port INTEGER,
          channel TEXT NOT NULL,
          protocol TEXT,
          user_agent TEXT,
          provider_event_id TEXT,
          occurred_at TIMESTAMPTZ NOT NULL,
          accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          content_sha256 TEXT,
          completeness_status TEXT NOT NULL DEFAULT 'complete',
          missing_reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
          metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          content_retention_until TIMESTAMPTZ NOT NULL,
          metadata_retention_until TIMESTAMPTZ NOT NULL,
          event_sha256 TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT chk_communication_event_type CHECK (event_type IN ('accepted','processed','delivered','read')),
          CONSTRAINT chk_communication_ports CHECK (
            (client_port IS NULL OR client_port BETWEEN 1 AND 65535) AND
            (service_port IS NULL OR service_port BETWEEN 1 AND 65535)
          )
        );
        CREATE INDEX IF NOT EXISTS idx_communication_events_room_time ON communication_events(room_id, occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_communication_events_message ON communication_events(message_id, event_type);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_communication_event_delivery_read
          ON communication_events(message_id, event_type, recipient_ref)
          WHERE message_id IS NOT NULL AND event_type IN ('delivered','read');

        CREATE TABLE IF NOT EXISTS communication_content_refs (
          id UUID PRIMARY KEY,
          event_id UUID NOT NULL REFERENCES communication_events(id) ON DELETE RESTRICT,
          message_id UUID,
          source_file_id UUID,
          content_kind TEXT NOT NULL,
          archive_backend TEXT NOT NULL DEFAULT 'pending',
          archive_key TEXT,
          mime_type TEXT,
          size_bytes BIGINT NOT NULL DEFAULT 0,
          sha256 TEXT NOT NULL,
          archive_status TEXT NOT NULL DEFAULT 'pending',
          retained_until TIMESTAMPTZ NOT NULL,
          verified_at TIMESTAMPTZ,
          deleted_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_communication_content_refs_event ON communication_content_refs(event_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_communication_content_ref_message_kind
          ON communication_content_refs(message_id, content_kind, sha256) WHERE message_id IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_communication_content_ref_source_file
          ON communication_content_refs(source_file_id) WHERE source_file_id IS NOT NULL;

        CREATE TABLE IF NOT EXISTS communication_outbox (
          id UUID PRIMARY KEY,
          event_id UUID NOT NULL REFERENCES communication_events(id) ON DELETE RESTRICT,
          object_kind TEXT NOT NULL,
          payload_json JSONB NOT NULL,
          payload_sha256 TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0,
          next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          locked_at TIMESTAMPTZ,
          archived_at TIMESTAMPTZ,
          last_error TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE(event_id, object_kind)
        );
        CREATE INDEX IF NOT EXISTS idx_communication_outbox_pending
          ON communication_outbox(status, next_attempt_at) WHERE status IN ('pending','retry');

        CREATE TABLE IF NOT EXISTS communication_access_audit (
          id UUID PRIMARY KEY,
          event_id UUID,
          room_id UUID,
          actor_type TEXT NOT NULL,
          actor_ref TEXT NOT NULL,
          action TEXT NOT NULL,
          reason TEXT,
          request_id TEXT,
          client_ip INET,
          occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          audit_sha256 TEXT NOT NULL,
          metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        CREATE INDEX IF NOT EXISTS idx_communication_access_audit_room_time
          ON communication_access_audit(room_id, occurred_at DESC);

        CREATE TABLE IF NOT EXISTS communication_legal_holds (
          id UUID PRIMARY KEY,
          room_id UUID,
          identity_id UUID REFERENCES communication_identities(id) ON DELETE RESTRICT,
          reason TEXT NOT NULL,
          legal_basis TEXT NOT NULL,
          active BOOLEAN NOT NULL DEFAULT TRUE,
          applied_by TEXT NOT NULL,
          applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          released_by TEXT,
          released_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_communication_legal_holds_active
          ON communication_legal_holds(room_id, active) WHERE active;

        CREATE TABLE IF NOT EXISTS communication_exports (
          id UUID PRIMARY KEY,
          requested_by TEXT NOT NULL,
          approved_by TEXT NOT NULL,
          reason TEXT NOT NULL,
          filters_json JSONB NOT NULL,
          manifest_sha256 TEXT,
          object_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'prepared',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          completed_at TIMESTAMPTZ
        );
        """
    )
    op.execute(
        """
        UPDATE sales_room_messages
           SET accepted_at = COALESCE(accepted_at, created_at),
               processed_at = COALESCE(processed_at, created_at),
               content_sha256 = COALESCE(content_sha256, encode(digest(COALESCE(body_text, ''), 'sha256'), 'hex')),
               archive_status = 'legacy_partial',
               content_retention_until = COALESCE(content_retention_until, created_at + INTERVAL '6 months'),
               metadata_retention_until = COALESCE(metadata_retention_until, created_at + INTERVAL '3 years');
        UPDATE sales_room_files
           SET archive_status = 'legacy_partial',
               content_retention_until = COALESCE(content_retention_until, created_at + INTERVAL '6 months'),
               metadata_retention_until = COALESCE(metadata_retention_until, created_at + INTERVAL '3 years');

        INSERT INTO communication_events (
          id, message_id, room_id, event_type, sender_ref, recipient_ref, channel,
          protocol, occurred_at, content_sha256, completeness_status, missing_reason_codes,
          content_retention_until, metadata_retention_until, event_sha256
        )
        SELECT gen_random_uuid(), m.id, m.room_id, 'accepted',
               COALESCE(NULLIF(m.author_contact, ''), NULLIF(m.author_name, ''), m.author_type),
               COALESCE(m.recipient_id, 'unknown'), COALESCE(NULLIF(m.source_channel, ''), 'digital_room'),
               'legacy', COALESCE(m.occurred_at, m.created_at), m.content_sha256, 'legacy_partial',
               '["legacy_missing_network_data","legacy_recipient_may_be_unknown"]'::jsonb,
               m.content_retention_until, m.metadata_retention_until,
               encode(digest(m.id::text || ':accepted:legacy', 'sha256'), 'hex')
          FROM sales_room_messages m
         WHERE NOT EXISTS (
           SELECT 1 FROM communication_events ce WHERE ce.message_id = m.id AND ce.event_type = 'accepted'
         );

        INSERT INTO communication_content_refs (
          id, event_id, message_id, content_kind, archive_backend, mime_type, size_bytes,
          sha256, archive_status, retained_until
        )
        SELECT gen_random_uuid(), ce.id, m.id, 'text', 'operational_db', 'text/plain',
               octet_length(COALESCE(m.body_text, '')), m.content_sha256, 'legacy_partial', m.content_retention_until
          FROM sales_room_messages m
          JOIN communication_events ce ON ce.message_id = m.id AND ce.event_type = 'accepted'
         WHERE COALESCE(m.body_text, '') <> ''
           AND NOT EXISTS (SELECT 1 FROM communication_content_refs cr WHERE cr.message_id = m.id AND cr.content_kind = 'text');

        INSERT INTO communication_outbox (id, event_id, object_kind, payload_json, payload_sha256, status)
        SELECT gen_random_uuid(), ce.id, 'metadata',
               jsonb_build_object('event_id', ce.id, 'message_id', ce.message_id, 'room_id', ce.room_id,
                                  'legacy_partial', TRUE),
               encode(digest(ce.id::text || 'metadata', 'sha256'), 'hex'), 'pending'
          FROM communication_events ce
         WHERE NOT EXISTS (SELECT 1 FROM communication_outbox co WHERE co.event_id = ce.id AND co.object_kind = 'metadata');
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_communication_evidence_mutation() RETURNS trigger AS $$
        BEGIN
          IF current_setting('localos.compliance_retention_mode', true) = 'on' THEN
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
          END IF;
          RAISE EXCEPTION 'communication evidence is append-only';
        END;
        $$ LANGUAGE plpgsql;
        DROP TRIGGER IF EXISTS trg_communication_events_immutable ON communication_events;
        CREATE TRIGGER trg_communication_events_immutable BEFORE UPDATE OR DELETE ON communication_events
          FOR EACH ROW EXECUTE FUNCTION prevent_communication_evidence_mutation();
        DROP TRIGGER IF EXISTS trg_communication_access_audit_immutable ON communication_access_audit;
        CREATE TRIGGER trg_communication_access_audit_immutable BEFORE UPDATE OR DELETE ON communication_access_audit
          FOR EACH ROW EXECUTE FUNCTION prevent_communication_evidence_mutation();
        """
    )


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_communication_access_audit_immutable ON communication_access_audit")
    op.execute("DROP TRIGGER IF EXISTS trg_communication_events_immutable ON communication_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_communication_evidence_mutation()")
    for table in (
        "communication_exports", "communication_legal_holds", "communication_access_audit",
        "communication_outbox", "communication_content_refs", "communication_events", "communication_identities",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("ALTER TABLE sales_room_files DROP COLUMN IF EXISTS idempotency_key, DROP COLUMN IF EXISTS metadata_retention_until, DROP COLUMN IF EXISTS content_retention_until, DROP COLUMN IF EXISTS archive_status, DROP COLUMN IF EXISTS quarantine_status, DROP COLUMN IF EXISTS sha256, DROP COLUMN IF EXISTS participant_id")
    op.execute("ALTER TABLE sales_room_messages DROP COLUMN IF EXISTS idempotency_key, DROP COLUMN IF EXISTS metadata_retention_until, DROP COLUMN IF EXISTS content_retention_until, DROP COLUMN IF EXISTS archive_status, DROP COLUMN IF EXISTS content_sha256, DROP COLUMN IF EXISTS delivered_at, DROP COLUMN IF EXISTS processed_at, DROP COLUMN IF EXISTS accepted_at, DROP COLUMN IF EXISTS recipient_id, DROP COLUMN IF EXISTS recipient_type, DROP COLUMN IF EXISTS participant_id")
    op.execute("ALTER TABLE sales_room_participants DROP COLUMN IF EXISTS access_token_revoked_at, DROP COLUMN IF EXISTS access_token_expires_at, DROP COLUMN IF EXISTS access_token_hash")
