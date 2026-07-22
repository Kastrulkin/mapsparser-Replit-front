from flask import Blueprint, jsonify, request

from auth_system import verify_session
from database_manager import get_db_connection
from services.knowledge_graph_service import (
    decide_privacy_candidate,
    decide_source,
    knowledge_layer_enabled,
    list_privacy_candidates,
    list_runs,
    list_signals,
    list_sources,
    overview,
    serialize_for_json,
)
from services.knowledge_embedding_ingestion import ingest_semantic_sources
from services.knowledge_embeddings import embedding_status, enqueue_document_chunks
from services.knowledge_retrieval import (
    KnowledgeSearchRequest,
    record_retrieval_outcome,
    retrieve_knowledge,
)


admin_knowledge_bp = Blueprint("admin_knowledge", __name__)


def _response(payload, status=200):
    return jsonify(serialize_for_json(payload)), status


def _current_superadmin():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    user_data = verify_session(token)
    if not user_data or not user_data.get("is_superadmin"):
        return None
    return user_data


def _require_superadmin():
    user_data = _current_superadmin()
    if not user_data:
        return None, _response({"success": False, "error": "Forbidden"}, 403)
    return user_data, None


def _request_json():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


@admin_knowledge_bp.get("/api/admin/knowledge/overview")
def knowledge_overview():
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    conn = get_db_connection()
    try:
        payload = overview(conn)
        payload["enabled"] = knowledge_layer_enabled()
        return _response({"success": True, "data": payload})
    finally:
        conn.close()


@admin_knowledge_bp.get("/api/admin/knowledge/signals")
def knowledge_signals():
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    conn = get_db_connection()
    try:
        items = list_signals(
            conn,
            concept_type=str(request.args.get("concept_type") or "").strip() or None,
            industry=str(request.args.get("industry") or "").strip() or None,
            allowed_use=str(request.args.get("allowed_use") or "").strip() or None,
            limit=int(request.args.get("limit") or 50),
        )
        return _response({"success": True, "items": items, "count": len(items)})
    finally:
        conn.close()


@admin_knowledge_bp.get("/api/admin/knowledge/sources")
def knowledge_sources():
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    conn = get_db_connection()
    try:
        items = list_sources(conn, status=str(request.args.get("status") or "").strip() or None)
        return _response({"success": True, "items": items, "count": len(items)})
    finally:
        conn.close()


@admin_knowledge_bp.post("/api/admin/knowledge/sources/<source_id>/decision")
def knowledge_source_decision(source_id):
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    payload = _request_json()
    conn = get_db_connection()
    try:
        source = decide_source(
            conn,
            source_id=source_id,
            status=str(payload.get("status") or ""),
            source_role=str(payload.get("source_role") or "").strip() or None,
            allowed_uses=payload.get("allowed_uses") if isinstance(payload.get("allowed_uses"), list) else None,
        )
        if not source:
            conn.rollback()
            return _response({"success": False, "error": "Source not found"}, 404)
        conn.commit()
        return _response({"success": True, "source": source})
    except ValueError as error:
        conn.rollback()
        return _response({"success": False, "error": str(error)}, 400)
    finally:
        conn.close()


@admin_knowledge_bp.get("/api/admin/knowledge/runs")
def knowledge_runs():
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    conn = get_db_connection()
    try:
        items = list_runs(conn, limit=int(request.args.get("limit") or 50))
        return _response({"success": True, "items": items, "count": len(items)})
    finally:
        conn.close()


@admin_knowledge_bp.get("/api/admin/knowledge/privacy-candidates")
def knowledge_privacy_candidates():
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    conn = get_db_connection()
    try:
        items = list_privacy_candidates(conn)
        return _response({"success": True, "items": items, "count": len(items)})
    finally:
        conn.close()


@admin_knowledge_bp.post("/api/admin/knowledge/privacy-candidates/<review_id>/decision")
def knowledge_privacy_decision(review_id):
    user_data, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    payload = _request_json()
    conn = get_db_connection()
    try:
        claim = decide_privacy_candidate(
            conn,
            review_id=review_id,
            decision=str(payload.get("decision") or ""),
            reviewer_id=str(user_data.get("user_id") or user_data.get("id") or ""),
            reason=str(payload.get("reason") or "").strip() or None,
        )
        if not claim:
            conn.rollback()
            return _response({"success": False, "error": "Privacy review not found"}, 404)
        conn.commit()
        return _response({"success": True, "claim": claim})
    except ValueError as error:
        conn.rollback()
        return _response({"success": False, "error": str(error)}, 400)
    finally:
        conn.close()


@admin_knowledge_bp.get("/api/admin/knowledge/embeddings/status")
def knowledge_embeddings_status():
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    conn = get_db_connection()
    try:
        return _response({"success": True, "data": embedding_status(conn)})
    finally:
        conn.close()


@admin_knowledge_bp.post("/api/admin/knowledge/embeddings/backfill")
def knowledge_embeddings_backfill():
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    payload = _request_json()
    conn = get_db_connection()
    try:
        ingestion = ingest_semantic_sources(
            conn,
            limit_per_source=max(1, min(int(payload.get("source_limit") or 1000), 10000)),
        )
        queued = enqueue_document_chunks(
            conn,
            limit=max(1, min(int(payload.get("document_limit") or 1000), 10000)),
            document_id=str(payload.get("document_id") or "").strip(),
        )
        conn.commit()
        return _response({"success": True, "ingestion": ingestion, "queue": queued}, 202)
    except (TypeError, ValueError) as error:
        conn.rollback()
        return _response({"success": False, "error": str(error)}, 400)
    finally:
        conn.close()


@admin_knowledge_bp.post("/api/admin/knowledge/embeddings/search")
def knowledge_embeddings_search():
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    payload = _request_json()
    business_id = str(payload.get("business_id") or "").strip()
    query = str(payload.get("query") or "").strip()
    purpose = str(payload.get("purpose") or "industry_recommendations").strip()
    if not business_id or not query:
        return _response({"success": False, "error": "business_id and query are required"}, 400)
    conn = get_db_connection()
    try:
        result = retrieve_knowledge(
            conn,
            KnowledgeSearchRequest(
                business_id=business_id,
                query=query,
                purpose=purpose,
                source_types=tuple(str(item) for item in payload.get("source_types") or [] if item),
                limit=max(1, min(int(payload.get("limit") or 12), 15)),
                pipeline_id=str(payload.get("pipeline_id") or ""),
                consumer=str(payload.get("consumer") or "admin_search"),
            ),
        )
        conn.commit()
        result["hits"] = [hit.__dict__ for hit in result.get("hits") or []]
        return _response({"success": True, "data": result})
    finally:
        conn.close()


@admin_knowledge_bp.post("/api/admin/knowledge/embeddings/retrieval/<event_id>/outcome")
def knowledge_retrieval_outcome(event_id):
    _, auth_error = _require_superadmin()
    if auth_error:
        return auth_error
    payload = _request_json()
    conn = get_db_connection()
    try:
        updated = record_retrieval_outcome(
            conn,
            event_id=event_id,
            outcome=str(payload.get("outcome") or ""),
            edit_ratio=payload.get("edit_ratio"),
            selected_evidence_ids=payload.get("selected_evidence_ids")
            if isinstance(payload.get("selected_evidence_ids"), list) else None,
        )
        conn.commit()
        return _response({"success": True, "updated": updated}, 200 if updated else 404)
    except ValueError as error:
        conn.rollback()
        return _response({"success": False, "error": str(error)}, 400)
    finally:
        conn.close()
