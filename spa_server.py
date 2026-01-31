import http.server
import socketserver
import os
import sys
import requests

PORT = 3000
API_PORT = 8000
DIRECTORY = "frontend/dist"

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api'):
            self.proxy_request('GET')
        elif os.path.exists(os.path.join(DIRECTORY, self.path.lstrip('/'))):
            super().do_GET()
        else:
            self.path = '/'
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api'):
            self.proxy_request('POST')
        else:
            self.send_error(405, "Method Not Allowed")

    def do_PUT(self):
        if self.path.startswith('/api'):
            self.proxy_request('PUT')
        else:
            self.send_error(405, "Method Not Allowed")

    def do_DELETE(self):
        if self.path.startswith('/api'):
            self.proxy_request('DELETE')
        else:
            self.send_error(405, "Method Not Allowed")
            
    def do_OPTIONS(self):
        if self.path.startswith('/api'):
            self.proxy_request('OPTIONS')
        else:
            self.send_response(200)
            self.end_headers()

    def proxy_request(self, method):
        target_url = f'http://127.0.0.1:{API_PORT}{self.path}'
        print(f"Proxying {method} {self.path} -> {target_url}")
        
        try:
            # Read body for POST/PUT
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            headers = {k: v for k, v in self.headers.items() if k.lower() != 'host'}
            
            response = requests.request(
                method=method,
                url=target_url,
                headers=headers,
                data=body,
                allow_redirects=False
            )
            
            self.send_response(response.status_code)
            for k, v in response.headers.items():
                if k.lower() not in ['content-encoding', 'transfer-encoding', 'content-length']:
                    self.send_header(k, v)
            
            self.send_header('Content-Length', str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)
            
        except Exception as e:
            print(f"Proxy error: {e}")
            self.send_error(502, f"Bad Gateway: {e}")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

if __name__ == "__main__":
    if not os.path.exists(DIRECTORY):
        print(f"Error: Directory {DIRECTORY} not found. Run 'npm run build' in frontend directory.")
        sys.exit(1)

    print(f"Starting SPA server on port {PORT} with API proxy to port {API_PORT}")
    with socketserver.TCPServer(("", PORT), SPAHandler) as httpd:
        print(f"Serving at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.shutdown()
