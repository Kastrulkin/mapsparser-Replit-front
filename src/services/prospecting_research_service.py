"""Evidence-backed prospecting shared by Codex and the LocalOS lead registry."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from psycopg2.extras import Json, RealDictCursor

from services.lead_workstream_service import CLIENT_PARTNERSHIP, LOCALOS_SALES, create_workstream


IMPORT_MODES = {
    "localos-sales": LOCALOS_SALES,
    "client-partners": CLIENT_PARTNERSHIP,
}
SCORE_WEIGHTS = {
    "pain_strength": 25,
    "product_fit": 25,
    "timing": 20,
    "reachability": 15,
    "evidence_quality": 15,
}
SIGNAL_KINDS = {"demand", "pain", "workaround", "switching", "timing"}
STAGES = {"high_intent", "problem_aware", "trigger_present", "potential_fit"}
MESSAGE_BRIEF_FIELDS = {
    "segment", "buyer_persona", "kpi", "pain", "pain_strength", "awareness",
    "signal", "result", "proof", "angle", "cta",
}


def _clean_text(value, limit=2000):
    return str(value or "").strip()[:limit]


def _json_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_public_url(value):
    raw = _clean_text(value, 1200)
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw
    return ""


def _domain(value):
    raw = _safe_public_url(value)
    if not raw:
        raw = _safe_public_url(f"https://{_clean_text(value, 500)}")
    parsed = urlparse(raw)
    return parsed.netloc.lower().removeprefix("www.")


def _normalized_name(value):
    return re.sub(r"[^a-zа-яё0-9]+", " ", _clean_text(value, 300).lower()).strip()


def _score_breakdown(candidate):
    raw = candidate.get("score_breakdown") if isinstance(candidate.get("score_breakdown"), dict) else {}
    result = {}
    for key in SCORE_WEIGHTS:
        source_key = "public_reachability" if key == "reachability" and "public_reachability" in raw else key
        try:
            value = float(raw.get(source_key) or 0)
        except (TypeError, ValueError):
            value = 0
        result[key] = max(0, min(5, round(value, 2)))
    return result


def _weighted_score(breakdown):
    total = 0.0
    for key, weight in SCORE_WEIGHTS.items():
        total += breakdown[key] / 5 * weight
    return max(0, min(100, round(total)))


def _signal_label(score, signals, has_evidence):
    if not has_evidence:
        return "fit_only"
    signal_kinds = {item.get("kind") for item in signals}
    if score >= 80 and signal_kinds.intersection({"demand", "pain", "workaround", "switching", "timing"}):
        return "strong_signal"
    if score >= 65:
        return "reason_to_check"
    return "fit_only"


def _stage(candidate, score, signals):
    requested = _clean_text(candidate.get("stage"), 40).lower().replace("-", "_").replace(" ", "_")
    kinds = {item.get("kind") for item in signals}
    if requested in STAGES:
        if requested == "high_intent" and not kinds.intersection({"demand", "switching"}):
            return "problem_aware" if "pain" in kinds else "potential_fit"
        return requested
    if score >= 80 and kinds.intersection({"demand", "switching"}):
        return "high_intent"
    if "pain" in kinds or "workaround" in kinds:
        return "problem_aware"
    if "timing" in kinds:
        return "trigger_present"
    return "potential_fit"


def _normalize_sources(candidate):
    raw_sources = candidate.get("sources") if isinstance(candidate.get("sources"), list) else []
    sources = []
    for raw in raw_sources[:20]:
        if not isinstance(raw, dict):
            continue
        url = _safe_public_url(raw.get("url") or raw.get("source_url"))
        if not url:
            continue
        sources.append(
            {
                "title": _clean_text(raw.get("title") or raw.get("source_title") or "Источник", 300),
                "url": url,
                "source_type": _clean_text(raw.get("source_type") or "public_web", 80),
                "published_at": _clean_text(raw.get("published_at") or raw.get("signal_date") or "date unavailable", 80),
                "researched_at": _clean_text(raw.get("researched_at") or datetime.now(timezone.utc).isoformat(), 80),
            }
        )
    return sources


def _normalize_signals(candidate, source_urls):
    raw_signals = candidate.get("signals") if isinstance(candidate.get("signals"), list) else []
    signals = []
    for raw in raw_signals[:20]:
        if not isinstance(raw, dict):
            continue
        kind = _clean_text(raw.get("kind"), 40).lower()
        observed = _clean_text(raw.get("observed"), 1200)
        source_url = _safe_public_url(raw.get("source_url"))
        if kind not in SIGNAL_KINDS or not observed or not source_url:
            continue
        if source_url not in source_urls:
            continue
        signals.append(
            {
                "kind": kind,
                "observed": observed,
                "inference": _clean_text(raw.get("inference"), 1000),
                "source_url": source_url,
            }
        )
    return signals


def _normalize_message_brief(candidate, has_evidence):
    raw = candidate.get("message_brief") if isinstance(candidate.get("message_brief"), dict) else {}
    brief = {
        key: _clean_text(raw.get(key), 1200)
        for key in MESSAGE_BRIEF_FIELDS
        if _clean_text(raw.get(key), 1200)
    }
    if not has_evidence:
        for key in ("pain", "signal", "proof"):
            brief.pop(key, None)
    return brief


def _normalize_contacts(candidate, source_urls):
    raw_contacts = candidate.get("contacts") if isinstance(candidate.get("contacts"), dict) else {}
    values = {}
    evidence = []
    field_limits = {"phone": 120, "email": 300, "telegram_url": 1200, "whatsapp_url": 1200}
    for field, limit in field_limits.items():
        raw = raw_contacts.get(field, candidate.get(field))
        details = raw if isinstance(raw, dict) else {}
        value = details.get("value") if details else raw
        normalized = _clean_text(value, limit)
        if field.endswith("_url"):
            normalized = _safe_public_url(normalized)
        if field == "email":
            normalized = normalized.lower()
        values[field] = normalized
        if not normalized:
            continue
        source_url = _safe_public_url(details.get("source_url"))
        if source_url not in source_urls:
            source_url = ""
        try:
            confidence = float(details.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0
        evidence.append(
            {
                "field": field,
                "source_url": source_url,
                "observed_at": _clean_text(
                    details.get("observed_at") or details.get("found_at") or datetime.now(timezone.utc).isoformat(),
                    80,
                ),
                "confidence": max(0, min(1, round(confidence, 2))),
            }
        )
    return values, evidence


def normalize_candidate(candidate):
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    name = _clean_text(candidate.get("name"), 300)
    if not name:
        raise ValueError("candidate name is required")
    sources = _normalize_sources(candidate)
    source_urls = {item["url"] for item in sources}
    signals = _normalize_signals(candidate, source_urls)
    contacts, contact_evidence = _normalize_contacts(candidate, source_urls)
    breakdown = _score_breakdown(candidate)
    score = _weighted_score(breakdown)
    limitations = candidate.get("limitations") if isinstance(candidate.get("limitations"), list) else []
    limitations = [_clean_text(item, 500) for item in limitations[:12] if _clean_text(item, 500)]
    has_evidence = bool(sources and signals)
    opener = _clean_text(candidate.get("suggested_opener") or candidate.get("opener"), 1200)
    opener_source_url = _safe_public_url(candidate.get("opener_source_url"))
    if opener_source_url not in source_urls:
        opener_source_url = signals[0]["source_url"] if signals else ""
    if not has_evidence:
        opener = ""
        opener_source_url = ""
        limitations.append("Публичный сигнал не подтверждён; первое письмо не будет подготовлено без дополнительных фактов.")
    if any(item["source_url"] == "" for item in contact_evidence):
        limitations.append("Для части контактов не указан публичный источник; проверьте их вручную.")
    normalized = {
        "candidate_id": _clean_text(candidate.get("candidate_id") or candidate.get("id") or _json_hash({"name": name})[:16], 120),
        "name": name,
        "category": _clean_text(candidate.get("category"), 200),
        "city": _clean_text(candidate.get("city"), 200),
        "address": _clean_text(candidate.get("address"), 500),
        "website": _safe_public_url(candidate.get("website")),
        "source_url": _safe_public_url(candidate.get("source_url")) or (sources[0]["url"] if sources else ""),
        "google_id": _clean_text(candidate.get("google_id"), 300),
        "external_id": _clean_text(candidate.get("external_id"), 300),
        "phone": contacts["phone"],
        "email": contacts["email"],
        "telegram_url": contacts["telegram_url"],
        "whatsapp_url": contacts["whatsapp_url"],
        "contact_evidence": contact_evidence,
        "score": score,
        "score_breakdown": breakdown,
        "signal_label": _signal_label(score, signals, has_evidence),
        "why_now": _clean_text(candidate.get("why_now"), 1600),
        "signals": signals,
        "sources": sources,
        "suggested_opener": opener,
        "opener_source_url": opener_source_url,
        "message_brief": _normalize_message_brief(candidate, has_evidence),
        "limitations": list(dict.fromkeys(limitations)),
    }
    normalized["qualification_stage"] = _stage(candidate, score, signals)
    normalized["report_hash"] = _json_hash(normalized)
    return normalized


def parse_report(payload):
    report = payload.get("report") if isinstance(payload, dict) and isinstance(payload.get("report"), dict) else payload
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    mode = _clean_text(report.get("mode"), 40).lower()
    if mode not in IMPORT_MODES:
        raise ValueError("LocalOS import supports localos-sales or client-partners mode")
    business_id = _clean_text(report.get("client_business_id"), 120) or None
    if mode == "client-partners" and not business_id:
        raise ValueError("client_business_id is required for client-partners mode")
    if mode == "localos-sales":
        business_id = None
    raw_candidates = report.get("candidates") if isinstance(report.get("candidates"), list) else []
    candidates = [normalize_candidate(item) for item in raw_candidates[:100]]
    return {
        "mode": mode,
        "workstream_type": IMPORT_MODES[mode],
        "client_business_id": business_id,
        "candidates": candidates,
        "report_hash": _json_hash({"mode": mode, "business_id": business_id, "candidates": candidates}),
    }


def load_grants(cursor, agent_client_id):
    cursor.execute(
        """
        SELECT id, workstream_type, client_business_id, created_at
        FROM agent_client_prospecting_grants
        WHERE agent_client_id = %s
        ORDER BY workstream_type, client_business_id NULLS FIRST
        """,
        (agent_client_id,),
    )
    return [dict(row) for row in cursor.fetchall() or []]


def replace_grants(cursor, agent_client_id, raw_grants):
    grants = raw_grants if isinstance(raw_grants, list) else []
    normalized = []
    for raw in grants:
        if not isinstance(raw, dict):
            continue
        workstream_type = _clean_text(raw.get("workstream_type"), 40)
        business_id = _clean_text(raw.get("client_business_id"), 120) or None
        if workstream_type == LOCALOS_SALES:
            business_id = None
        elif workstream_type == CLIENT_PARTNERSHIP and business_id:
            cursor.execute("SELECT id FROM businesses WHERE id = %s LIMIT 1", (business_id,))
            if not cursor.fetchone():
                raise ValueError("Client business for prospecting grant was not found")
        else:
            raise ValueError("Invalid prospecting grant")
        normalized.append({"workstream_type": workstream_type, "client_business_id": business_id})
    cursor.execute("DELETE FROM agent_client_prospecting_grants WHERE agent_client_id = %s", (agent_client_id,))
    for grant in normalized:
        cursor.execute(
            """
            INSERT INTO agent_client_prospecting_grants (
                id, agent_client_id, workstream_type, client_business_id
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (str(uuid.uuid4()), agent_client_id, grant["workstream_type"], grant["client_business_id"]),
        )
    return normalized


