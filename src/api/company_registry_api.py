from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json, RealDictCursor

from auth_system import verify_session
from database_manager import DatabaseManager
from services.company_registry_service import get_company_detail, list_companies, list_company_map_points
from services.lead_workstream_service import create_workstream


company_registry_bp = Blueprint("company_registry_api", __name__)


def _enabled() -> bool:
    return str(os.getenv("COMPANY_REGISTRY_ENABLED", "true")).strip().lower() in {"1", "true", "yes", "on"}


def _token() -> str:
    header = str(request.headers.get("Authorization") or "")
    return header.split(" ", 1)[1].strip() if header.startswith("Bearer ") else ""


def _auth() -> tuple[dict | None, tuple | None]:
    if not _enabled():
        return None, (jsonify({"error": "company_registry_disabled"}), 404)
    user = verify_session(_token()) if _token() else None
    if not user:
        return None, (jsonify({"error": "unauthorized"}), 401)
    if user.get("is_active") is False:
        return None, (jsonify({"error": "account_blocked"}), 403)
    db = DatabaseManager()
    try:
        result = dict(user)
        result["is_superadmin"] = bool(db.is_superadmin(str(user.get("user_id") or user.get("id") or "")))
        return result, None
    finally:
        db.close()


def _superadmin() -> tuple[dict | None, tuple | None]:
    user, error = _auth()
    if error:
        return None, error
    if not user or not user.get("is_superadmin"):
        return None, (jsonify({"error": "forbidden"}), 403)
    return user, None


def _user_id(user: dict) -> str:
    return str(user.get("user_id") or user.get("id") or "")


@company_registry_bp.route("/api/companies", methods=["GET"])
def companies_list():
    user, error = _auth()
    if error:
        return error
    try:
        cursor_value = max(0, int(request.args.get("cursor") or 0))
        limit_value = max(1, min(int(request.args.get("limit") or 30), 100))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_pagination"}), 400
    db = DatabaseManager()
    try:
        result = list_companies(
            db.conn,
            user_id=_user_id(user or {}),
            is_superadmin=bool((user or {}).get("is_superadmin")),
            search=str(request.args.get("search") or ""),
            role=str(request.args.get("role") or ""),
            category=str(request.args.get("category") or ""),
            city=str(request.args.get("city") or ""),
            status=str(request.args.get("status") or ""),
            cursor_value=cursor_value,
            limit=limit_value,
        )
        return jsonify({"success": True, **result})
    except Exception:
        return jsonify({"error": "company_registry_unavailable"}), 503
    finally:
        db.close()


@company_registry_bp.route("/api/admin/companies/map", methods=["GET"])
def companies_map():
    user, error = _superadmin()
    if error:
        return error
    db = DatabaseManager()
    try:
        summary_only = str(request.args.get("summary_only") or "").strip().lower() in {"1", "true", "yes", "on"}
        result = list_company_map_points(
            db.conn,
            user_id=_user_id(user or {}),
            is_superadmin=True,
            search=str(request.args.get("search") or ""),
            role=str(request.args.get("role") or ""),
            category=str(request.args.get("category") or ""),
            status=str(request.args.get("status") or ""),
            include_points=not summary_only,
        )
        return jsonify({"success": True, **result})
    except Exception:
        return jsonify({"error": "company_map_unavailable"}), 503
    finally:
        db.close()


@company_registry_bp.route("/api/companies/<company_id>", methods=["GET"])
def company_detail(company_id: str):
    user, error = _auth()
    if error:
        return error
    db = DatabaseManager()
    try:
        detail = get_company_detail(
            db.conn,
            company_id=company_id,
            user_id=_user_id(user or {}),
            is_superadmin=bool((user or {}).get("is_superadmin")),
        )
        if not detail:
            return jsonify({"error": "company_not_found"}), 404
        return jsonify({"success": True, **detail})
    except Exception:
        return jsonify({"error": "company_registry_unavailable"}), 503
    finally:
        db.close()


