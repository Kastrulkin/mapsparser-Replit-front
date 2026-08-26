"""Production health check for lead journey projections."""
from __future__ import annotations

import json
import sys

from psycopg2.extras import RealDictCursor

from database_manager import DatabaseManager
from services.lead_journey_service import reconcile_map_actions


def collect_health(cursor):
    cursor.execute(
        """
        SELECT DISTINCT business_id
        FROM journey_actions
        WHERE flow_type = 'maps'
          AND action_type = 'compare_snapshot'
          AND status = 'waiting'
          AND business_id IS NOT NULL
        """
    )
    business_ids = [str(row["business_id"]) for row in cursor.fetchall() or []]
    reconcile_map_actions(cursor, business_ids=business_ids)
    cursor.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE action.status IN ('ready', 'in_progress', 'waiting', 'blocked')) AS active_actions,
          COUNT(*) FILTER (
            WHERE action.status IN ('ready', 'in_progress', 'waiting', 'blocked')
              AND action.business_id IS NULL
          ) AS orphan_actions,
          COUNT(*) FILTER (
            WHERE action.status IN ('ready', 'in_progress', 'waiting', 'blocked')
              AND action.updated_at < NOW() - INTERVAL '7 days'
          ) AS stale_actions,
          COUNT(*) FILTER (WHERE action.status = 'blocked') AS blocked_actions,
          COUNT(*) FILTER (
            WHERE action.journey_id IS NOT NULL AND journey.id IS NULL
          ) AS missing_journey_links,
          COUNT(*) FILTER (
            WHERE action.status IN ('ready', 'in_progress', 'waiting', 'blocked')
              AND (
                (action.entity_type = 'creator_collaboration' AND creator.id IS NULL)
                OR (action.entity_type = 'lead_workstream' AND workstream.id IS NULL)
                OR (action.flow_type = 'maps' AND business.id IS NULL)
              )
          ) AS missing_domain_entities
        FROM journey_actions action
        LEFT JOIN lead_journeys journey ON journey.id = action.journey_id
        LEFT JOIN creator_collaborations creator
          ON action.entity_type = 'creator_collaboration' AND CONCAT(creator.id) = action.entity_id
        LEFT JOIN lead_workstreams workstream
          ON action.entity_type = 'lead_workstream' AND CONCAT(workstream.id) = action.entity_id
        LEFT JOIN businesses business
          ON action.flow_type = 'maps' AND business.id = action.business_id
        """
    )
    health = dict(cursor.fetchone() or {})
    cursor.execute(
        """
        SELECT COUNT(*) AS notification_dedupe_failures
        FROM journey_action_notification_deliveries delivery
        JOIN journey_actions action ON action.id = delivery.action_id
        WHERE delivery.sent_at IS NULL
          AND delivery.created_at < NOW() - INTERVAL '1 hour'
          AND action.status IN ('ready', 'waiting', 'blocked')
          AND action.version = delivery.action_version
        """
    )
    health.update(dict(cursor.fetchone() or {}))
    return health


def main() -> int:
    database = DatabaseManager()
    try:
        cursor = database.conn.cursor(cursor_factory=RealDictCursor)
        health = collect_health(cursor)
        database.conn.commit()
    except Exception as exc:
        database.conn.rollback()
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    finally:
        database.close()

    critical_keys = (
        "orphan_actions",
        "stale_actions",
        "missing_journey_links",
        "missing_domain_entities",
        "notification_dedupe_failures",
    )
    critical = any(health.get(key) for key in critical_keys)
    warning = bool(health.get("blocked_actions"))
    status = "critical" if critical else "warning" if warning else "ok"
    print(json.dumps({"status": status, **health}, ensure_ascii=False, default=str))
    return 2 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
