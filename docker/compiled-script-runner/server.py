"""Internal-only executor. The process holding this service key never enters user code."""
import hashlib
import ast
import hmac
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

SECRET = os.environ.get("COMPILED_SCRIPT_RUNNER_SHARED_SECRET", "")
IMAGE_DIGEST = os.environ.get("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", "")
NONCES = deque(maxlen=2048)
NONCE_LOCK = threading.Lock()
MAX_REQUEST_BYTES = 262144
READ_TIMEOUT = 2

def valid(schema, value):
    allowed = {'type','properties','required','additionalProperties','items','enum','minItems','maxItems','minLength','maxLength','minimum','maximum'}
    if not isinstance(schema, dict) or set(schema) - allowed: return False
    kind = schema.get('type')
    if 'enum' in schema and (not isinstance(schema['enum'], list) or value not in schema['enum']): return False
    if kind == 'object':
        props = schema.get('properties', {}); required = schema.get('required', [])
        if not isinstance(value, dict) or not isinstance(props, dict) or any(key not in props or key not in value for key in required): return False
        if schema.get('additionalProperties', False) is not True and set(value) - set(props): return False
        return all(key not in value or valid(child, value[key]) for key, child in props.items())
    if kind == 'array': return isinstance(value, list) and isinstance(schema.get('items'), dict) and (not isinstance(schema.get('minItems'), int) or len(value) >= schema['minItems']) and (not isinstance(schema.get('maxItems'), int) or len(value) <= schema['maxItems']) and all(valid(schema['items'], item) for item in value)
    if kind == 'string': return isinstance(value, str) and (not isinstance(schema.get('minLength'), int) or len(value) >= schema['minLength']) and (not isinstance(schema.get('maxLength'), int) or len(value) <= schema['maxLength'])
    if kind == 'boolean': return isinstance(value, bool)
    if kind == 'integer': return isinstance(value, int) and not isinstance(value, bool) and (not isinstance(schema.get('minimum'), (int,float)) or value >= schema['minimum']) and (not isinstance(schema.get('maximum'), (int,float)) or value <= schema['maximum'])
    if kind == 'number': return isinstance(value, (int,float)) and not isinstance(value, bool) and (not isinstance(schema.get('minimum'), (int,float)) or value >= schema['minimum']) and (not isinstance(schema.get('maximum'), (int,float)) or value <= schema['maximum'])
    if kind == 'null': return value is None
    return False


def sign(value):
    return hmac.new(SECRET.encode(), value, hashlib.sha256).hexdigest()


