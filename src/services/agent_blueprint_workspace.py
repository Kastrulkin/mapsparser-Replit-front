from __future__ import annotations

import csv
import io
import json
import sys
import uuid
from typing import Any, Dict, List, Optional

from services.agent_document_llm import analyze_document_sources_with_llm
from services.agent_email_llm import draft_email_with_llm
from services.agent_review_reply_analysis import draft_review_replies_with_llm
from services.agent_table_analysis import analyze_table_with_llm
from services.gigachat_client import analyze_text_with_gigachat


MAX_SOURCE_TEXT_CHARS = 30000
MAX_REVIEW_ITEMS = 12
SUPPORTED_FILE_EXTENSIONS = {".txt", ".csv", ".tsv", ".md", ".pdf", ".docx", ".xlsx"}


def parse_json_field(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def workspace_parse_json_field(value: Any, fallback: Any) -> Any:
    return parse_json_field(value, fallback)


def normalize_agent_setup(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workflow_description": _clean_text(payload.get("workflow_description") or payload.get("description")),
        "data_sources": _clean_list(payload.get("data_sources")),
        "extraction_rules": _clean_text(payload.get("extraction_rules")),
        "processing_rules": _clean_text(payload.get("processing_rules")),
        "output_format": _clean_text(payload.get("output_format")),
        "approval_boundaries": _clean_list(payload.get("approval_boundaries")) or ["final_output", "external_delivery"],
        "manual_control": _clean_text(payload.get("manual_control")),
        "clarifying_questions": _build_clarifying_questions(payload),
    }


def normalize_agent_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    source_type = _clean_text(payload.get("source_type") or payload.get("type") or "text").lower()
    if source_type not in {"text", "file", "internal"}:
        source_type = "text"
    name = _clean_text(payload.get("name") or payload.get("file_name") or payload.get("internal_source") or "Источник")
    content = _clean_text(payload.get("content") or payload.get("content_text") or payload.get("text"))
    file_name = _clean_text(payload.get("file_name") or name)
    extension = _file_extension(file_name)
    extraction_state = "ready"
    if source_type == "file" and extension and extension not in SUPPORTED_FILE_EXTENSIONS:
        extraction_state = "unsupported_file_type"
    if source_type == "file" and extension in {".pdf", ".docx", ".xlsx"} and not content:
        extraction_state = "needs_text_export"
    return {
        "id": _clean_text(payload.get("id")) or str(uuid.uuid4()),
        "source_type": source_type,
        "name": name,
        "file_name": file_name if source_type == "file" else "",
        "mime_type": _clean_text(payload.get("mime_type")) if source_type == "file" else "",
        "file_size_bytes": _safe_int(payload.get("file_size_bytes")),
        "internal_source": _clean_text(payload.get("internal_source")) if source_type == "internal" else "",
        "content_text": content[:MAX_SOURCE_TEXT_CHARS],
        "content_length": len(content),
        "extraction_state": _clean_text(payload.get("extraction_state")) or extraction_state,
        "extraction_method": _clean_text(payload.get("extraction_method")),
        "extraction_error": _clean_text(payload.get("extraction_error")),
    }


def build_version_payload_from_row(version: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "goal": _clean_text(version.get("goal")),
        "inputs_schema": _copy_json_value(parse_json_field(version.get("inputs_schema_json"), {}), {}),
        "steps": _copy_json_value(parse_json_field(version.get("steps_json"), []), []),
        "persona_agent_id": _clean_text(version.get("persona_agent_id")) or None,
        "capability_allowlist": _copy_json_value(parse_json_field(version.get("capability_allowlist_json"), []), []),
        "approval_policy": _copy_json_value(parse_json_field(version.get("approval_policy_json"), {}), {}),
        "output_schema": _copy_json_value(parse_json_field(version.get("output_schema_json"), {}), {}),
    }


def build_agent_version_diff(from_version: Dict[str, Any] | None, to_version: Dict[str, Any]) -> Dict[str, Any]:
    from_payload = build_version_payload_from_row(from_version or {})
    to_payload = build_version_payload_from_row(to_version or {})
    fields = [
        ("goal", "Цель агента"),
        ("inputs_schema", "Входные данные"),
        ("steps", "Шаги workflow"),
        ("persona_agent_id", "Голос агента"),
        ("capability_allowlist", "Разрешённые действия"),
        ("approval_policy", "Ручной контроль"),
        ("output_schema", "Формат результата"),
    ]
    changes = []
    for key, label in fields:
        before = from_payload.get(key)
        after = to_payload.get(key)
        if _stable_json(before) == _stable_json(after):
            continue
        changes.append(
            {
                "field": key,
                "label": label,
                "change_type": _change_type(before, after),
                "before": _human_diff_value(before),
                "after": _human_diff_value(after),
            }
        )
    if not from_version:
        change_type = "created"
    elif changes:
        change_type = "changed"
    else:
        change_type = "unchanged"
    return {
        "from_version_id": _clean_text((from_version or {}).get("id")),
        "from_version_number": _safe_int((from_version or {}).get("version_number")),
        "to_version_id": _clean_text(to_version.get("id")),
        "to_version_number": _safe_int(to_version.get("version_number")),
        "change_type": change_type,
        "changed_fields": [item["field"] for item in changes],
        "changes": changes,
        "summary": _version_diff_summary(changes, change_type),
    }


def build_feedback_version_payload(version: Dict[str, Any], feedback: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_version_payload_from_row(version)
    output_schema = payload.get("output_schema") if isinstance(payload.get("output_schema"), dict) else {}
    history = output_schema.get("feedback_history") if isinstance(output_schema.get("feedback_history"), list) else []
    history.append(feedback)
    output_schema["feedback_history"] = history[-10:]
    payload["output_schema"] = output_schema
    approval_policy = payload.get("approval_policy") if isinstance(payload.get("approval_policy"), dict) else {}
    approval_policy["last_feedback_requires_review"] = True
    payload["approval_policy"] = approval_policy
    return payload


def build_learning_loop_summary(
    feedback: Dict[str, Any],
    previous_version: Dict[str, Any],
    candidate_version: Dict[str, Any],
    diff: Dict[str, Any],
    activated: bool = False,
) -> Dict[str, Any]:
    trigger_type = _clean_text(feedback.get("trigger_type") or feedback.get("source") or "manual_feedback")
    return {
        "schema": "agent_learning_loop_v1",
        "mode": "versioned_review",
        "trigger_type": trigger_type,
        "trigger_label": _learning_trigger_label(trigger_type),
        "feedback": _clean_text(feedback.get("feedback")),
        "run_id": _clean_text(feedback.get("run_id")),
        "previous_version_id": _clean_text(previous_version.get("id")),
        "previous_version_number": _safe_int(previous_version.get("version_number")),
        "candidate_version_id": _clean_text(candidate_version.get("id")),
        "candidate_version_number": _safe_int(candidate_version.get("version_number")),
        "activation_state": "active" if activated else "candidate",
        "human_gate_required": not activated,
        "diff": diff,
        "available_actions": ["activate", "rollback"] if not activated else ["rollback"],
        "explanation": "Агент не меняет поведение скрыто: feedback сохранён как новая версия blueprint, diff доступен перед активацией.",
    }


def _learning_trigger_label(trigger_type: str) -> str:
    return {
        "manual_edit": "Ручная правка текста",
        "approval_rejected": "Отклонение результата",
        "bad_outcome": "Плохой outcome",
        "runtime_error": "Ошибка запуска",
        "manual_feedback": "Ручной feedback",
        "run_review": "Проверка запуска",
    }.get(trigger_type, trigger_type or "Ручной feedback")


def build_generic_artifact_payload(cursor: Any, run: Dict[str, Any], step: Dict[str, Any], base_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    artifact_type = _clean_text(step.get("artifact_type"))
    if artifact_type not in {"agent_input_plan", "agent_extracted_context", "agent_output_draft", "agent_final_result", "telegram_post_draft"}:
        return None
    workspace = _load_workspace(cursor, run)
    if artifact_type == "agent_input_plan":
        return _build_input_plan_payload(base_payload, workspace)
    if artifact_type == "agent_extracted_context":
        return _build_extracted_context_payload(base_payload, workspace)
    if artifact_type in {"agent_output_draft", "telegram_post_draft"}:
        return _build_output_draft_payload(cursor, run, base_payload, workspace)
    if artifact_type == "agent_final_result":
        return _build_final_result_payload(cursor, run, base_payload, workspace)
    return None


def build_blueprint_review(cursor: Any, blueprint_id: str) -> Dict[str, Any]:
    blueprint = _load_blueprint(cursor, blueprint_id)
    metadata = _metadata_from_blueprint(blueprint)
    cursor.execute(
        """
        SELECT *
        FROM agent_runs
        WHERE blueprint_id = %s
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (blueprint_id,),
    )
    run = cursor.fetchone()
    if not run:
        return {
            "blueprint_id": blueprint_id,
            "has_run": False,
            "setup": metadata.get("agent_setup") if isinstance(metadata.get("agent_setup"), dict) else {},
            "sources": metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else [],
            "sections": [],
            "journal": [],
            "approvals": [],
        }
    run_dict = dict(run)
    cursor.execute(
        """
        SELECT *
        FROM agent_artifacts
        WHERE run_id = %s
        ORDER BY created_at ASC
        """,
        (run_dict.get("id"),),
    )
    artifacts = [dict(row) for row in (cursor.fetchall() or [])]
    cursor.execute(
        """
        SELECT *
        FROM agent_approvals
        WHERE run_id = %s
        ORDER BY requested_at ASC
        """,
        (run_dict.get("id"),),
    )
    approvals = [dict(row) for row in (cursor.fetchall() or [])]
    return {
        "blueprint_id": blueprint_id,
        "has_run": True,
        "run_id": run_dict.get("id"),
        "run_status": run_dict.get("status"),
        "setup": metadata.get("agent_setup") if isinstance(metadata.get("agent_setup"), dict) else {},
        "sources": metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else [],
        "used_sources": _used_source_summaries(metadata, artifacts),
        "sections": _review_sections(artifacts),
        "journal": _review_journal(run_dict, artifacts, approvals, metadata),
        "approvals": [_human_approval(item) for item in approvals],
    }


def _load_workspace(cursor: Any, run: Dict[str, Any]) -> Dict[str, Any]:
    blueprint = _load_blueprint(cursor, _clean_text(run.get("blueprint_id")))
    metadata = _metadata_from_blueprint(blueprint)
    setup = metadata.get("agent_setup") if isinstance(metadata.get("agent_setup"), dict) else {}
    sources = metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else []
    internal_sources = _hydrate_internal_sources(cursor, _clean_text(run.get("business_id")), sources)
    return {
        "blueprint": blueprint,
        "metadata": metadata,
        "setup": setup,
        "sources": sources,
        "internal_sources": internal_sources,
        "feedback_history": metadata.get("feedback_history") if isinstance(metadata.get("feedback_history"), list) else [],
        "run_input": parse_json_field(run.get("input_json"), {}),
        "business_id": _clean_text(run.get("business_id")),
        "user_id": _clean_text(run.get("created_by_user_id")),
    }


def _build_input_plan_payload(base_payload: Dict[str, Any], workspace: Dict[str, Any]) -> Dict[str, Any]:
    setup = workspace["setup"] if isinstance(workspace.get("setup"), dict) else {}
    sources = workspace["sources"] if isinstance(workspace.get("sources"), list) else []
    missing = []
    if not sources:
        missing.append("Добавьте хотя бы один источник данных")
    if not _clean_text(setup.get("output_format")):
        missing.append("Опишите формат результата")
    return {
        **base_payload,
        "status": "ready" if not missing else "needs_clarification",
        "workflow_description": setup.get("workflow_description") or base_payload.get("request") or "",
        "data_sources": _source_summaries(sources),
        "extraction_rules": setup.get("extraction_rules") or "",
        "processing_rules": setup.get("processing_rules") or "",
        "output_format": setup.get("output_format") or base_payload.get("format") or "",
        "manual_control": setup.get("manual_control") or "",
        "missing_information": missing,
        "external_dispatch_performed": False,
    }


def _build_extracted_context_payload(base_payload: Dict[str, Any], workspace: Dict[str, Any]) -> Dict[str, Any]:
    sources = workspace["sources"] if isinstance(workspace.get("sources"), list) else []
    internal_sources = workspace["internal_sources"] if isinstance(workspace.get("internal_sources"), list) else []
    all_items = _extract_source_items(sources) + internal_sources
    return {
        **base_payload,
        "status": "extracted" if all_items else "needs_source_upload",
        "source_count": len(sources),
        "internal_source_count": len(internal_sources),
        "items": all_items[:MAX_REVIEW_ITEMS],
        "provenance": [item.get("source_name") for item in all_items[:MAX_REVIEW_ITEMS] if item.get("source_name")],
        "external_dispatch_performed": False,
    }


def _build_output_draft_payload(cursor: Any, run: Dict[str, Any], base_payload: Dict[str, Any], workspace: Dict[str, Any]) -> Dict[str, Any]:
    setup = workspace["setup"] if isinstance(workspace.get("setup"), dict) else {}
    category = _clean_text(base_payload.get("category") or (workspace.get("metadata") or {}).get("draft_category") or "custom")
    extracted = (
        _extract_run_source_items(cursor, _clean_text(run.get("id")))
        + _extract_source_items(workspace.get("sources") or [])
        + (workspace.get("internal_sources") or [])
    )
    output = _render_output(category, setup, extracted, workspace.get("feedback_history") or [], workspace)
    return {
        **base_payload,
        "status": "generated",
        "category": category,
        "result": output,
        "items_used": len(extracted),
        "provenance": output.get("provenance") if isinstance(output, dict) else [],
        "analysis_source": output.get("analysis_source") if isinstance(output, dict) else "",
        "llm_analysis_used": bool(output.get("llm_analysis_used")) if isinstance(output, dict) else False,
        "approval_required": True,
        "external_dispatch_performed": False,
        "dispatch_state": "not_dispatched",
    }


def _build_final_result_payload(cursor: Any, run: Dict[str, Any], base_payload: Dict[str, Any], workspace: Dict[str, Any]) -> Dict[str, Any]:
    output_payload = _latest_artifact_payload(cursor, _clean_text(run.get("id")), "agent_output_draft")
    return {
        **base_payload,
        "status": "accepted",
        "result": output_payload.get("result") if isinstance(output_payload.get("result"), dict) else {},
        "approval_required": False,
        "external_dispatch_performed": False,
        "delivery_state": "not_dispatched",
        "feedback_applied": len(workspace.get("feedback_history") or []),
    }


def _render_output(
    category: str,
    setup: Dict[str, Any],
    extracted: List[Dict[str, Any]],
    feedback_history: List[Dict[str, Any]],
    workspace: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    facts = [item.get("summary") for item in extracted if item.get("summary")]
    facts = [str(item) for item in facts][:6]
    rules = _clean_text(setup.get("processing_rules"))
    output_format = _clean_text(setup.get("output_format")) or "Краткий структурированный результат"
    feedback_notes = [_clean_text(item.get("feedback")) for item in feedback_history if isinstance(item, dict)]
    feedback_notes = [item for item in feedback_notes if item][-3:]
    if category == "email":
        return draft_email_with_llm(
            setup,
            extracted,
            feedback_history,
            business_id=_clean_text((workspace or {}).get("business_id")),
            user_id=_clean_text((workspace or {}).get("user_id")),
        )
    if category == "tables":
        return analyze_table_with_llm(
            setup,
            extracted,
            feedback_history,
            business_id=_clean_text((workspace or {}).get("business_id")),
            user_id=_clean_text((workspace or {}).get("user_id")),
        )
    if category == "reviews":
        return draft_review_replies_with_llm(
            setup,
            extracted,
            feedback_history,
            business_id=_clean_text((workspace or {}).get("business_id")),
            user_id=_clean_text((workspace or {}).get("user_id")),
        )
    if category == "documents":
        return analyze_document_sources_with_llm(
            setup,
            extracted,
            feedback_history,
            business_id=_clean_text((workspace or {}).get("business_id")),
            user_id=_clean_text((workspace or {}).get("user_id")),
        )
    if _looks_like_message_result(setup, output_format):
        return _render_message_result(setup, extracted, rules, output_format, feedback_notes)
    return {
        "title": "Результат агента",
        "summary": facts,
        "rules_applied": rules,
        "format": output_format,
        "feedback_notes": feedback_notes,
    }


def _looks_like_message_result(setup: Dict[str, Any], output_format: str) -> bool:
    text = " ".join(
        [
            _clean_text(output_format),
            _clean_text(setup.get("workflow_description")),
            _clean_text(setup.get("processing_rules")),
        ]
    ).lower()
    return any(marker in text for marker in ["пост", "сообщ", "telegram", "телеграм", "новост", "публикац", "контент"])


def _render_message_result(
    setup: Dict[str, Any],
    extracted: List[Dict[str, Any]],
    rules: str,
    output_format: str,
    feedback_notes: List[str],
) -> Dict[str, Any]:
    workflow = _clean_text(setup.get("workflow_description"))
    selected_items = _select_message_items(extracted, workflow)
    selected_facts = [_clean_text(item.get("summary")) for item in selected_items if _clean_text(item.get("summary"))]
    if selected_facts:
        return _generate_message_result_with_llm(
            setup,
            selected_items,
            selected_facts,
            rules,
            output_format,
            feedback_notes,
        )
    else:
        return {
            "title": "Нужны данные таблицы",
            "status": "needs_source_data",
            "summary": [
                "Агент не получил строку поездки из Google Sheets или другого источника данных, поэтому сообщение не сформировано.",
            ],
            "next_questions": [
                "Проверьте, что Google Sheets подключён именно как источник данных агента.",
                "Укажите таблицу и лист со списком поездок, затем запустите тест ещё раз.",
            ],
            "rules_applied": rules,
            "format": output_format,
            "feedback_notes": feedback_notes,
            "preparation_method": "Сообщение не готовилось: не было строки источника для безопасного результата.",
        }


def _generate_message_result_with_llm(
    setup: Dict[str, Any],
    selected_items: List[Dict[str, Any]],
    selected_facts: List[str],
    rules: str,
    output_format: str,
    feedback_notes: List[str],
) -> Dict[str, Any]:
    fallback = _build_message_result_fallback(selected_items, selected_facts, rules, output_format, feedback_notes, _clean_text(setup.get("workflow_description")))
    prompt = _build_message_prompt(setup, selected_items, feedback_notes)
    try:
        raw_response = analyze_text_with_gigachat(prompt, task_type="agent_custom_message_draft")
        parsed = _parse_message_llm_json(raw_response)
        draft_text = _clean_text(parsed.get("draft_text") or parsed.get("post_text") or parsed.get("message"))
        if not draft_text:
            raise ValueError("LLM response does not contain draft text")
        summary = _clean_list(parsed.get("summary")) or selected_facts[:3]
        checklist = _clean_list(parsed.get("checklist")) or ["Проверить факты по строке таблицы перед отправкой."]
        return {
            **fallback,
            "title": _clean_text(parsed.get("title")) or fallback["title"],
            "draft_text": draft_text,
            "summary": summary,
            "checklist": checklist,
            "rules_applied": _clean_list(parsed.get("rules_applied")) or fallback["rules_applied"],
            "analysis_source": "gigachat",
            "analysis_prompt_key": "agent_custom_message_draft",
            "analysis_prompt_version": "agent_custom_message_draft_v1",
            "llm_analysis_used": True,
            "llm_error": "",
            "preparation_method": "ИИ подготовил черновик по данным этого тестового запуска. Внешняя отправка не выполнялась.",
        }
    except Exception:
        exc = sys.exc_info()[1]
        return {
            **fallback,
            "analysis_source": "deterministic_fallback",
            "analysis_prompt_key": "agent_custom_message_draft",
            "analysis_prompt_version": "agent_custom_message_draft_v1",
            "llm_analysis_used": False,
            "llm_error": str(exc)[:240],
            "preparation_method": "Черновик подготовлен локальным fallback, потому что ИИ-генерация не вернула готовый текст. Внешняя отправка не выполнялась.",
        }


def _build_message_result_fallback(
    selected_items: List[Dict[str, Any]],
    selected_facts: List[str],
    rules: str,
    output_format: str,
    feedback_notes: List[str],
    workflow: str,
) -> Dict[str, Any]:
    return {
        "title": "Черновик сообщения",
        "draft_text": _compose_message_draft(selected_items, workflow),
        "summary": selected_facts or ["Нужны данные источника для текста сообщения."],
        "checklist": ["Проверить факты по строке таблицы перед отправкой."],
        "rules_applied": [rules] if rules else [],
        "format": output_format,
        "feedback_notes": feedback_notes,
        "provenance": [item.get("source_name") for item in selected_items if item.get("source_name")],
        "external_dispatch_performed": False,
        "delivery_state": "not_dispatched",
    }


def _build_message_prompt(setup: Dict[str, Any], selected_items: List[Dict[str, Any]], feedback_notes: List[str]) -> str:
    payload = {
        "task": _clean_text(setup.get("workflow_description")),
        "extraction_rules": _clean_text(setup.get("extraction_rules")),
        "processing_rules": _clean_text(setup.get("processing_rules")),
        "output_format": _clean_text(setup.get("output_format")),
        "manual_control": _clean_text(setup.get("manual_control")),
        "feedback_notes": feedback_notes,
        "sources": _message_context(selected_items),
    }
    return (
        "Ты готовишь безопасный черновик сообщения для LocalOS AI employee test run. "
        "Используй только предоставленные строки источника, не придумывай факты и не выполняй отправку. "
        "Если данных мало, напиши аккуратный короткий черновик только на основе доступных полей. "
        "Верни только JSON без markdown с полями: "
        "title, draft_text, summary(list), checklist(list), rules_applied(list). "
        "draft_text должен быть конкретным сообщением, готовым для проверки владельцем бизнеса.\n\n"
        f"INPUT_JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _message_context(selected_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    context = []
    for index, item in enumerate(selected_items[:8], start=1):
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        context.append(
            {
                "row": index,
                "source_name": _clean_text(item.get("source_name")) or "Источник",
                "summary": _clean_text(item.get("summary")),
                "values": raw,
            }
        )
    return context


def _parse_message_llm_json(raw_response: str) -> Dict[str, Any]:
    text = _clean_text(raw_response)
    if not text:
        raise ValueError("empty LLM response")
    try:
        parsed = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM response does not contain JSON")
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON is not an object")
    return parsed
    return {
        "title": "Черновик сообщения",
        "draft_text": "\n".join(body_lines).strip(),
        "summary": selected_facts or ["Нужны данные источника для текста сообщения."],
        "rules_applied": rules,
        "format": output_format,
        "feedback_notes": feedback_notes,
        "provenance": [item.get("source_name") for item in selected_items if item.get("source_name")],
    }


def _select_message_items(extracted: List[Dict[str, Any]], workflow: str) -> List[Dict[str, Any]]:
    candidates = [item for item in extracted if _can_use_for_message(item)]
    workflow_lower = workflow.lower()
    if "20" in workflow_lower:
        by_day = [item for item in candidates if "20" in _message_item_text(item).lower()]
        if by_day:
            return by_day
    preferred_markers = []
    if "апрел" in workflow_lower:
        preferred_markers.extend(["апрел", "apr"])
    preferred = [
        item
        for item in candidates
        if any(marker in _message_item_text(item).lower() for marker in preferred_markers)
    ]
    return preferred or candidates[:5]


def _can_use_for_message(item: Dict[str, Any]) -> bool:
    source_name = _clean_text(item.get("source_name")).lower()
    if source_name in {"business_profile", "services", "reviews", "external_reviews"}:
        return False
    summary = _clean_text(item.get("summary"))
    if not summary:
        return False
    lowered = summary.lower()
    internal_markers = ["ready", "id:", "name:", "business_type:", "источник добавлен без текстового содержимого"]
    if any(marker in lowered for marker in internal_markers) and source_name in {"профиль бизнеса", "business profile"}:
        return False
    return True


def _message_item_text(item: Dict[str, Any]) -> str:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    raw_text = " ".join(_clean_text(value) for value in raw.values())
    return " ".join([_clean_text(item.get("source_name")), _clean_text(item.get("summary")), raw_text])


def _compose_message_draft(items: List[Dict[str, Any]], workflow: str) -> str:
    first = items[0] if items else {}
    raw = first.get("raw") if isinstance(first.get("raw"), dict) else {}
    title = "Поездка на 20 апреля" if "20" in workflow or "апрел" in workflow.lower() else "Черновик сообщения"
    route = _first_row_value(raw, ["route", "маршрут", "поездка", "direction", "направление"])
    date = _first_row_value(raw, ["date", "дата", "day", "день"])
    time = _first_row_value(raw, ["time", "время", "departure", "выезд", "start"])
    client = _first_row_value(raw, ["client", "клиент", "passenger", "пассажир", "name", "имя"])
    status = _first_row_value(raw, ["status", "статус"])
    details = []
    if route:
        details.append(f"маршрут: {route}")
    if date:
        details.append(f"дата: {date}")
    if time:
        details.append(f"время: {time}")
    if client:
        details.append(f"клиент/пассажир: {client}")
    if status:
        details.append(f"статус: {status}")
    if details:
        return f"{title}\n\nПодготовлен черновик сообщения:\n{'; '.join(details)}."
    facts = [_clean_text(item.get("summary")) for item in items if _clean_text(item.get("summary"))]
    return f"{title}\n\nПодготовлен черновик сообщения:\n" + "\n".join(f"- {fact}" for fact in facts[:5])


def _first_row_value(row: Dict[str, Any], names: List[str]) -> str:
    normalized = {_clean_text(key).lower(): _clean_text(value) for key, value in row.items()}
    for name in names:
        value = normalized.get(name.lower())
        if value:
            return value
    return ""


def _hydrate_internal_sources(cursor: Any, business_id: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    requested = {_clean_text(item.get("internal_source")) for item in sources if isinstance(item, dict) and item.get("source_type") == "internal"}
    requested = {item for item in requested if item}
    result = []
    if "business_profile" in requested:
        result.extend(_safe_select(cursor, "business_profile", "SELECT id, name, business_type, city, address FROM businesses WHERE id = %s", (business_id,)))
    if "services" in requested:
        result.extend(_safe_select(cursor, "services", "SELECT id, name, price, description FROM userservices WHERE business_id = %s LIMIT 20", (business_id,)))
    if "reviews" in requested or "external_reviews" in requested:
        result.extend(_safe_select(cursor, "reviews", "SELECT id, author_name, rating, text FROM externalbusinessreviews WHERE business_id = %s ORDER BY created_at DESC LIMIT 20", (business_id,)))
    if "prospectingleads" in requested:
        result.extend(_safe_select(cursor, "prospectingleads", "SELECT id, name, city, category, status FROM prospectingleads WHERE business_id = %s ORDER BY updated_at DESC NULLS LAST LIMIT 20", (business_id,)))
    if "outreach_drafts" in requested:
        result.extend(_safe_select(cursor, "outreach_drafts", "SELECT d.id, d.channel, d.status, d.generated_text FROM outreachmessagedrafts d JOIN prospectingleads l ON l.id = d.lead_id WHERE l.business_id = %s ORDER BY d.updated_at DESC LIMIT 20", (business_id,)))
    return result


def _safe_select(cursor: Any, source_name: str, query: str, params: tuple[Any, ...]) -> List[Dict[str, Any]]:
    try:
        cursor.execute(query, params)
        rows = [dict(row) for row in (cursor.fetchall() or [])]
    except Exception:
        return []
    return [{"source_name": source_name, "summary": _row_summary(row), "raw": row} for row in rows[:MAX_REVIEW_ITEMS]]


def _extract_source_items(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        name = _clean_text(source.get("name") or source.get("file_name") or source.get("internal_source") or "Источник")
        text = _clean_text(source.get("content_text"))
        if not text:
            state = _clean_text(source.get("extraction_state"))
            items.append({"source_name": name, "summary": state or "Источник добавлен без текстового содержимого", "raw": {}})
            continue
        rows = _csv_rows(text)
        if rows:
            for row in rows[:MAX_REVIEW_ITEMS]:
                items.append({"source_name": name, "summary": _row_summary(row), "raw": row})
        else:
            items.append({"source_name": name, "summary": _text_summary(text), "raw": {"text": text[:1000]}})
    return items


def _extract_run_source_items(cursor: Any, run_id: str) -> List[Dict[str, Any]]:
    if not run_id:
        return []
    try:
        cursor.execute(
            """
            SELECT step_key, output_json
            FROM agent_run_steps
            WHERE run_id = %s
              AND status = 'completed'
            ORDER BY step_index ASC
            """,
            (run_id,),
        )
        rows = [dict(row) for row in (cursor.fetchall() or [])]
    except Exception:
        return []
    items = []
    for row in rows:
        step_key = _clean_text(row.get("step_key"))
        output = parse_json_field(row.get("output_json"), {})
        if not isinstance(output, dict):
            continue
        result = _step_result_payload(output)
        source = _clean_text(result.get("source") or output.get("source") or step_key)
        if source != "google_sheets" and "google_sheets" not in step_key:
            continue
        source_rows = result.get("rows") if isinstance(result.get("rows"), list) else []
        for source_row in source_rows[:MAX_REVIEW_ITEMS]:
            if isinstance(source_row, dict):
                items.append({"source_name": "google_sheets", "summary": _row_summary(source_row), "raw": source_row})
    return items


def _step_result_payload(output: Dict[str, Any]) -> Dict[str, Any]:
    orchestrator = output.get("orchestrator") if isinstance(output.get("orchestrator"), dict) else {}
    result = orchestrator.get("result") if isinstance(orchestrator.get("result"), dict) else {}
    if result:
        return result
    direct_result = output.get("result") if isinstance(output.get("result"), dict) else {}
    if direct_result:
        return direct_result
    return output


def _csv_rows(text: str) -> List[Dict[str, Any]]:
    sample = text[:4096]
    delimiter = "\t" if "\t" in sample and sample.count("\t") > sample.count(",") else ","
    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            return []
        return [dict(row) for row in reader if isinstance(row, dict)]
    except Exception:
        return []


def _review_sections(artifacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sections = []
    for artifact in artifacts:
        payload = parse_json_field(artifact.get("payload_json"), {})
        sections.append(
            {
                "title": _human_artifact_title(_clean_text(artifact.get("artifact_type"))),
                "artifact_type": artifact.get("artifact_type"),
                "status": payload.get("status") if isinstance(payload, dict) else "",
                "summary": _payload_summary(payload if isinstance(payload, dict) else {}),
                "payload": payload,
            }
        )
    return sections


def _review_journal(
    run: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    approvals: List[Dict[str, Any]],
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    journal: List[Dict[str, Any]] = []
    setup = metadata.get("agent_setup") if isinstance(metadata.get("agent_setup"), dict) else {}
    journal.append(
        {
            "kind": "input",
            "title": "Входные данные",
            "status": "ready",
            "summary": _clean_text(setup.get("workflow_description")) or "Агент получил задачу и источники.",
            "details": _setup_details(setup, metadata),
            "payload": {
                "run_id": run.get("id"),
                "input": parse_json_field(run.get("input_json"), {}),
                "setup": setup,
                "sources": metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else [],
            },
        }
    )
    for artifact in artifacts:
        artifact_type = _clean_text(artifact.get("artifact_type"))
        payload = parse_json_field(artifact.get("payload_json"), {})
        if not isinstance(payload, dict):
            payload = {}
        journal.append(_artifact_journal_entry(artifact_type, payload))
    for approval in approvals:
        payload = parse_json_field(approval.get("payload_json"), {})
        journal.append(
            {
                "kind": "approval",
                "title": "Ручное решение",
                "status": approval.get("status"),
                "summary": _clean_text(approval.get("title")) or _clean_text(approval.get("approval_type")) or "Ожидает решения",
                "details": _approval_details(approval, payload if isinstance(payload, dict) else {}),
                "payload": payload,
            }
        )
    return journal


def _artifact_journal_entry(artifact_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if artifact_type == "lead_source_plan":
        return {
            "kind": "sourcing",
            "title": "Откуда агент взял лидов",
            "status": payload.get("status") or "completed",
            "summary": _payload_summary(payload),
            "details": _lead_source_details(payload),
            "payload": payload,
        }
    if artifact_type == "lead_shortlist":
        return {
            "kind": "shortlist",
            "title": "Кого агент предложил взять в работу",
            "status": payload.get("status") or "completed",
            "summary": _payload_summary(payload),
            "details": _lead_shortlist_details(payload),
            "payload": payload,
        }
    if artifact_type == "message_drafts":
        return {
            "kind": "drafts",
            "title": "Черновики сообщений",
            "status": payload.get("status") or "completed",
            "summary": _payload_summary(payload),
            "details": _message_draft_details(payload),
            "payload": payload,
        }
    if artifact_type == "outreach_outcomes":
        return {
            "kind": "queue",
            "title": "Очередь отправки",
            "status": payload.get("status") or "completed",
            "summary": _payload_summary(payload),
            "details": _outreach_queue_details(payload),
            "payload": payload,
        }
    if artifact_type == "finance_import_preview":
        return {
            "kind": "finance_preview",
            "title": "Предпросмотр финансового импорта",
            "status": payload.get("status") or "ready",
            "summary": _finance_preview_summary(payload),
            "details": _finance_preview_details(payload),
            "payload": payload,
        }
    if artifact_type == "localos_finance_outcome":
        return {
            "kind": "finance_outcome",
            "title": "Итог записи в финансы",
            "status": payload.get("status") or "request_created",
            "summary": _finance_outcome_summary(payload),
            "details": _finance_outcome_details(payload),
            "payload": payload,
        }
    if artifact_type == "agent_input_plan":
        return {
            "kind": "input",
            "title": "Проверка входных данных",
            "status": payload.get("status") or "ready",
            "summary": _payload_summary(payload),
            "details": _input_plan_details(payload),
            "payload": payload,
        }
    if artifact_type == "agent_extracted_context":
        return {
            "kind": "extraction",
            "title": "Что агент извлёк",
            "status": payload.get("status") or "completed",
            "summary": _payload_summary(payload),
            "details": _extraction_details(payload),
            "payload": payload,
        }
    if artifact_type == "agent_output_draft":
        return {
            "kind": "output",
            "title": "Подготовленный результат",
            "status": payload.get("status") or "generated",
            "summary": _payload_summary(payload),
            "details": _output_details(payload),
            "payload": payload,
        }
    if artifact_type == "agent_final_result":
        return {
            "kind": "final",
            "title": "Принятый итог",
            "status": payload.get("status") or "completed",
            "summary": _payload_summary(payload),
            "details": _output_details(payload),
            "payload": payload,
        }
    return {
        "kind": "artifact",
        "title": _human_artifact_title(artifact_type),
        "status": payload.get("status") or "completed",
        "summary": _payload_summary(payload),
        "details": _generic_payload_details(payload),
        "payload": payload,
    }


def _setup_details(setup: Dict[str, Any], metadata: Dict[str, Any]) -> List[Dict[str, str]]:
    sources = metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else []
    return _non_empty_details(
        [
            ("Что сделать", setup.get("workflow_description")),
            ("Какие данные", ", ".join(_clean_list(setup.get("data_sources")))),
            ("Что извлечь", setup.get("extraction_rules")),
            ("Какие правила", setup.get("processing_rules")),
            ("Какой результат", setup.get("output_format")),
            ("Ручной контроль", setup.get("manual_control")),
            ("Подключено источников", str(len(sources)) if sources else ""),
        ]
    )


def _input_plan_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    sources = payload.get("data_sources") if isinstance(payload.get("data_sources"), list) else []
    source_names = []
    for source in sources:
        if isinstance(source, dict):
            source_names.append(_clean_text(source.get("name") or source.get("type")))
    missing = payload.get("missing_information") if isinstance(payload.get("missing_information"), list) else []
    return _non_empty_details(
        [
            ("Задача", payload.get("workflow_description")),
            ("Источники", ", ".join(source_names)),
            ("Не хватает", ", ".join(str(item) for item in missing)),
            ("Ручной контроль", payload.get("manual_control")),
        ]
    )


def _extraction_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    names = []
    for item in items[:5]:
        if isinstance(item, dict):
            names.append(_clean_text(item.get("source_name") or item.get("name") or item.get("source_type")))
    return _non_empty_details(
        [
            ("Источник", payload.get("source")),
            ("Извлечено элементов", str(len(items)) if items else ""),
            ("Что обработано", ", ".join(names)),
            ("Правило извлечения", payload.get("extraction_rules")),
        ]
    )


def _output_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), list) else []
    risks = result.get("risks") if isinstance(result.get("risks"), list) else []
    facts = result.get("facts") if isinstance(result.get("facts"), list) else []
    next_questions = result.get("next_questions") if isinstance(result.get("next_questions"), list) else []
    checklist = result.get("checklist") if isinstance(result.get("checklist"), list) else []
    exceptions = result.get("exceptions") if isinstance(result.get("exceptions"), list) else []
    rows_to_review = result.get("rows_to_review") if isinstance(result.get("rows_to_review"), list) else []
    reply_drafts = result.get("reply_drafts") if isinstance(result.get("reply_drafts"), list) else []
    manual_review_reasons = result.get("manual_review_reasons") if isinstance(result.get("manual_review_reasons"), list) else []
    return _non_empty_details(
        [
            ("Источник анализа", payload.get("analysis_source") or result.get("analysis_source")),
            ("Использовал LLM", "да" if payload.get("llm_analysis_used") or result.get("llm_analysis_used") else ""),
            ("Тема письма", result.get("subject")),
            ("Использованные источники", ", ".join(str(item) for item in provenance)),
            ("Фактов", str(len(facts)) if facts else ""),
            ("Рисков", str(len(risks)) if risks else ""),
            ("Исключений", str(len(exceptions)) if exceptions else ""),
            ("Строк к проверке", str(len(rows_to_review)) if rows_to_review else ""),
            ("Черновиков ответов", str(len(reply_drafts)) if reply_drafts else ""),
            ("Причин ручной проверки", str(len(manual_review_reasons)) if manual_review_reasons else ""),
            ("Вопросов", str(len(next_questions)) if next_questions else ""),
            ("Чеклист", str(len(checklist)) if checklist else ""),
            ("Внешняя отправка", "не выполнялась" if payload.get("external_dispatch_performed") is False else ""),
            ("Публикация", "не выполнялась" if result.get("publish_state") == "not_published" else ""),
        ]
    )


def _approval_details(approval: Dict[str, Any], payload: Dict[str, Any]) -> List[Dict[str, str]]:
    return _non_empty_details(
        [
            ("Тип решения", approval.get("approval_type")),
            ("Статус", approval.get("status")),
            ("Артефакт", payload.get("artifact_type")),
            ("Элементов", str(payload.get("count")) if payload.get("count") is not None else ""),
            ("Причина", approval.get("decision_reason")),
        ]
    )


def _generic_payload_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    return _non_empty_details(
        [
            ("Статус", payload.get("status")),
            ("Источник", payload.get("source")),
            ("Элементов", str(payload.get("count")) if payload.get("count") is not None else ""),
            ("Dispatch", payload.get("dispatch_state")),
        ]
    )


def _finance_preview_summary(payload: Dict[str, Any]) -> str:
    rows_read = int(payload.get("rows_read") or 0)
    if rows_read:
        return f"Агент прочитал {rows_read} строк и подготовил их к нормализации."
    return "Агент ждёт строки из подключённого источника."


def _finance_preview_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    sample_rows = payload.get("sample_rows") if isinstance(payload.get("sample_rows"), list) else []
    return _non_empty_details(
        [
            ("Источник шага", payload.get("source_step")),
            ("Прочитано строк", str(payload.get("rows_read")) if payload.get("rows_read") is not None else ""),
            ("Нормализатор", payload.get("normalizer")),
            ("Примеров строк", str(len(sample_rows)) if sample_rows else ""),
            ("Запись в LocalOS", "да" if payload.get("localos_write_performed") else "нет"),
        ]
    )


def _finance_outcome_summary(payload: Dict[str, Any]) -> str:
    proposals = int(payload.get("proposal_count") or 0)
    review_count = int(payload.get("review_count") or 0)
    imported = int(payload.get("rows_imported") or 0)
    errors = int(payload.get("error_count") or 0)
    if imported:
        return f"Записано {imported} финансовых строк; на проверке {review_count}, ошибок {errors}."
    return f"Подготовлено {proposals} финансовых предложений; на проверке {review_count}, ошибок {errors}."


def _finance_outcome_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    return _non_empty_details(
        [
            ("Прочитано строк", str(payload.get("rows_read")) if payload.get("rows_read") is not None else ""),
            ("Предложений", str(payload.get("proposal_count")) if payload.get("proposal_count") is not None else ""),
            ("Требует проверки", str(payload.get("review_count")) if payload.get("review_count") is not None else ""),
            ("Ошибок", str(payload.get("error_count")) if payload.get("error_count") is not None else ""),
            ("Записано", str(payload.get("rows_imported")) if payload.get("rows_imported") is not None else ""),
            ("Состояние применения", payload.get("apply_state")),
            ("Запись в LocalOS", "да" if payload.get("localos_write_performed") else "нет"),
        ]
    )


def _lead_source_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
    status_counts = payload.get("status_counts") if isinstance(payload.get("status_counts"), dict) else {}
    filter_text = _compact_key_values(filters, ("source", "city", "category", "intent", "limit"))
    status_text = _compact_key_values(status_counts, tuple(status_counts.keys()))
    return _non_empty_details(
        [
            ("Источник данных", payload.get("source")),
            ("Найдено лидов", str(payload.get("count")) if payload.get("count") is not None else ""),
            ("Фильтры", filter_text),
            ("Статусы", status_text),
        ]
    )


def _lead_shortlist_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    names = _item_values(items, "name")
    channels = _item_values(items, "selected_channel")
    return _non_empty_details(
        [
            ("Источник", payload.get("source")),
            ("Лидов в shortlist", str(payload.get("count")) if payload.get("count") is not None else ""),
            ("Сформировано из", payload.get("source_artifact")),
            ("Лиды", ", ".join(names[:5])),
            ("Каналы", ", ".join(channels[:5])),
        ]
    )


def _message_draft_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    channels = _item_values(items, "channel")
    statuses = _item_values(items, "status")
    lead_names = _item_values(items, "lead_name")
    return _non_empty_details(
        [
            ("Источник", payload.get("source")),
            ("Черновиков", str(payload.get("count")) if payload.get("count") is not None else ""),
            ("Лиды", ", ".join(lead_names[:5])),
            ("Каналы", ", ".join(channels[:5])),
            ("Статусы", ", ".join(statuses[:5])),
            ("Внешняя отправка", "не выполнялась"),
        ]
    )


def _outreach_queue_details(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    delivery_statuses = _item_values(items, "delivery_status")
    return _non_empty_details(
        [
            ("Источник", payload.get("source")),
            ("В очереди", str(payload.get("queued_count")) if payload.get("queued_count") is not None else ""),
            ("Элементов", str(payload.get("count")) if payload.get("count") is not None else ""),
            ("Dispatch", payload.get("dispatch_state")),
            ("Delivery", ", ".join(delivery_statuses[:5])),
            ("Внешняя отправка", "не выполнялась" if payload.get("external_dispatch_performed") is False else ""),
            ("Контур", payload.get("operator_note")),
        ]
    )


def _item_values(items: List[Any], key: str) -> List[str]:
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = _clean_text(item.get(key))
        if value:
            result.append(value)
    return list(dict.fromkeys(result))


def _compact_key_values(payload: Dict[str, Any], keys: tuple[Any, ...]) -> str:
    parts = []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            clean_items = [_clean_text(item) for item in value if _clean_text(item)]
            clean_value = ", ".join(clean_items)
        else:
            clean_value = _clean_text(value)
        if clean_value:
            parts.append(f"{key}: {clean_value}")
    return "; ".join(parts)


def _non_empty_details(items: List[tuple[str, Any]]) -> List[Dict[str, str]]:
    details = []
    for label, value in items:
        clean_value = _clean_text(value)
        if clean_value:
            details.append({"label": label, "value": clean_value})
    return details


def _human_approval(approval: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": approval.get("id"),
        "status": approval.get("status"),
        "title": approval.get("title"),
        "approval_type": approval.get("approval_type"),
        "payload": parse_json_field(approval.get("payload_json"), {}),
    }


def _source_summaries(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        result.append(
            {
                "id": source.get("id"),
                "type": source.get("source_type"),
                "name": source.get("name") or source.get("file_name") or source.get("internal_source"),
                "state": source.get("extraction_state"),
                "content_length": source.get("content_length", 0),
            }
        )
    return result


def _used_source_summaries(metadata: Dict[str, Any], artifacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources = metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else []
    by_name: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        name = _clean_text(source.get("name") or source.get("file_name") or source.get("internal_source"))
        if not name:
            continue
        by_name[name] = source

    used_names: List[str] = []
    for artifact in artifacts:
        payload = parse_json_field(artifact.get("payload_json"), {})
        if not isinstance(payload, dict):
            continue
        provenance = payload.get("provenance") if isinstance(payload.get("provenance"), list) else []
        for name in provenance:
            clean_name = _clean_text(name)
            if clean_name and clean_name not in used_names:
                used_names.append(clean_name)
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            clean_name = _clean_text(item.get("source_name") or item.get("name"))
            if clean_name and clean_name not in used_names:
                used_names.append(clean_name)

    result = []
    for name in used_names:
        source = by_name.get(name, {})
        result.append(
            {
                "id": source.get("id"),
                "name": name,
                "source_type": source.get("source_type") or "internal",
                "file_name": source.get("file_name") or "",
                "internal_source": source.get("internal_source") or "",
                "extraction_state": source.get("extraction_state") or "ready",
                "content_length": source.get("content_length", 0),
                "file_size_bytes": source.get("file_size_bytes", 0),
            }
        )
    return result


def _load_blueprint(cursor: Any, blueprint_id: str) -> Dict[str, Any]:
    if not blueprint_id:
        return {}
    cursor.execute("SELECT * FROM agent_blueprints WHERE id = %s", (blueprint_id,))
    row = cursor.fetchone()
    return dict(row) if row else {}


def _metadata_from_blueprint(blueprint: Dict[str, Any]) -> Dict[str, Any]:
    metadata = parse_json_field(blueprint.get("metadata_json"), {})
    return metadata if isinstance(metadata, dict) else {}


def _latest_artifact_payload(cursor: Any, run_id: str, artifact_type: str) -> Dict[str, Any]:
    if not run_id:
        return {}
    try:
        cursor.execute(
            """
            SELECT payload_json
            FROM agent_artifacts
            WHERE run_id = %s
              AND artifact_type = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (run_id, artifact_type),
        )
        row = cursor.fetchone()
    except Exception:
        return {}
    if not row:
        return {}
    payload = row.get("payload_json") if isinstance(row, dict) else {}
    parsed = parse_json_field(payload, {})
    return parsed if isinstance(parsed, dict) else {}


def _payload_summary(payload: Dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        title = _clean_text(result.get("title"))
        if title:
            return title
    items = payload.get("items")
    if isinstance(items, list):
        return f"Найдено элементов: {len(items)}"
    missing = payload.get("missing_information")
    if isinstance(missing, list) and missing:
        return ", ".join(str(item) for item in missing[:3])
    return _clean_text(payload.get("status")) or "Готово"


def _human_artifact_title(artifact_type: str) -> str:
    titles = {
        "agent_input_plan": "Входные данные",
        "agent_extracted_context": "Что агент понял",
        "agent_output_draft": "Подготовленный результат",
        "agent_final_result": "Принятый итог",
        "lead_source_plan": "Откуда агент взял лидов",
        "lead_shortlist": "Shortlist лидов",
        "message_drafts": "Черновики сообщений",
        "outreach_outcomes": "Очередь отправки",
    }
    return titles.get(artifact_type, artifact_type or "Результат")


def _build_clarifying_questions(payload: Dict[str, Any]) -> List[str]:
    questions = []
    if not _clean_text(payload.get("extraction_rules")):
        questions.append("Что агент должен извлечь или понять из данных?")
    if not _clean_text(payload.get("processing_rules")):
        questions.append("Какие правила применить при обработке?")
    if not _clean_text(payload.get("output_format")):
        questions.append("В каком формате вернуть результат?")
    return questions


def _text_summary(text: str) -> str:
    compact = " ".join(text.split())
    return compact[:500]


def _row_summary(row: Dict[str, Any]) -> str:
    parts = []
    for key, value in row.items():
        text = _clean_text(value)
        if text:
            parts.append(f"{key}: {text}")
        if len(parts) >= 5:
            break
    return "; ".join(parts)


def _email_body(facts: List[str], rules: str, feedback_notes: List[str]) -> str:
    lines = ["Здравствуйте!", "", "Подготовили черновик по вашему запросу."]
    if facts:
        lines.append("Ключевой контекст:")
        lines.extend(f"- {item}" for item in facts[:4])
    if rules:
        lines.extend(["", f"Учтено правило: {rules}"])
    if feedback_notes:
        lines.extend(["", f"Учтена последняя правка: {feedback_notes[-1]}"])
    lines.extend(["", "Готовы адаптировать текст под ваш тон и канал отправки."])
    return "\n".join(lines)


def _table_exceptions(items: List[Dict[str, Any]]) -> List[str]:
    exceptions = []
    for item in items:
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        empty_keys = [key for key, value in raw.items() if not _clean_text(value)]
        if empty_keys:
            exceptions.append(f"{item.get('source_name')}: пустые поля {', '.join(empty_keys[:4])}")
    return exceptions[:10]


def _review_replies(facts: List[str]) -> List[Dict[str, str]]:
    if not facts:
        return [{"reply": "Спасибо за отзыв. Мы учтём обратную связь и улучшим сервис."}]
    return [{"source": item, "reply": "Спасибо за отзыв. Мы внимательно изучили ваш комментарий и учтём его в работе."} for item in facts[:6]]


def _risk_hints(facts: List[str], rules: str) -> List[str]:
    risks = []
    keywords = ("штраф", "срок", "ответствен", "неустой", "расторж", "персональн", "оплат")
    for fact in facts:
        lowered = fact.lower()
        for keyword in keywords:
            if keyword in lowered:
                risks.append(f"Проверьте условие: {fact[:180]}")
                break
    if rules:
        risks.append(f"Проверено по правилу: {rules[:180]}")
    return risks[:8]


def _document_fields(facts: List[str]) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    labels = {
        "срок": "Сроки",
        "оплат": "Оплата",
        "сумм": "Суммы",
        "штраф": "Штрафы",
        "ответствен": "Ответственность",
        "расторж": "Расторжение",
        "персональн": "Персональные данные",
    }
    for fact in facts:
        lowered = fact.lower()
        for keyword, label in labels.items():
            if keyword in lowered and label not in fields:
                fields[label] = fact[:300]
    return fields


def _document_next_questions(facts: List[str]) -> List[str]:
    text = " ".join(facts).lower()
    questions = []
    if "подпис" not in text:
        questions.append("Кто подписывает документ и есть ли полномочия?")
    if "срок" not in text:
        questions.append("Какие сроки исполнения или действия документа?")
    if "оплат" not in text and "сумм" not in text:
        questions.append("Какие суммы, порядок оплаты и условия возврата?")
    if "ответствен" not in text and "штраф" not in text:
        questions.append("Какая ответственность сторон и что происходит при нарушении?")
    return questions[:4]


def _file_extension(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return "." + file_name.rsplit(".", 1)[-1].lower()


def _clean_list(value: Any) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = _clean_text(item)
        if text:
            result.append(text)
    return list(dict.fromkeys(result))


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _copy_json_value(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return fallback


def _change_type(before: Any, after: Any) -> str:
    if before in (None, "", [], {}) and after not in (None, "", [], {}):
        return "added"
    if before not in (None, "", [], {}) and after in (None, "", [], {}):
        return "removed"
    return "changed"


def _human_diff_value(value: Any) -> Any:
    if isinstance(value, list):
        return value[:8]
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for index, key in enumerate(value.keys()):
            if index >= 8:
                result["..."] = "truncated"
                break
            result[str(key)] = value.get(key)
        return result
    return value


def _version_diff_summary(changes: List[Dict[str, Any]], change_type: str) -> str:
    if change_type == "created":
        return "Первая версия агента создана."
    if not changes:
        return "Изменений между версиями не найдено."
    labels = [str(item.get("label") or item.get("field") or "") for item in changes]
    labels = [item for item in labels if item]
    return "Изменено: " + ", ".join(labels[:4]) + ("." if len(labels) <= 4 else " и ещё.")


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0
