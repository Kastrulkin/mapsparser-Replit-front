#!/usr/bin/env python3

import json
import sys

from services.agent_template_catalog import build_agent_template_catalog
from services.agent_template_certification import evaluate_template_certification
from services.agent_template_evidence import EVIDENCE_PATH, load_template_certification_evidence


def main() -> int:
    results = []
    for template in build_agent_template_catalog():
        if template.get("certification_status") != "beta":
            continue
        evidence = load_template_certification_evidence(str(template["key"]), str(template["version"]))
        results.append(evaluate_template_certification(template, evidence))
    print(json.dumps({"evidence_path": str(EVIDENCE_PATH), "templates": results}, ensure_ascii=False, indent=2))
    return 0 if results and all(item["certified"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
