import json
import os
import uuid
from typing import Any

from psycopg2.extras import Json

from core.knowledge_policy import KnowledgePolicyError, prepare_external_model_text
from services.gigachat_client import get_gigachat_client


def _enabled() -> bool:
    return str(os.getenv("KNOWLEDGE_SEMANTIC_ANALYSIS_ENABLED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _estimated_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def analyze_knowledge_text(
    conn,
    *,
    prompt: str,
    source_id: str | None,
    analysis_version: str,
    purpose: str,
    sensitivity_class: str,
    pii_flags: list[str],
    allowed_uses: list[str],
    source_visibility: str = "public",
    token_budget: int = 4000,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    cursor = conn.cursor()
    safe_payload: dict[str, Any] | None = None
    try:
        if not _enabled():
            cursor.execute(
                """
                INSERT INTO knowledge_analysis_runs (
                    id, run_type, analysis_version, status, source_id, token_budget,
                    transmitted_classes, error_json, completed_at
                ) VALUES (%s, 'semantic_document', %s, 'blocked', %s, %s, %s, %s, NOW())
                """,
                (
                    run_id,
                    analysis_version,
                    source_id,
                    token_budget,
                    Json([]),
                    Json({"code": "SEMANTIC_ANALYSIS_DISABLED"}),
                ),
            )
            return {"run_id": run_id, "status": "blocked", "code": "SEMANTIC_ANALYSIS_DISABLED"}

        safe_payload = prepare_external_model_text(
            prompt,
            sensitivity_class=sensitivity_class,
            pii_flags=pii_flags,
            allowed_uses=allowed_uses,
            purpose=purpose,
            source_visibility=source_visibility,
        )
        estimated_input_tokens = _estimated_tokens(safe_payload["text"])
        if estimated_input_tokens > token_budget:
            raise KnowledgePolicyError("Knowledge analysis token budget exceeded")

        cursor.execute(
            """
            INSERT INTO knowledge_analysis_runs (
                id, run_type, analysis_version, model, status, source_id,
                document_count, token_budget, transmitted_classes, metadata_json, started_at
            ) VALUES (%s, 'semantic_document', %s, %s, 'running', %s, 1, %s, %s, %s, NOW())
            """,
            (
                run_id,
                analysis_version,
                str(os.getenv("KNOWLEDGE_LLM_MODEL") or "gigachat"),
                source_id,
                token_budget,
                Json([safe_payload["sensitivity_class"]]),
                Json({"purpose": purpose, "redacted": safe_payload["redacted"]}),
            ),
        )

        client = get_gigachat_client()
        content, usage = client.analyze_text(safe_payload["text"], task_type="ai_agent_marketing")
        input_tokens = int(usage.get("prompt_tokens") or estimated_input_tokens)
        output_tokens = int(usage.get("completion_tokens") or 0)
        cursor.execute(
            """
            UPDATE knowledge_analysis_runs
            SET status = 'completed', processed_count = 1,
                input_tokens = %s, output_tokens = %s, completed_at = NOW()
            WHERE id = %s
            """,
            (input_tokens, output_tokens, run_id),
        )
        return {
            "run_id": run_id,
            "status": "completed",
            "content": content,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        }
    except KnowledgePolicyError as error:
        cursor.execute(
            """
            INSERT INTO knowledge_analysis_runs (
                id, run_type, analysis_version, status, source_id, token_budget,
                transmitted_classes, error_json, completed_at
            ) VALUES (%s, 'semantic_document', %s, 'blocked', %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                status = 'blocked', error_json = EXCLUDED.error_json, completed_at = NOW()
            """,
            (
                run_id,
                analysis_version,
                source_id,
                token_budget,
                Json([safe_payload["sensitivity_class"]] if safe_payload else []),
                Json({"code": "KNOWLEDGE_POLICY_BLOCKED", "message": str(error)}),
            ),
        )
        return {"run_id": run_id, "status": "blocked", "code": "KNOWLEDGE_POLICY_BLOCKED", "message": str(error)}
    except Exception as error:
        cursor.execute(
            """
            INSERT INTO knowledge_analysis_runs (
                id, run_type, analysis_version, status, source_id, token_budget,
                transmitted_classes, error_json, completed_at
            ) VALUES (%s, 'semantic_document', %s, 'failed', %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                status = 'failed', error_json = EXCLUDED.error_json, completed_at = NOW()
            """,
            (
                run_id,
                analysis_version,
                source_id,
                token_budget,
                Json([safe_payload["sensitivity_class"]] if safe_payload else []),
                Json({"code": "KNOWLEDGE_PROVIDER_ERROR", "message": str(error)[:500]}),
            ),
        )
        return {"run_id": run_id, "status": "failed", "code": "KNOWLEDGE_PROVIDER_ERROR"}
    finally:
        cursor.close()


def parse_json_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") != "completed":
        return result
    content = str(result.get("content") or "").strip()
    try:
        result["data"] = json.loads(content)
    except json.JSONDecodeError:
        result["status"] = "partial"
        result["code"] = "KNOWLEDGE_INVALID_JSON"
    return result
