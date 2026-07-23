"""Public sales-room routes."""
from __future__ import annotations

from flask import Blueprint

from core.ai_learning import record_ai_learning_event

from services.sales_room_public_service import (
    AUDIT_OFFER_REQUESTABLE_STATUSES,
    CONSENT_VERSION,
    Json,
    PUBLIC_SALES_ROOM_EVENT_LIMIT,
    PUBLIC_SALES_ROOM_EVENT_WINDOW_SEC,
    PUBLIC_SALES_ROOM_FILE_LIMIT,
    PUBLIC_SALES_ROOM_MESSAGE_LIMIT,
    PUBLIC_SALES_ROOM_SUGGESTION_LIMIT,
    PUBLIC_SALES_ROOM_WRITE_WINDOW_SEC,
    RealDictCursor,
    SALES_ROOM_ALLOWED_EXTENSIONS,
    SALES_ROOM_UPLOAD_MAX_BYTES,
    _audit_offer_processing_delay_seconds,
    _build_sales_room_participant_access_token,
    _can_edit_sales_room,
    _check_public_sales_room_rate_limit,
    _clean_sales_room_filename,
    _create_sales_room_proposal_version,
    _ensure_audit_offer_user,
    _ensure_sales_room_proposal_version,
    _ensure_sales_room_tables,
    _is_uuid_string,
    _load_sales_room_audit_offer,
    _load_sales_room_by_slug,
    _load_sales_room_latest_version,
    _load_sales_room_messages,
    _load_sales_room_participant_by_token,
    _load_sales_room_review,
    _make_sales_room_url,
    _normalize_public_sales_room_proposal,
    _optional_auth,
    _participant_token_from_request,
    _public_audit_offer_allowed_for_participant,
    _public_audit_offer_visible_for_user,
    _record_sales_room_event,
    _record_sales_room_event_by_id,
    _replace_text_for_sales_room_suggestion,
    _require_auth,
    _row_to_dict,
    _sales_room_file_extension,
    _send_sales_room_participant_verification_email,
    _serialize_public_audit_offer,
    _serialize_sales_room_message,
    _serialize_sales_room_participant,
    _serialize_sales_room_suggestion,
    _serialize_sales_room_version,
    _slugify_company_name,
    _to_json_compatible,
    _update_sales_room_proposal_body,
    get_db_connection,
    io,
    jsonify,
    load_sales_room_file,
    normalize_email,
    quote,
    release_ready_audit_offers,
    request,
    secrets,
    send_file,
    store_sales_room_file,
    uuid,
)


sales_rooms_bp = Blueprint("sales_rooms_api", __name__)


