"""Stage an explicit code/synthetic-fixture allowlist; never copy a checkout wholesale."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
FILES = (
    "src/services/ai_spend_budget.py", "src/services/gigachat_client.py",
    "src/services/operator_tool_loop.py", "src/services/operator_context.py", "src/gigachat_config.py",
    "tests/conftest.py", "tests/test_pii_protection.py", "tests/test_llm_budget_boundary.py",
    "tests/test_operator_tool_loop.py", "tests/fixtures/pii/synthetic_200.jsonl", "pytest.ini",
    "requirements.pii.txt", "requirements.pii-pilot.txt", "scripts/pii_pilot/Dockerfile",
    "requirements.pii-vps.txt", "requirements.pii-linux.lock.txt", "scripts/pii_pilot/Dockerfile.vps",
    "tests/test_pii_shared_runtime.py",
)


def stage(destination):
    destination = Path(destination).resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError("Stage outside the checkout")
    paths = {ROOT / path for path in FILES}
    for folder in ("src/services/llm", "src/services/pii_protection", "scripts/pii_pilot"):
        paths.update((ROOT / folder).glob("*.py"))
    fixture = ROOT / "tests/fixtures/pii/public_context.json"
    if fixture.exists():
        paths.add(fixture)
    manifest = {}
    for source in sorted(paths):
        if source.is_symlink() or not source.is_file():
            raise ValueError("Unexpected source file")
        relative = source.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
    (destination / "stage-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Staged {len(manifest)} allowlisted code/fixture files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    stage(parser.parse_args().destination)
