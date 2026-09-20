"""Bounded copy-contract tests: no network, DB, dotenv or child processes."""
import json
import os
from pathlib import Path
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
        raise PermissionError("copy contract tests forbid network")
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        name = Path(os.fsdecode(args[0])).name
        if name == ".env" or name.startswith(".env."):
            attempts["dotenv"] += 1
            raise PermissionError("copy contract tests forbid dotenv files")
    if event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty"}:
        attempts["child_process"] += 1
        raise PermissionError("copy contract tests forbid child processes")


sys.addaudithook(audit)
import psycopg2


def no_database(*args, **kwargs):
    attempts["database"] += 1
    raise PermissionError("copy contract tests forbid database connections")


psycopg2.connect = no_database
sys.path.insert(0, str(ROOT / "src"))
import pytest

result = pytest.main(["tests/test_card_growth_copy_contract.py", "tests/test_card_growth_service.py",
                      "--noconftest", "-q", "-p", "no:cacheprovider"])
print(json.dumps({"blocked_attempts": attempts}))
raise SystemExit(79 if any(attempts.values()) else result)
