import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from .service import run_capability
from .web_read import handle_web_read


SUPPORTED_CAPABILITIES = [
    "leads.score",
    "leads.channel_enrich",
    "partners.search_geo",
    "partners.enrich_contacts",
    "outreach.draft_first_message",
]


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _load_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        raise ValueError("request body is required")
    raw = handler.rfile.read(length)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json body must be an object")
    return payload


def handle_request(
    method: str,
    path: str,
    headers: Dict[str, str] | None = None,
    payload: Dict[str, Any] | None = None,
) -> tuple[int, Dict[str, Any]]:
    headers = headers or {}
    web_result = handle_web_read(method, path, headers, payload)
    if web_result is not None:
        return web_result

    if method == "GET":
        if path == "/healthz":
            return HTTPStatus.OK, {"ok": True, "success": True}
        if path == "/capabilities":
            catalog = handle_web_read("GET", "/capabilities/catalog", headers, None)
            declared = [{"name": name, "capability": name, "status": "declared"} for name in SUPPORTED_CAPABILITIES]
            actions = declared + (catalog[1].get("actions", []) if catalog and catalog[0] == 200 else [])
            return HTTPStatus.OK, {
                "actions": actions,
                "ok": True,
                "success": True,
                "capabilities": SUPPORTED_CAPABILITIES,
                "mode": "stateless",
                "autosend": False,
            }
        return HTTPStatus.NOT_FOUND, {"ok": False, "success": False, "error": "not found"}

    if method != "POST":
        return HTTPStatus.METHOD_NOT_ALLOWED, {"ok": False, "success": False, "error": "method not allowed"}

    token = os.environ.get("OPENCLAW_INTERNAL_TOKEN", "").strip()
    if token:
        provided = str(headers.get("X-OpenClaw-Internal-Token", "")).strip()
        if provided != token:
            return HTTPStatus.UNAUTHORIZED, {"ok": False, "success": False, "error": "unauthorized"}

    prefix = "/capabilities/"
    if not path.startswith(prefix):
        return HTTPStatus.NOT_FOUND, {"ok": False, "success": False, "error": "not found"}

    capability = path[len(prefix) :]
    if capability not in SUPPORTED_CAPABILITIES:
        return HTTPStatus.NOT_FOUND, {"ok": False, "success": False, "error": "not found"}

    try:
        start = time.monotonic()
        body = payload or {}
        if not isinstance(body, dict):
            raise ValueError("json body must be an object")
        header_tenant = str(headers.get("X-Tenant-Id", "")).strip()
        body_tenant = str(body.get("tenant_id", "")).strip()
        if header_tenant and body_tenant and header_tenant != body_tenant:
            return HTTPStatus.FORBIDDEN, {"ok": False, "success": False, "error": "tenant mismatch between header and body"}
        if header_tenant and not body_tenant:
            body["tenant_id"] = header_tenant
        result = run_capability(capability, body)
        duration_ms = int((time.monotonic() - start) * 1000)
        items_count = len(result.get("items", [])) if isinstance(result, dict) and isinstance(result.get("items", []), list) else None
        found_fields = []
        provider = None
        if isinstance(result, dict):
            provider = result.get("provider")
            if not provider and isinstance(result.get("meta"), dict):
                provider = result["meta"].get("provider")
        if capability == "partners.enrich_contacts":
            candidate_fields = result.get("found_fields", [])
            if isinstance(candidate_fields, list):
                found_fields = [str(x) for x in candidate_fields]
        print(
            json.dumps(
                {
                    "event": "capability_call",
                    "capability": capability,
                    "tenant_id": body.get("tenant_id"),
                    "duration_ms": duration_ms,
                    "provider": provider,
                    "items_count": items_count,
                    "found_fields": found_fields,
                },
                ensure_ascii=False,
            )
        )
    except ValueError as exc:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "success": False, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive boundary
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "success": False, "error": str(exc)}

    return HTTPStatus.OK, {"ok": True, "success": True, "result": result}


class CapabilityHandler(BaseHTTPRequestHandler):
    server_version = "OutreachMVP/1.0"

    def do_GET(self) -> None:
        status, body = handle_request("GET", self.path, dict(self.headers.items()))
        _json_response(self, status, body)

    def do_POST(self) -> None:
        try:
            payload = _load_body(self)
        except ValueError as exc:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "success": False, "error": str(exc)})
            return
        status, body = handle_request("POST", self.path, dict(self.headers.items()), payload)
        _json_response(self, status, body)

    def log_message(self, format: str, *args: Any) -> None:
        return

def serve(host: str = "127.0.0.1", port: int = 8091) -> None:
    with ThreadingHTTPServer((host, port), CapabilityHandler) as server:
        print(f"Outreach MVP capability server listening on http://{host}:{port}")
        server.serve_forever()


def main() -> int:
    host = os.environ.get("OPENCLAW_OUTREACH_HOST", "127.0.0.1")
    port = int(os.environ.get("OPENCLAW_OUTREACH_PORT", "8091"))
    serve(host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