def grant_allows(cursor, agent_client_id, workstream_type, client_business_id=None):
    cursor.execute(
        """
        SELECT 1
        FROM agent_client_prospecting_grants
        WHERE agent_client_id = %s
          AND workstream_type = %s
          AND (
              (%s IS NULL AND client_business_id IS NULL)
              OR client_business_id = %s
          )
        LIMIT 1
        """,
        (agent_client_id, workstream_type, client_business_id, client_business_id),
    )
    return bool(cursor.fetchone())


def load_context(cursor, mode, client_business_id=None):
    workstream_type = IMPORT_MODES.get(mode)
    if not workstream_type:
        raise ValueError("Unsupported prospecting mode")
    if workstream_type == LOCALOS_SALES:
        return {
            "mode": mode,
            "product": {
                "name": "LocalOS",
                "url": "https://localos.pro",
                "outcome": "Помочь локальному бизнесу управлять картами, отзывами, контентом, финансами, партнёрствами и контролируемой автоматизацией.",
                "primary_users": ["владелец локального бизнеса", "управляющий", "специалист по локальному SEO"],
                "safety": "Внешние отправки и публикации требуют ручного подтверждения.",
            },
        }
    if not client_business_id:
        raise ValueError("business_id is required")
    cursor.execute(
        """
        SELECT b.id, b.name, b.address, b.city, b.business_type, b.website,
               b.description, b.industry, b.categories, b.geo
        FROM businesses b
        WHERE b.id = %s
        LIMIT 1
        """,
        (client_business_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise LookupError("Client business not found")
    business = dict(row)
    cursor.execute(
        """
        SELECT name, category, price
        FROM userservices
        WHERE business_id = %s AND COALESCE(is_active, TRUE) = TRUE
        ORDER BY category NULLS LAST, name
        LIMIT 80
        """,
        (client_business_id,),
    )
    business["services"] = [dict(item) for item in cursor.fetchall() or []]
    return {"mode": mode, "business": business}


def _candidate_matches(cursor, candidate):
    clauses = []
    params = []
    external_id = candidate.get("external_id") or candidate.get("google_id")
    if external_id:
        clauses.append("source_external_id = %s OR google_id = %s")
        params.extend([external_id, external_id])
    domain = _domain(candidate.get("website"))
    if domain:
        clauses.append("LOWER(COALESCE(website, '')) LIKE %s")
        params.append(f"%{domain}%")
    name = _normalized_name(candidate.get("name"))
    if name:
        clauses.append("LOWER(REGEXP_REPLACE(COALESCE(name, ''), '[^a-zA-Zа-яА-ЯёЁ0-9]+', ' ', 'g')) = %s")
        params.append(name)
    if not clauses:
        return []
    cursor.execute(
        f"""
        SELECT id, name, city, address, website, source_url, google_id, source_external_id
        FROM prospectingleads
        WHERE {' OR '.join(f'({clause})' for clause in clauses)}
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 10
        """,
        tuple(params),
    )
    rows = [dict(row) for row in cursor.fetchall() or []]
    if len(rows) <= 1:
        return rows
    city = _clean_text(candidate.get("city"), 200).lower()
    address = _clean_text(candidate.get("address"), 500).lower()
    narrowed = [
        row for row in rows
        if (city and _clean_text(row.get("city"), 200).lower() == city)
        or (address and _clean_text(row.get("address"), 500).lower() == address)
    ]
    return narrowed or rows


def preview_report(cursor, parsed_report):
    results = []
    for candidate in parsed_report["candidates"]:
        matches = _candidate_matches(cursor, candidate)
        if len(matches) > 1:
            action = "ambiguous"
            workstream_id = None
        elif not matches:
            action = "create_lead"
            workstream_id = None
        else:
            lead_id = matches[0]["id"]
            if parsed_report["workstream_type"] == LOCALOS_SALES:
                cursor.execute(
                    "SELECT id FROM lead_workstreams WHERE lead_id = %s AND workstream_type = 'localos_sales' LIMIT 1",
                    (lead_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id FROM lead_workstreams
                    WHERE lead_id = %s AND workstream_type = 'client_partnership' AND client_business_id = %s
                    LIMIT 1
                    """,
                    (lead_id, parsed_report["client_business_id"]),
                )
            workstream = cursor.fetchone()
            action = "update_research" if workstream else "add_workstream"
            workstream_id = str(workstream["id"]) if workstream else None
        results.append(
            {
                "candidate_id": candidate["candidate_id"],
                "name": candidate["name"],
                "action": action,
                "score": candidate["score"],
                "signal_label": candidate["signal_label"],
                "workstream_id": workstream_id,
                "matches": matches if action == "ambiguous" else matches[:1],
            }
        )
    return results


def _insert_lead(cursor, candidate, workstream_type, client_business_id):
    lead_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO prospectingleads (
            id, name, address, city, phone, website, source_url, google_id,
            category, status, pipeline_status, source, source_external_id,
            email, telegram_url, whatsapp_url, intent, business_id,
            matched_sources_json, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, NULLIF(%s, ''),
            %s, 'new', 'unprocessed', 'codex_public_research', NULLIF(%s, ''),
            %s, %s, %s, %s, NULLIF(%s, ''), %s, NOW(), NOW()
        )
        """,
        (
            lead_id,
            candidate["name"],
            candidate["address"] or None,
            candidate["city"] or None,
            candidate["phone"] or None,
            candidate["website"] or None,
            candidate["source_url"] or None,
            candidate["google_id"],
            candidate["category"] or None,
            candidate["external_id"] or candidate["google_id"],
            candidate["email"] or None,
            candidate["telegram_url"] or None,
            candidate["whatsapp_url"] or None,
            "partnership_outreach" if workstream_type == CLIENT_PARTNERSHIP else "client_outreach",
            client_business_id or "",
            Json(candidate["sources"]),
        ),
    )
    return lead_id


def _insert_research(cursor, workstream_id, candidate, agent_client_id):
    research_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO lead_workstream_research (
            id, workstream_id, score, qualification_stage, signal_label,
            score_breakdown, why_now, signals_json, sources_json, contact_evidence_json,
            suggested_opener, opener_source_url, limitations_json, message_brief_json,
            message_readiness_json, report_hash, created_by_agent_client_id,
            researched_at, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            '{}'::jsonb, %s, %s, NOW(), NOW()
        )
        ON CONFLICT (workstream_id, report_hash) DO UPDATE
        SET researched_at = EXCLUDED.researched_at
        RETURNING *
        """,
        (
            research_id,
            workstream_id,
            candidate["score"],
            candidate["qualification_stage"],
            candidate["signal_label"],
            Json(candidate["score_breakdown"]),
            candidate["why_now"] or None,
            Json(candidate["signals"]),
            Json(candidate["sources"]),
            Json(candidate["contact_evidence"]),
            candidate["suggested_opener"] or None,
            candidate["opener_source_url"] or None,
            Json(candidate["limitations"]),
            Json(candidate["message_brief"]),
            candidate["report_hash"],
            agent_client_id,
        ),
    )
    return dict(cursor.fetchone())


def import_report(conn, parsed_report, candidate_ids, agent_client_id, idempotency_key):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s))",
        (f"prospecting:{agent_client_id}:{idempotency_key}",),
    )
    cursor.execute(
        """
        SELECT report_hash, result_json FROM agent_prospecting_imports
        WHERE agent_client_id = %s AND idempotency_key = %s
        LIMIT 1
        """,
        (agent_client_id, idempotency_key),
    )
    existing = cursor.fetchone()
    if existing:
        existing_hash = existing.get("report_hash") if isinstance(existing, dict) else existing[0]
        if str(existing_hash or "") != str(parsed_report["report_hash"]):
            raise ValueError("idempotency_key was already used for another prospecting report")
        result = existing.get("result_json") if isinstance(existing, dict) else existing[1]
        result = result if isinstance(result, dict) else {}
        result["reused"] = True
        return result

    selected = set(candidate_ids)
    preview = {item["candidate_id"]: item for item in preview_report(cursor, parsed_report)}
    imported = []
    skipped = []
    for candidate in parsed_report["candidates"]:
        candidate_id = candidate["candidate_id"]
        if candidate_id not in selected:
            continue
        plan = preview[candidate_id]
        if plan["action"] == "ambiguous":
            skipped.append({"candidate_id": candidate_id, "reason": "ambiguous"})
            continue
        matches = _candidate_matches(cursor, candidate)
        if len(matches) > 1:
            skipped.append({"candidate_id": candidate_id, "reason": "ambiguous"})
            continue
        lead_id = matches[0]["id"] if matches else _insert_lead(
            cursor,
            candidate,
            parsed_report["workstream_type"],
            parsed_report["client_business_id"],
        )
        workstream = create_workstream(
            conn,
            lead_id=str(lead_id),
            workstream_type=parsed_report["workstream_type"],
            client_business_id=parsed_report["client_business_id"],
            actor_id=agent_client_id,
        )
        research = _insert_research(cursor, str(workstream["id"]), candidate, agent_client_id)
        cursor.execute(
            """
            INSERT INTO lead_timeline_events (
                id, lead_id, workstream_id, event_type, actor_id, comment, payload_json, created_at
            ) VALUES (%s, %s, %s, 'public_research_imported', %s, %s, %s, NOW())
            """,
            (
                str(uuid.uuid4()),
                lead_id,
                workstream["id"],
                agent_client_id,
                "Публичные сигналы проверены и добавлены в карточку.",
                Json({"research_id": str(research["id"]), "score": research["score"]}),
            ),
        )
        imported.append(
            {
                "candidate_id": candidate_id,
                "lead_id": str(lead_id),
                "workstream_id": str(workstream["id"]),
                "action": plan["action"],
                "score": candidate["score"],
            }
        )
    result = {"success": True, "reused": False, "imported": imported, "skipped": skipped}
    cursor.execute(
        """
        INSERT INTO agent_prospecting_imports (
            id, agent_client_id, idempotency_key, report_hash, result_json
        ) VALUES (%s, %s, %s, %s, %s)
        """,
        (str(uuid.uuid4()), agent_client_id, idempotency_key, parsed_report["report_hash"], Json(result)),
    )
    conn.commit()
    return result


def load_latest_research(conn, workstream_id):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT *
        FROM lead_workstream_research
        WHERE workstream_id = %s
        ORDER BY researched_at DESC, created_at DESC
        LIMIT 1
        """,
        (workstream_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def prepare_workstream_artifacts(workstream_id, agent_client_id):
    from pg_db_utils import get_db_connection
    from api import admin_prospecting

    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT ws.*, l.name AS lead_name
            FROM lead_workstreams ws
            JOIN prospectingleads l ON l.id = ws.lead_id
            WHERE ws.id = %s
            LIMIT 1
            """,
            (workstream_id,),
        )
        workstream = cursor.fetchone()
        if not workstream:
            raise LookupError("Lead workstream not found")
        workstream = dict(workstream)
        cursor.execute("SELECT owner_user_id FROM agent_clients WHERE id = %s LIMIT 1", (agent_client_id,))
        owner = cursor.fetchone()
        actor_user_id = _clean_text(owner.get("owner_user_id") if owner else "", 120)
        if not actor_user_id:
            raise LookupError("Agent client owner was not found")
        channel = _clean_text(workstream.get("selected_channel"), 40) or "manual"
        lead_id = str(workstream["lead_id"])
        workstream_type = str(workstream["workstream_type"])
        business_id = _clean_text(workstream.get("client_business_id"), 120)
        if not grant_allows(cursor, agent_client_id, workstream_type, business_id or None):
            raise PermissionError("Agent client has no grant for this lead workstream")
    finally:
        conn.close()

    if workstream_type == LOCALOS_SALES:
        result = admin_prospecting._prepare_client_sales_room(
            lead_id=lead_id,
            user_id=actor_user_id,
            data_mode="template",
            channel=channel,
            workstream_id=workstream_id,
            reuse_existing=True,
        )
    else:
        result = admin_prospecting._prepare_partnership_sales_room(
            lead_id=lead_id,
            business_id=business_id,
            user_id=actor_user_id,
            data_mode="template",
            channel=channel,
            reuse_existing=True,
            workstream_id=workstream_id,
        )
    result["external_send_performed"] = False
    return result
