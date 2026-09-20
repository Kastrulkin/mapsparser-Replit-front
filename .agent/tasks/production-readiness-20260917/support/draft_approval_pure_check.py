"""Explicit mocked approval tests; no DB, network, dotenv or child processes."""
import json
import os
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[4]
if Path.cwd().resolve() != ROOT:
    raise RuntimeError("unexpected repository cwd")
if os.getenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD") != "1":
    raise RuntimeError("pytest plugin autoload must be disabled")
attempts = {"network": 0, "database": 0, "dotenv": 0, "child_process": 0}


def audit(event, args):
    if event.startswith("socket.") and event != "socket.__new__":
        attempts["network"] += 1
        raise PermissionError("approval tests forbid network")
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        name = Path(os.fsdecode(args[0])).name
        if name == ".env" or name.startswith(".env."):
            attempts["dotenv"] += 1
            raise PermissionError("approval tests forbid dotenv files")
    if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty"}:
        attempts["child_process"] += 1
        raise PermissionError("approval tests forbid child processes")


sys.addaudithook(audit)
# Avoid urllib3's import-time IPv6 bind probe; network is not under test.
socket.has_ipv6 = False
import psycopg2
import dotenv
import dotenv.main


def no_database(*args, **kwargs):
    attempts["database"] += 1
    raise PermissionError("approval tests forbid database connections")


def no_dotenv(*args, **kwargs):
    return False


psycopg2.connect = no_database
dotenv.load_dotenv = no_dotenv
dotenv.main.load_dotenv = no_dotenv
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import pytest

checks = ["tests/test_agent_draft_approval_identity.py"]
if sys.argv[1:] == ["adjacent"]:
    checks += [
        "tests/test_agent_blueprint_reviews_outreach.py",
        "tests/test_legacy_agent_approval_policy.py",
        "tests/test_agent_blueprint_runtime_policy.py",
        "tests/test_agent_blueprint_capabilities.py",
        "tests/test_agent_blueprint_async_contracts.py",
        "tests/test_agent_blueprint_compiler.py",
        "tests/test_agent_blueprint_runtime_connections.py",
        "tests/test_approval_boundaries_audit.py",
        "tests/test_google_sheets_preconditions.py",
    ]
elif sys.argv[1:]:
    raise RuntimeError("unsupported check selection")
result = pytest.main([*checks, "--noconftest", "-q", "-p", "no:cacheprovider"])
print(json.dumps({"blocked_attempts": attempts}))
raise SystemExit(79 if any(attempts.values()) else result)
