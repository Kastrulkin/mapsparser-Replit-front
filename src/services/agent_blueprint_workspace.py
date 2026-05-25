from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Any, Dict, List, Optional


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
        "inputs_schema": parse_json_field(version.get("inputs_schema_json"), {}),
        "steps": parse_json_field(version.get("steps_json"), []),
        "persona_agent_id": _clean_text(version.get("persona_agent_id")) or None,
        "capability_allowlist": parse_json_field(version.get("capability_allowlist_json"), []),
        "approval_policy": parse_json_field(version.get("approval_policy_json"), {}),
        "output_schema": parse_json_field(version.get("output_schema_json"), {}),
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


def build_generic_artifact_payload(cursor: Any, run: Dict[str, Any], step: Dict[str, Any], base_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    artifact_type = _clean_text(step.get("artifact_type"))
    if artifact_type not in {"agent_input_plan", "agent_extracted_context", "agent_output_draft", "agent_final_result"}:
        return None
    workspace = _load_workspace(cursor, run)
    if artifact_type == "agent_input_plan":
        return _build_input_plan_payload(base_payload, workspace)
    if artifact_type == "agent_extracted_context":
        return _build_extracted_context_payload(base_payload, workspace)
    if artifact_type == "agent_output_draft":
        return _build_output_draft_payload(base_payload, workspace)
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
        "sections": _review_sections(artifacts),
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


def _build_output_draft_payload(base_payload: Dict[str, Any], workspace: Dict[str, Any]) -> Dict[str, Any]:
    setup = workspace["setup"] if isinstance(workspace.get("setup"), dict) else {}
    category = _clean_text(base_payload.get("category") or (workspace.get("metadata") or {}).get("draft_category") or "custom")
    extracted = _extract_source_items(workspace.get("sources") or []) + (workspace.get("internal_sources") or [])
    output = _render_output(category, setup, extracted, workspace.get("feedback_history") or [])
    return {
        **base_payload,
        "status": "generated",
        "category": category,
        "result": output,
        "items_used": len(extracted),
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


def _render_output(category: str, setup: Dict[str, Any], extracted: List[Dict[str, Any]], feedback_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    facts = [item.get("summary") for item in extracted if item.get("summary")]
    facts = [str(item) for item in facts][:6]
    rules = _clean_text(setup.get("processing_rules"))
    output_format = _clean_text(setup.get("output_format")) or "Краткий структурированный результат"
    feedback_notes = [_clean_text(item.get("feedback")) for item in feedback_history if isinstance(item, dict)]
    feedback_notes = [item for item in feedback_notes if item][-3:]
    if category == "email":
        return {
            "title": "Черновик письма",
            "subject": "Предложение по вашему запросу",
            "body": _email_body(facts, rules, feedback_notes),
            "format": output_format,
        }
    if category == "tables":
        return {
            "title": "Отчёт по таблице",
            "summary": facts,
            "exceptions": _table_exceptions(extracted),
            "format": output_format,
        }
    if category == "reviews":
        return {
            "title": "Черновики ответов на отзывы",
            "replies": _review_replies(facts),
            "format": output_format,
        }
    if category == "documents":
        return {
            "title": "Разбор документа",
            "summary": facts,
            "risks": _risk_hints(facts, rules),
            "facts": facts,
            "fields": _document_fields(facts),
            "next_questions": _document_next_questions(facts),
            "format": output_format,
        }
    return {
        "title": "Результат агента",
        "summary": facts,
        "rules_applied": rules,
        "format": output_format,
        "feedback_notes": feedback_notes,
    }


def _hydrate_internal_sources(cursor: Any, business_id: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    requested = {_clean_text(item.get("internal_source")) for item in sources if isinstance(item, dict) and item.get("source_type") == "internal"}
    requested = {item for item in requested if item}
    result = []
    if "business_profile" in requested:
        result.extend(_safe_select(cursor, "business_profile", "SELECT id, name, business_type, city, address FROM businesses WHERE id = %s", (business_id,)))
    if "services" in requested:
        result.extend(_safe_select(cursor, "services", "SELECT id, name, price, duration FROM userservices WHERE business_id = %s LIMIT 20", (business_id,)))
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


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0