@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>", methods=["GET"])
def public_sales_room(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        user_data = _optional_auth()
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            visibility = str(row.get("visibility") or "shared").strip().lower()
            can_edit = _can_edit_sales_room(cur, row, user_data)
            if visibility != "shared" and not can_edit:
                return jsonify({"error": "Sales room not found"}), 404
            _record_sales_room_event(conn, slug=normalized_slug, event_type="view", metadata={"source": "public_page"})
            conn.commit()
            room_json = row.get("room_json") if isinstance(row.get("room_json"), dict) else {}
            room_json = _normalize_public_sales_room_proposal(cur, row, room_json)
            room_json["slug"] = normalized_slug
            room_json["public_url"] = _make_sales_room_url(normalized_slug)
            room_json["permissions"] = {
                "can_edit_welcome": can_edit,
            }
            room_id = str(row.get("id") or "")
            proposal = room_json.get("proposal") if isinstance(room_json.get("proposal"), dict) else {}
            body_text = str(proposal.get("body_text") or "").strip()
            if body_text:
                latest_version = _ensure_sales_room_proposal_version(cur, room_id=room_id, body_text=body_text)
                if latest_version:
                    proposal["body_text"] = str(latest_version.get("body_text") or body_text)
                    room_json["proposal"] = proposal
            room_json["messages"] = _load_sales_room_messages(cur, str(row.get("id") or ""))
            room_json["proposal_review"] = _load_sales_room_review(cur, room_id)
            participant = _load_sales_room_participant_by_token(cur, room_id, _participant_token_from_request())
            room_json["participant"] = _serialize_sales_room_participant(participant)
            offer = _load_sales_room_audit_offer(cur, room_id)
            current_business_id = str(request.headers.get("X-LocalOS-Current-Business-Id") or "").strip()
            if _public_audit_offer_visible_for_user(cur, row, offer, user_data, current_business_id=current_business_id):
                public_offer = _serialize_public_audit_offer(offer, participant, expose_teaser=True)
            else:
                public_offer = None
            room_json["audit_offer"] = public_offer
            if public_offer:
                _record_sales_room_event_by_id(
                    cur,
                    room_id=room_id,
                    event_type="audit_offer_shown",
                    metadata={"offer_id": str(public_offer.get("id") or ""), "participant_id": str(participant.get("id") or "")},
                )
            conn.commit()
            return jsonify({"success": True, "room": _to_json_compatible(room_json)})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error loading public sales room: {e}")
        return jsonify({"error": str(e)}), 500

@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/welcome", methods=["PATCH"])
def public_sales_room_welcome(slug):
    user_data, auth_error = _require_auth()
    if auth_error:
        return auth_error
    try:
        normalized_slug = _slugify_company_name(slug)
        data = request.get_json(silent=True) or {}
        body_text = str(data.get("body_text") or "").strip()
        if not body_text:
            return jsonify({"error": "body_text is required"}), 400
        if len(body_text) > 1200:
            return jsonify({"error": "body_text is too long"}), 400
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            if not _can_edit_sales_room(cur, row, user_data):
                return jsonify({"error": "Forbidden"}), 403
            cur.execute(
                """
                UPDATE sales_rooms
                SET room_json = jsonb_set(
                        COALESCE(room_json, '{}'),
                        '{welcome,body_text}',
                        to_jsonb(%s::text),
                        TRUE
                    ),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING room_json
                """,
                (body_text, str(row.get("id") or "")),
            )
            updated = cur.fetchone() or {}
            _record_sales_room_event(
                conn,
                slug=normalized_slug,
                event_type="welcome_updated",
                metadata={"updated_by": user_data.get("user_id") or user_data.get("id")},
            )
            conn.commit()
            room_json = updated.get("room_json") if isinstance(updated.get("room_json"), dict) else {}
            welcome = room_json.get("welcome") if isinstance(room_json.get("welcome"), dict) else {}
            return jsonify({"success": True, "welcome": {"body_text": str(welcome.get("body_text") or body_text)}})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error updating public sales room welcome: {e}")
        return jsonify({"error": str(e)}), 500


@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/participants", methods=["POST"])
def public_sales_room_participant_register(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        data = request.get_json(silent=True) or {}
        email = normalize_email(str(data.get("email") or ""))
        name = str(data.get("name") or "").strip()
        company = str(data.get("company") or "").strip()
        personal_data_consent = bool(data.get("personal_data_consent"))
        consent_version = str(data.get("consent_version") or CONSENT_VERSION).strip()
        if not email:
            return jsonify({"error": "email is required"}), 400
        if not personal_data_consent:
            return jsonify({"error": "Необходимо согласие на обработку персональных данных"}), 400
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            room_id = str(row.get("id") or "")
            participant_id = str(uuid.uuid4())
            verification_token = secrets.token_urlsafe(32)
            access_token = _build_sales_room_participant_access_token(participant_id)
            cur.execute(
                """
                INSERT INTO sales_room_participants (
                    id, room_id, email, name, company, is_verified,
                    personal_data_consent_at, personal_data_consent_version, privacy_accepted_at,
                    consent_ip, consent_user_agent,
                    verification_token, access_token, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, FALSE,
                    NOW(), %s, NOW(),
                    %s, %s,
                    %s, %s, NOW(), NOW()
                )
                ON CONFLICT (room_id, email) DO UPDATE
                SET name = COALESCE(NULLIF(EXCLUDED.name, ''), sales_room_participants.name),
                    company = COALESCE(NULLIF(EXCLUDED.company, ''), sales_room_participants.company),
                    personal_data_consent_at = COALESCE(sales_room_participants.personal_data_consent_at, EXCLUDED.personal_data_consent_at),
                    personal_data_consent_version = COALESCE(sales_room_participants.personal_data_consent_version, EXCLUDED.personal_data_consent_version),
                    privacy_accepted_at = COALESCE(sales_room_participants.privacy_accepted_at, EXCLUDED.privacy_accepted_at),
                    consent_ip = COALESCE(sales_room_participants.consent_ip, EXCLUDED.consent_ip),
                    consent_user_agent = COALESCE(sales_room_participants.consent_user_agent, EXCLUDED.consent_user_agent),
                    verification_token = CASE
                        WHEN sales_room_participants.is_verified THEN sales_room_participants.verification_token
                        ELSE EXCLUDED.verification_token
                    END,
                    access_token = COALESCE(sales_room_participants.access_token, EXCLUDED.access_token),
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    participant_id,
                    room_id,
                    email,
                    name,
                    company,
                    consent_version,
                    request.headers.get("X-Forwarded-For") or request.remote_addr,
                    request.headers.get("User-Agent"),
                    verification_token,
                    access_token,
                ),
            )
            participant = _row_to_dict(cur.fetchone())
            token_for_email = str(participant.get("verification_token") or verification_token)
            participant_token = str(participant.get("access_token") or access_token)
            email_sent = True
            if not bool(participant.get("is_verified")):
                email_sent = _send_sales_room_participant_verification_email(
                    email=email,
                    name=name,
                    slug=normalized_slug,
                    participant_token=participant_token,
                    verification_token=token_for_email,
                )
            _record_sales_room_event_by_id(
                cur,
                room_id=room_id,
                event_type="participant_registered",
                metadata={"participant_id": str(participant.get("id") or ""), "email": email, "email_sent": bool(email_sent)},
            )
            conn.commit()
            return jsonify(
                {
                    "success": True,
                    "participant_token": participant_token,
                    "participant": _serialize_sales_room_participant(participant),
                    "email_sent": bool(email_sent),
                    "verification_required": not bool(participant.get("is_verified")),
                }
            )
        finally:
            conn.close()
    except Exception as e:
        print(f"Error registering public sales room participant: {e}")
        return jsonify({"error": str(e)}), 500


@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/participants/verify", methods=["POST"])
def public_sales_room_participant_verify(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        data = request.get_json(silent=True) or {}
        verification_token = str(data.get("verification_token") or "").strip()
        participant_token = str(data.get("participant_token") or "").strip()
        if not verification_token:
            return jsonify({"error": "verification_token is required"}), 400
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            room_id = str(row.get("id") or "")
            params = [room_id, verification_token]
            token_clause = ""
            if participant_token:
                token_clause = " AND access_token = %s"
                params.append(participant_token)
            cur.execute(
                f"""
                UPDATE sales_room_participants
                SET is_verified = TRUE,
                    verified_at = COALESCE(verified_at, NOW()),
                    verification_token = NULL,
                    updated_at = NOW()
                WHERE room_id = %s
                  AND verification_token = %s
                  {token_clause}
                RETURNING *
                """,
                tuple(params),
            )
            participant = _row_to_dict(cur.fetchone())
            if not participant:
                return jsonify({"error": "Verification link is invalid or already used"}), 400
            _record_sales_room_event_by_id(
                cur,
                room_id=room_id,
                event_type="participant_verified",
                metadata={"participant_id": str(participant.get("id") or ""), "email": str(participant.get("email") or "")},
            )
            conn.commit()
            return jsonify(
                {
                    "success": True,
                    "participant_token": str(participant.get("access_token") or ""),
                    "participant": _serialize_sales_room_participant(participant),
                }
            )
        finally:
            conn.close()
    except Exception as e:
        print(f"Error verifying public sales room participant: {e}")
        return jsonify({"error": str(e)}), 500


@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/audit-offer/request", methods=["POST"])
def public_sales_room_audit_offer_request(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            room_id = str(row.get("id") or "")
            participant = _load_sales_room_participant_by_token(cur, room_id, _participant_token_from_request())
            if not participant or not bool(participant.get("is_verified")):
                return jsonify({"error": "Verified room participant is required"}), 403
            offer = _load_sales_room_audit_offer(cur, room_id, for_update=True)
            if not _public_audit_offer_allowed_for_participant(offer, participant):
                return jsonify({"error": "Audit offer is not available"}), 403
            status = str(offer.get("status") or "").strip().lower()
            if status in AUDIT_OFFER_REQUESTABLE_STATUSES:
                user_id = _ensure_audit_offer_user(str(participant.get("email") or ""), str(participant.get("name") or ""))
                cur.execute(
                    """
                    UPDATE sales_room_audit_offers
                    SET status = 'processing',
                        requested_by_participant_id = %s,
                        requested_user_id = NULLIF(%s, '')::uuid,
                        requested_at = COALESCE(requested_at, NOW()),
                        processing_started_at = COALESCE(processing_started_at, NOW()),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (participant.get("id"), user_id, offer.get("id")),
                )
                offer = _row_to_dict(cur.fetchone())
                _record_sales_room_event_by_id(
                    cur,
                    room_id=room_id,
                    event_type="audit_offer_requested",
                    metadata={"offer_id": str(offer.get("id") or ""), "participant_id": str(participant.get("id") or "")},
                )
                _record_sales_room_event_by_id(
                    cur,
                    room_id=room_id,
                    event_type="audit_offer_processing_started",
                    metadata={"offer_id": str(offer.get("id") or ""), "delay_seconds": _audit_offer_processing_delay_seconds()},
                )
            conn.commit()
            return jsonify({"success": True, "audit_offer": _serialize_public_audit_offer(offer, participant)})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error requesting public sales room audit offer: {e}")
        return jsonify({"error": str(e)}), 500


@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/audit-offer/status", methods=["GET"])
def public_sales_room_audit_offer_status(slug):
    try:
        release_ready_audit_offers()
        normalized_slug = _slugify_company_name(slug)
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            room_id = str(row.get("id") or "")
            participant = _load_sales_room_participant_by_token(cur, room_id, _participant_token_from_request())
            offer = _load_sales_room_audit_offer(cur, room_id)
            public_offer = _serialize_public_audit_offer(offer, participant)
            if not public_offer:
                return jsonify({"error": "Audit offer is not available"}), 403
            return jsonify({"success": True, "audit_offer": public_offer})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error loading public sales room audit offer status: {e}")
        return jsonify({"error": str(e)}), 500


@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/audit-offer/opened", methods=["POST"])
def public_sales_room_audit_offer_opened(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            room_id = str(row.get("id") or "")
            participant = _load_sales_room_participant_by_token(cur, room_id, _participant_token_from_request())
            offer = _load_sales_room_audit_offer(cur, room_id, for_update=True)
            public_offer = _serialize_public_audit_offer(offer, participant)
            if not public_offer or not public_offer.get("audit_url"):
                return jsonify({"error": "Audit is not ready"}), 403
            if str(offer.get("status") or "") != "opened":
                cur.execute(
                    """
                    UPDATE sales_room_audit_offers
                    SET status = 'opened',
                        opened_at = COALESCE(opened_at, NOW()),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (offer.get("id"),),
                )
                offer = _row_to_dict(cur.fetchone())
                _record_sales_room_event_by_id(
                    cur,
                    room_id=room_id,
                    event_type="audit_offer_opened",
                    metadata={"offer_id": str(offer.get("id") or ""), "participant_id": str(participant.get("id") or "")},
                )
            conn.commit()
            return jsonify({"success": True, "audit_offer": _serialize_public_audit_offer(offer, participant)})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error marking public sales room audit offer opened: {e}")
        return jsonify({"error": str(e)}), 500

@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/proposal/suggestions", methods=["POST"])
def public_sales_room_proposal_suggestion(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        rate_limit_response = _check_public_sales_room_rate_limit(
            "suggestion",
            normalized_slug,
            PUBLIC_SALES_ROOM_SUGGESTION_LIMIT,
            PUBLIC_SALES_ROOM_WRITE_WINDOW_SEC,
        )
        if rate_limit_response:
            return rate_limit_response
        data = request.get_json(silent=True) or {}
        author_name = str(data.get("author_name") or "").strip()
        author_contact = str(data.get("author_contact") or "").strip()
        suggestion_type = str(data.get("suggestion_type") or "replace").strip().lower()
        selection_text = str(data.get("selection_text") or "").strip()
        replacement_text = str(data.get("replacement_text") or "").strip()
        comment_text = str(data.get("comment_text") or "").strip()
        if suggestion_type not in {"replace", "comment"}:
            return jsonify({"error": "suggestion_type must be replace or comment"}), 400
        if not author_name:
            return jsonify({"error": "author_name is required"}), 400
        if not author_contact:
            return jsonify({"error": "author_contact is required"}), 400
        if not selection_text:
            return jsonify({"error": "selection_text is required"}), 400
        if suggestion_type == "replace" and not replacement_text:
            return jsonify({"error": "replacement_text is required"}), 400
        if suggestion_type == "comment" and not comment_text:
            return jsonify({"error": "comment_text is required"}), 400
        if len(selection_text) > 2000 or len(replacement_text) > 4000 or len(comment_text) > 2000:
            return jsonify({"error": "suggestion is too long"}), 400
        selection_start = data.get("selection_start")
        selection_end = data.get("selection_end")
        try:
            normalized_start = int(selection_start) if selection_start is not None else None
            normalized_end = int(selection_end) if selection_end is not None else None
        except (TypeError, ValueError):
            normalized_start = None
            normalized_end = None
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            room_json = row.get("room_json") if isinstance(row.get("room_json"), dict) else {}
            room_json = _normalize_public_sales_room_proposal(cur, row, room_json)
            proposal = room_json.get("proposal") if isinstance(room_json.get("proposal"), dict) else {}
            body_text = str(proposal.get("body_text") or "").strip()
            room_id = str(row.get("id") or "")
            version = _ensure_sales_room_proposal_version(cur, room_id=room_id, body_text=body_text)
            suggestion_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO sales_room_proposal_suggestions (
                    id, room_id, version_id, suggestion_type, selection_text, selection_start, selection_end,
                    replacement_text, comment_text, author_name, author_contact, status, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, 'pending', NOW(), NOW()
                )
                RETURNING id, version_id, suggestion_type, selection_text, selection_start, selection_end,
                          replacement_text, comment_text, author_name, author_contact, status,
                          resolved_by_name, resolved_by_contact, resolved_at, created_at, updated_at
                """,
                (
                    suggestion_id,
                    room_id,
                    version.get("id"),
                    suggestion_type,
                    selection_text,
                    normalized_start,
                    normalized_end,
                    replacement_text,
                    comment_text,
                    author_name,
                    author_contact,
                ),
            )
            suggestion = _serialize_sales_room_suggestion(dict(cur.fetchone()))
            _record_sales_room_event(
                conn,
                slug=normalized_slug,
                event_type="proposal_suggestion_created",
                metadata={"suggestion_id": suggestion_id, "suggestion_type": suggestion_type},
            )
            conn.commit()
            return jsonify({"success": True, "suggestion": suggestion})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error creating public sales room proposal suggestion: {e}")
        return jsonify({"error": str(e)}), 500

@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/proposal/suggestions/<string:suggestion_id>/resolve", methods=["POST"])
def public_sales_room_proposal_suggestion_resolve(slug, suggestion_id):
    try:
        normalized_slug = _slugify_company_name(slug)
        rate_limit_response = _check_public_sales_room_rate_limit(
            "suggestion-resolve",
            normalized_slug,
            PUBLIC_SALES_ROOM_SUGGESTION_LIMIT,
            PUBLIC_SALES_ROOM_WRITE_WINDOW_SEC,
        )
        if rate_limit_response:
            return rate_limit_response
        normalized_suggestion_id = str(suggestion_id or "").strip()
        if not _is_uuid_string(normalized_suggestion_id):
            return jsonify({"error": "Suggestion not found"}), 404
        data = request.get_json(silent=True) or {}
        action = str(data.get("action") or "").strip().lower()
        author_name = str(data.get("author_name") or "").strip()
        author_contact = str(data.get("author_contact") or "").strip()
        if action not in {"accept", "reject"}:
            return jsonify({"error": "action must be accept or reject"}), 400
        if not author_name:
            return jsonify({"error": "author_name is required"}), 400
        if not author_contact:
            return jsonify({"error": "author_contact is required"}), 400
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            room_id = str(row.get("id") or "")
            cur.execute(
                """
                SELECT id, version_id, suggestion_type, selection_text, selection_start, selection_end,
                       replacement_text, comment_text, author_name, author_contact, status,
                       resolved_by_name, resolved_by_contact, resolved_at, created_at, updated_at
                FROM sales_room_proposal_suggestions
                WHERE id = %s
                  AND room_id = %s
                LIMIT 1
                """,
                (normalized_suggestion_id, room_id),
            )
            suggestion = dict(cur.fetchone() or {})
            if not suggestion:
                return jsonify({"error": "Suggestion not found"}), 404
            if str(suggestion.get("status") or "") != "pending":
                return jsonify({"error": "Suggestion already resolved"}), 409
            latest = _load_sales_room_latest_version(cur, room_id)
            current_text = str(latest.get("body_text") or "")
            next_text = current_text
            applied_by = ""
            if action == "accept" and str(suggestion.get("suggestion_type") or "replace") == "replace":
                next_text, applied, applied_by = _replace_text_for_sales_room_suggestion(current_text, suggestion)
                if not applied:
                    return jsonify({"error": "selection_not_found", "reason": applied_by}), 409
                version = _create_sales_room_proposal_version(
                    cur,
                    room_id=room_id,
                    body_text=next_text,
                    author_name=author_name,
                    author_contact=author_contact,
                    metadata={"accepted_suggestion_id": normalized_suggestion_id, "applied_by": applied_by},
                )
                _update_sales_room_proposal_body(cur, room_id=room_id, body_text=next_text)
            else:
                version = latest
            next_status = "accepted" if action == "accept" else "rejected"
            cur.execute(
                """
                UPDATE sales_room_proposal_suggestions
                SET status = %s,
                    resolved_by_name = %s,
                    resolved_by_contact = %s,
                    resolved_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, version_id, suggestion_type, selection_text, selection_start, selection_end,
                          replacement_text, comment_text, author_name, author_contact, status,
                          resolved_by_name, resolved_by_contact, resolved_at, created_at, updated_at
                """,
                (next_status, author_name, author_contact, normalized_suggestion_id),
            )
            resolved = _serialize_sales_room_suggestion(dict(cur.fetchone()))
            _record_sales_room_event(
                conn,
                slug=normalized_slug,
                event_type="proposal_suggestion_resolved",
                metadata={"suggestion_id": normalized_suggestion_id, "action": action},
            )
            if action == "accept" and next_text != current_text:
                record_ai_learning_event(
                    capability="outreach.room_proposal",
                    event_type="edited_and_accepted",
                    intent="partnership_outreach",
                    business_id=str(row.get("business_id") or "") or None,
                    accepted=True,
                    rejected=False,
                    edited_before_accept=True,
                    outcome="human_copy_preference",
                    action_id=room_id,
                    prompt_key="partnership_room_proposal",
                    draft_text=current_text[:3000],
                    final_text=next_text[:3000],
                    metadata={
                        "room_id": room_id,
                        "room_slug": normalized_slug,
                        "suggestion_id": normalized_suggestion_id,
                        "suggestion_comment": str(suggestion.get("comment_text") or "")[:1000],
                        "learning_scope": "copy_quality_not_business_outcome",
                    },
                    conn=conn,
                )
            conn.commit()
            return jsonify(
                {
                    "success": True,
                    "suggestion": resolved,
                    "latest_version": _serialize_sales_room_version(version) if version else None,
                    "body_text": next_text,
                }
            )
        finally:
            conn.close()
    except Exception as e:
        print(f"Error resolving public sales room proposal suggestion: {e}")
        return jsonify({"error": str(e)}), 500

@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/messages", methods=["POST"])
def public_sales_room_message(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        rate_limit_response = _check_public_sales_room_rate_limit(
            "message",
            normalized_slug,
            PUBLIC_SALES_ROOM_MESSAGE_LIMIT,
            PUBLIC_SALES_ROOM_WRITE_WINDOW_SEC,
        )
        if rate_limit_response:
            return rate_limit_response
        data = request.get_json(silent=True) or {}
        author_name = str(data.get("author_name") or "").strip()
        author_contact = str(data.get("author_contact") or "").strip()
        body_text = str(data.get("body_text") or "").strip()
        attachments = data.get("attachments") if isinstance(data.get("attachments"), list) else []
        clean_attachments: list[dict[str, Any]] = []
        for attachment in attachments[:5]:
            if not isinstance(attachment, dict):
                continue
            file_id = str(attachment.get("id") or "").strip()
            original_name = str(attachment.get("original_name") or attachment.get("name") or "").strip()
            public_url = str(attachment.get("public_url") or "").strip()
            if file_id and _is_uuid_string(file_id) and original_name and public_url:
                clean_attachments.append(
                    {
                        "id": file_id,
                        "original_name": original_name,
                        "mime_type": str(attachment.get("mime_type") or "").strip(),
                        "size_bytes": int(attachment.get("size_bytes") or 0),
                        "public_url": public_url,
                    }
                )
        if not author_name:
            return jsonify({"error": "author_name is required"}), 400
        if not author_contact:
            return jsonify({"error": "author_contact is required"}), 400
        if not body_text and not clean_attachments:
            return jsonify({"error": "message or attachment is required"}), 400
        if len(body_text) > 4000:
            return jsonify({"error": "message is too long"}), 400
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            message_id = str(uuid.uuid4())
            room_id = str(row.get("id") or "")
            cur.execute(
                """
                INSERT INTO sales_room_messages (
                    id, room_id, author_type, author_name, author_contact, body_text, attachments_json, created_at
                ) VALUES (
                    %s, %s, 'visitor', %s, %s, %s, %s, NOW()
                )
                RETURNING id, author_type, author_name, author_contact, body_text, attachments_json, created_at
                """,
                (message_id, room_id, author_name, author_contact, body_text, Json(clean_attachments)),
            )
            message = _serialize_sales_room_message(dict(cur.fetchone()))
            if clean_attachments:
                file_ids = [str(item.get("id") or "") for item in clean_attachments if str(item.get("id") or "").strip()]
                cur.execute(
                    """
                    UPDATE sales_room_files
                    SET message_id = %s
                    WHERE room_id = %s
                      AND id = ANY(%s::uuid[])
                    """,
                    (message_id, room_id, file_ids),
                )
            _record_sales_room_event(
                conn,
                slug=normalized_slug,
                event_type="message_sent",
                metadata={"has_attachments": bool(clean_attachments)},
            )
            conn.commit()
            return jsonify({"success": True, "message": message})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error creating public sales room message: {e}")
        return jsonify({"error": str(e)}), 500

@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/files", methods=["POST"])
def public_sales_room_file_upload(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        rate_limit_response = _check_public_sales_room_rate_limit(
            "file",
            normalized_slug,
            PUBLIC_SALES_ROOM_FILE_LIMIT,
            PUBLIC_SALES_ROOM_WRITE_WINDOW_SEC,
        )
        if rate_limit_response:
            return rate_limit_response
        uploaded_file = request.files.get("file")
        if not uploaded_file:
            return jsonify({"error": "file is required"}), 400
        original_name = _clean_sales_room_filename(uploaded_file.filename or "file")
        extension = _sales_room_file_extension(original_name)
        if extension not in SALES_ROOM_ALLOWED_EXTENSIONS:
            return jsonify({"error": "Unsupported file type"}), 400
        content = uploaded_file.read()
        if not content:
            return jsonify({"error": "file is empty"}), 400
        if len(content) > SALES_ROOM_UPLOAD_MAX_BYTES:
            return jsonify({"error": "file is too large"}), 400
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            row = _load_sales_room_by_slug(cur, normalized_slug)
            if not row:
                return jsonify({"error": "Sales room not found"}), 404
            room_id = str(row.get("id") or "")
            file_id = str(uuid.uuid4())
            public_url = f"/api/sales-rooms/public/{quote(normalized_slug)}/files/{file_id}"
            stored_file = store_sales_room_file(
                room_id=room_id,
                file_id=file_id,
                extension=extension,
                content=content,
                original_name=original_name,
                mime_type=uploaded_file.mimetype or "",
            )
            storage_path = str(stored_file.get("storage_path") or "")
            attachment = {
                "id": file_id,
                "original_name": original_name,
                "mime_type": uploaded_file.mimetype or "",
                "size_bytes": len(content),
                "public_url": public_url,
            }
            cur.execute(
                """
                INSERT INTO sales_room_files (
                    id, room_id, original_name, mime_type, size_bytes, storage_path, public_url, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                """,
                (
                    file_id,
                    room_id,
                    original_name,
                    uploaded_file.mimetype or "",
                    len(content),
                    storage_path,
                    public_url,
                ),
            )
            _record_sales_room_event(
                conn,
                slug=normalized_slug,
                event_type="file_uploaded",
                metadata={"file_id": file_id, "size_bytes": len(content), "mime_type": uploaded_file.mimetype or ""},
            )
            conn.commit()
            return jsonify({"success": True, "file": attachment})
        finally:
            conn.close()
    except Exception as e:
        print(f"Error uploading public sales room file: {e}")
        return jsonify({"error": str(e)}), 500

@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/files/<string:file_id>", methods=["GET"])
def public_sales_room_file(slug, file_id):
    try:
        normalized_slug = _slugify_company_name(slug)
        normalized_file_id = str(file_id or "").strip()
        if not _is_uuid_string(normalized_file_id):
            return jsonify({"error": "File not found"}), 404
        conn = get_db_connection()
        try:
            _ensure_sales_room_tables(conn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT f.storage_path, f.original_name, f.mime_type
                FROM sales_room_files f
                JOIN sales_rooms sr ON sr.id = f.room_id
                WHERE sr.slug = %s
                  AND f.id = %s
                LIMIT 1
                """,
                (normalized_slug, normalized_file_id),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "File not found"}), 404
            content = load_sales_room_file(str(row.get("storage_path") or ""))
            if content is None:
                return jsonify({"error": "File not found"}), 404
            return send_file(
                io.BytesIO(content),
                mimetype=row.get("mime_type") or None,
                download_name=str(row.get("original_name") or "file"),
                as_attachment=False,
            )
        finally:
            conn.close()
    except Exception as e:
        print(f"Error loading public sales room file: {e}")
        return jsonify({"error": str(e)}), 500

@sales_rooms_bp.route("/api/sales-rooms/public/<string:slug>/events", methods=["POST"])
def public_sales_room_event(slug):
    try:
        normalized_slug = _slugify_company_name(slug)
        rate_limit_response = _check_public_sales_room_rate_limit(
            "event",
            normalized_slug,
            PUBLIC_SALES_ROOM_EVENT_LIMIT,
            PUBLIC_SALES_ROOM_EVENT_WINDOW_SEC,
        )
        if rate_limit_response:
            return rate_limit_response
        data = request.get_json(silent=True) or {}
        event_type = str(data.get("event_type") or "").strip().lower()
        if event_type not in {"cta_click", "audit_open", "copy_link", "view", "proposal_viewed", "message_sent", "file_uploaded"}:
            return jsonify({"error": "Unsupported event_type"}), 400
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        conn = get_db_connection()
        try:
            _record_sales_room_event(conn, slug=normalized_slug, event_type=event_type, metadata=metadata)
            conn.commit()
        finally:
            conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error recording public sales room event: {e}")
        return jsonify({"error": str(e)}), 500
