"""Explicit recipient projection tests under process-local effect guards."""
import json
import os
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[4]
if Path.cwd().resolve() != ROOT or os.getenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD") != "1":
    raise RuntimeError("repository cwd and disabled pytest autoload required")
attempts = {"network": 0, "database": 0, "dotenv": 0, "child_process": 0}


def audit(event, args):
    if event.startswith("socket.") and event != "socket.__new__":
        attempts["network"] += 1
        raise PermissionError("recipient tests forbid network")
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        name = Path(os.fsdecode(args[0])).name
        if name == ".env" or name.startswith(".env."):
            attempts["dotenv"] += 1
            raise PermissionError("recipient tests forbid dotenv files")
    if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty"}:
        attempts["child_process"] += 1
        raise PermissionError("recipient tests forbid child processes")


sys.addaudithook(audit)
socket.has_ipv6 = False
import psycopg2
import dotenv
import dotenv.main


def no_database(*args, **kwargs):
    attempts["database"] += 1
    raise PermissionError("recipient tests forbid database connections")


def no_dotenv(*args, **kwargs):
    return False


psycopg2.connect = no_database
dotenv.load_dotenv = no_dotenv
dotenv.main.load_dotenv = no_dotenv
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import pytest

checks = [
    "tests/test_campaign_recipient_review.py",
    "tests/test_riderra_template_authorization.py::test_native_preview_persist_and_template_approval_hooks_use_same_grant",
]
if sys.argv[1:] == ["adjacent"]:
    checks += [
        "tests/test_outreach_campaign_history_payload.py",
        "tests/test_author_template_authorization.py",
        "tests/test_manual_campaign_dispatch_identity.py",
        "tests/test_outreach_campaign_resume_sender_scope.py",
        "tests/test_founder_outreach_campaigns.py",
    ]
elif sys.argv[1:]:
    raise RuntimeError("unsupported test selection")
result = pytest.main([*checks, "--noconftest", "-q", "-p", "no:cacheprovider"])
print(json.dumps({"blocked_attempts": attempts}))
raise SystemExit(79 if any(attempts.values()) else result)
