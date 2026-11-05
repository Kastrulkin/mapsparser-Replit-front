"""Additive PostgreSQL schema contract for legacy ChatGPT routes.

Revision ID: 20260928_chatgpt_schema
Revises: 20260907_001
Create Date: 2026-09-28
"""

from alembic import op


revision = "20260928_chatgpt_schema"
down_revision = "20260907_001"
branch_labels = None
depends_on = None


def _add_columns(table_name, columns):
    for name, column_type in columns:
        op.execute(
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {name} {column_type}"
        )


def upgrade():
    # Supported legacy tables retain their identity columns. Never manufacture
    # IDs or mark a damaged table upgraded without a separate data-repair plan.
    op.execute(
        """
        DO $$
        DECLARE
            target_table TEXT;
        BEGIN
            FOREACH target_table IN ARRAY ARRAY[
                'bookings', 'chatgptusersessions', 'chatgptrequests'
            ] LOOP
                IF to_regclass(target_table) IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM pg_catalog.pg_attribute
                    WHERE attrelid = to_regclass(target_table)
                      AND attname = 'id' AND NOT attisdropped
                ) THEN
                    RAISE EXCEPTION
                        'Existing % table has no id; explicit repair is required',
                        target_table;
                END IF;
            END LOOP;
        END $$;
        """
    )
    # These are the fields selected by chatgpt_search_api and inserted by the
    # isolated schema fixture. Existing values stay untouched and nullable.
    _add_columns(
        "businesses",
        [
            ("city", "TEXT"),
            ("phone", "TEXT"),
            ("whatsapp_phone", "TEXT"),
            ("email", "TEXT"),
            ("website", "TEXT"),
            ("working_hours_json", "TEXT"),
            ("timezone", "TEXT DEFAULT 'UTC'"),
            ("latitude", "DOUBLE PRECISION"),
            ("longitude", "DOUBLE PRECISION"),
            ("network_id", "TEXT"),
            ("moderation_status", "TEXT DEFAULT 'pending'"),
            ("chatgpt_enabled", "BOOLEAN DEFAULT FALSE"),
            ("chatgpt_context", "TEXT"),
            ("subscription_status", "TEXT DEFAULT 'active'"),
            ("subscription_tier", "TEXT DEFAULT 'trial'"),
            ("subscription_ends_at", "TIMESTAMP"),
            ("telegram_username", "TEXT"),
            ("whatsapp_verified", "BOOLEAN DEFAULT FALSE"),
        ],
    )

    # Fresh rows use the public ChatGPT ISO timestamp contract. Existing
    # installations are only expanded: a legacy TIME column is never cast or
    # backfilled here and remains a separate writer/reader compatibility gate.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            client_name TEXT,
            client_phone TEXT,
            client_email TEXT,
            service_id TEXT,
            service_name TEXT,
            booking_date DATE,
            booking_time TIMESTAMP,
            booking_time_local TEXT,
            source TEXT DEFAULT 'chatgpt',
            status TEXT DEFAULT 'pending',
            notes TEXT,
            conversation_id TEXT,
            master_id TEXT,
            notification_sent INTEGER DEFAULT 0,
            notification_channel TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES userservices(id) ON DELETE SET NULL
        )
        """
    )
    _add_columns(
        "bookings",
        [
            ("business_id", "TEXT"),
            ("client_name", "TEXT"),
            ("client_phone", "TEXT"),
            ("client_email", "TEXT"),
            ("service_id", "TEXT"),
            ("service_name", "TEXT"),
            ("booking_date", "DATE"),
            ("booking_time", "TIMESTAMP"),
            ("booking_time_local", "TEXT"),
            ("source", "TEXT DEFAULT 'chatgpt'"),
            ("status", "TEXT DEFAULT 'pending'"),
            ("notes", "TEXT"),
            ("conversation_id", "TEXT"),
            ("master_id", "TEXT"),
            ("notification_sent", "INTEGER DEFAULT 0"),
            ("notification_channel", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ],
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chatgptusersessions (
            id TEXT PRIMARY KEY,
            chatgpt_user_id TEXT NOT NULL,
            business_id TEXT,
            session_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_interaction_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_interactions INTEGER DEFAULT 0,
            preferred_city TEXT,
            preferred_service_types TEXT,
            search_history TEXT,
            booking_history TEXT,
            preferences_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE SET NULL
        )
        """
    )
    _add_columns(
        "chatgptusersessions",
        [
            ("chatgpt_user_id", "TEXT"),
            ("business_id", "TEXT"),
            ("session_started_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("last_interaction_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("total_interactions", "INTEGER DEFAULT 0"),
            ("preferred_city", "TEXT"),
            ("preferred_service_types", "TEXT"),
            ("search_history", "TEXT"),
            ("booking_history", "TEXT"),
            ("preferences_json", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ],
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chatgptrequests (
            id TEXT PRIMARY KEY,
            chatgpt_user_id TEXT,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL,
            request_params TEXT,
            response_status INTEGER,
            response_time_ms INTEGER,
            error_message TEXT,
            business_id TEXT,
            service_id TEXT,
            booking_id TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE SET NULL
        )
        """
    )
    _add_columns(
        "chatgptrequests",
        [
            ("chatgpt_user_id", "TEXT"),
            ("endpoint", "TEXT"),
            ("method", "TEXT"),
            ("request_params", "TEXT"),
            ("response_status", "INTEGER"),
            ("response_time_ms", "INTEGER"),
            ("error_message", "TEXT"),
            ("business_id", "TEXT"),
            ("service_id", "TEXT"),
            ("booking_id", "TEXT"),
            ("ip_address", "TEXT"),
            ("user_agent", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ],
    )


def downgrade():
    # Retain additive compatibility data; prior application code ignores it.
    pass
