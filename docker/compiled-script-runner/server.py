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
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = os.environ.get("COMPILED_SCRIPT_RUNNER_SHARED_SECRET", "")
IMAGE_DIGEST = os.environ.get("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", "")
NONCES = deque(maxlen=2048)

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
    program = """import json, sys
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
    def limits():
        os.setgroups([])
        os.setgid(10002)
        os.setuid(10002)
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_AS, (96 * 1024 * 1024, 96 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    preexec = limits if sys.platform.startswith("linux") and os.geteuid() == 0 else None
    with tempfile.NamedTemporaryFile(mode="w+b", dir="/tmp") as output:
        # A fully constructed environment prevents inherited settings/secrets.
        # -P removes the working directory from sys.path; -S skips site hooks.
        # Unlike -I, this permits the fixed hash seed needed for reproducible sets.
        complete = subprocess.run([sys.executable, "-P", "-S", "-c", program], input=json.dumps(source) + "\n" + json.dumps(payload) + "\n", text=True, stdout=output, stderr=subprocess.PIPE, timeout=3, preexec_fn=preexec, env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1"})
        if complete.returncode:
            raise ValueError(complete.stderr[:300] or "compiled_script_failed")
        if output.tell() > 1_000_000:
            raise ValueError("compiled_script_output_limit")
        output.seek(0)
        return json.loads(output.read().decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/run" or len(SECRET) < 32 or not IMAGE_DIGEST.startswith("sha256:"):
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > 65536:
            self.send_error(413)
            return
        raw = self.rfile.read(size)
        timestamp, nonce = self.headers.get("X-Compiled-Timestamp", ""), self.headers.get("X-Compiled-Nonce", "")
        try:
            stale = abs(int(time.time()) - int(timestamp)) > 30
        except ValueError:
            stale = True
        expected = sign(timestamp.encode() + b"." + nonce.encode() + b"." + raw)
        if stale or not nonce or nonce in NONCES or not hmac.compare_digest(self.headers.get("X-Compiled-Signature", ""), expected):
            self.send_error(401)
            return
        NONCES.append(nonce)
        try:
            value = json.loads(raw)
            canonical = json.dumps({"source": str(value["source"]).replace("\r\n", "\n"), "manifest": value["manifest"], "fixtures": value["fixtures"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if value.get("artifact_hash") != "sha256:" + hashlib.sha256(canonical.encode()).hexdigest():
                raise ValueError("artifact_hash_mismatch")
            if not valid(value["manifest"].get("input_schema"), value["input"]):
                raise ValueError("input_schema_invalid")
            result = run_source(str(value["source"]), value["input"])
            if not isinstance(result, dict):
                raise ValueError("script_result_must_be_object")
            if not valid(value["manifest"].get("output_schema"), result):
                raise ValueError("output_schema_invalid")
            response = json.dumps({**result, "artifact_hash": value["artifact_hash"], "runtime_ai_calls": 0, "external_effects": []}, ensure_ascii=False, separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Compiled-Signature", sign(response))
            self.send_header("X-Compiled-Image-Digest", IMAGE_DIGEST)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers(); self.wfile.write(response)
        except Exception as error:
            self.send_error(422, str(error)[:200])
    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8091), Handler).serve_forever()
