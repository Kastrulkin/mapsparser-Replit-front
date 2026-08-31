"""Central browser security headers for LocalOS responses."""

import os


CSP_REPORT_ONLY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'self'; "
    "script-src 'self' 'unsafe-inline' https://telegram.org https://mc.yandex.ru; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "connect-src 'self' https: wss:; "
    "frame-src 'self' https://oauth.telegram.org https://mc.yandex.ru https://yoomoney.ru https://*.yookassa.ru; "
    "form-action 'self' https:"
)

PERMISSIONS_POLICY = (
    "camera=(), microphone=(), geolocation=(self), payment=(self), usb=()"
)
HSTS_POLICY = "max-age=31536000; includeSubDomains"


def register_security_headers(app):
    """Register conservative headers without enforcing CSP during rollout."""

    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = PERMISSIONS_POLICY
        response.headers["Content-Security-Policy-Report-Only"] = CSP_REPORT_ONLY
        if str(os.getenv("APP_ENV", "") or "").strip().lower() == "production":
            response.headers["Strict-Transport-Security"] = HSTS_POLICY
        return response

    return app
