"""Revocable authorization for Riderra buyer first-touch template records.

The grant is an append-only sender permission event.  It contains a closed
membership manifest; callers cannot turn arbitrary text into an approved send.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg2.extras import Json

from services.outreach_safety_service import research_source_fact_fingerprint


PERMISSION_KIND = "riderra_buyer_template"
PRICEBOOK_ATTESTATION_KIND = "riderra_pricebook_snapshot"
APPROVAL_MODE = "riderra_template"
BUSINESS_ID = "edbd961a-273f-4f15-836e-33aacc0aa0e3"
SENDER_ACCOUNT_ID = "5e9ce7db-44d1-49dc-9aed-b35ed7174089"
SENDER_IDENTITY = "riderracs@gmail.com"
AUTHORIZATION_REFERENCE = "codex:019fd1f3-f2a4-7ea3-8741-0b54ffec3b7e/01a084f0-4624-7650-82d3-8c86c9771af7"
PRICEBOOK_ID = "17YqqHe0TgDvUgXDNq0FeYe7113R2LTZza4musWLjEUo"
PRICEBOOK_SHEET = "Актуальный полный"
PRICEBOOK_PROVIDER = "Google Sheets via configured Google Drive connector"
DAILY_LIMIT = 150
TIMEZONE = "Europe/Moscow"
MANIFEST_VERSION = 1
TEMPLATE_VERSION = "riderra-buyer-first-email-v1"
APPROVED_TEMPLATE_ARTIFACT_SHA256 = "00862a0e8b463746a58f4008702d5151690f416ecd12548e412f9fc2ef524237"
APPROVED_TEMPLATE_DEFINITION_SHA256 = "40ad6f4afa17cc1180ca65902194d6da4fb8802ea9171dbcb05ea70de83d7854"

SUBJECT_TEMPLATE = "{company} | Riderra | {city} airport transfers"

BODY_TEMPLATE = """Hello {company} team,

{opening}

I'm Alex from Riderra. Large transfer brands can add intermediaries without improving the transfer itself.

We keep the chain short, so most of your payment goes to the local operator. We have over 10 years of experience and a 0.24% complaint rate. We've arranged transfers for private aviation pilots, ministers and presidents' families.

Would you be open to trying us for a transfer from {route} for just {price} ({vehicle}, up to {pax} passengers)? You can submit a request at https://riderra.com.

Best regards,
Alex Demyanov
Riderra"""

BODY_WITHOUT_OPENING_TEMPLATE = """Hello {company} team,

I'm Alex from Riderra. Large transfer brands can add intermediaries without improving the transfer itself.

We keep the chain short, so most of your payment goes to the local operator. We have over 10 years of experience and a 0.24% complaint rate. We've arranged transfers for private aviation pilots, ministers and presidents' families.

Would you be open to trying us for a transfer from {route} for just {price} ({vehicle}, up to {pax} passengers)? You can submit a request at https://riderra.com.

