import builtins
from pathlib import Path
import socket
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SCRIPT = ROOT / "tests" / "legacy" / "test_api.py"
NO_EGRESS_HOOK = """
import sys

def block_network(event, _arguments):
    if event in ("socket.connect", "socket.connect_ex"):
        raise RuntimeError("network disabled by TEST-SAFE-01 child guard")

sys.addaudithook(block_network)
"""


def _run_child_without_egress(script, *arguments, timeout=60):
    return subprocess.run(
        [sys.executable, "-c", NO_EGRESS_HOOK + script, *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_default_collection_excludes_quarantined_legacy_directory():
    result = _run_child_without_egress(
        """
import pytest
raise SystemExit(pytest.main(["--collect-only", "-q"]))
"""
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "tests/legacy/test_api.py" not in result.stdout


def test_explicit_legacy_api_script_is_fail_closed_before_network():
    result = _run_child_without_egress(
        """
import runpy
import sys
runpy.run_path(sys.argv[1], run_name="__main__")
""",
        str(LEGACY_SCRIPT),
        timeout=10,
    )

    assert result.returncode != 0
    assert "quarantined" in result.stderr
    assert "cannot call register/login" in result.stderr


def test_legacy_api_entry_point_raises_before_any_request(monkeypatch):
    class NetworkForbidden:
        def __getattr__(self, _name):
            pytest.fail("legacy API entry attempted to access a network client")

    forbidden_requests = NetworkForbidden()
    original_import = builtins.__import__

    def safe_import(name, *arguments, **keywords):
        if name == "requests":
            return forbidden_requests
        return original_import(name, *arguments, **keywords)

    monkeypatch.setattr(socket.socket, "connect", lambda *_arguments: pytest.fail("legacy API entry attempted network access"))
    monkeypatch.setattr(socket.socket, "connect_ex", lambda *_arguments: pytest.fail("legacy API entry attempted network access"))
    namespace = {
        "__name__": "legacy_api_test",
        "__builtins__": {**vars(builtins), "__import__": safe_import},
    }
    source = LEGACY_SCRIPT.read_text()
    exec(compile(source, str(LEGACY_SCRIPT), "exec"), namespace)

    with pytest.raises(namespace["LegacyApiScriptDisabledError"], match="cannot call register/login"):
        namespace["test_api"]()


def test_child_no_egress_guard_blocks_legacy_style_loopback_request():
    result = _run_child_without_egress(
        """
import socket
socket.socket().connect(("127.0.0.1", 8000))
"""
    )

    assert result.returncode != 0
    assert "network disabled by TEST-SAFE-01 child guard" in result.stderr
