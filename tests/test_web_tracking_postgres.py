from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from services.web_tracking_maintenance import aggregate_web_tracking_day
from services.web_tracking_service import (
    WebTrackingConflictError,
    delete_business_web_analytics,
    get_business_web_metrics,
    get_web_tracking_health,
    ingest_events,
    validate_batch,
)


pytestmark = pytest.mark.integration


def _dsn(postgres_container):
    return postgres_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)


def _run_migration(database_url: str, action: str, revision: str | None = None):
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["FLASK_APP"] = "src.main:app"
    environment["PYTHONPATH"] = os.pathsep.join([str(project_root / "src"), str(project_root)])
    command = [sys.executable, "-m", "flask", "db", action]
    if revision:
        command.append(revision)
    subprocess.run(command, cwd=project_root, env=environment, check=True, timeout=60, capture_output=True, text=True)


def test_postgres_migration_idempotent_ingestion_and_tenant_isolation(postgres_container, run_migrations):
    database_url = _dsn(postgres_container)
    _run_migration(database_url, "upgrade")
    _run_migration(database_url, "downgrade", "20260814_003")
    _run_migration(database_url, "upgrade", "20260816_001")
    connection = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    business_one = f"web-business-{uuid.uuid4()}"
    business_two = f"web-business-{uuid.uuid4()}"
    owner_one = f"web-owner-{uuid.uuid4()}"
    owner_two = f"web-owner-{uuid.uuid4()}"
    tracker_one = str(uuid.uuid4())
    tracker_two = str(uuid.uuid4())
    try:
        cursor.execute("INSERT INTO users (id, email) VALUES (%s, %s), (%s, %s)", (owner_one, f"{owner_one}@test.local", owner_two, f"{owner_two}@test.local"))
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name) VALUES (%s, %s, 'Web One'), (%s, %s, 'Web Two')",
            (business_one, owner_one, business_two, owner_two),
        )
        cursor.execute(
            """INSERT INTO business_web_trackers
               (id, business_id, public_tracker_id, allowed_domains)
               VALUES (%s, %s, %s, ARRAY['one.example']),
                      (%s, %s, %s, ARRAY['two.example'])""",
            (tracker_one, business_one, f"pub_{uuid.uuid4().hex}", tracker_two, business_two, f"pub_{uuid.uuid4().hex}"),
        )
        connection.commit()
        public_id = f"pub_{uuid.uuid4().hex}"
        cursor.execute("UPDATE business_web_trackers SET public_tracker_id = %s WHERE id = %s", (public_id, tracker_one))
        now = datetime.now(timezone.utc)
        payload = {
            "tracker_id": public_id,
            "tracker_version": "1.1.0",
            "schema_version": 2,
            "events": [{
                "event_id": f"e_{uuid.uuid4().hex}",
                "visitor_id": f"v_{uuid.uuid4().hex}",
                "session_id": f"s_{uuid.uuid4().hex}",
                "event": "page_view",
                "timestamp": now.isoformat(),
                "page": {"hostname": "one.example", "path": "/services", "title": "Services"},
            }],
        }
        _tracker_id, events, error = validate_batch(payload, now)
        assert error is None
        tracker = {"id": tracker_one, "business_id": business_one}
        first = ingest_events(cursor, tracker, events)
        second = ingest_events(cursor, tracker, events)
        connection.commit()

        assert first == {"accepted": 1, "duplicates": 0}
        assert second == {"accepted": 0, "duplicates": 1}
        cursor.execute("SELECT COUNT(*) AS count FROM web_events WHERE business_id = %s", (business_one,))
        assert cursor.fetchone()["count"] == 1
        cursor.execute("SELECT COUNT(*) AS count FROM web_events WHERE business_id = %s", (business_two,))
        assert cursor.fetchone()["count"] == 0
        cursor.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'web_events' AND indexname = 'uq_web_events_tracker_event'"
        )
        assert cursor.fetchone()["indexname"] == "uq_web_events_tracker_event"

        visitor_two = str(uuid.uuid4())
        session_two = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO web_visitors (id, business_id, anonymous_id)
               VALUES (%s, %s, %s)""",
            (visitor_two, business_two, f"v_{uuid.uuid4().hex}"),
        )
        cursor.execute(
            """INSERT INTO web_sessions
               (id, business_id, visitor_id, session_key, started_at, landing_page, landing_hostname)
               VALUES (%s, %s, %s, %s, NOW(), '/', 'two.example')""",
            (session_two, business_two, visitor_two, f"s_{uuid.uuid4().hex}"),
        )
        cursor.execute(
            """INSERT INTO web_events
               (business_id, tracker_id, session_id, event_id, event_type, page_hostname, page_path, occurred_at)
               SELECT %s, %s, %s, 'e_' || md5(value::text), 'page_view', 'two.example', '/', NOW()
               FROM generate_series(1, 5000) AS value""",
            (business_two, tracker_two, session_two),
        )
        cursor.execute("ANALYZE web_events")
        cursor.execute(
            """EXPLAIN (ANALYZE, FORMAT JSON)
               SELECT COUNT(*) FROM web_events
               WHERE business_id = %s AND occurred_at >= NOW() - INTERVAL '90 days'""",
            (business_one,),
        )
        plan = str(cursor.fetchone()["QUERY PLAN"])
        assert "Seq Scan" not in plan
        assert "Index" in plan

        cursor.execute("SAVEPOINT tenant_guard")
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cursor.execute(
                """INSERT INTO web_events
                   (business_id, tracker_id, session_id, event_id, event_type, occurred_at)
                   VALUES (%s, %s, %s, %s, 'page_view', NOW())""",
                (business_one, tracker_two, session_two, f"e_{uuid.uuid4().hex}"),
            )
        cursor.execute("ROLLBACK TO SAVEPOINT tenant_guard")

        conflicting_payload = {
            **payload,
            "events": [{**payload["events"][0], "event_id": f"e_{uuid.uuid4().hex}", "visitor_id": f"v_{uuid.uuid4().hex}"}],
        }
        _tracker_id, conflicting_events, error = validate_batch(conflicting_payload, now)
        assert error is None
        cursor.execute("SAVEPOINT conflicting_session")
        with pytest.raises(WebTrackingConflictError, match="session_visitor_mismatch"):
            ingest_events(cursor, tracker, conflicting_events)
        cursor.execute("ROLLBACK TO SAVEPOINT conflicting_session")

        metrics_rows = aggregate_web_tracking_day(cursor, now.date())
        assert metrics_rows > 0
        cursor.execute(
            "SELECT SUM(events) AS events FROM web_daily_metrics WHERE metric_date = %s AND dimension_type = 'total'",
            (now.date(),),
        )
        assert cursor.fetchone()["events"] == 5001
        analytics = get_business_web_metrics(cursor, business_one, 30)
        assert analytics["totals"]["sessions"] == 1
        assert analytics["totals"]["page_views"] == 1
        assert analytics["top_pages"][0]["path"] == "/services"
        assert analytics["traffic_sources"][0]["source"] == "direct"
        health = get_web_tracking_health(cursor)
        assert health["trackers"]["trackers"] == 2
        assert len(health["tracker_diagnostics"]) == 2
        assert health["maintenance"] == []

        dry_run = delete_business_web_analytics(cursor, business_one, owner_one, dry_run=True)
        assert dry_run["events"] == 1
        cursor.execute("UPDATE business_web_trackers SET tracking_enabled = FALSE WHERE business_id = %s", (business_one,))
        connection.commit()
        deletion = delete_business_web_analytics(cursor, business_one, owner_one, dry_run=False)
        assert deletion["status"] == "completed"
        connection.commit()
        cursor.execute("SELECT COUNT(*) AS count FROM web_events WHERE business_id = %s", (business_one,))
        assert cursor.fetchone()["count"] == 0
        cursor.execute("SELECT COUNT(*) AS count FROM web_events WHERE business_id = %s", (business_two,))
        assert cursor.fetchone()["count"] == 5000
        cursor.execute("SELECT COUNT(*) AS count FROM web_tracking_deletion_audits WHERE business_id = %s", (business_one,))
        assert cursor.fetchone()["count"] == 2
    finally:
        connection.rollback()
        connection.close()
