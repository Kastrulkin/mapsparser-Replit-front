"""Feature-flagged browser cookie sessions and CSRF protection."""

import hmac
import os
import secrets
import uuid

from flask import g, jsonify, request


SESSION_COOKIE_NAME = "localos_session"
CSRF_COOKIE_NAME = "localos_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/register-with-business",
    "/api/auth/verify-email",
    "/api/auth/resend-verification",
    "/api/auth/set-password",
    "/api/auth/accept-invite",
}


def browser_cookie_auth_enabled() -> bool:
    return os.getenv("BROWSER_COOKIE_AUTH_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def browser_cookie_secure() -> bool:
    return os.getenv("BROWSER_COOKIE_AUTH_SECURE", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def issue_browser_session(response, session_token: str):
    if not browser_cookie_auth_enabled():
        return response
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        secure=browser_cookie_secure(),
        samesite="Lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        secure=browser_cookie_secure(),
        samesite="Lax",
        path="/",
    )
    return response


def clear_browser_session(response):
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        httponly=True,
        secure=browser_cookie_secure(),
        samesite="Lax",
        path="/",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        httponly=False,
        secure=browser_cookie_secure(),
        samesite="Lax",
        path="/",
    )
    return response


def register_browser_session_security(app):
    @app.before_request
    def authenticate_browser_cookie():
        if not browser_cookie_auth_enabled():
            return None

        supplied_authorization = str(request.headers.get("Authorization") or "").strip()
        if supplied_authorization:
            return None

        session_token = str(request.cookies.get(SESSION_COOKIE_NAME) or "").strip()
        if not session_token:
            return None

        if request.method in UNSAFE_METHODS and request.path not in CSRF_EXEMPT_PATHS:
            csrf_cookie = str(request.cookies.get(CSRF_COOKIE_NAME) or "")
            csrf_header = str(request.headers.get(CSRF_HEADER_NAME) or "")
            if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
                request_id = str(getattr(g, "request_id", "") or uuid.uuid4())
                return jsonify(
                    {
                        "code": "csrf_required",
                        "message": "Обновите страницу и повторите действие.",
                        "request_id": request_id,
                    }
                ), 403

        request.environ["HTTP_AUTHORIZATION"] = f"Bearer {session_token}"
        g.browser_cookie_authenticated = True
        return None

    return app
