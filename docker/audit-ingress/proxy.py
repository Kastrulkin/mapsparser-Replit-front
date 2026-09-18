#!/usr/bin/env python3
"""A deliberately narrow loopback ingress for the compiled staging proof.

The proxy has one fixed upstream: the Compose ``app`` service on port 8000.
It is not a general purpose forward proxy and deliberately rejects CONNECT,
absolute-form request targets and transfer-encoded request bodies.
"""

from __future__ import annotations

import http.client
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final
from urllib.parse import urlsplit


UPSTREAM_HOST: Final = "app"
UPSTREAM_PORT: Final = 8000
REQUEST_TIMEOUT_SECONDS: Final = 15
MAX_REQUEST_BODY_BYTES: Final = 2 * 1024 * 1024
MAX_RESPONSE_BODY_BYTES: Final = 8 * 1024 * 1024
HOP_BY_HOP_HEADERS: Final = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


def _connection_header_names(headers: http.client.HTTPMessage) -> set[str]:
    values = headers.get_all("Connection", [])
    return {
        value.strip().lower()
        for line in values
        for value in line.split(",")
        if value.strip()
    }


def _forward_headers(headers: http.client.HTTPMessage) -> dict[str, str]:
    blocked = HOP_BY_HOP_HEADERS | _connection_header_names(headers) | {"host", "content-length"}
    return {name: value for name, value in headers.items() if name.lower() not in blocked}


class AuditIngressHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LocalOSAuditIngress/1.0"

    def log_message(self, _format: str, *_arguments: object) -> None:
        """Keep request details, including cookies, out of container logs."""

    def do_CONNECT(self) -> None:  # noqa: N802 - required stdlib handler name
        self.send_error(405, "CONNECT is not supported")

    def do_GET(self) -> None:  # noqa: N802 - required stdlib handler name
        self._forward()

    def do_HEAD(self) -> None:  # noqa: N802 - required stdlib handler name
        self._forward()

    def do_POST(self) -> None:  # noqa: N802 - required stdlib handler name
        self._forward()

    def do_PUT(self) -> None:  # noqa: N802 - required stdlib handler name
        self._forward()

    def do_PATCH(self) -> None:  # noqa: N802 - required stdlib handler name
        self._forward()

    def do_DELETE(self) -> None:  # noqa: N802 - required stdlib handler name
        self._forward()

    def do_OPTIONS(self) -> None:  # noqa: N802 - required stdlib handler name
        self._forward()

    def _request_body(self) -> bytes | None:
        if "Transfer-Encoding" in self.headers:
            self.send_error(400, "transfer-encoded request bodies are not supported")
            return None
        values = self.headers.get_all("Content-Length", [])
        if len(values) > 1:
            self.send_error(400, "multiple Content-Length headers are not supported")
            return None
        value = values[0] if values else "0"
        try:
            length = int(value)
        except ValueError:
            self.send_error(400, "invalid Content-Length")
            return None
        if length < 0 or length > MAX_REQUEST_BODY_BYTES:
            self.send_error(413, "request body is too large")
            return None
        return self.rfile.read(length)

    def _valid_target(self) -> bool:
        parsed = urlsplit(self.path)
        return (
            self.path.startswith("/")
            and not self.path.startswith("//")
            and not parsed.scheme
            and not parsed.netloc
        )

    def _forward(self) -> None:
        if not self._valid_target():
            self.send_error(400, "only origin-form paths are supported")
            return
        self.connection.settimeout(REQUEST_TIMEOUT_SECONDS)
        try:
            body = self._request_body()
        except (OSError, socket.timeout):
            self.send_error(408, "request body timed out")
            return
        if body is None:
            return
        headers = _forward_headers(self.headers)
        headers["Host"] = f"{UPSTREAM_HOST}:{UPSTREAM_PORT}"
        headers["Content-Length"] = str(len(body))
        connection = http.client.HTTPConnection(
            UPSTREAM_HOST,
            UPSTREAM_PORT,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read(MAX_RESPONSE_BODY_BYTES + 1)
        except (OSError, http.client.HTTPException):
            self.send_error(502, "staging app is unavailable")
            return
        finally:
            connection.close()
        if len(payload) > MAX_RESPONSE_BODY_BYTES:
            self.send_error(502, "staging app response is too large")
            return
        blocked = HOP_BY_HOP_HEADERS | _connection_header_names(response.headers) | {"content-length"}
        content_length = str(len(payload))
        if self.command == "HEAD":
            advertised_length = response.headers.get("Content-Length")
            if advertised_length is not None:
                try:
                    if int(advertised_length) >= 0:
                        content_length = advertised_length
                except ValueError:
                    pass
        self.send_response(response.status, response.reason)
        for name, value in response.headers.items():
            if name.lower() not in blocked:
                self.send_header(name, value)
        self.send_header("Content-Length", content_length)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8000), AuditIngressHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
