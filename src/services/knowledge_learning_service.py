import statistics
import uuid
from datetime import timedelta
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from core.knowledge_policy import deidentify_shared_payload


EVIDENCE_LEVELS = {
    "observed_after",
    "associated_with",
    "likely_contributed",
    "causal_evidence",
    "insufficient_evidence",
}


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row) if isinstance(row, dict) else {}


def evaluate_action_window(conn, *, action_event_id: str, metric_name: str) -> dict[str, Any]:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "SELECT * FROM business_action_events WHERE id = %s",
            (action_event_id,),
        )
        action = cursor.fetchone()
        if not action:
            raise ValueError("Action event not found")
        action_payload = _row_dict(action)
        occurred_at = action_payload["occurred_at"]
        before_start = occurred_at - timedelta(days=28)
        after_end = occurred_at + timedelta(days=28)
        cursor.execute(
            """
            SELECT metric_value, observed_at
            FROM metric_observations_v
            WHERE business_id = %s AND metric_name = %s
              AND observed_at >= %s AND observed_at < %s
            ORDER BY observed_at
            """,
            (action_payload["business_id"], metric_name, before_start, occurred_at),
        )
        before_rows = [_row_dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT metric_value, observed_at
            FROM metric_observations_v
            WHERE business_id = %s AND metric_name = %s
              AND observed_at > %s AND observed_at <= %s
            ORDER BY observed_at
            """,
            (action_payload["business_id"], metric_name, occurred_at, after_end),
        )
        after_rows = [_row_dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()

    before_days = {row["observed_at"].date() for row in before_rows if row.get("observed_at")}
    after_days = {row["observed_at"].date() for row in after_rows if row.get("observed_at")}
    limitations: list[str] = list(action_payload.get("limitations_json") or [])
    if len(before_days) < 14:
        limitations.append("Меньше 14 дней наблюдений до изменения")
    if len(after_days) < 14:
        limitations.append("Меньше 14 дней наблюдений после изменения")
    if len(before_days) < 14 or len(after_days) < 14:
        return {
            "action_event_id": action_event_id,
            "metric_name": metric_name,
            "evidence_level": "insufficient_evidence",
            "before_observations": len(before_rows),
            "after_observations": len(after_rows),
            "limitations": limitations,
        }

    before_values = [float(row["metric_value"]) for row in before_rows]
    after_values = [float(row["metric_value"]) for row in after_rows]
    before_median = statistics.median(before_values)
    after_median = statistics.median(after_values)
    change_percent = None
    if before_median:
        change_percent = round((after_median - before_median) / abs(before_median) * 100, 1)
    limitations.append("Наблюдение до/после не доказывает причинность")
    return {
        "action_event_id": action_event_id,
        "metric_name": metric_name,
        "evidence_level": "associated_with",
        "before_median": before_median,
        "after_median": after_median,
        "change_percent": change_percent,
        "before_observations": len(before_rows),
        "after_observations": len(after_rows),
        "limitations": limitations,
    }


def create_aggregate_claim_candidate(
    conn,
    *,
    claim_type: str,
    title: str,
    statement_text: str,
    industry: str,
    segment: str | None,
    evidence_level: str,
    business_ids: list[str],
    evidence_ids: list[str],
    limitations: list[str],
    sensitive_segment: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if evidence_level not in EVIDENCE_LEVELS:
        raise ValueError("Unknown evidence level")
    distinct_businesses = sorted(set(str(item) for item in business_ids if item))
    minimum = 10 if sensitive_segment else 5
    if len(distinct_businesses) < minimum:
        return {
            "status": "blocked",
            "code": "KNOWLEDGE_SAMPLE_TOO_SMALL",
            "required_businesses": minimum,
            "sample_businesses": len(distinct_businesses),
        }
    if evidence_level in {"likely_contributed", "causal_evidence"}:
        evidence_level = "associated_with"
        limitations = list(limitations) + ["Автоматический анализ ограничен уровнем связи, а не причинности"]

    claim_id = str(uuid.uuid4())
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO learning_claims (
                id, claim_type, title, statement_text, industry, segment,
                evidence_level, sample_businesses, evidence_ids, limitations_json,
                sensitivity_class, privacy_status, status, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      'internal', 'pending_review', 'candidate', %s)
            RETURNING *
            """,
            (
                claim_id,
                claim_type,
                title,
                statement_text,
                industry,
                segment,
                evidence_level,
                len(distinct_businesses),
                Json(evidence_ids),
                Json(limitations),
                Json(metadata or {}),
            ),
        )
        claim = _row_dict(cursor.fetchone())
        redacted = deidentify_shared_payload(
            {
                "claim_type": claim_type,
                "title": title,
                "statement": statement_text,
                "industry": industry,
                "segment": segment,
                "evidence_level": evidence_level,
                "sample_businesses": len(distinct_businesses),
                "limitations": limitations,
                "metadata": metadata or {},
            }
        )
        cursor.execute(
            """
            INSERT INTO privacy_release_reviews (
                id, claim_id, status, redacted_payload_json
            ) VALUES (%s, %s, 'pending', %s)
            ON CONFLICT (claim_id) WHERE status = 'pending' DO UPDATE SET
                redacted_payload_json = EXCLUDED.redacted_payload_json,
                updated_at = NOW()
            """,
            (str(uuid.uuid4()), claim_id, Json(redacted)),
        )
        claim["privacy_preview"] = redacted
        return claim
    finally:
        cursor.close()
