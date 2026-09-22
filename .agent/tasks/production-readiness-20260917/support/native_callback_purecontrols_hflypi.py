#!/usr/bin/env python3
"""Pure callback-DSN guard controls; imports no project runtime or Docker."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from urllib.parse import urlsplit


SOURCE = Path(__file__).with_name("native_hflypi_sitecustomize.py")
DATABASE = "readiness_full_test_" + "a" * 32
RELAY_PORT = 41001
LEGACY_PORT = 41002
LOGICAL = f"postgresql://test:test@127.0.0.1:35418/{DATABASE}"
PHYSICAL = f"postgresql://test:test@127.0.0.1:{RELAY_PORT}/{DATABASE}"


def make_dsn(dsn=None, **kwargs):
    parsed = urlsplit(str(dsn or "postgresql://"))
    values = {
        "host": parsed.hostname or "",
        "port": str(parsed.port or ""),
        "dbname": parsed.path.lstrip("/"),
        "user": parsed.username or "",
        "password": parsed.password or "",
    }
    values.update({key: str(value) for key, value in kwargs.items()})
    return "postgresql://%s:%s@%s:%s/%s" % (values["user"], values["password"], values["host"], values["port"], values["dbname"])


def parse_dsn(dsn):
    parsed = urlsplit(dsn)
    return {
        "host": parsed.hostname or "",
        "port": str(parsed.port or ""),
        "dbname": parsed.path.lstrip("/"),
        "user": parsed.username or "",
        "password": parsed.password or "",
    }


def selected_functions():
    tree = ast.parse(SOURCE.read_text())
    wanted = {"_validate_dsn", "_patch_psycopg2"}
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if {node.name for node in body} != wanted:
        raise RuntimeError("guard functions missing from source")
    return ast.Module(body=body, type_ignores=[])


def main() -> int:
    captures = []
    fake = ModuleType("psycopg2")
    fake.extensions = SimpleNamespace(make_dsn=make_dsn, parse_dsn=parse_dsn)

    def original_connect(dsn=None, connection_factory=None, cursor_factory=None, **kwargs):
        captures.append({"dsn": dsn, "kwargs": kwargs, "connection_factory": connection_factory, "cursor_factory": cursor_factory})
        return object()

    fake.connect = original_connect
    previous = sys.modules.get("psycopg2")
    sys.modules["psycopg2"] = fake
    environment = {
        "os": os,
        "NATIVE_HOSTS": {"127.0.0.1", "::1"},
        "_testcontainer_ports": set(),
        "_deny": lambda detail: (_ for _ in ()).throw(PermissionError("hfLYPi native aggregate guard: " + detail)),
    }

    class Adapter:
        def validate_dsn(self, parsed):
            if parsed["host"] != "127.0.0.1" or parsed["dbname"] != DATABASE or parsed["user"] != "test" or parsed["password"] != "test":
                raise PermissionError("bad fake callback DSN")
            if parsed["port"] == "35418":
                return PHYSICAL
            if parsed["port"] == str(RELAY_PORT) and os.environ.get("LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_MIGRATION_DSN") == PHYSICAL:
                return PHYSICAL
            if os.environ.get("LOCALOS_HFLYPI_TC_MODE") == "legacy-v1" and parsed["port"] == str(LEGACY_PORT):
                return None
            raise PermissionError("bad fake callback port")

    environment["_tc_adapter"] = Adapter()
    try:
        exec(compile(selected_functions(), str(SOURCE), "exec"), environment)
        environment["_patch_psycopg2"]()
        try:
            fake.connect(LOGICAL, port=35418)
        except PermissionError:
            pass
        else:
            raise RuntimeError("URL logical override was accepted")
        if captures:
            raise RuntimeError("URL logical override reached original connect")
        fake.connect(host="127.0.0.1", port=35418, dbname=DATABASE, user="test", password="test")
        fake.connect(host="127.0.0.1", port=RELAY_PORT, dbname=DATABASE, user="test", password="test")
        os.environ["LOCALOS_HFLYPI_TC_MODE"] = "legacy-v1"
        fake.connect(host="127.0.0.1", port=LEGACY_PORT, dbname=DATABASE, user="test", password="test")
    finally:
        if previous is None:
            sys.modules.pop("psycopg2", None)
        else:
            sys.modules["psycopg2"] = previous
    if len(captures) != 3 or any(row["dsn"] != PHYSICAL or row["kwargs"] for row in captures[:2]) or captures[2]["dsn"] is not None or captures[2]["kwargs"].get("port") != LEGACY_PORT or 35418 in environment["_testcontainer_ports"] or RELAY_PORT not in environment["_testcontainer_ports"] or LEGACY_PORT in environment["_testcontainer_ports"]:
        raise RuntimeError("callback DSN normalization control failed")
    print(json.dumps({"url_override_denied": True, "keyword_logical_rewritten": True, "keyword_physical_normalized": True, "legacy_kwargs_preserved": True, "legacy_port_registered": False, "logical_port_registered": False, "relay_port_registered": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    os.environ["LOCALOS_HFLYPI_TC_MODE"] = "callback-recovery-pg-v1"
    os.environ["LOCALOS_HFLYPI_TC_CALLBACK_RECOVERY_MIGRATION_DSN"] = PHYSICAL
    raise SystemExit(main())
