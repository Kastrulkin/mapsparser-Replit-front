from __future__ import annotations

from typing import Any


JSON_TASK_KEYS = {
    "agent_compiler",
    "agent_document_analysis",
    "agent_table_analysis",
    "operator_intent_classify",
}


def normalize_pilot_metric(row: dict[str, Any]) -> dict[str, Any]:
    requests_count = int(row.get("requests_count") or 0)
    completed_count = int(row.get("completed_count") or 0)
    corrected_count = int(row.get("corrected_count") or 0)
    fallback_count = int(row.get("fallback_count") or 0)
    policy_blocked_count = int(row.get("policy_blocked_count") or 0)
    task_key = str(row.get("task_key") or "unknown")
    model = str(row.get("model") or "unknown")
    p95_latency_ms = int(round(float(row.get("p95_latency_ms") or 0)))

    completion_rate = completed_count / requests_count if requests_count else 0.0
    fallback_rate = fallback_count / requests_count if requests_count else 0.0
    first_pass_valid_count = max(0, completed_count - corrected_count)
    first_pass_valid_rate = first_pass_valid_count / requests_count if requests_count else 0.0
    latency_limit_ms = 20_000 if "flash" in model.lower() else 45_000

    automated_checks = {
        "json_valid_after_retry": task_key not in JSON_TASK_KEYS or completion_rate >= 0.98,
        "fallback_rate": fallback_rate <= 0.03,
        "policy_boundary": policy_blocked_count == 0,
        "p95_latency": p95_latency_ms <= latency_limit_ms,
    }
    return {
        "task_key": task_key,
        "provider": str(row.get("provider") or "gigachat"),
        "model": model,
        "shadow": bool(row.get("shadow")),
        "total_tokens": int(row.get("total_tokens") or 0),
        "requests_count": requests_count,
        "completed_count": completed_count,
        "corrected_count": corrected_count,
        "fallback_count": fallback_count,
        "policy_blocked_count": policy_blocked_count,
        "completion_rate": round(completion_rate, 4),
        "first_pass_valid_rate": round(first_pass_valid_rate, 4),
        "fallback_rate": round(fallback_rate, 4),
        "average_latency_ms": round(float(row.get("average_latency_ms") or 0), 2),
        "p95_latency_ms": p95_latency_ms,
        "latency_limit_ms": latency_limit_ms,
        "automated_checks": automated_checks,
        "automated_gate_passed": requests_count > 0 and all(automated_checks.values()),
        "manual_review_required": True,
    }


def pilot_metrics_select(where_clause: str = "") -> str:
    where_sql = f"WHERE {where_clause}" if where_clause else ""
    return f"""
        SELECT
            COALESCE(task_type, 'unknown') AS task_key,
            COALESCE(provider, 'gigachat') AS provider,
            COALESCE(model, 'unknown') AS model,
            COALESCE(shadow, FALSE) AS shadow,
            COALESCE(SUM(total_tokens), 0) AS total_tokens,
            COUNT(*) AS requests_count,
            COUNT(*) FILTER (WHERE request_status = 'completed') AS completed_count,
            COUNT(*) FILTER (
                WHERE metadata_json ->> 'correction_attempted' = 'true'
            ) AS corrected_count,
            COUNT(*) FILTER (
                WHERE request_status IN (
                    'fallback_required', 'provider_error', 'provider_unavailable',
                    'empty_response', 'invalid_json', 'schema_invalid'
                )
            ) AS fallback_count,
            COUNT(*) FILTER (WHERE request_status = 'policy_blocked') AS policy_blocked_count,
            COALESCE(AVG(latency_ms), 0) AS average_latency_ms,
            COALESCE(
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms),
                0
            ) AS p95_latency_ms
        FROM tokenusage
        {where_sql}
        GROUP BY COALESCE(task_type, 'unknown'), COALESCE(provider, 'gigachat'),
                 COALESCE(model, 'unknown'), COALESCE(shadow, FALSE)
        ORDER BY requests_count DESC
    """
