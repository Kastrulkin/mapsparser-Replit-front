"""Add privacy-first website tracking.

Revision ID: 20260816_001
Revises: 20260814_003
"""

from alembic import op


revision = "20260816_001"
down_revision = "20260814_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS business_web_trackers (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            public_tracker_id TEXT NOT NULL UNIQUE,
            domain TEXT,
            allowed_domains TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            tracking_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            first_event_at TIMESTAMPTZ,
            last_event_at TIMESTAMPTZ,
            last_tracker_version TEXT,
            last_schema_version SMALLINT,
            last_error_code TEXT,
            last_error_at TIMESTAMPTZ,
            raw_retention_days SMALLINT NOT NULL DEFAULT 180,
            aggregate_retention_days SMALLINT NOT NULL DEFAULT 730,
            CONSTRAINT uq_web_tracker_id_business UNIQUE (id, business_id),
            CONSTRAINT chk_web_tracker_retention CHECK (raw_retention_days BETWEEN 90 AND 365),
            CONSTRAINT chk_web_tracker_aggregate_retention CHECK (aggregate_retention_days BETWEEN 365 AND 1825),
            CONSTRAINT chk_web_tracker_domain CHECK (domain IS NULL OR length(domain) <= 253)
        );

        CREATE INDEX IF NOT EXISTS idx_web_trackers_business
            ON business_web_trackers (business_id, created_at);

        CREATE TABLE IF NOT EXISTS web_visitors (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            anonymous_id TEXT NOT NULL,
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_web_visitor_id_business UNIQUE (id, business_id),
            CONSTRAINT uq_web_visitor_business_anonymous UNIQUE (business_id, anonymous_id)
        );

        CREATE INDEX IF NOT EXISTS idx_web_visitors_business_seen
            ON web_visitors (business_id, last_seen_at DESC);

        CREATE TABLE IF NOT EXISTS web_sessions (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            visitor_id UUID NOT NULL,
            session_key TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            ended_at TIMESTAMPTZ,
            landing_page TEXT NOT NULL DEFAULT '/',
            landing_hostname TEXT NOT NULL DEFAULT '',
            referrer TEXT NOT NULL DEFAULT '',
            utm_source TEXT NOT NULL DEFAULT '',
            utm_medium TEXT NOT NULL DEFAULT '',
            utm_campaign TEXT NOT NULL DEFAULT '',
            device_type TEXT NOT NULL DEFAULT 'unknown',
            source_type TEXT NOT NULL DEFAULT 'direct',
            source_label TEXT NOT NULL DEFAULT 'direct',
            source_domain TEXT NOT NULL DEFAULT '',
            CONSTRAINT uq_web_session_id_business UNIQUE (id, business_id),
            CONSTRAINT fk_web_session_visitor_business FOREIGN KEY (visitor_id, business_id)
                REFERENCES web_visitors(id, business_id) ON DELETE CASCADE,
            CONSTRAINT chk_web_session_source_type CHECK (
                source_type IN ('utm', 'search', 'social', 'maps', 'referral', 'direct', 'unknown')
            ),
            CONSTRAINT uq_web_session_business_key UNIQUE (business_id, session_key)
        );

        CREATE INDEX IF NOT EXISTS idx_web_sessions_business_started
            ON web_sessions (business_id, started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_web_sessions_visitor_started
            ON web_sessions (visitor_id, started_at DESC);

        CREATE TABLE IF NOT EXISTS web_events (
            id BIGSERIAL PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            tracker_id UUID NOT NULL,
            session_id UUID NOT NULL,
            event_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            tracker_version TEXT NOT NULL DEFAULT 'legacy',
            schema_version SMALLINT NOT NULL DEFAULT 1,
            page_hostname TEXT NOT NULL DEFAULT '',
            page_path TEXT NOT NULL DEFAULT '/',
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            action_type TEXT,
            action_provider TEXT,
            action_domain TEXT,
            occurred_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_web_event_tracker_business FOREIGN KEY (tracker_id, business_id)
                REFERENCES business_web_trackers(id, business_id) ON DELETE CASCADE,
            CONSTRAINT fk_web_event_session_business FOREIGN KEY (session_id, business_id)
                REFERENCES web_sessions(id, business_id) ON DELETE CASCADE,
            CONSTRAINT chk_web_event_action_type CHECK (
                action_type IS NULL OR action_type IN (
                    'form', 'phone', 'email', 'whatsapp', 'telegram', 'booking', 'outbound'
                )
            ),
            CONSTRAINT chk_web_event_type CHECK (
                event_type IN ('session_start', 'page_view', 'scroll_depth', 'click',
                               'outbound_click', 'form_start', 'form_submit',
                               'heartbeat', 'page_leave')
            )
        );

        CREATE INDEX IF NOT EXISTS idx_web_events_business_time
            ON web_events (business_id, occurred_at DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_web_events_tracker_event
            ON web_events (tracker_id, event_id);
        CREATE INDEX IF NOT EXISTS idx_web_events_business_type_time
            ON web_events (business_id, event_type, occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_web_events_session_time
            ON web_events (session_id, occurred_at, id);
        CREATE INDEX IF NOT EXISTS idx_web_events_tracker_time
            ON web_events (tracker_id, occurred_at, id);
        CREATE INDEX IF NOT EXISTS idx_web_events_business_page_time
            ON web_events (business_id, page_path, occurred_at DESC)
            WHERE event_type = 'page_view';
        CREATE INDEX IF NOT EXISTS idx_web_events_business_action_time
            ON web_events (business_id, action_type, occurred_at DESC)
            WHERE action_type IS NOT NULL;

        CREATE TABLE IF NOT EXISTS web_daily_metrics (
            id BIGSERIAL PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            tracker_id UUID NOT NULL,
            metric_date DATE NOT NULL,
            dimension_type TEXT NOT NULL,
            dimension_key TEXT NOT NULL DEFAULT '',
            visitors BIGINT NOT NULL DEFAULT 0,
            sessions BIGINT NOT NULL DEFAULT 0,
            events BIGINT NOT NULL DEFAULT 0,
            page_views BIGINT NOT NULL DEFAULT 0,
            target_actions BIGINT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_web_daily_tracker_business FOREIGN KEY (tracker_id, business_id)
                REFERENCES business_web_trackers(id, business_id) ON DELETE CASCADE,
            CONSTRAINT chk_web_daily_dimension CHECK (dimension_type IN ('total', 'page', 'source', 'event', 'action')),
            CONSTRAINT uq_web_daily_metric UNIQUE (
                business_id, tracker_id, metric_date, dimension_type, dimension_key
            )
        );

        CREATE INDEX IF NOT EXISTS idx_web_daily_metrics_business_date
            ON web_daily_metrics (business_id, metric_date DESC, dimension_type);

        CREATE TABLE IF NOT EXISTS web_tracking_deletion_audits (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL,
            requested_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            trackers BIGINT NOT NULL DEFAULT 0,
            visitors BIGINT NOT NULL DEFAULT 0,
            sessions BIGINT NOT NULL DEFAULT 0,
            events BIGINT NOT NULL DEFAULT 0,
            metrics BIGINT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_web_deletion_mode CHECK (mode IN ('dry_run', 'execute')),
            CONSTRAINT chk_web_deletion_status CHECK (status IN ('reviewed', 'completed', 'failed'))
        );

        CREATE INDEX IF NOT EXISTS idx_web_deletion_audits_business_created
            ON web_tracking_deletion_audits (business_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS web_tracking_maintenance_runs (
            id UUID PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finished_at TIMESTAMPTZ,
            dry_run BOOLEAN NOT NULL,
            status TEXT NOT NULL,
            aggregate_date DATE,
            metrics_rows BIGINT NOT NULL DEFAULT 0,
            raw_events BIGINT NOT NULL DEFAULT 0,
            aggregate_events BIGINT NOT NULL DEFAULT 0,
            eligible_events BIGINT NOT NULL DEFAULT 0,
            eligible_metrics BIGINT NOT NULL DEFAULT 0,
            deleted_events BIGINT NOT NULL DEFAULT 0,
            deleted_metrics BIGINT NOT NULL DEFAULT 0,
            deleted_sessions BIGINT NOT NULL DEFAULT 0,
            deleted_visitors BIGINT NOT NULL DEFAULT 0,
            error_code TEXT,
            CONSTRAINT chk_web_maintenance_status CHECK (status IN ('running', 'completed', 'failed'))
        );

        CREATE INDEX IF NOT EXISTS idx_web_maintenance_started
            ON web_tracking_maintenance_runs (started_at DESC);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS web_tracking_maintenance_runs;
        DROP TABLE IF EXISTS web_tracking_deletion_audits;
        DROP TABLE IF EXISTS web_daily_metrics;
        DROP TABLE IF EXISTS web_events;
        DROP TABLE IF EXISTS web_sessions;
        DROP TABLE IF EXISTS web_visitors;
        DROP TABLE IF EXISTS business_web_trackers;
        """
    )
