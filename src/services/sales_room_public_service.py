"""Explicit public sales-room dependencies.

This module is a transitional seam for extracting sales-room logic from
``api.admin_prospecting``. Public route modules should import the exact helpers
they use from here instead of copying the whole admin prospecting namespace.
"""
from __future__ import annotations

import io
import secrets
import uuid
from typing import Any
from urllib.parse import quote

from flask import jsonify, request, send_file
from psycopg2.extras import Json, RealDictCursor

from auth_system import CONSENT_VERSION, normalize_email
from pg_db_utils import get_db_connection
from services.sales_room_file_storage import load_sales_room_file, store_sales_room_file
from services.sales_room_helpers import (
    clean_sales_room_filename as _clean_sales_room_filename,
    is_uuid_string as _is_uuid_string,
    make_sales_room_url as _make_sales_room_url,
    sales_room_file_extension as _sales_room_file_extension,
)
from services.sales_room_review_service import (
    can_edit_sales_room as _can_edit_sales_room,
    create_sales_room_proposal_version as _create_sales_room_proposal_version,
    ensure_sales_room_proposal_version as _ensure_sales_room_proposal_version,
    load_sales_room_by_slug as _load_sales_room_by_slug,
    load_sales_room_latest_version as _load_sales_room_latest_version,
    load_sales_room_messages as _load_sales_room_messages,
    load_sales_room_review as _load_sales_room_review,
    replace_text_for_sales_room_suggestion as _replace_text_for_sales_room_suggestion,
    serialize_sales_room_message as _serialize_sales_room_message,
    serialize_sales_room_suggestion as _serialize_sales_room_suggestion,
    serialize_sales_room_version as _serialize_sales_room_version,
    update_sales_room_proposal_body as _update_sales_room_proposal_body,
)
from services.sales_room_audit_offer_service import (
    AUDIT_OFFER_REQUESTABLE_STATUSES,
    audit_offer_processing_delay_seconds as _audit_offer_processing_delay_seconds,
    build_sales_room_participant_access_token as _build_sales_room_participant_access_token,
    ensure_audit_offer_user as _ensure_audit_offer_user,
    load_sales_room_participant_by_token as _load_sales_room_participant_by_token,
    participant_token_from_request as _participant_token_from_request,
    public_audit_offer_allowed_for_participant as _public_audit_offer_allowed_for_participant,
    record_sales_room_event_by_id as _record_sales_room_event_by_id,
    send_sales_room_participant_verification_email as _send_sales_room_participant_verification_email,
    serialize_public_audit_offer as _serialize_public_audit_offer,
    serialize_sales_room_participant as _serialize_sales_room_participant,
)

from api.admin_prospecting import (
    PUBLIC_SALES_ROOM_EVENT_LIMIT,
    PUBLIC_SALES_ROOM_EVENT_WINDOW_SEC,
    PUBLIC_SALES_ROOM_FILE_LIMIT,
    PUBLIC_SALES_ROOM_MESSAGE_LIMIT,
    PUBLIC_SALES_ROOM_SUGGESTION_LIMIT,
    PUBLIC_SALES_ROOM_WRITE_WINDOW_SEC,
    SALES_ROOM_ALLOWED_EXTENSIONS,
    SALES_ROOM_UPLOAD_MAX_BYTES,
    _check_public_sales_room_rate_limit,
    _ensure_sales_room_tables,
    _load_sales_room_audit_offer,
    _normalize_public_sales_room_proposal,
    _optional_auth,
    _public_audit_offer_visible_for_user,
    _record_sales_room_event,
    _require_auth,
    _row_to_dict,
    _slugify_company_name,
    _to_json_compatible,
    release_ready_audit_offers,
)

__all__ = [
    "AUDIT_OFFER_REQUESTABLE_STATUSES",
    "Any",
    "CONSENT_VERSION",
    "Json",
    "PUBLIC_SALES_ROOM_EVENT_LIMIT",
    "PUBLIC_SALES_ROOM_EVENT_WINDOW_SEC",
    "PUBLIC_SALES_ROOM_FILE_LIMIT",
    "PUBLIC_SALES_ROOM_MESSAGE_LIMIT",
    "PUBLIC_SALES_ROOM_SUGGESTION_LIMIT",
    "PUBLIC_SALES_ROOM_WRITE_WINDOW_SEC",
    "RealDictCursor",
    "SALES_ROOM_ALLOWED_EXTENSIONS",
    "SALES_ROOM_UPLOAD_MAX_BYTES",
    "_audit_offer_processing_delay_seconds",
    "_build_sales_room_participant_access_token",
    "_can_edit_sales_room",
    "_check_public_sales_room_rate_limit",
    "_clean_sales_room_filename",
    "_create_sales_room_proposal_version",
    "_ensure_audit_offer_user",
    "_ensure_sales_room_proposal_version",
    "_ensure_sales_room_tables",
    "_is_uuid_string",
    "_load_sales_room_audit_offer",
    "_load_sales_room_by_slug",
    "_load_sales_room_latest_version",
    "_load_sales_room_messages",
    "_load_sales_room_participant_by_token",
    "_load_sales_room_review",
    "_make_sales_room_url",
    "_normalize_public_sales_room_proposal",
    "_optional_auth",
    "_participant_token_from_request",
    "_public_audit_offer_allowed_for_participant",
    "_public_audit_offer_visible_for_user",
    "_record_sales_room_event",
    "_record_sales_room_event_by_id",
    "_replace_text_for_sales_room_suggestion",
    "_require_auth",
    "_row_to_dict",
    "_sales_room_file_extension",
    "_send_sales_room_participant_verification_email",
    "_serialize_public_audit_offer",
    "_serialize_sales_room_message",
    "_serialize_sales_room_participant",
    "_serialize_sales_room_suggestion",
    "_serialize_sales_room_version",
    "_slugify_company_name",
    "_to_json_compatible",
    "_update_sales_room_proposal_body",
    "get_db_connection",
    "io",
    "jsonify",
    "load_sales_room_file",
    "normalize_email",
    "quote",
    "release_ready_audit_offers",
    "request",
    "secrets",
    "send_file",
    "store_sales_room_file",
    "uuid",
]
