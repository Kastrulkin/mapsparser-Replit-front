#!/usr/bin/env python3
"""Build complete Party 9 review chains with current verified facts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_OUTPUTS = Path(__file__).resolve().parent
BASE = REPO_OUTPUTS / "build_localos_party10_offline_review_20260813.py"
ROOT = Path("/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Obsidian/Obsidian Vault/outputs")


def load_base():
    spec = importlib.util.spec_from_file_location("party10_builder", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("party10_builder_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    base = load_base()
    base.SELECTION = ROOT / "localos-party9-family-fitness-hotels-20260812.json"
    base.LIVE = ROOT / "localos-party9-family-fitness-hotels-live-yandex-20260812.json"
    base.OUTPUT = ROOT / "localos-party9-review-v1-20260813.json"
    base.MARKDOWN = ROOT / "localos-party9-review-v1-20260813.md"
    base.main()
    payload = json.loads(base.OUTPUT.read_text(encoding="utf-8"))
    payload["schema_version"] = "localos_party9_offline_review_v1"
    payload["party"] = "Партия 9"
    for result in payload["results"]:
        result["party"] = "Партия 9"
    payload["canonical_sha256"] = base.canonical_sha(payload["results"])
    base.OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = base.MARKDOWN.read_text(encoding="utf-8").replace(
        "# Партия 10 - цепочки на проверку",
        "# Партия 9 - цепочки на проверку",
        1,
    )
    base.MARKDOWN.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