@company_registry_bp.route("/api/companies/by-business/<business_id>", methods=["GET"])
def company_by_business(business_id: str):
    user, error = _auth()
    if error:
        return error
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor(cursor_factory=RealDictCursor)
        if (user or {}).get("is_superadmin"):
            cursor.execute(
                """
                SELECT company_id
                FROM business_company_links
                WHERE business_id = %s
                ORDER BY is_primary DESC, created_at ASC
                LIMIT 1
                """,
                (business_id,),
            )
        else:
            cursor.execute(
                """
                SELECT link.company_id
                FROM business_company_links link
                JOIN businesses business ON business.id = link.business_id
                LEFT JOIN networks network ON network.id = business.network_id
                WHERE link.business_id = %s
                  AND (business.owner_id = %s OR network.owner_id = %s)
                ORDER BY link.is_primary DESC, link.created_at ASC
                LIMIT 1
                """,
                (business_id, _user_id(user or {}), _user_id(user or {})),
            )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return jsonify({"error": "company_not_found"}), 404
        company_id = str(row.get("company_id") if hasattr(row, "get") else row[0])
        detail = get_company_detail(
            db.conn,
            company_id=company_id,
            user_id=_user_id(user or {}),
            is_superadmin=bool((user or {}).get("is_superadmin")),
        )
        if not detail:
            return jsonify({"error": "company_not_found"}), 404
        return jsonify({"success": True, **detail})
    except Exception:
        return jsonify({"error": "company_registry_unavailable"}), 503
    finally:
        db.close()


@company_registry_bp.route("/api/companies/<company_id>/workstreams", methods=["POST"])
def company_add_to_work(company_id: str):
    user, error = _auth()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    requested_business_id = str(payload.get("business_id") or "").strip()
    db = DatabaseManager()
    try:
        detail = get_company_detail(
            db.conn,
            company_id=company_id,
            user_id=_user_id(user or {}),
            is_superadmin=bool((user or {}).get("is_superadmin")),
        )
        if not detail:
            return jsonify({"error": "company_not_found"}), 404
        cursor = db.conn.cursor(cursor_factory=RealDictCursor)
        workstream_type = "localos_sales" if (user or {}).get("is_superadmin") and not requested_business_id else "client_partnership"
        if workstream_type == "client_partnership":
            if (user or {}).get("is_superadmin"):
                cursor.execute("SELECT id FROM businesses WHERE id = %s", (requested_business_id,))
            else:
                cursor.execute(
                    """
                    SELECT business.id
                    FROM businesses business
                    LEFT JOIN networks network ON network.id = business.network_id
                    WHERE business.id = %s AND (business.owner_id = %s OR network.owner_id = %s)
                    """,
                    (requested_business_id, _user_id(user or {}), _user_id(user or {})),
                )
            if not cursor.fetchone():
                return jsonify({"error": "business_scope_forbidden"}), 403
        cursor.execute(
            """
            SELECT lead.id
            FROM prospectingleads lead
            JOIN lead_workstreams workstream ON workstream.lead_id = lead.id
            WHERE lead.company_id = %s
              AND workstream.workstream_type = %s
              AND (%s = 'localos_sales' OR workstream.client_business_id = %s)
            ORDER BY workstream.created_at ASC
            LIMIT 1
            """,
            (company_id, workstream_type, workstream_type, requested_business_id or None),
        )
        existing = cursor.fetchone()
        if existing:
            lead_id = str(existing.get("id") if hasattr(existing, "get") else existing[0])
            cursor.close()
            return jsonify({"success": True, "reused": True, "lead_id": lead_id, "workstream_type": workstream_type})
        company = detail["company"]
        location = next((item for item in detail.get("locations", []) if item.get("is_primary")), (detail.get("locations") or [{}])[0])
        profile = (detail.get("external_profiles") or [{}])[0]
        contacts = detail.get("contacts") or []
        contact = lambda kind: next((str(item.get("value") or "") for item in contacts if item.get("contact_type") == kind), "")
        lead_id = db.save_lead(
            {
                "name": company.get("canonical_name") or company.get("name"),
                "address": location.get("address"),
                "city": location.get("city"),
                "phone": contact("phone"),
                "email": contact("email"),
                "website": contact("website"),
                "source_url": profile.get("canonical_url"),
                "category": company.get("primary_category"),
                "status": "new",
                "source": "company_registry",
            }
        )
        cursor = db.conn.cursor()
        cursor.execute(
            "UPDATE prospectingleads SET company_id = %s, company_location_id = %s WHERE id = %s",
            (company_id, location.get("id"), lead_id),
        )
        workstream = create_workstream(
            db.conn,
            lead_id=lead_id,
            workstream_type=workstream_type,
            client_business_id=requested_business_id or None,
            actor_id=_user_id(user or {}),
        )
        db.conn.commit()
        return jsonify({"success": True, "reused": False, "lead_id": lead_id, "workstream": workstream})
    except Exception:
        db.conn.rollback()
        return jsonify({"error": "company_workstream_failed"}), 409
    finally:
        db.close()


