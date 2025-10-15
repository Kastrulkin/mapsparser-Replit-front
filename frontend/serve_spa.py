#!/usr/bin/env python3
import http.server
import socketserver
import os
from pathlib import Path

DIST_DIR = Path(__file__).parent / 'dist'
PORT = int(os.environ.get('PORT', '3001'))


class SPARequestHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Serve files from dist directory
        path = super().translate_path(path)
        # Map to dist
        rel = os.path.relpath(path, os.getcwd())
        return str(DIST_DIR / rel)

    def do_GET(self):
        # Try to serve static file; on 404 fall back to index.html for SPA routes
        requested_path = (DIST_DIR / self.path.lstrip('/')).resolve()
        if requested_path.is_file():
            return super().do_GET()
        # Serve index.html for any unknown route
        self.path = '/index.html'
        return super().do_GET()


if __name__ == '__main__':
    os.chdir(DIST_DIR)
    with socketserver.TCPServer(('', PORT), SPARequestHandler) as httpd:
        print(f"SPA static server running at http://localhost:{PORT}")
        httpd.serve_forever()


