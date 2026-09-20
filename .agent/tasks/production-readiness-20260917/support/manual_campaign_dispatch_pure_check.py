"""Explicit fake-cursor dispatch checks; no DB, network, dotenv or child processes."""
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
        raise PermissionError("dispatch tests forbid network")
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        name = Path(os.fsdecode(args[0])).name
        if name == ".env" or name.startswith(".env."):
            attempts["dotenv"] += 1
            raise PermissionError("dispatch tests forbid dotenv files")
    if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty"}:
        attempts["child_process"] += 1
        raise PermissionError("dispatch tests forbid child processes")


sys.addaudithook(audit)
socket.has_ipv6 = False
import psycopg2
import dotenv
import dotenv.main


def no_database(*args, **kwargs):
    attempts["database"] += 1
    raise PermissionError("dispatch tests forbid database connections")


def no_dotenv(*args, **kwargs):
    return False


psycopg2.connect = no_database
dotenv.load_dotenv = no_dotenv
dotenv.main.load_dotenv = no_dotenv
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import pytest

checks = ["tests/test_manual_campaign_dispatch_identity.py"]
if sys.argv[1:] == ["adjacent"]:
    checks += [
        "tests/test_author_template_authorization.py",
        "tests/test_riderra_template_authorization.py::test_dispatch_binds_only_freshly_validated_riderra_payload",
        "tests/test_riderra_template_authorization.py::test_native_dispatch_preflight_returns_only_exact_validated_riderra_payload",
        "tests/test_riderra_template_authorization.py::test_native_dispatch_preflight_accepts_exact_fresh_v2_riderra_receipt",
        "tests/test_riderra_template_authorization.py::test_native_dispatch_preflight_fails_closed_on_riderra_mutation",
        "tests/test_riderra_template_authorization.py::test_legacy_policy_never_loads_riderra_grant",
        "tests/test_agent_draft_approval_identity.py",
        "tests/test_agent_blueprint_reviews_outreach.py",
    ]
elif sys.argv[1:]:
    raise RuntimeError("unsupported check selection")
result = pytest.main([*checks, "--noconftest", "-q", "-p", "no:cacheprovider"])
print(json.dumps({"blocked_attempts": attempts}))
raise SystemExit(79 if any(attempts.values()) else result)
