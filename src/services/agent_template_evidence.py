import json
from pathlib import Path
from typing import Any, Dict

from services.agent_template_certification import empty_certification_evidence


EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "config" / "agent_template_certification_evidence.json"


def load_template_certification_evidence(template_key: str, template_version: str) -> Dict[str, Any]:
    evidence = empty_certification_evidence()
    try:
        payload = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return evidence
    records = payload.get("templates") if isinstance(payload, dict) and isinstance(payload.get("templates"), dict) else {}
    record = records.get(f"{template_key}@{template_version}") if isinstance(records, dict) else None
    if not isinstance(record, dict):
        return evidence
    for key in evidence:
        if key in record:
            evidence[key] = record[key]
    evidence["template_key"] = template_key
    evidence["template_version"] = template_version
    return evidence
