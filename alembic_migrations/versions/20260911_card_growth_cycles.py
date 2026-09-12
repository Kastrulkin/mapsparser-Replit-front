"""Add managed card growth cycles and normalized provider snapshots."""
from alembic import op


revision = "20260911_card_growth_cycles"
down_revision = "20260911_operator_services"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS card_growth_cycles (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            goal TEXT NOT NULL,
            goal_status TEXT NOT NULL DEFAULT 'confirmed',
            status TEXT NOT NULL DEFAULT 'active',
            policy_version TEXT NOT NULL,
            baseline_start DATE NOT NULL,
            baseline_end DATE NOT NULL,
            baseline_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            focus_action_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            measurement_days_json JSONB NOT NULL DEFAULT '[14, 28]'::jsonb,
            measurement_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            decision TEXT,
            decision_reason TEXT,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            action_completed_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_card_growth_cycle_goal CHECK (
                goal IN ('inquiries', 'bookings', 'orders', 'directions', 'website_visits')
            ),
            CONSTRAINT ck_card_growth_cycle_goal_status CHECK (
                goal_status IN ('recommended', 'confirmed')
            ),
            CONSTRAINT ck_card_growth_cycle_status CHECK (
                status IN ('active', 'waiting_for_measurement', 'completed', 'cancelled')
            ),
            CONSTRAINT ck_card_growth_cycle_decision CHECK (
                decision IS NULL OR decision IN ('continue', 'adjust', 'replace', 'insufficient_data')
            )
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_card_growth_cycle_active "
        "ON card_growth_cycles(business_id) WHERE status IN ('active', 'waiting_for_measurement')"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_card_growth_cycles_business "
        "ON card_growth_cycles(business_id, created_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS card_state_snapshots (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            growth_cycle_id UUID REFERENCES card_growth_cycles(id) ON DELETE SET NULL,
            provider TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            snapshot_kind TEXT NOT NULL DEFAULT 'current',
            source_state TEXT NOT NULL,
            source_observed_at TIMESTAMPTZ,
            facts_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            benchmark_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_card_state_provider CHECK (provider IN ('google', 'yandex', '2gis')),
            CONSTRAINT ck_card_state_kind CHECK (snapshot_kind IN ('baseline', 'current', 'checkpoint_14d', 'checkpoint_28d', 'checkpoint_60d')),
            CONSTRAINT ck_card_state_source CHECK (source_state IN ('observed', 'unknown', 'blocked'))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_card_state_snapshot_latest "
        "ON card_state_snapshots(business_id, provider, created_at DESC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_card_state_cycle_kind_provider "
        "ON card_state_snapshots(growth_cycle_id, provider, snapshot_kind) WHERE growth_cycle_id IS NOT NULL"
    )
    op.execute("ALTER TABLE journey_actions ADD COLUMN IF NOT EXISTS growth_cycle_id UUID REFERENCES card_growth_cycles(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_journey_actions_growth_cycle ON journey_actions(growth_cycle_id, status, due_at)")
    for source_table in ("businessmaplinks", "mapparseresults"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{source_table}') IS NOT NULL THEN
                    INSERT INTO card_growth_cycles (
                        id, business_id, goal, goal_status, status, policy_version,
                        baseline_start, baseline_end, baseline_json
                    )
                    SELECT gen_random_uuid(), b.id,
                           CASE
                               WHEN LOWER(COALESCE(b.business_type, '')) ~ '(салон|красот|школ|образован|мед|клиник|фитнес|spa|спа)' THEN 'bookings'
                               WHEN LOWER(COALESCE(b.business_type, '')) ~ '(ресторан|кафе|достав|магазин|товар)' THEN 'orders'
                               WHEN LOWER(COALESCE(b.business_type, '')) ~ '(парк|музей|каток|достопримеч)' THEN 'directions'
                               ELSE 'inquiries'
                           END,
                           'recommended', 'active', '2026-09-11.1',
                           CURRENT_DATE - 27, CURRENT_DATE, '{{}}'::jsonb
                    FROM businesses b
                    WHERE COALESCE(b.is_active, TRUE)=TRUE
                      AND EXISTS (SELECT 1 FROM {source_table} source WHERE source.business_id=b.id)
                    ON CONFLICT DO NOTHING;
                END IF;
            END $$
            """
        )
    op.execute(
        """
        UPDATE journey_actions action
        SET growth_cycle_id = cycle.id
        FROM card_growth_cycles cycle
        WHERE action.business_id = cycle.business_id
          AND action.flow_type = 'maps'
          AND action.status IN ('ready', 'in_progress', 'waiting', 'blocked')
          AND cycle.status IN ('active', 'waiting_for_measurement')
          AND action.growth_cycle_id IS NULL
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_journey_actions_growth_cycle")
    op.execute("ALTER TABLE journey_actions DROP COLUMN IF EXISTS growth_cycle_id")
    op.execute("DROP TABLE IF EXISTS card_state_snapshots")
    op.execute("DROP TABLE IF EXISTS card_growth_cycles")
