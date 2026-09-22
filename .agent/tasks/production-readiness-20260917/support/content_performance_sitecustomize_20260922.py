"""Guard for the fresh, private native PostgreSQL performance cluster only.

Copied to a private directory under the name sitecustomize.py by the lifecycle
runner. The OS network policy is an independent boundary for native libraries.
Import under another name is inert so validation can be tested without a DB.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys


ROLE = "readiness_perf_owner"
BASE_DATABASE = "readiness_perf_control"
OWNED_DATABASE = re.compile(r"localos_readiness_measure_[0-9a-f]{32}")
CONTEXT_KEYS = {"host", "port", "role", "base_database"}
DSN_KEYS = {"host", "port", "user", "dbname", "connect_timeout", "sslmode", "application_name"}


def validate_context(context: object) -> dict:
    if not isinstance(context, dict) or set(context) != CONTEXT_KEYS:
        raise PermissionError("invalid performance runtime context")
    if (
        context["host"] != "127.0.0.1"
        or type(context["port"]) is not int
        or not 32768 <= context["port"] <= 65535
        or context["role"] != ROLE
        or context["base_database"] != BASE_DATABASE
    ):
        raise PermissionError("performance runtime identity is not admitted")
    return context


def validate_parameters(parameters: dict, context: dict) -> None:
    if set(parameters) - DSN_KEYS:
        raise PermissionError("unexpected libpq connection parameter")
    if (
        parameters.get("host") != context["host"]
        or parameters.get("port") != f"{context['port']}"
        or parameters.get("user") != ROLE
    ):
        raise PermissionError("connection does not target the private performance cluster")
    database = parameters.get("dbname", "")
    if database not in {"postgres", BASE_DATABASE} and OWNED_DATABASE.fullmatch(database) is None:
        raise PermissionError("database is outside the performance fixture")
    if parameters.get("sslmode", "disable") not in {"disable", "prefer"}:
        raise PermissionError("unexpected TLS configuration for private loopback fixture")


def validate_environment() -> None:
    if any(key.startswith("PG") for key in os.environ):
        raise PermissionError("inherited libpq environment is prohibited")


def install() -> None:
    context_path = Path(__file__).resolve().with_name("context.json")
    if context_path.is_symlink() or not context_path.is_file():
        raise PermissionError("performance context must be a regular file")
    context = validate_context(json.loads(context_path.read_text(encoding="utf-8")))
    validate_environment()

    import psycopg2
    from psycopg2.extensions import make_dsn, parse_dsn

    original_connect = psycopg2.connect

    def guarded_connect(dsn=None, connection_factory=None, cursor_factory=None, **kwargs):
        validate_environment()
        parameters = parse_dsn(make_dsn(dsn, **kwargs))
        validate_parameters(parameters, context)
        parameters["connect_timeout"] = "5"
        parameters["sslmode"] = "disable"
        # Bound each database statement; these are applied only after the caller's
        # entire connection identity has been checked, never from caller options.
        parameters["options"] = "-c statement_timeout=30000 -c lock_timeout=5000"
        return original_connect(
            make_dsn(**parameters),
            connection_factory=connection_factory,
            cursor_factory=cursor_factory,
        )

    def audit(event, arguments):
        if event == "socket.connect":
            address = arguments[1]
            if not isinstance(address, tuple) or address[:2] != (context["host"], context["port"]):
                raise PermissionError("performance fixture prohibits other network connections")
        elif event == "socket.getaddrinfo" and arguments[0] != context["host"]:
            raise PermissionError("performance fixture prohibits external name resolution")
        elif event in {"socket.gethostbyname", "socket.gethostbyaddr", "socket.sendto", "socket.bind"}:
            raise PermissionError("performance fixture prohibits this network operation")

    psycopg2.connect = guarded_connect
    sys.addaudithook(audit)
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"


if __name__ == "sitecustomize":
    try:
        install()
    except BaseException:
        # Python otherwise continues after a sitecustomize import error.
        os.write(2, b"performance runtime guard initialization failed\n")
        os._exit(78)
