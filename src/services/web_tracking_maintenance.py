"""Bounded daily aggregation and retention maintenance for website tracking."""

from datetime import date, datetime, timedelta, timezone
import uuid


class WebTrackingAggregationError(RuntimeError):
    """Raised when a daily aggregate does not reconcile with raw events."""


def aggregate_web_tracking_day(cursor, target_date: date) -> int:
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    cursor.execute("DELETE FROM web_daily_metrics WHERE metric_date = %s", (target_date,))
    cursor.execute(
        """
        INSERT INTO web_daily_metrics (
            business_id, tracker_id, metric_date, dimension_type, dimension_key,
            visitors, sessions, events, page_views, target_actions
        )
        SELECT e.business_id, e.tracker_id, %s, 'total', '',
               COUNT(DISTINCT s.visitor_id), COUNT(DISTINCT e.session_id),
               COUNT(*),
               COUNT(*) FILTER (WHERE e.event_type = 'page_view'),
               COUNT(*) FILTER (WHERE e.action_type IS NOT NULL)
        FROM web_events e
        JOIN web_sessions s ON s.id = e.session_id
        WHERE e.occurred_at >= %s AND e.occurred_at < %s
        GROUP BY e.business_id, e.tracker_id
        """,
        (target_date, day_start, day_end),
    )
    total_rows = cursor.rowcount
    cursor.execute(
        """
        INSERT INTO web_daily_metrics (
            business_id, tracker_id, metric_date, dimension_type, dimension_key,
            visitors, sessions, events, page_views, target_actions
        )
        SELECT e.business_id, e.tracker_id, %s, 'page', e.page_hostname || E'\n' || e.page_path,
               COUNT(DISTINCT s.visitor_id), COUNT(DISTINCT e.session_id),
               COUNT(*),
               COUNT(*) FILTER (WHERE e.event_type = 'page_view'),
               COUNT(*) FILTER (WHERE e.action_type IS NOT NULL)
        FROM web_events e
        JOIN web_sessions s ON s.id = e.session_id
        WHERE e.occurred_at >= %s AND e.occurred_at < %s
        GROUP BY e.business_id, e.tracker_id, e.page_hostname, e.page_path
        """,
        (target_date, day_start, day_end),
    )
    page_rows = cursor.rowcount
    cursor.execute(
        """
        INSERT INTO web_daily_metrics (
            business_id, tracker_id, metric_date, dimension_type, dimension_key,
            visitors, sessions, events, page_views, target_actions
        )
        SELECT s.business_id, e.tracker_id, %s, 'source',
               s.source_type || '|' || s.source_label || '|' || s.source_domain,
               COUNT(DISTINCT s.visitor_id), COUNT(DISTINCT s.id), COUNT(*),
               COUNT(*) FILTER (WHERE e.event_type = 'page_view'),
               COUNT(*) FILTER (WHERE e.action_type IS NOT NULL)
        FROM web_sessions s
        JOIN web_events e ON e.session_id = s.id
        WHERE e.occurred_at >= %s AND e.occurred_at < %s
        GROUP BY s.business_id, e.tracker_id, s.source_type, s.source_label, s.source_domain
        """,
        (target_date, day_start, day_end),
    )
    source_rows = cursor.rowcount
    cursor.execute(
        """
        INSERT INTO web_daily_metrics (
            business_id, tracker_id, metric_date, dimension_type, dimension_key,
            visitors, sessions, events, page_views, target_actions
        )
        SELECT e.business_id, e.tracker_id, %s, 'event', e.event_type,
               COUNT(DISTINCT s.visitor_id), COUNT(DISTINCT e.session_id),
               COUNT(*),
               COUNT(*) FILTER (WHERE e.event_type = 'page_view'),
               COUNT(*) FILTER (WHERE e.action_type IS NOT NULL)
        FROM web_events e
        JOIN web_sessions s ON s.id = e.session_id
        WHERE e.occurred_at >= %s AND e.occurred_at < %s
        GROUP BY e.business_id, e.tracker_id, e.event_type
        """,
        (target_date, day_start, day_end),
    )
    event_rows = cursor.rowcount
    cursor.execute(
        """
        INSERT INTO web_daily_metrics (
            business_id, tracker_id, metric_date, dimension_type, dimension_key,
            visitors, sessions, events, page_views, target_actions
        )
        SELECT e.business_id, e.tracker_id, %s, 'action',
               e.action_type || '|' || COALESCE(e.action_provider, '') || '|' || COALESCE(e.action_domain, ''),
               COUNT(DISTINCT s.visitor_id), COUNT(DISTINCT e.session_id), COUNT(*), 0, COUNT(*)
        FROM web_events e
        JOIN web_sessions s ON s.id = e.session_id
        WHERE e.occurred_at >= %s AND e.occurred_at < %s
          AND e.action_type IS NOT NULL
        GROUP BY e.business_id, e.tracker_id, e.action_type, e.action_provider, e.action_domain
        """,
        (target_date, day_start, day_end),
    )
    action_rows = cursor.rowcount
    cursor.execute(
        "SELECT COUNT(*) AS raw_events FROM web_events WHERE occurred_at >= %s AND occurred_at < %s",
        (day_start, day_end),
    )
    raw_events = int((cursor.fetchone() or {}).get("raw_events") or 0)
    cursor.execute(
        "SELECT COALESCE(SUM(events), 0) AS aggregate_events FROM web_daily_metrics WHERE metric_date = %s AND dimension_type = 'total'",
        (target_date,),
    )
    aggregate_events = int((cursor.fetchone() or {}).get("aggregate_events") or 0)
    if raw_events != aggregate_events:
        raise WebTrackingAggregationError("daily_event_checksum_mismatch")
    return sum(max(0, rows) for rows in (total_rows, page_rows, source_rows, event_rows, action_rows))


