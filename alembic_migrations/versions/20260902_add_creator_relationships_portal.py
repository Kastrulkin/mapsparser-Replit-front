"""add creator relationships and creator portal

Revision ID: 20260902_001
Revises: 20260830_003
Create Date: 2026-09-02
"""

from alembic import op


revision = "20260902_001"
down_revision = "20260830_003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_relationships (
            creator_profile_id UUID PRIMARY KEY REFERENCES creator_profiles(id) ON DELETE CASCADE,
            stage TEXT NOT NULL DEFAULT 'discovered',
            primary_channel TEXT,
            contact_value TEXT,
            last_contacted_at TIMESTAMPTZ,
            last_replied_at TIMESTAMPTZ,
            paused_until TIMESTAMPTZ,
            status_reason TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_relationship_stage CHECK (
                stage IN ('discovered', 'contact_ready', 'contacted', 'replied',
                          'interested', 'needs_details', 'declined', 'paid_only',
                          'invalid_contact', 'paused')
            )
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_relationship_stage ON creator_relationships(stage, updated_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_contact_events (
            id UUID PRIMARY KEY,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            campaign_id UUID REFERENCES creator_campaigns(id) ON DELETE SET NULL,
            collaboration_id UUID REFERENCES creator_collaborations(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,
            channel TEXT NOT NULL,
            contact_value TEXT,
            provider_message_id TEXT,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            classification TEXT,
            body_text TEXT,
            source TEXT NOT NULL DEFAULT 'localos',
            actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_contact_events_profile ON creator_contact_events(creator_profile_id, occurred_at DESC)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_contact_provider_event
        ON creator_contact_events(channel, provider_message_id, event_type)
        WHERE provider_message_id IS NOT NULL AND provider_message_id <> ''
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_creator_contact_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'creator_contact_events is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_creator_contact_events_append_only ON creator_contact_events")
    op.execute(
        """
        CREATE TRIGGER trg_creator_contact_events_append_only
        BEFORE UPDATE OR DELETE ON creator_contact_events
        FOR EACH ROW EXECUTE FUNCTION prevent_creator_contact_event_mutation()
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_accounts (
            id UUID PRIMARY KEY,
            creator_profile_id UUID NOT NULL UNIQUE REFERENCES creator_profiles(id) ON DELETE CASCADE,
            email TEXT,
            password_hash TEXT,
            email_verified_at TIMESTAMPTZ,
            telegram_id TEXT UNIQUE,
            telegram_username TEXT,
            preferred_auth TEXT,
            status TEXT NOT NULL DEFAULT 'invited',
            notification_preferences_json JSONB NOT NULL DEFAULT '{"telegram": true, "email": true}'::jsonb,
            last_login_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_account_status CHECK (status IN ('invited', 'active', 'suspended')),
            CONSTRAINT ck_creator_account_auth CHECK (preferred_auth IS NULL OR preferred_auth IN ('email', 'telegram'))
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_account_email ON creator_accounts(LOWER(email)) WHERE email IS NOT NULL")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_invites (
            id UUID PRIMARY KEY,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            purpose TEXT NOT NULL DEFAULT 'claim',
            email TEXT,
            expires_at TIMESTAMPTZ NOT NULL,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            claimed_at TIMESTAMPTZ,
            claimed_account_id UUID REFERENCES creator_accounts(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_invite_purpose CHECK (purpose IN ('claim', 'email_verify', 'password_reset', 'telegram_login'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_invite_profile ON creator_invites(creator_profile_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_sessions (
            id UUID PRIMARY KEY,
            creator_account_id UUID NOT NULL REFERENCES creator_accounts(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_session_account ON creator_sessions(creator_account_id, expires_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_profile_change_events (
            id UUID PRIMARY KEY,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            changed_fields_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            source TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_profile_actor CHECK (actor_type IN ('creator', 'localos', 'system'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_profile_changes ON creator_profile_change_events(creator_profile_id, created_at DESC)")

    op.execute(
        """
        ALTER TABLE creator_collaborations
            ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'draft',
            ADD COLUMN IF NOT EXISTS reviewed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS creator_notified_at TIMESTAMPTZ
        """
    )
    op.execute("ALTER TABLE creator_collaborations DROP CONSTRAINT IF EXISTS ck_creator_collaboration_review")
    op.execute(
        """
        ALTER TABLE creator_collaborations ADD CONSTRAINT ck_creator_collaboration_review
        CHECK (review_status IN ('draft', 'needs_review', 'approved', 'rejected'))
        """
    )
    op.execute(
        """
        UPDATE creator_collaborations
        SET review_status = 'approved', reviewed_at = COALESCE(updated_at, NOW())
        WHERE approved_terms_version = terms_version
           OR status IN ('invited', 'replied', 'negotiating', 'agreed', 'awaiting_content',
                         'published', 'measuring', 'completed', 'declined')
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_offer_messages (
            id UUID PRIMARY KEY,
            collaboration_id UUID NOT NULL REFERENCES creator_collaborations(id) ON DELETE CASCADE,
            sender_type TEXT NOT NULL,
            sender_id TEXT,
            body_text TEXT NOT NULL,
            visible_to_business BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_offer_sender CHECK (sender_type IN ('creator', 'localos', 'system'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_offer_messages ON creator_offer_messages(collaboration_id, created_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_notification_outbox (
            id UUID PRIMARY KEY,
            creator_account_id UUID NOT NULL REFERENCES creator_accounts(id) ON DELETE CASCADE,
            collaboration_id UUID REFERENCES creator_collaborations(id) ON DELETE CASCADE,
            channel TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            dedupe_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            provider_message_id TEXT,
            last_error TEXT,
            sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_notification_channel CHECK (channel IN ('telegram', 'email')),
            CONSTRAINT ck_creator_notification_status CHECK (status IN ('pending', 'sending', 'sent', 'failed', 'cancelled'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_notification_due ON creator_notification_outbox(status, next_attempt_at)")

    op.execute(
        """
        INSERT INTO creator_relationships (
            creator_profile_id, stage, primary_channel, contact_value,
            last_contacted_at, last_replied_at, status_reason, metadata_json
        )
        SELECT
            profile.id,
            CASE
                WHEN response.outcome = 'interested' THEN 'interested'
                WHEN response.outcome = 'question' THEN 'needs_details'
                WHEN response.outcome = 'paid_only' THEN 'paid_only'
                WHEN response.outcome = 'not_interested' THEN 'declined'
                WHEN collaboration.agreed_terms_json->'delivery_failure' IS NOT NULL THEN 'invalid_contact'
                WHEN candidate.status IN ('replied', 'negotiating', 'agreed') THEN 'replied'
                WHEN candidate.status IN ('invited', 'no_reply') OR outreach.recipient IS NOT NULL THEN 'contacted'
                WHEN commercial.preferred_contact IS NOT NULL THEN 'contact_ready'
                ELSE 'discovered'
            END,
            COALESCE(outreach.channel, CASE WHEN commercial.preferred_contact LIKE '%@%' THEN 'email' END),
            COALESCE(response.contact_email, outreach.recipient, commercial.preferred_contact),
            CASE WHEN outreach.sent_at ~ '^\\d{4}-' THEN outreach.sent_at::timestamptz END,
            CASE WHEN response.received_at ~ '^\\d{4}-' THEN response.received_at::timestamptz END,
            COALESCE(response.summary, candidate.selection_reason),
            jsonb_build_object('backfilled_from', 'creator_campaigns', 'backfilled_at', NOW())
        FROM creator_profiles profile
        LEFT JOIN LATERAL (
            SELECT item.* FROM creator_campaign_candidates item
            WHERE item.creator_profile_id = profile.id ORDER BY item.updated_at DESC LIMIT 1
        ) candidate ON TRUE
        LEFT JOIN creator_collaborations collaboration ON collaboration.campaign_candidate_id = candidate.id
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        LEFT JOIN LATERAL jsonb_to_record(COALESCE(collaboration.agreed_terms_json->'outreach', '{}'::jsonb))
            AS outreach(recipient TEXT, channel TEXT, sent_at TEXT) ON TRUE
        LEFT JOIN LATERAL jsonb_to_record(COALESCE(collaboration.agreed_terms_json->'response', '{}'::jsonb))
            AS response(outcome TEXT, contact_email TEXT, received_at TEXT, summary TEXT) ON TRUE
        ON CONFLICT (creator_profile_id) DO NOTHING
        """
    )


def downgrade():
    # The portal contains creator communication history. Keep it on rollback.
    pass
