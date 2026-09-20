"""Read distribution metadata only; never import application or package modules."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys

import sitecustomize

GUARD_SHA = "93e4d9d7c99e9653a8e95e2735a369c3ab986e02c2afcb6d206aa63d05a9b590"
if hashlib.sha256(Path(sitecustomize.__file__).read_bytes()).hexdigest() != GUARD_SHA:
    raise RuntimeError("unexpected inherited guard")

PREFIX = Path("/private/tmp/localos-backend-deps-v2-20260920.xYc0jK/venv")
if Path(sys.prefix).resolve() != PREFIX:
    raise RuntimeError("unexpected metadata environment")
ROOT = Path(__file__).resolve().parents[4]
LOCK = ROOT / ".agent/tasks/production-readiness-20260917/raw/backend-deps-v2-artifact-lock-20260920.json"


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


expected = {
    normalize(item["name"]): item["version"]
    for item in json.loads(LOCK.read_text())["artifacts"]
}
distributions = []
installed = {}
for distribution in importlib.metadata.distributions(path=[str(PREFIX / "lib/python3.11/site-packages")]):
    metadata = distribution.metadata
    name = normalize(metadata["Name"])
    if name in installed:
        raise RuntimeError(f"duplicate installed distribution: {name}")
    installed[name] = distribution.version
    declaration = metadata.get("License", "").strip()
    distributions.append({
        "name": name,
        "version": distribution.version,
        "license_expression": metadata.get("License-Expression"),
        "license_first_line": declaration.splitlines()[0][:200] if declaration else None,
        "license_classifiers": [
            item for item in metadata.get_all("Classifier", [])
            if item.startswith("License ::")
        ],
        "license_files": metadata.get_all("License-File", []),
    })

payload = {
    "scope": "Current private macOS distribution metadata; not legal compliance or image/native library coverage",
    "prefix": str(PREFIX),
    "guard_sha256": GUARD_SHA,
    "artifact_manifest_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
    "inventory_equal_to_artifact_manifest": installed == expected,
    "distribution_count": len(distributions),
    "expression_count": sum(bool(item["license_expression"]) for item in distributions),
    "without_expression_classifiers_or_license": [
        item["name"] for item in distributions
        if not any((item["license_expression"], item["license_first_line"], item["license_classifiers"]))
    ],
    "distributions": sorted(distributions, key=lambda item: item["name"]),
}
print(json.dumps(payload, indent=2, sort_keys=True))
raise SystemExit(0 if installed == expected else 1)
