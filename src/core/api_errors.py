"""Safe, traceable API error responses."""

import uuid

from flask import current_app, g, jsonify, request


def internal_error_response(message):
    request_id = str(getattr(g, "request_id", "") or request.headers.get("X-Request-ID") or uuid.uuid4())
    current_app.logger.exception("API request failed request_id=%s", request_id)
    return jsonify({
        "code": "internal_error",
        "message": message,
        "request_id": request_id,
    }), 500