def _eligible_events(cursor) -> int:
    cursor.execute(
        """
        WITH candidate_days AS (
            SELECT DISTINCT e.tracker_id, (e.occurred_at AT TIME ZONE 'UTC')::date AS metric_date
            FROM web_events e
            JOIN business_web_trackers t ON t.id = e.tracker_id
            WHERE e.occurred_at < NOW() - (t.raw_retention_days * INTERVAL '1 day')
        ), verified_days AS (
            SELECT c.tracker_id, c.metric_date
            FROM candidate_days c
            JOIN web_daily_metrics m ON m.tracker_id = c.tracker_id
                 AND m.metric_date = c.metric_date AND m.dimension_type = 'total'
            JOIN LATERAL (
                SELECT COUNT(*) AS raw_events FROM web_events raw
                WHERE raw.tracker_id = c.tracker_id
                  AND raw.occurred_at >= c.metric_date::timestamp AT TIME ZONE 'UTC'
                  AND raw.occurred_at < (c.metric_date + 1)::timestamp AT TIME ZONE 'UTC'
            ) checksum ON checksum.raw_events = m.events
        )
        SELECT COUNT(*) AS count
        FROM web_events e
        JOIN business_web_trackers t ON t.id = e.tracker_id
        JOIN verified_days v ON v.tracker_id = e.tracker_id
             AND v.metric_date = (e.occurred_at AT TIME ZONE 'UTC')::date
        WHERE e.occurred_at < NOW() - (t.raw_retention_days * INTERVAL '1 day')
        """
    )
    row = cursor.fetchone() or {}
    return int(row.get("count") or 0)