Best regards,
Alex Demyanov
Riderra"""


def _hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def canonical_company_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _iso_timestamp(value: Any, *, require_fresh: bool = True) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("riderra_quote_verified_at_required")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if (parsed.tzinfo is None or parsed.astimezone(timezone.utc) > now
            or (require_fresh and now - parsed.astimezone(timezone.utc) > timedelta(hours=24))):
        raise ValueError("riderra_quote_verified_at_invalid")
    return parsed.isoformat()


def render_record(record: dict[str, Any]) -> dict[str, str]:
    company = str(record.get("company") or "").strip()
    opening = str(record.get("opening") or "").strip()
    city = str(record.get("city") or "").strip()
    quote = record.get("pricebook") if isinstance(record.get("pricebook"), dict) else {}
    route = str(quote.get("route") or "").strip()
    vehicle = str(quote.get("vehicle") or "").strip()
    price = str(quote.get("price") or "").strip()
    currency = str(quote.get("currency") or "").strip()
    pax = quote.get("pax")
    opening_variant = str(record.get("opening_variant") or "")
    if not company or not city or not route or not vehicle or not price:
        raise ValueError("riderra_template_slot_missing")
    if opening_variant == "verified_opening_v1" and not opening:
        raise ValueError("riderra_template_opening_missing")
    if opening_variant == "no_opening_v1" and opening:
        raise ValueError("riderra_template_no_opening_changed")
    if opening_variant not in {"verified_opening_v1", "no_opening_v1"}:
        raise ValueError("riderra_template_opening_variant_invalid")
    if currency not in {"EUR", "USD", "GBP"} or type(pax) is not int or pax < 1 or pax > 99:
        raise ValueError("riderra_quote_type_invalid")
    if ("\n" in company or "\n" in city
            or not re.fullmatch(r"[^{}]{2,160}", company)
            or not re.fullmatch(r"[^{}]{2,120}", city)):
        raise ValueError("riderra_template_slot_invalid")
    subject = SUBJECT_TEMPLATE.format(company=company, city=city)
    template = BODY_TEMPLATE if opening_variant == "verified_opening_v1" else BODY_WITHOUT_OPENING_TEMPLATE
    body = template.format(
        company=company, opening=opening, route=route, price=price,
        vehicle=vehicle, pax=pax,
    )
    return {"subject": subject, "body": body, "content_sha256": hashlib.sha256((subject + "\n\n" + body).encode("utf-8")).hexdigest()}


def normalize_pricebook_attestation(artifact: dict[str, Any], artifact_sha256: str) -> dict[str, Any]:
    if (not isinstance(artifact, dict)
        or
        artifact.get("spreadsheet_id") != PRICEBOOK_ID or artifact.get("sheet") != PRICEBOOK_SHEET
        or artifact.get("evidence_kind") != "provider_observed"
        or artifact.get("provider") != PRICEBOOK_PROVIDER
        or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256)
    ):
        raise ValueError("riderra_pricebook_attestation_invalid")
    verified_at = _iso_timestamp(artifact.get("verified_at"))
    rows: dict[str, list[Any]] = {}
    header_ok = False
    for item in artifact.get("ranges") or []:
        values = item.get("values") if isinstance(item, dict) else None
        row_values = values[0] if isinstance(values, list) and len(values) == 1 and isinstance(values[0], list) else None
        range_name = str(item.get("range") or "") if isinstance(item, dict) else ""
        if range_name == f"'{PRICEBOOK_SHEET}'!A1:G1" and row_values == ["Country", "From", "To", "Type", "Pax", "Price", "Currency"]:
            header_ok = True
            continue
        match = re.fullmatch(rf"'{re.escape(PRICEBOOK_SHEET)}'!A([1-9][0-9]+):G\1", range_name)
        if match and int(match.group(1)) >= 2 and row_values and len(row_values) == 7:
            rows[match.group(1)] = row_values
    if not header_ok or not rows:
        raise ValueError("riderra_pricebook_rows_missing")
    return {"artifact_sha256": artifact_sha256, "verified_at": verified_at,
            "provider": str(artifact["provider"]), "rows": rows}


def normalize_record(record: dict[str, Any], *, pricebook_attestation: dict[str, Any]) -> dict[str, Any]:
    quote = dict(record.get("pricebook") or {})
    raw_cells = pricebook_attestation.get("rows", {}).get(str(quote.get("row") or ""))
    source_row_sha256 = _hash(raw_cells) if isinstance(raw_cells, list) else ""
    if (
        str(record.get("audience") or "") != "transfer_buyer"
        or str(quote.get("spreadsheet_id") or "") != PRICEBOOK_ID
        or str(quote.get("sheet") or "") != PRICEBOOK_SHEET
        or type(quote.get("row")) is not int or quote["row"] < 2
        or not isinstance(raw_cells, list) or len(raw_cells) != 7
        or str(quote.get("source_row_sha256") or "") != source_row_sha256
        or str(quote.get("source_artifact_sha256") or "") != pricebook_attestation.get("artifact_sha256")
        or str(quote.get("source_version") or "") != pricebook_attestation.get("artifact_sha256")
        or not re.fullmatch(r"(?:facts:|report:)[0-9a-f]{64}", str(record.get("source_fact_fingerprint") or ""))
    ):
        raise ValueError("riderra_template_provenance_invalid")
    country, route_from, route_to, vehicle_cell, pax_cell, price_cell, currency_cell = [str(value).strip() for value in raw_cells]
    currency_symbol = {"EUR": "€", "USD": "$", "GBP": "£"}.get(currency_cell)
    if (
        not country or str(quote.get("route") or "") != f"{route_from} to a hotel in {route_to}"
        or str(quote.get("currency") or "") != currency_cell
        or str(quote.get("price") or "") != f"{currency_symbol}{price_cell}"
        or str(quote.get("pax") or "") != pax_cell
        or str(quote.get("vehicle") or "").lower() != re.sub(rf"\s+{re.escape(pax_cell)}\s+pax$", "", vehicle_cell, flags=re.I).lower()
    ):
        raise ValueError("riderra_quote_row_semantics_mismatch")
    quote["verified_at"] = pricebook_attestation["verified_at"]
    quote["source_row_values"] = raw_cells
    normalized = {
        "audience": "transfer_buyer",
        "lead_id": str(record.get("lead_id") or "").strip(),
        "workstream_id": str(record.get("workstream_id") or "").strip(),
        "contact_point_id": str(record.get("contact_point_id") or "").strip(),
        "recipient": str(record.get("recipient") or "").strip().lower(),
        "company": str(record.get("company") or "").strip(),
        "company_key": canonical_company_key(record.get("company")),
        "city": str(record.get("city") or "").strip(),
        "opening": str(record.get("opening") or "").strip(),
        "opening_source_url": str(record.get("opening_source_url") or "").strip(),
        "opening_variant": str(record.get("opening_variant") or "").strip(),
        "subject_route_label": f"{str(record.get('city') or '').strip()} airport transfers",
        "source_fact_fingerprint": str(record.get("source_fact_fingerprint")),
        "pricebook": quote,
    }
    if not all(normalized[key] for key in ("lead_id", "workstream_id", "contact_point_id", "recipient", "company", "city")):
        raise ValueError("riderra_template_identity_missing")
    verified_opening = normalized["opening_variant"] == "verified_opening_v1"
    no_opening = normalized["opening_variant"] == "no_opening_v1"
    if ("berlin" in normalized["city"].lower() or "@" not in normalized["recipient"]
            or "\n" in normalized["opening"]
            or (verified_opening and (
                not 20 <= len(normalized["opening"]) <= 400
                or not re.fullmatch(r"https?://[^\s]+", normalized["opening_source_url"])
            ))
            or (no_opening and (normalized["opening"] or normalized["opening_source_url"]))
            or not (verified_opening or no_opening)):
        raise ValueError("riderra_template_recipient_excluded")
    rendered = render_record(normalized)
    expected = str(record.get("content_sha256") or "")
    if expected != rendered["content_sha256"]:
        raise ValueError("riderra_template_content_hash_changed")
    normalized.update(rendered)
    return normalized


def build_manifest(records: list[dict[str, Any]], *, pricebook_attestation: dict[str, Any]) -> dict[str, Any]:
    if (not str(pricebook_attestation.get("id") or "")
            or not re.fullmatch(r"[0-9a-f]{64}", str(pricebook_attestation.get("artifact_sha256") or ""))):
        raise ValueError("riderra_pricebook_attestation_required")
    _iso_timestamp(pricebook_attestation.get("verified_at"))
    normalized = [normalize_record(record, pricebook_attestation=pricebook_attestation) for record in records]
    keys = [(record["workstream_id"], record["lead_id"], record["contact_point_id"]) for record in normalized]
    lead_ids = [record["lead_id"] for record in normalized]
    company_keys = [record["company_key"] for record in normalized]
    recipients = [record["recipient"] for record in normalized]
    if (not normalized or len(normalized) > DAILY_LIMIT
            or len(keys) != len(set(keys)) or len(lead_ids) != len(set(lead_ids))
            or len(company_keys) != len(set(company_keys))
            or len(recipients) != len(set(recipients))):
        raise ValueError("riderra_template_membership_invalid")
    body_variants = {
        "verified_opening_v1": hashlib.sha256(BODY_TEMPLATE.encode("utf-8")).hexdigest(),
        "no_opening_v1": hashlib.sha256(BODY_WITHOUT_OPENING_TEMPLATE.encode("utf-8")).hexdigest(),
    }
    template_definition = {
        "subject_template": SUBJECT_TEMPLATE,
        "body_variants": body_variants,
        "allowed_variant_ids": sorted(body_variants),
    }
    definition_sha256 = _hash(template_definition)
    if definition_sha256 != APPROVED_TEMPLATE_DEFINITION_SHA256:
        raise ValueError("riderra_approved_template_definition_changed")
    return {
        "manifest_version": MANIFEST_VERSION,
        "scope": "riderra_buyer_first_email",
        "business_id": BUSINESS_ID,
        "sender_account_id": SENDER_ACCOUNT_ID,
        "sender_identity": SENDER_IDENTITY,
        "workstream_type": "client_partnership",
        "audience": "transfer_buyer",
        "channels": ["email"],
        "daily_limit": DAILY_LIMIT,
        "timezone": TIMEZONE,
        "template_version": TEMPLATE_VERSION,
        "template_definition_sha256": definition_sha256,
        "subject_template": SUBJECT_TEMPLATE,
        "template_variants": body_variants,
        "approved_template_artifact_sha256": APPROVED_TEMPLATE_ARTIFACT_SHA256,
        "pricebook_id": PRICEBOOK_ID,
        "pricebook_sheet": PRICEBOOK_SHEET,
        "pricebook_attestation": pricebook_attestation,
        "records_sha256": _hash(normalized),
        "records": normalized,
    }


def _canonical_sender(cursor: Any, sender_account_id: str) -> dict[str, Any]:
    cursor.execute(
        """SELECT id, business_id, owner_user_id, status, outreach_enabled, health_status, capabilities_json
           FROM outreach_sender_accounts
           WHERE id = %s AND scope_type = 'business' AND business_id = %s
             AND channel = 'email' AND lower(btrim(sender_identity)) = %s""",
        (sender_account_id, BUSINESS_ID, SENDER_IDENTITY),
    )
    row = cursor.fetchone()
    return dict(row) if row else {}


def _latest_event(cursor: Any, sender_account_id: str) -> dict[str, Any]:
    cursor.execute(
        """SELECT event.id, event.event_type, event.actor_id, event.payload_json, event.created_at,
                  COALESCE(actor.is_active, FALSE) AND COALESCE(actor.is_superadmin, FALSE) AS actor_authorized
           FROM outreach_sender_account_events event
           LEFT JOIN users actor ON actor.id = event.actor_id
           WHERE event.sender_account_id = %s AND event.event_type = 'permission_changed'
             AND event.payload_json->>'permission_kind' = %s
           ORDER BY event.created_at DESC, event.id DESC LIMIT 1""",
        (sender_account_id, PERMISSION_KIND),
    )
    row = cursor.fetchone()
    return dict(row) if row else {}


def record_pricebook_attestation(cursor: Any, *, actor_id: str, artifact_bytes: bytes,
                                 evidence_reference: str) -> dict[str, Any]:
    """Import one provider-observed frozen snapshot; it does not read Sheets."""
    cursor.execute("SELECT id FROM users WHERE id=%s AND is_active=TRUE AND is_superadmin=TRUE", (actor_id,))
    if not cursor.fetchone():
        raise PermissionError("riderra_pricebook_superadmin_required")
    if not str(evidence_reference or "").strip():
        raise ValueError("riderra_pricebook_evidence_reference_required")
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"riderra-pricebook:{SENDER_ACCOUNT_ID}",))
    if not _canonical_sender(cursor, SENDER_ACCOUNT_ID):
        raise ValueError("riderra_template_sender_scope_invalid")
    artifact = json.loads(artifact_bytes)
    attestation = normalize_pricebook_attestation(artifact, hashlib.sha256(artifact_bytes).hexdigest())
    event_id = str(uuid.uuid4())
    cursor.execute(
        """INSERT INTO outreach_sender_account_events
           (id,sender_account_id,event_type,actor_id,payload_json,created_at)
           VALUES(%s,%s,'provider_snapshot_verified',%s,%s,clock_timestamp())""",
        (event_id, SENDER_ACCOUNT_ID, actor_id, Json({"snapshot_kind": PRICEBOOK_ATTESTATION_KIND,
            "attestation_id": event_id, "attestation": attestation,
            "evidence_reference": str(evidence_reference).strip()})),
    )
    return {"id": event_id, "attestation": attestation}


def load_pricebook_attestation(cursor: Any, attestation_id: str) -> dict[str, Any]:
    cursor.execute(
        """SELECT event.id,event.event_type,event.payload_json,event.created_at,
                  COALESCE(actor.is_active,FALSE) AND COALESCE(actor.is_superadmin,FALSE) AS actor_authorized
           FROM outreach_sender_account_events event LEFT JOIN users actor ON actor.id=event.actor_id
           WHERE event.id=%s AND event.sender_account_id=%s AND event.event_type='provider_snapshot_verified'
             AND event.payload_json->>'snapshot_kind'=%s""",
        (attestation_id, SENDER_ACCOUNT_ID, PRICEBOOK_ATTESTATION_KIND),
    )
    row = cursor.fetchone()
    event = dict(row) if row else {}
    payload = event.get("payload_json") if isinstance(event.get("payload_json"), dict) else {}
    attestation = payload.get("attestation") if isinstance(payload.get("attestation"), dict) else {}
    try:
        _iso_timestamp(attestation.get("verified_at"))
    except (TypeError, ValueError):
        return {}
    if (event.get("event_type") != "provider_snapshot_verified"
            or payload.get("snapshot_kind") != PRICEBOOK_ATTESTATION_KIND
            or not event.get("actor_authorized") or not event.get("created_at")
            or payload.get("attestation_id") != str(event.get("id")) or not payload.get("evidence_reference")):
        return {}
    return {"id": str(event["id"]), **attestation}


def _authorization_event(cursor: Any, sender_account_id: str, authorization_id: str | None) -> dict[str, Any]:
    if not authorization_id:
        return _latest_event(cursor, sender_account_id)
    cursor.execute(
        """SELECT event.id,event.event_type,event.actor_id,event.payload_json,event.created_at,
                  COALESCE(actor.is_active,FALSE) AND COALESCE(actor.is_superadmin,FALSE) AS actor_authorized
           FROM outreach_sender_account_events event LEFT JOIN users actor ON actor.id=event.actor_id
           WHERE event.id=%s AND event.sender_account_id=%s AND event.event_type='permission_changed'
             AND event.payload_json->>'permission_kind'=%s""",
        (authorization_id, sender_account_id, PERMISSION_KIND),
    )
    row = cursor.fetchone()
    return dict(row) if row else {}


def _revoked_after(cursor: Any, sender_account_id: str, created_at: Any) -> bool:
    cursor.execute(
        """SELECT 1 FROM outreach_sender_account_events
           WHERE sender_account_id=%s AND event_type='permission_changed'
             AND payload_json->>'permission_kind'=%s AND payload_json->>'state'='revoked'
             AND (created_at,id)>(%s,'00000000-0000-0000-0000-000000000000'::uuid)
           LIMIT 1""",
        (sender_account_id, PERMISSION_KIND, created_at),
    )
    return bool(cursor.fetchone())


def load_authorization(cursor: Any, *, sender_account_id: str = SENDER_ACCOUNT_ID,
                       authorization_id: str | None = None) -> dict[str, Any]:
    sender = _canonical_sender(cursor, sender_account_id)
    event = _authorization_event(cursor, sender_account_id, authorization_id) if sender else {}
    payload = event.get("payload_json") if isinstance(event.get("payload_json"), dict) else {}
    if (not event or event.get("event_type") != "permission_changed"
            or payload.get("permission_kind") != PERMISSION_KIND or payload.get("state") != "active"
            or (authorization_id and _revoked_after(cursor, sender_account_id, event.get("created_at")))):
        return {}
    attestation = load_pricebook_attestation(cursor, str(payload.get("pricebook_attestation_id") or "")) if payload else {}
    try:
        manifest = build_manifest((payload.get("manifest") or {}).get("records") or [], pricebook_attestation=attestation)
    except (TypeError, ValueError):
        return {}
    capabilities = sender.get("capabilities_json") if isinstance(sender.get("capabilities_json"), dict) else {}
    if (
        sender_account_id != SENDER_ACCOUNT_ID or not event.get("actor_authorized") or not event.get("created_at")
        or payload.get("grant_id") != str(event.get("id"))
        or payload.get("authorization_reference") != AUTHORIZATION_REFERENCE
        or payload.get("manifest") != manifest
        or sender.get("status") != "connected" or not sender.get("outreach_enabled")
        or sender.get("health_status") in {"paused", "blocked"}
        or capabilities.get("direct_send") is not True or capabilities.get("reply_sync") is not True
    ):
        return {}
    return {"id": str(event["id"]), "approved_by": str(event["actor_id"]), "approved_at": event["created_at"],
            "sender_account_id": sender_account_id, "authorization_reference": AUTHORIZATION_REFERENCE, "manifest": manifest}


def set_authorization(cursor: Any, *, actor_id: str, enabled: bool, records: list[dict[str, Any]],
                      authorization_reference: str, pricebook_attestation_id: str | None = None) -> dict[str, Any]:
    if type(enabled) is not bool or authorization_reference != AUTHORIZATION_REFERENCE:
        raise ValueError("riderra_template_explicit_user_reference_required")
    cursor.execute("SELECT id FROM users WHERE id=%s AND is_active=TRUE AND is_superadmin=TRUE", (actor_id,))
    if not cursor.fetchone():
        raise PermissionError("riderra_template_superadmin_required")
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"riderra-template:{SENDER_ACCOUNT_ID}",))
    if not _canonical_sender(cursor, SENDER_ACCOUNT_ID):
        raise ValueError("riderra_template_sender_scope_invalid")
    previous = _latest_event(cursor, SENDER_ACCOUNT_ID)
    previous_payload = previous.get("payload_json") if isinstance(previous.get("payload_json"), dict) else {}
    if enabled:
        attestation = load_pricebook_attestation(cursor, str(pricebook_attestation_id or ""))
        if not attestation:
            raise ValueError("riderra_pricebook_attestation_required")
        manifest = build_manifest(records, pricebook_attestation=attestation)
    else:
        # Revocation must remain possible after quote expiry or manifest damage.
        manifest = previous_payload.get("manifest") if isinstance(previous_payload.get("manifest"), dict) else {}
    event_id = str(uuid.uuid4())
    payload = {"permission_kind": PERMISSION_KIND, "state": "active" if enabled else "revoked",
               "grant_id": event_id if enabled else previous_payload.get("grant_id"),
               "manifest": manifest, "authorization_reference": authorization_reference,
               "pricebook_attestation_id": str(pricebook_attestation_id or previous_payload.get("pricebook_attestation_id") or "") or None,
               "revokes_all_prior_grants": not enabled,
               "replaces_event_id": str(previous.get("id") or "") or None}
    cursor.execute(
        """INSERT INTO outreach_sender_account_events
           (id,sender_account_id,event_type,actor_id,payload_json,created_at)
           VALUES(%s,%s,'permission_changed',%s,%s,clock_timestamp())""",
        (event_id, SENDER_ACCOUNT_ID, actor_id, Json(payload)),
    )
    return {"id": event_id, "state": payload["state"], "manifest": manifest}


def manifest_record(authorization: dict[str, Any], *, workstream_id: str, lead_id: str,
                    contact_point_id: str) -> dict[str, Any]:
    matches = [record for record in (authorization.get("manifest") or {}).get("records") or []
               if record.get("workstream_id") == workstream_id and record.get("lead_id") == lead_id
               and record.get("contact_point_id") == contact_point_id]
    return dict(matches[0]) if len(matches) == 1 else {}


def verify_database_binding(cursor: Any, record: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """SELECT ws.id AS workstream_id, ws.lead_id, ws.workstream_type, ws.client_business_id,
                  lead.name AS company, lead.city, contact.id AS contact_point_id,
                  lower(btrim(contact.normalized_value)) AS recipient,
                  contact.contact_type, contact.verification_status,
                  research.evidence_json, research.signals_json, research.report_hash,
                  research.suggested_opener, research.opener_source_url
           FROM lead_workstreams ws
           JOIN prospectingleads lead ON lead.id=ws.lead_id
           JOIN lead_contact_points contact ON contact.id=ws.selected_contact_point_id AND contact.lead_id=lead.id
           LEFT JOIN LATERAL (
             SELECT evidence_json,signals_json,report_hash,suggested_opener,opener_source_url FROM lead_workstream_research
             WHERE workstream_id=ws.id AND researched_at >= NOW()-INTERVAL '90 days'
             ORDER BY researched_at DESC,created_at DESC LIMIT 1
           ) research ON TRUE
           WHERE ws.id=%s AND ws.lead_id=%s AND contact.id=%s""",
        (record.get("workstream_id"), record.get("lead_id"), record.get("contact_point_id")),
    )
    row = cursor.fetchone()
    current = dict(row) if row else {}
    fingerprint = research_source_fact_fingerprint(current)
    if (
        not current or current.get("workstream_type") != "client_partnership"
        or str(current.get("client_business_id") or "") != BUSINESS_ID
        or str(current.get("company") or "").strip() != record.get("company")
        or canonical_company_key(current.get("company")) != record.get("company_key")
        or str(current.get("city") or "").strip() != record.get("city")
        or "berlin" in str(current.get("city") or "").lower()
        or current.get("contact_type") != "email"
        or current.get("verification_status") not in {"verified", "confirmed_source"}
        or current.get("recipient") != record.get("recipient")
        or fingerprint != record.get("source_fact_fingerprint")
        or (record.get("opening_variant") == "verified_opening_v1" and (
            str(current.get("suggested_opener") or "").strip() != record.get("opening")
            or str(current.get("opener_source_url") or "").strip() != record.get("opening_source_url")
        ))
    ):
        raise ValueError("riderra_template_database_binding_changed")
    return current


def exact_invitation(*, record: dict[str, Any], authorization: dict[str, Any], subject: str,
                     body: str, sender_account_id: str, channel: str, sequence_index: int) -> bool:
    member = manifest_record(authorization, workstream_id=str(record.get("workstream_id") or ""),
                             lead_id=str(record.get("lead_id") or ""), contact_point_id=str(record.get("contact_point_id") or ""))
    try:
        rendered = render_record(member)
    except (TypeError, ValueError):
        return False
    return bool(member == record and authorization.get("sender_account_id") == SENDER_ACCOUNT_ID
                and sender_account_id == SENDER_ACCOUNT_ID and channel == "email" and sequence_index == 0
                and subject == rendered["subject"] and body == rendered["body"])


def is_riderra_template_lane(item: dict[str, Any]) -> bool:
    policy = item.get("policy_json") if isinstance(item.get("policy_json"), dict) else {}
    return bool(
        policy.get("approval_mode") == APPROVAL_MODE
        and str(item.get("business_id") or "") == BUSINESS_ID
        and str(item.get("workstream_type") or "") == "client_partnership"
    )


def reserve_daily_company_slot(cursor: Any, *, queue_id: str, item: dict[str, Any]) -> dict[str, Any]:
    """Count queued/reserved/sent/uncertain Riderra companies for Moscow day."""
    if not is_riderra_template_lane(item):
        return {"allowed": False, "reason_code": "riderra_template_scope_invalid", "item": item}
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("riderra:buyer-daily:Europe/Moscow",))
    cursor.execute(
        """WITH automatic_activity AS (
             SELECT q.id::text AS queue_id, q.lead_id,
                    lower(regexp_replace(btrim(lead.name),'\\s+',' ','g')) AS company_key,
                    CASE
                      WHEN q.delivery_status IN ('sent','delivered') THEN COALESCE(q.sent_at,q.dispatch_started_at,q.updated_at)
                      WHEN lower(COALESCE(q.error_text,'')) LIKE '%%send_uncertain%%' THEN COALESCE(q.dispatch_started_at,q.updated_at)
                      WHEN q.delivery_status='sending' THEN COALESCE(q.dispatch_started_at,q.updated_at)
                      ELSE COALESCE(q.scheduled_at,q.created_at)
                    END AS occurred_at,
                    CASE WHEN q.delivery_status IN ('sent','delivered')
                           OR lower(COALESCE(q.error_text,'')) LIKE '%%send_uncertain%%'
                         THEN 'consumed' ELSE 'reservation' END AS accounting_state
             FROM outreachsendqueue q
             JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
             JOIN outreach_campaigns c ON c.id=t.campaign_id
             JOIN lead_workstreams ws ON ws.id=q.workstream_id
             JOIN prospectingleads lead ON lead.id=q.lead_id
             WHERE c.business_id=%s AND ws.client_business_id=%s AND ws.workstream_type='client_partnership'
               AND (q.delivery_status IN ('queued','sending','sent','delivered')
                    OR (q.delivery_status IN ('retry','failed','dlq') AND lower(COALESCE(q.error_text,'')) LIKE '%%send_uncertain%%'))
           ), manual_activity AS (
             SELECT NULL::text AS queue_id,campaign.lead_id,
                    lower(regexp_replace(btrim(lead.name),'\\s+',' ','g')) AS company_key,
                    COALESCE(
                      CASE WHEN COALESCE(pg_input_is_valid(event.payload_json->>'occurred_at','timestamp with time zone'),FALSE)
                           THEN (event.payload_json->>'occurred_at')::timestamptz ELSE NULL END,
                      event.created_at
                    ) AS occurred_at,
                    'consumed'::text AS accounting_state
             FROM outreach_campaign_events event
             JOIN outreach_campaigns campaign ON campaign.id=event.campaign_id
             JOIN lead_workstreams workstream ON workstream.id=campaign.workstream_id
             JOIN prospectingleads lead ON lead.id=campaign.lead_id
             WHERE campaign.business_id=%s AND workstream.client_business_id=%s
               AND workstream.workstream_type='client_partnership'
               AND event.event_type='manual_sent'
               AND event.payload_json->>'evidence_kind'='user_confirmed'
           ), activity AS (
             SELECT * FROM automatic_activity
             UNION ALL
             SELECT * FROM manual_activity
           ), current_item AS (
             SELECT occurred_at FROM activity WHERE queue_id=%s
           ), admitted AS (
             SELECT activity.* FROM activity CROSS JOIN current_item
             WHERE (activity.occurred_at AT TIME ZONE %s)::date=(NOW() AT TIME ZONE %s)::date
               AND (activity.accounting_state='consumed' OR activity.queue_id=%s
                    OR (activity.occurred_at,activity.queue_id)<(current_item.occurred_at,%s))
           )
           SELECT COUNT(DISTINCT company_key)::int AS company_count,
                  COALESCE(BOOL_OR(
                    (lead_id=%s OR company_key=%s) AND COALESCE(queue_id,'')<>%s
                  ),FALSE) AS duplicate_company
           FROM admitted""",
        (BUSINESS_ID, BUSINESS_ID, BUSINESS_ID, BUSINESS_ID, queue_id, TIMEZONE, TIMEZONE, queue_id, queue_id,
         item.get("lead_id"), canonical_company_key(item.get("lead_name")), queue_id),
    )
    counts = dict(cursor.fetchone() or {})
    if counts.get("duplicate_company"):
        return {"allowed": False, "reason_code": "riderra_company_already_reserved", "item": item}
    if int(counts.get("company_count") or 0) > DAILY_LIMIT:
        return {"allowed": False, "reason_code": "riderra_daily_limit_reached", "item": item}
    return {"allowed": True, "reason_code": "riderra_daily_slot_reserved",
            "riderra_daily_company_count": int(counts.get("company_count") or 0), "item": item}


def previously_contacted_buyer(cursor: Any, *, queue_id: str, item: dict[str, Any]) -> bool:
    """All-time native first-touch duplicate guard for this Riderra business."""
    normalized = re.sub(r"\s+", "", str(item.get("normalized_value") or "").lower())
    company_key = canonical_company_key(item.get("lead_name"))
    cursor.execute(
        """SELECT 1 FROM (
             SELECT previous.lead_id
             FROM outreachsendqueue previous
             JOIN outreach_campaign_touches touch ON touch.id=previous.campaign_touch_id
             JOIN outreach_campaigns campaign ON campaign.id=touch.campaign_id
             JOIN prospectingleads previous_lead ON previous_lead.id=previous.lead_id
             LEFT JOIN lead_contact_points contact ON contact.id=touch.contact_point_id
             WHERE previous.id::text<>%s AND campaign.business_id=%s
               AND (previous.lead_id=%s
                    OR (%s<>'' AND lower(regexp_replace(btrim(previous_lead.name),'\\s+',' ','g'))=%s)
                    OR (%s<>'' AND lower(regexp_replace(COALESCE(contact.normalized_value,previous.recipient_value,''),'\\s+','','g'))=%s))
               AND (previous.delivery_status IN ('sent','delivered')
                    OR lower(COALESCE(previous.error_text,'')) LIKE '%%send_uncertain%%')
             UNION ALL
             SELECT campaign.lead_id
             FROM outreach_campaign_events event
             JOIN outreach_campaigns campaign ON campaign.id=event.campaign_id
             JOIN prospectingleads manual_lead ON manual_lead.id=campaign.lead_id
             LEFT JOIN outreach_campaign_touches touch ON touch.id=event.touch_id
             LEFT JOIN lead_contact_points contact ON contact.id=touch.contact_point_id
             WHERE campaign.business_id=%s
               AND (campaign.lead_id=%s
                    OR (%s<>'' AND lower(regexp_replace(btrim(manual_lead.name),'\\s+',' ','g'))=%s)
                    OR (%s<>'' AND lower(regexp_replace(
                    COALESCE(NULLIF(event.payload_json->>'recipient_value',''),contact.normalized_value,''),
                    '\\s+','','g'))=%s))
               AND event.event_type='manual_sent' AND event.payload_json->>'evidence_kind'='user_confirmed'
           ) contacted
           LIMIT 1""",
        (queue_id, BUSINESS_ID, item.get("lead_id"), company_key, company_key, normalized, normalized,
         BUSINESS_ID, item.get("lead_id"), company_key, company_key, normalized, normalized),
    )
    return bool(cursor.fetchone())
