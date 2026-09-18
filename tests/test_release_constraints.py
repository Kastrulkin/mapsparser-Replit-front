"""Static contract for the app/worker release-only Python constraints."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
CONSTRAINTS = ROOT / "requirements.release.constraints.txt"
REQUIREMENTS = ROOT / "requirements.txt"
DOCKERFILE = ROOT / "Dockerfile"
SOURCE_PINS_SHA256 = "05c83919609c13ad2c27bdc5a87df56a4f43929d7dc82f7a03182e02c22519ab"
SOURCE_MAP_SHA256 = "0961bffa79bdfa53d38521f4342720ed8f1757ce46528550adddd1c3b996c96a"
RELEASE_MAP_SHA256 = "4f01951e8a11562e6733996a4b4ba010f46869aabefec4339e0e931f31998376"
CONSTRAINTS_MAP_SHA256 = "3a8dd28ab79796ee76903c5cc25625aecc4516f3799e23e6a1ae1ab24af437bf"
PACKAGING_TOOLS = {"pip": "26.2", "setuptools": "84.0.0", "wheel": "0.48.0"}


def _normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _constraint_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        name, version = value.split("==", 1)
        key = _normalize_name(name)
        assert key not in result
        result[key] = version
    return result


def _direct_requirement_names() -> set[str]:
    names: set[str] = set()
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        name = re.split(r"[<>=!~\[]", value, maxsplit=1)[0]
        names.add(_normalize_name(name))
    return names


def _map_digest(items: dict[str, str]) -> str:
    payload = "".join(f"{name}=={version}\n" for name, version in sorted(items.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_release_constraints_match_audited_app_inventory_contract():
    content = CONSTRAINTS.read_text(encoding="utf-8")
    constraints = _constraint_map()

    assert SOURCE_PINS_SHA256 in content
    assert SOURCE_MAP_SHA256 in content
    assert RELEASE_MAP_SHA256 in content
    assert CONSTRAINTS_MAP_SHA256 in content
    assert len(constraints) == 101
    assert not set(PACKAGING_TOOLS).intersection(constraints)
    assert _map_digest(constraints) == CONSTRAINTS_MAP_SHA256
    source_tools = dict(PACKAGING_TOOLS)
    source_tools["pip"] = "24.0"
    assert _map_digest(constraints | source_tools) == SOURCE_MAP_SHA256
    assert _map_digest(constraints | PACKAGING_TOOLS) == RELEASE_MAP_SHA256


def test_every_app_intent_root_is_constrained_exactly():
    constraints = _constraint_map()

    assert _direct_requirement_names().issubset(constraints)


def test_app_dockerfile_copies_and_consumes_constraints_without_disabling_dependencies():
    content = DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY requirements.txt requirements.release.constraints.txt ./" in content
    assert "python -m pip install --no-cache-dir --retries 3" in content
    assert "-c requirements.release.constraints.txt" in content
    assert "-r requirements.txt" in content
    assert "--no-deps" not in content