@company_registry_bp.route("/api/companies/<company_id>/timeline", methods=["GET"])
def company_timeline(company_id: str):
    user, error = _auth()
    if error:
        return error
    db = DatabaseManager()
    try:
        detail = get_company_detail(db.conn, company_id=company_id, user_id=_user_id(user or {}), is_superadmin=bool((user or {}).get("is_superadmin")))
        if not detail:
            return jsonify({"error": "company_not_found"}), 404
        return jsonify({"success": True, "company_id": company_id, "items": detail.get("timeline", []), "cursor": None, "as_of": datetime.now(timezone.utc).isoformat()})
    finally:
        db.close()


@company_registry_bp.route("/api/companies/<company_id>/audits", methods=["GET"])
def company_audits(company_id: str):
    user, error = _auth()
    if error:
        return error
    db = DatabaseManager()
    try:
        detail = get_company_detail(db.conn, company_id=company_id, user_id=_user_id(user or {}), is_superadmin=bool((user or {}).get("is_superadmin")))
        if not detail:
            return jsonify({"error": "company_not_found"}), 404
        return jsonify({"success": True, "company_id": company_id, "items": detail.get("audits", []), "cursor": None, "as_of": datetime.now(timezone.utc).isoformat()})
    finally:
        db.close()


@company_registry_bp.route("/api/admin/companies/duplicates", methods=["GET"])
def company_duplicates():
    _, error = _superadmin()
    if error:
        return error
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT key.key_type, key.normalized_value, COUNT(DISTINCT key.company_id) AS companies_count,
                   JSONB_AGG(DISTINCT JSONB_BUILD_OBJECT('id', company.id, 'name', company.canonical_name)) AS companies
            FROM company_identity_keys key
            JOIN companies company ON company.id = key.company_id
            WHERE key.verification_status <> 'rejected' AND company.status IN ('observed', 'active')
            GROUP BY key.key_type, key.normalized_value
            HAVING COUNT(DISTINCT key.company_id) > 1
            ORDER BY COUNT(DISTINCT key.company_id) DESC
            LIMIT 100
            """
        )
        items = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        return jsonify({"success": True, "items": items, "as_of": datetime.now(timezone.utc).isoformat()})
    finally:
        db.close()


@company_registry_bp.route("/api/admin/companies/merge/preview", methods=["POST"])
def merge_preview():
    user, error = _superadmin()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    source_id = str(payload.get("source_company_id") or "")
    target_id = str(payload.get("target_company_id") or "")
    if not source_id or not target_id or source_id == target_id:
        return jsonify({"error": "invalid_merge_targets"}), 400
    action_id = str(uuid.uuid4())
    idempotency_key = str(payload.get("idempotency_key") or uuid.uuid4())
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, canonical_name, status FROM companies WHERE id = ANY(%s::uuid[])", ([source_id, target_id],))
        rows = [dict(row) for row in cursor.fetchall()]
        if len(rows) != 2:
            return jsonify({"error": "company_not_found"}), 404
        cursor.execute(
            """
            INSERT INTO company_merge_events (
                id, source_company_id, target_company_id, reason, evidence_json,
                idempotency_key, created_by, expires_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO UPDATE SET updated_at = NOW()
            RETURNING id, expires_at
            """,
            (action_id, source_id, target_id, str(payload.get("reason") or "manual_review"), Json(payload.get("evidence") or {}), idempotency_key, _user_id(user or {}), datetime.now(timezone.utc) + timedelta(minutes=30)),
        )
        action = dict(cursor.fetchone())
        db.conn.commit()
        return jsonify({"success": True, "action_id": str(action["id"]), "source_company_id": source_id, "target_company_id": target_id, "companies": rows, "changes": ["Объединить идентичность и историю", "Сохранить исходный ID как merged"], "requires_confirmation": True, "expires_at": action["expires_at"]})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@company_registry_bp.route("/api/admin/companies/merge/<action_id>/confirm", methods=["POST"])
def merge_confirm(action_id: str):
    user, error = _superadmin()
    if error:
        return error
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM company_merge_events WHERE id = %s FOR UPDATE", (action_id,))
        event = cursor.fetchone()
        if not event:
            return jsonify({"error": "merge_preview_not_found"}), 404
        event = dict(event)
        if event.get("status") == "confirmed":
            return jsonify({"success": True, "idempotent": True, "result": event.get("result_json") or {}})
        if event.get("expires_at") and event["expires_at"] < datetime.now(timezone.utc):
            cursor.execute("UPDATE company_merge_events SET status = 'expired', updated_at = NOW() WHERE id = %s", (action_id,))
            db.conn.commit()
            return jsonify({"error": "merge_preview_expired"}), 409
        source_id = str(event["source_company_id"])
        target_id = str(event["target_company_id"])
        cursor.execute(
            """
            INSERT INTO business_company_links (business_id, company_id, company_location_id, relation_role, is_primary)
            SELECT business_id, %s, company_location_id, relation_role, is_primary
            FROM business_company_links WHERE company_id = %s
            ON CONFLICT DO NOTHING
            """,
            (target_id, source_id),
        )
        cursor.execute("DELETE FROM business_company_links WHERE company_id = %s", (source_id,))
        cursor.execute("UPDATE company_locations SET company_id = %s, is_primary = FALSE, updated_at = NOW() WHERE company_id = %s", (target_id, source_id))
        cursor.execute("UPDATE company_identity_keys SET company_id = %s, updated_at = NOW() WHERE company_id = %s", (target_id, source_id))
        cursor.execute("UPDATE company_contact_points SET company_id = %s, updated_at = NOW() WHERE company_id = %s", (target_id, source_id))
        cursor.execute("UPDATE company_observations SET company_id = %s, updated_at = NOW() WHERE company_id = %s", (target_id, source_id))
        cursor.execute(
            """
            INSERT INTO company_social_source_links (
                company_id, company_location_id, source_id, relation_type, confidence,
                verification_status, evidence_json, created_at, updated_at
            )
            SELECT %s, company_location_id, source_id, relation_type, confidence,
                   verification_status, evidence_json, created_at, NOW()
            FROM company_social_source_links WHERE company_id = %s
            ON CONFLICT (company_id, source_id, relation_type) DO NOTHING
            """,
            (target_id, source_id),
        )
        cursor.execute("DELETE FROM company_social_source_links WHERE company_id = %s", (source_id,))
        cursor.execute(
            """
            INSERT INTO company_relationships (
                subject_company_id, object_company_id, context_business_id, relationship_type,
                status, source_url, confidence, created_at, updated_at
            )
            SELECT
                CASE WHEN subject_company_id = %s THEN %s ELSE subject_company_id END,
                CASE WHEN object_company_id = %s THEN %s ELSE object_company_id END,
                context_business_id, relationship_type, status, source_url, confidence, created_at, NOW()
            FROM company_relationships
            WHERE (subject_company_id = %s OR object_company_id = %s)
              AND NOT (
                  (subject_company_id = %s AND object_company_id = %s)
                  OR (subject_company_id = %s AND object_company_id = %s)
              )
            ON CONFLICT DO NOTHING
            """,
            (source_id, target_id, source_id, target_id, source_id, source_id, source_id, target_id, target_id, source_id),
        )
        cursor.execute("DELETE FROM company_relationships WHERE subject_company_id = %s OR object_company_id = %s", (source_id, source_id))
        cursor.execute("UPDATE prospectingleads SET company_id = %s, updated_at = NOW() WHERE company_id = %s", (target_id, source_id))
        cursor.execute(
            """
            DO $$ BEGIN
                IF to_regclass('public.partnership_partner_cards') IS NOT NULL THEN
                    UPDATE partnership_partner_cards SET company_id = %s, updated_at = NOW() WHERE company_id = %s;
                END IF;
            END $$
            """,
            (target_id, source_id),
        )
        cursor.execute("UPDATE companies SET status = 'merged', merged_into_company_id = %s, updated_at = NOW() WHERE id = %s", (target_id, source_id))
        result = {"source_company_id": source_id, "company_id": target_id, "merged_at": datetime.now(timezone.utc).isoformat()}
        cursor.execute("UPDATE company_merge_events SET status = 'confirmed', confirmed_at = NOW(), result_json = %s, updated_at = NOW() WHERE id = %s", (Json(result), action_id))
        db.conn.commit()
        return jsonify({"success": True, "idempotent": False, "result": result})
    except Exception:
        db.conn.rollback()
        return jsonify({"error": "merge_failed"}), 409
    finally:
        db.close()
