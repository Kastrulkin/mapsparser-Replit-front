#!/usr/bin/env python3
"""Quarantined manual API script; it is not a runnable pytest test."""


class LegacyApiScriptDisabledError(RuntimeError):
    """Raised before the retired script can make a network request."""


_GUIDANCE = (
    "tests/legacy/test_api.py is quarantined and cannot call register/login. "
    "Use the canonical isolated Docker/Testcontainers API gate command in README.md instead."
)


def test_api():
    raise LegacyApiScriptDisabledError(_GUIDANCE)


if __name__ == "__main__":
    raise SystemExit(_GUIDANCE)