def run_source(source, payload):
    tree = ast.parse(source, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) or isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("unsafe_source")
    program = """import json, sys, resource
if sys.platform.startswith('linux'):
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (96 * 1024 * 1024, 96 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
source = json.loads(sys.stdin.readline())
payload = json.loads(sys.stdin.readline())
safe = {'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool, 'dict': dict, 'list': list, 'enumerate': enumerate, 'range': range, 'sum': sum, 'min': min, 'max': max, 'sorted': sorted, 'set': set, 'zip': zip, 'abs': abs}
scope = {'__builtins__': safe}
exec(compile(source, '<approved-compiled-script>', 'exec'), scope, scope)
fn = scope.get('process')
if not callable(fn): raise ValueError('script must define process(input_payload)')
result = fn(payload)
print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
"""
    # Popen's native credential switches avoid preexec_fn in a threaded server.
    # Resource limits are set in the clean child before any user code is loaded.
    credentials = {"user": 10002, "group": 10002, "extra_groups": []} if sys.platform.startswith("linux") and os.geteuid() == 0 else {}
    with tempfile.NamedTemporaryFile(mode="w+b", dir="/tmp") as output:
        # A fully constructed environment prevents inherited settings/secrets.
        # -P removes the working directory from sys.path; -S skips site hooks.
        # Unlike -I, this permits the fixed hash seed needed for reproducible sets.
        complete = subprocess.run([sys.executable, "-P", "-S", "-c", program], input=json.dumps(source) + "\n" + json.dumps(payload) + "\n", text=True, stdout=output, stderr=subprocess.DEVNULL, timeout=3, env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1"}, **credentials)
        if complete.returncode:
            raise ValueError("compiled_script_failed")
        if output.tell() > 1_000_000:
            raise ValueError("compiled_script_output_limit")
        output.seek(0)
        return json.loads(output.read().decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    def signed_json(self, status, value):
        response = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Compiled-Signature", sign(response))
        self.send_header("X-Compiled-Image-Digest", IMAGE_DIGEST)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def setup(self):
        self.request.settimeout(READ_TIMEOUT)
        super().setup()

    def do_POST(self):
        if self.path != "/v1/run" or len(SECRET) < 32 or not IMAGE_DIGEST.startswith("sha256:"):
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if self.headers.get("Transfer-Encoding") or size <= 0 or size > MAX_REQUEST_BYTES:
            self.send_error(413)
            return
        try:
            raw = self.rfile.read(size)
        except TimeoutError:
            self.send_error(408)
            return
        if len(raw) != size:
            self.send_error(400)
            return
        timestamp, nonce = self.headers.get("X-Compiled-Timestamp", ""), self.headers.get("X-Compiled-Nonce", "")
        try:
            stale = abs(int(time.time()) - int(timestamp)) > 30
        except ValueError:
            stale = True
        expected = sign(timestamp.encode() + b"." + nonce.encode() + b"." + raw)
        with NONCE_LOCK:
            authorized = not stale and bool(nonce) and nonce not in NONCES and hmac.compare_digest(self.headers.get("X-Compiled-Signature", ""), expected)
            if authorized:
                NONCES.append(nonce)
        if not authorized:
            self.send_error(401)
            return
        try:
            value = json.loads(raw)
            canonical = json.dumps({"source": str(value["source"]).replace("\r\n", "\n"), "manifest": value["manifest"], "fixtures": value["fixtures"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if value.get("artifact_hash") != "sha256:" + hashlib.sha256(canonical.encode()).hexdigest():
                raise ValueError("artifact_hash_mismatch")
            if value["manifest"].get("runner_image_digest") != IMAGE_DIGEST:
                raise ValueError("runner_image_mismatch")
            if not valid(value["manifest"].get("input_schema"), value["input"]):
                raise ValueError("input_schema_invalid")
            result = run_source(str(value["source"]), value["input"])
            if not isinstance(result, dict):
                raise ValueError("script_result_must_be_object")
            if not valid(value["manifest"].get("output_schema"), result):
                raise ValueError("output_schema_invalid")
            self.signed_json(200, {**result, "artifact_hash": value["artifact_hash"], "runtime_ai_calls": 0, "external_effects": []})
        except Exception:
            error = sys.exc_info()[1]
            known = {"compiled_script_failed", "compiled_script_output_limit", "script_result_must_be_object", "output_schema_invalid", "unsafe_source", "artifact_hash_mismatch", "runner_image_mismatch", "input_schema_invalid"}
            code = str(error) if str(error) in known else "runner_request_invalid"
            if isinstance(error, subprocess.TimeoutExpired):
                code = "compiled_script_timeout"
            self.signed_json(422, {"error": code})
    def log_message(self, format, *args):
        return


class BoundedHTTPServer(HTTPServer):
    """Two executions, no unbounded request queue, shared replay protection."""
    request_queue_size = 4

    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.capacity = threading.BoundedSemaphore(2)
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="compiled")

    def process_request(self, request, client_address):
        if not self.capacity.acquire(blocking=False):
            try:
                request.settimeout(0.2)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nRetry-After: 1\r\n\r\n")
            finally:
                self.shutdown_request(request)
            return
        self.pool.submit(self._serve_request, request, client_address)

    def _serve_request(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            # Do not log request bodies, source, table data or authentication.
            pass
        finally:
            self.shutdown_request(request)
            self.capacity.release()

    def server_close(self):
        super().server_close()
        self.pool.shutdown(wait=True)


if __name__ == "__main__":
    BoundedHTTPServer(("0.0.0.0", 8091), Handler).serve_forever()
