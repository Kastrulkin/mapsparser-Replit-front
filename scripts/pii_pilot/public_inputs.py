"""Synthetic server-provenance inputs, separate from private PII expectations."""

import json
from functools import lru_cache
from pathlib import Path

from services.pii_protection.public_context import PublicSpan


@lru_cache(maxsize=1)
def records():
    path = Path(__file__).resolve().parents[2] / "tests/fixtures/pii/public_context.json"
    return json.loads(path.read_text())["cases"]


def public_context_for_case(case_id):
    return tuple(PublicSpan(**value) for value in records().get(case_id, ()))
