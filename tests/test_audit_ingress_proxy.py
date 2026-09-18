"""Loopback-only behaviour tests for the compiled staging ingress proxy."""

from __future__ import annotations

import http.client
import importlib.util
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


PROXY_PATH = Path(__file__).parents[1] / "docker" / "audit-ingress" / "proxy.py"


def load_proxy_module():
    specification = importlib.util.spec_from_file_location("audit_ingress_proxy", PROXY_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def start_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_server(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def raw_request(port, request):
    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    try:
        client.sendall(request)
        chunks = []
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        client.close()


def test_proxy_preserves_browser_auth_headers_and_set_cookie_without_external_access():
    received = {}

    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - stdlib handler name
            received["path"] = self.path
            received["body"] = self.rfile.read(int(self.headers["Content-Length"]))
            received["cookie"] = self.headers.get("Cookie")
            received["csrf"] = self.headers.get("X-CSRF-Token")
            received["origin"] = self.headers.get("Origin")
            received["connection"] = self.headers.get("Connection")
            self.send_response(201)
            self.send_header("Set-Cookie", "localos_session=synthetic; HttpOnly")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, _format, *_arguments):
            pass

    upstream, upstream_thread = start_server(Upstream)
    proxy = load_proxy_module()
    proxy.UPSTREAM_HOST = "127.0.0.1"
    proxy.UPSTREAM_PORT = upstream.server_port
    ingress, ingress_thread = start_server(proxy.AuditIngressHandler)
    try:
        connection = http.client.HTTPConnection("127.0.0.1", ingress.server_port, timeout=2)
        connection.request(
            "POST",
            "/api/auth/login",
            body=b'{"email":"synthetic@example.test"}',
            headers={
                "Content-Type": "application/json",
                "Cookie": "localos_session=before",
                "X-CSRF-Token": "synthetic-csrf",
                "Origin": "http://127.0.0.1:18017",
                "Connection": "keep-alive, X-Remove-Me",
                "X-Remove-Me": "do-not-forward",
            },
        )
        response = connection.getresponse()
        assert response.status == 201
        assert response.read() == b'{"ok":true}'
        assert response.getheader("Set-Cookie") == "localos_session=synthetic; HttpOnly"
        assert received == {
            "path": "/api/auth/login",
            "body": b'{"email":"synthetic@example.test"}',
            "cookie": "localos_session=before",
            "csrf": "synthetic-csrf",
            "origin": "http://127.0.0.1:18017",
            "connection": None,
        }
    finally:
        stop_server(ingress, ingress_thread)
        stop_server(upstream, upstream_thread)


def test_proxy_rejects_connect_and_absolute_form_before_any_upstream_connection():
    proxy = load_proxy_module()
    ingress, ingress_thread = start_server(proxy.AuditIngressHandler)
    try:
        connection = http.client.HTTPConnection("127.0.0.1", ingress.server_port, timeout=2)
        connection.request("CONNECT", "example.invalid:443")
        assert connection.getresponse().status == 405

        connection = http.client.HTTPConnection("127.0.0.1", ingress.server_port, timeout=2)
        connection.request("GET", "http://example.invalid/never-contacted")
        assert connection.getresponse().status == 400
    finally:
        stop_server(ingress, ingress_thread)


def test_proxy_rejects_empty_transfer_encoding_and_duplicate_content_length():
    proxy = load_proxy_module()
    ingress, ingress_thread = start_server(proxy.AuditIngressHandler)
    try:
        transfer_encoded = raw_request(
            ingress.server_port,
            b"POST / HTTP/1.1\r\nHost: 127.0.0.1\r\nTransfer-Encoding: \r\nContent-Length: 0\r\n\r\n",
        )
        duplicate_length = raw_request(
            ingress.server_port,
            b"POST / HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n",
        )
        assert b" 400 " in transfer_encoded
        assert b" 400 " in duplicate_length
    finally:
        stop_server(ingress, ingress_thread)


def test_proxy_bounds_request_body_and_client_read_time():
    proxy = load_proxy_module()
    proxy.MAX_REQUEST_BODY_BYTES = 4
    proxy.REQUEST_TIMEOUT_SECONDS = 0.05
    ingress, ingress_thread = start_server(proxy.AuditIngressHandler)
    try:
        oversized = raw_request(
            ingress.server_port,
            b"POST / HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 5\r\n\r\n",
        )
        assert b" 413 " in oversized

        client = socket.create_connection(("127.0.0.1", ingress.server_port), timeout=2)
        try:
            client.sendall(b"POST / HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 1\r\n\r\n")
            assert b" 408 " in client.recv(4096)
        finally:
            client.close()
    finally:
        stop_server(ingress, ingress_thread)


def test_proxy_bounds_response_body_and_preserves_head_content_length():
    class Upstream(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler name
            self.send_response(200)
            self.send_header("Content-Length", "5")
            self.end_headers()
            self.wfile.write(b"12345")

        def do_HEAD(self):  # noqa: N802 - stdlib handler name
            self.send_response(200)
            self.send_header("Content-Length", "27")
            self.end_headers()

        def log_message(self, _format, *_arguments):
            pass

    upstream, upstream_thread = start_server(Upstream)
    proxy = load_proxy_module()
    proxy.UPSTREAM_HOST = "127.0.0.1"
    proxy.UPSTREAM_PORT = upstream.server_port
    proxy.MAX_RESPONSE_BODY_BYTES = 4
    ingress, ingress_thread = start_server(proxy.AuditIngressHandler)
    try:
        connection = http.client.HTTPConnection("127.0.0.1", ingress.server_port, timeout=2)
        connection.request("GET", "/")
        assert connection.getresponse().status == 502

        proxy.MAX_RESPONSE_BODY_BYTES = 8
        connection = http.client.HTTPConnection("127.0.0.1", ingress.server_port, timeout=2)
        connection.request("HEAD", "/")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Length") == "27"
        assert response.read() == b""
    finally:
        stop_server(ingress, ingress_thread)
        stop_server(upstream, upstream_thread)
