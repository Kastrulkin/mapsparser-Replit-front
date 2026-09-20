"""One bounded reset-route check; no dotenv, sockets, DB or arbitrary children.

Baseline replaces only the registered handler implementation with the exact
function from cf36cbb0. The Flask route/facade and current regression stay real;
this is not a historical full-application or rate-limiter verification.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[4]
GUARD_DIR = Path("/private/tmp/localos-backend-full-20260920.XoKy4o/guard")
if Path.cwd().resolve() != ROOT:
    raise RuntimeError("unexpected repository cwd")
if os.getenv("PYTHONPATH") != f"{GUARD_DIR}:src":
    raise RuntimeError("unexpected import search path")
if any(key.startswith("GIT_") for key in os.environ):
    raise RuntimeError("Git environment overrides are forbidden")
main_spec = importlib.util.find_spec("main")
if main_spec is None or Path(main_spec.origin).resolve() != ROOT / "src/main.py":
    raise RuntimeError("unexpected main import origin")

import sitecustomize

GUARD_SHA = "93e4d9d7c99e9653a8e95e2735a369c3ab986e02c2afcb6d206aa63d05a9b590"
if hashlib.sha256(Path(sitecustomize.__file__).read_bytes()).hexdigest() != GUARD_SHA:
    raise RuntimeError("unexpected inherited guard")
if sitecustomize.AGGREGATE_GUARD_ACTIVE_PID != os.getpid():
    raise RuntimeError("inherited guard not active")
if os.getenv("PYTHON_DOTENV_DISABLED") != "1":
    raise RuntimeError("dotenv must be disabled before imports")

attempts = {"network": 0, "database": 0, "dotenv_file": 0, "child_process": 0,
            "inherited_guard": 0}
baseline_command = ["/usr/bin/git", "show", "cf36cbb0:src/legacy_routes/public_requests.py"]
BASELINE_SHA = "ff444056f3bf396d31c6ebef2cc33e5a8b5ce50d8347829ad70040eefdbbb5c3"
inherited_deny = sitecustomize._deny


def counted_inherited_deny(message):
    attempts["inherited_guard"] += 1
    inherited_deny(message)


sitecustomize._deny = counted_inherited_deny


def audit(event, args):
    if event in {"socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg",
                 "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
                 "socket.getnameinfo"}:
        attempts["network"] += 1
        print(json.dumps({"denied_event": event, "frames": [
            {"file": frame.filename, "line": frame.lineno, "function": frame.name}
            for frame in traceback.extract_stack(limit=10)
        ]}))
        raise PermissionError("reset pure check: no network")
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        name = Path(os.fsdecode(args[0])).name
        if name == ".env" or name.startswith(".env."):
            attempts["dotenv_file"] += 1
            raise PermissionError("reset pure check: no dotenv file reads")
    if event == "subprocess.Popen" and list(args[1]) != baseline_command:
        attempts["child_process"] += 1
        raise PermissionError("reset pure check: unexpected child process")
    if event in {"os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty"}:
        attempts["child_process"] += 1
        raise PermissionError("reset pure check: unexpected process primitive")


sys.addaudithook(audit)
# urllib3 otherwise probes IPv6 by binding ::1 during import. This pure suite
# has no transport coverage; mark IPv6 unavailable instead of allowing that bind.
# The diagnostic capture retains the denied probe; every network guard stays on.
socket.has_ipv6 = False
import psycopg2


def no_database(*args, **kwargs):
    attempts["database"] += 1
    raise PermissionError("reset pure check: no database")


psycopg2.connect = no_database
# Flask-SQLAlchemy requires a URI even though these tests never use its engine.
# The connect guard above remains unconditional; this is synthetic configuration.
if os.getenv("DATABASE_URL"):
    raise RuntimeError("inherited database configuration is forbidden")
os.environ["DATABASE_URL"] = "postgresql://reset_test:synthetic@127.0.0.1:1/reset_pure_never_connect"
import dotenv
import dotenv.main


def no_dotenv(*args, **kwargs):
    return False


dotenv.load_dotenv = no_dotenv
dotenv.main.load_dotenv = no_dotenv
import main
import pytest

mode = sys.argv[1]
if mode == "baseline":
    original = subprocess.check_output(baseline_command, text=True)
    if hashlib.sha256(original.encode()).hexdigest() != BASELINE_SHA:
        raise RuntimeError("historical source hash mismatch")
    function = next(node for node in ast.parse(original).body
                    if isinstance(node, ast.FunctionDef) and node.name == "confirm_reset")
    function.decorator_list = []
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, "cf36cbb0:public_requests.py", "exec"), vars(main._chunk_public_requests))
    main._IMPLEMENTATIONS["confirm_reset"] = main._chunk_public_requests.confirm_reset
    print(json.dumps({"baseline_source_sha256": hashlib.sha256(original.encode()).hexdigest()}))
elif mode not in {"current", "adjacent"}:
    raise ValueError("expected baseline, current or adjacent")

test_files = ["tests/test_password_reset_sessions.py"]
if mode == "adjacent":
    test_files += ["tests/test_auth_security_regressions.py", "tests/test_browser_session_security.py"]
result = pytest.main([*test_files, "-q", "-p", "no:cacheprovider"])
print(json.dumps({"mode": mode, "guard_sha256": GUARD_SHA, "blocked_attempts": attempts}))
if any(attempts.values()):
    raise SystemExit(79)
raise SystemExit(result)
