#!/usr/bin/env python3
"""DRAFT / UNEXECUTED negative/propagation probe for the hfLYPi guard.

The probe is intentionally not self-running.  Invoke it only from the
aggregate's named tmux wrapper after the guard has been copied into the frozen
archive and the launcher has set ``LOCALOS_HFLYPI_DOCKER_SOCKET``,
``TESTCONTAINERS_RYUK_DISABLED=true`` and the literal Testcontainers host
override and owned internal network.  Negative modes must be denied before a
packet is emitted.  ``own-postgres`` is the only positive mode and is reserved
for after root has created and identity-verified the synthetic native cluster.
This is not authorization to run the draft guard before launcher review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


NONCE = "hfLYPi"
NATIVE_PORT = 35418
FROZEN_SOURCE_ROOT = Path("/private/tmp/localos-readiness-20260921.hfLYPi/source")


def _guard_details() -> dict[str, object]:
    import sitecustomize

    guard_path = Path(sitecustomize.__file__).resolve()
    return {
        "guard_path": str(guard_path),
        "guard_sha256": hashlib.sha256(guard_path.read_bytes()).hexdigest(),
        "provenance": sitecustomize.guard_provenance(),
    }


def _expect_denied(label: str, action) -> dict[str, object]:
    try:
        action()
    except PermissionError:
        return {"case": label, "denied": True}
    raise RuntimeError(f"guard unexpectedly allowed {label}")


def _external_tcp() -> None:
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        connection.settimeout(1)
        connection.connect(("198.51.100.1", 443))
    finally:
        connection.close()


def _foreign_local() -> None:
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        connection.settimeout(1)
        connection.connect(("127.0.0.1", 8000))
    finally:
        connection.close()


def _udp() -> None:
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        connection.sendto(b"guard-probe", ("198.51.100.1", 53))
    finally:
        connection.close()


def _dns() -> None:
    socket.getaddrinfo("example.invalid", 443)


def _postgres_foreign_host() -> None:
    import psycopg2

    psycopg2.connect("postgresql://audit_owner@198.51.100.1:35418/readiness_full_test_hflypi", connect_timeout=1)


def _postgres_foreign_database() -> None:
    import psycopg2

    psycopg2.connect("postgresql://audit_owner@127.0.0.1:35418/not_owned", connect_timeout=1)


def _postgres_explicit_options() -> None:
    import psycopg2

    psycopg2.connect(
        "postgresql://audit_owner@127.0.0.1:35418/readiness_full_test_hflypi?options=-c%20search_path%3Dpublic",
        connect_timeout=1,
    )


def _postgres_pghostaddr() -> None:
    import psycopg2

    original = os.environ.get("PGHOSTADDR")
    os.environ["PGHOSTADDR"] = "198.51.100.1"
    try:
        psycopg2.connect("postgresql://audit_owner@127.0.0.1:35418/readiness_full_test_hflypi", connect_timeout=1)
    finally:
        if original is None:
            os.environ.pop("PGHOSTADDR", None)
        else:
            os.environ["PGHOSTADDR"] = original


def _postgres_pgoptions() -> None:
    import psycopg2

    original = os.environ.get("PGOPTIONS")
    os.environ["PGOPTIONS"] = "-c search_path=public"
    try:
        psycopg2.connect("postgresql://audit_owner@127.0.0.1:35418/readiness_full_test_hflypi", connect_timeout=1)
    finally:
        if original is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = original


def _postgres_pgservice() -> None:
    import psycopg2

    original = os.environ.get("PGSERVICE")
    os.environ["PGSERVICE"] = "foreign"
    try:
        psycopg2.connect("postgresql://audit_owner@127.0.0.1:35418/readiness_full_test_hflypi", connect_timeout=1)
    finally:
        if original is None:
            os.environ.pop("PGSERVICE", None)
        else:
            os.environ["PGSERVICE"] = original


def _child() -> None:
    source_root = Path(os.environ.get("LOCALOS_HFLYPI_SOURCE_ROOT", "")).resolve()
    if source_root != FROZEN_SOURCE_ROOT or not (source_root / "src" / "sitecustomize.py").is_file():
        raise RuntimeError("child probe requires the exact frozen archive guard copy")
    child_environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHON_DOTENV_DISABLED": "1",
        "LOCALOS_HFLYPI_DOCKER_SOCKET": os.environ.get("LOCALOS_HFLYPI_DOCKER_SOCKET", ""),
        "TESTCONTAINERS_RYUK_DISABLED": "true",
        "TESTCONTAINERS_HOST_OVERRIDE": "127.0.0.1",
        "LOCALOS_HFLYPI_TESTCONTAINERS_NETWORK": "localos-readiness-hflypi_internal",
        "PYTHONPATH": os.pathsep.join((str(source_root / "src"), str(source_root))),
    }
    source = """
import json
import socket
import sitecustomize
result = {'origin': sitecustomize.__file__, 'pid': sitecustomize.AGGREGATE_GUARD_ACTIVE_PID}
try:
    socket.socket().connect(('127.0.0.1', 8000))
except PermissionError:
    result['denied'] = True
else:
    result['denied'] = False
print(json.dumps(result))
raise SystemExit(0 if result['denied'] else 1)
"""
    completed = subprocess.run(
        [sys.executable, "-c", source],
        env=child_environment,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())


def _own_postgres() -> None:
    import psycopg2

    database_url = os.environ.get("LOCALOS_HFLYPI_PROBE_DSN", "")
    expected = "postgresql://audit_owner:hflypi-local-only@127.0.0.1:35418/readiness_full_test_hflypi"
    if database_url != expected:
        raise RuntimeError("positive probe requires the exact synthetic hfLYPi DSN")
    connection = psycopg2.connect(database_url, connect_timeout=5)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT current_database(), current_user")
            observed = cursor.fetchone()
        finally:
            cursor.close()
    finally:
        connection.close()
    if observed != ("readiness_full_test_hflypi", "audit_owner"):
        raise RuntimeError("positive probe database identity mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("negative", "child", "own-postgres"))
    arguments = parser.parse_args()
    payload = _guard_details()
    if arguments.mode == "negative":
        payload["checks"] = [
            _expect_denied("external_tcp", _external_tcp),
            _expect_denied("foreign_local", _foreign_local),
            _expect_denied("udp", _udp),
            _expect_denied("dns", _dns),
            _expect_denied("postgres_foreign_host", _postgres_foreign_host),
            _expect_denied("postgres_foreign_database", _postgres_foreign_database),
            _expect_denied("postgres_explicit_options", _postgres_explicit_options),
            _expect_denied("postgres_pghostaddr", _postgres_pghostaddr),
            _expect_denied("postgres_pgoptions", _postgres_pgoptions),
            _expect_denied("postgres_pgservice", _postgres_pgservice),
        ]
    elif arguments.mode == "child":
        _child()
        payload["child_guard_propagated"] = True
    else:
        _own_postgres()
        payload["own_postgres_verified"] = True
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