def _eligible_metrics(cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM web_daily_metrics m
        JOIN business_web_trackers t ON t.id = m.tracker_id
        WHERE m.metric_date < (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - t.aggregate_retention_days
        """
    )
    row = cursor.fetchone() or {}
    return int(row.get("count") or 0)


def _next_aggregate_date(cursor, fallback: date) -> date:
    cursor.execute(
        """
        SELECT MIN((e.occurred_at AT TIME ZONE 'UTC')::date) AS metric_date
        FROM web_events e
        WHERE (e.occurred_at AT TIME ZONE 'UTC')::date < (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date
          AND NOT EXISTS (
              SELECT 1 FROM web_daily_metrics m
              WHERE m.tracker_id = e.tracker_id
                AND m.metric_date = (e.occurred_at AT TIME ZONE 'UTC')::date
                AND m.dimension_type = 'total'
          )
        """
    )
    row = cursor.fetchone() or {}
    return row.get("metric_date") or fallback


def run_web_tracking_maintenance(cursor, *, dry_run: bool = True, batch_size: int = 10000, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    recheck_offset_days = 1 + (int(current.timestamp() // 3600) % 7)
    fallback_date = (current - timedelta(days=recheck_offset_days)).date()
    target_date = _next_aggregate_date(cursor, fallback_date)
    run_id = str(uuid.uuid4())
    cursor.execute(
        """INSERT INTO web_tracking_maintenance_runs
           (id, dry_run, status, aggregate_date) VALUES (%s, %s, 'running', %s)""",
        (run_id, dry_run, target_date),
    )
    cursor.execute("SAVEPOINT web_tracking_maintenance_work")
    try:
        eligible_events = _eligible_events(cursor)
        eligible_metrics = _eligible_metrics(cursor)
        if dry_run:
            metrics_rows = 0
            raw_events = 0
            aggregate_events = 0
            deleted_events = 0
            deleted_metrics = 0
            deleted_sessions = 0
            deleted_visitors = 0
        else:
            metrics_rows = aggregate_web_tracking_day(cursor, target_date)
            cursor.execute(
                """SELECT COALESCE(SUM(events), 0) AS aggregate_events
                   FROM web_daily_metrics WHERE metric_date = %s AND dimension_type = 'total'""",
                (target_date,),
            )
            aggregate_events = int((cursor.fetchone() or {}).get("aggregate_events") or 0)
            day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
            cursor.execute(
                "SELECT COUNT(*) AS raw_events FROM web_events WHERE occurred_at >= %s AND occurred_at < %s",
                (day_start, day_start + timedelta(days=1)),
            )
            raw_events = int((cursor.fetchone() or {}).get("raw_events") or 0)
            cursor.execute(
                """
                WITH candidate_days AS (
                    SELECT DISTINCT e.tracker_id, (e.occurred_at AT TIME ZONE 'UTC')::date AS metric_date
                    FROM web_events e
                    JOIN business_web_trackers t ON t.id = e.tracker_id
                    WHERE e.occurred_at < NOW() - (t.raw_retention_days * INTERVAL '1 day')
                ), verified_days AS (
                    SELECT c.tracker_id, c.metric_date
                    FROM candidate_days c
                    JOIN web_daily_metrics m ON m.tracker_id = c.tracker_id
                         AND m.metric_date = c.metric_date AND m.dimension_type = 'total'
                    JOIN LATERAL (
                        SELECT COUNT(*) AS raw_events FROM web_events raw
                        WHERE raw.tracker_id = c.tracker_id
                          AND raw.occurred_at >= c.metric_date::timestamp AT TIME ZONE 'UTC'
                          AND raw.occurred_at < (c.metric_date + 1)::timestamp AT TIME ZONE 'UTC'
                    ) checksum ON checksum.raw_events = m.events
                ), doomed AS (
                    SELECT e.id
                    FROM web_events e
                    JOIN business_web_trackers t ON t.id = e.tracker_id
                    JOIN verified_days v ON v.tracker_id = e.tracker_id
                         AND v.metric_date = (e.occurred_at AT TIME ZONE 'UTC')::date
                    WHERE e.occurred_at < NOW() - (t.raw_retention_days * INTERVAL '1 day')
                    ORDER BY e.id
                    LIMIT %s
                )
                DELETE FROM web_events e USING doomed WHERE e.id = doomed.id
                """,
                (max(100, min(batch_size, 50000)),),
            )
            deleted_events = max(0, cursor.rowcount)
            cursor.execute(
                """
                WITH doomed AS (
                    SELECT m.id
                    FROM web_daily_metrics m
                    JOIN business_web_trackers t ON t.id = m.tracker_id
                    WHERE m.metric_date < (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - t.aggregate_retention_days
                    ORDER BY m.id
                    LIMIT %s
                )
                DELETE FROM web_daily_metrics m USING doomed WHERE m.id = doomed.id
                """,
                (max(100, min(batch_size, 50000)),),
            )
            deleted_metrics = max(0, cursor.rowcount)
            cursor.execute(
                """WITH doomed AS (
                       SELECT s.id FROM web_sessions s
                       WHERE NOT EXISTS (SELECT 1 FROM web_events e WHERE e.session_id = s.id)
                       ORDER BY s.started_at LIMIT %s
                   )
                   DELETE FROM web_sessions s USING doomed WHERE s.id = doomed.id""",
                (max(100, min(batch_size, 50000)),),
            )
            deleted_sessions = max(0, cursor.rowcount)
            cursor.execute(
                """WITH doomed AS (
                       SELECT v.id FROM web_visitors v
                       WHERE NOT EXISTS (SELECT 1 FROM web_sessions s WHERE s.visitor_id = v.id)
                       ORDER BY v.last_seen_at LIMIT %s
                   )
                   DELETE FROM web_visitors v USING doomed WHERE v.id = doomed.id""",
                (max(100, min(batch_size, 50000)),),
            )
            deleted_visitors = max(0, cursor.rowcount)
        result = {
            "run_id": run_id,
            "status": "completed",
            "dry_run": dry_run,
            "aggregate_date": target_date.isoformat(),
            "metrics_rows": metrics_rows,
            "raw_events": raw_events,
            "aggregate_events": aggregate_events,
            "eligible_events": eligible_events,
            "eligible_metrics": eligible_metrics,
            "deleted_events": deleted_events,
            "deleted_metrics": deleted_metrics,
            "deleted_sessions": deleted_sessions,
            "deleted_visitors": deleted_visitors,
        }
        cursor.execute(
            """UPDATE web_tracking_maintenance_runs
               SET status = 'completed', finished_at = NOW(), metrics_rows = %s,
                   raw_events = %s, aggregate_events = %s, eligible_events = %s,
                   eligible_metrics = %s, deleted_events = %s, deleted_metrics = %s,
                   deleted_sessions = %s, deleted_visitors = %s WHERE id = %s""",
            (metrics_rows, raw_events, aggregate_events, eligible_events, eligible_metrics,
             deleted_events, deleted_metrics, deleted_sessions, deleted_visitors, run_id),
        )
        cursor.execute("RELEASE SAVEPOINT web_tracking_maintenance_work")
        return result
    except Exception as error:
        cursor.execute("ROLLBACK TO SAVEPOINT web_tracking_maintenance_work")
        error_code = str(error) if isinstance(error, WebTrackingAggregationError) else type(error).__name__
        cursor.execute(
            """UPDATE web_tracking_maintenance_runs
               SET status = 'failed', finished_at = NOW(), error_code = %s WHERE id = %s""",
            (error_code[:120], run_id),
        )
        cursor.execute("RELEASE SAVEPOINT web_tracking_maintenance_work")
        return {
            "run_id": run_id,
            "status": "failed",
            "dry_run": dry_run,
            "aggregate_date": target_date.isoformat(),
            "error_code": error_code[:120],
        }
