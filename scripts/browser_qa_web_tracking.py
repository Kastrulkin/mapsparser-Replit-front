#!/usr/bin/env python3
"""Local browser fixture for the tracker consent and SPA release gate."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
TRACKER_PATH = ROOT / "frontend" / "public" / "tracker.js"
EVENTS: list[dict] = []
EVENTS_LOCK = threading.Lock()


HTML = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>LocalOS tracker browser QA</title>
</head>
<body style="font-family:system-ui;max-width:720px;margin:40px auto;line-height:1.5">
  <h1>LocalOS tracker browser QA</h1>
  <p id="route">Текущий путь: <strong>/</strong></p>
  <p id="storage-status" role="status">Анонимные ID: нет</p>
  <button id="allow" type="button">Разрешить tracking</button>
  <button id="revoke" type="button">Отозвать consent</button>
  <button id="spa" type="button">SPA-переход</button>
  <form id="lead-form" action="/never-submitted">
    <label>Секретное значение <input id="secret" name="phone" value="PRIVATE-INPUT-VALUE"></label>
    <button type="submit">Отправить форму</button>
  </form>
  <button id="after-revoke" data-localos-cta="after-revoke" type="button">Действие после revoke</button>
  <script async src="/tracker.js" data-business="pub_browser_qa_123456" data-consent="denied"></script>
  <script>
    function refreshStorageStatus() {
      var hasIds = Boolean(localStorage.getItem('localos_visitor_id') || sessionStorage.getItem('localos_session_id'));
      document.querySelector('#storage-status').textContent = 'Анонимные ID: ' + (hasIds ? 'созданы' : 'нет');
    }
    document.querySelector('#allow').addEventListener('click', function () {
      window.LocalOSTracker.setConsent(true);
      refreshStorageStatus();
    });
    document.querySelector('#revoke').addEventListener('click', function () {
      window.LocalOSTracker.setConsent(false);
      refreshStorageStatus();
    });
    document.querySelector('#spa').addEventListener('click', function () {
      history.pushState({}, '', '/services?private_query=must_not_enter_page_path');
      document.querySelector('#route strong').textContent = location.pathname;
    });
    document.querySelector('#lead-form').addEventListener('submit', function (event) {
      event.preventDefault();
    });
    refreshStorageStatus();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/tracker.js":
            self._send(200, TRACKER_PATH.read_bytes(), "application/javascript; charset=utf-8")
            return
        if path == "/events":
            with EVENTS_LOCK:
                payload = json.dumps({"batches": EVENTS}, ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")

    def do_DELETE(self) -> None:
        if urlparse(self.path).path != "/events":
            self._send(404, b"", "text/plain")
            return
        with EVENTS_LOCK:
            EVENTS.clear()
        self._send(204, b"", "text/plain")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/tracking/events":
            self._send(404, b"", "text/plain")
            return
        length = min(int(self.headers.get("Content-Length", "0") or 0), 65536)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, b'{"success":false}', "application/json")
            return
        with EVENTS_LOCK:
            EVENTS.append(payload)
        self._send(202, b'{"success":true}', "application/json")

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Browser QA fixture listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
