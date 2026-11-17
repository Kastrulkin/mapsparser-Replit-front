"""Versioned, provider-free preparation contract. No industry-specific actions."""
import hashlib
import json

CONTRACT = "inbound_case_review.v1"
STEPS = [
    {"key": "prepare_case", "type": "artifact", "title": "Подготовить обращение", "artifact_type": "inbound_case_review"},
    {"key": "review_case", "type": "approval", "title": "Проверить черновик", "approval_type": "inbound_case_review"},
    {"key": "record_resolution", "type": "artifact", "title": "Сохранить решение", "artifact_type": "inbound_case_resolution"},
]


class CaseError(Exception):
    def __init__(self, code, status=409):
        super().__init__(code)
        self.code, self.status = code, status


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def object_value(value):
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else {}


def text(value, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise CaseError("invalid_case_input", 400)
    return value.strip()


def normalize_case(body):
    """Only a reference and selected preparation are shared, never the raw mailbox."""
    if not isinstance(body, dict):
        raise CaseError("invalid_case_input", 400)
    result = {key: text(body.get(key), limit, True) for key, limit in (
        ("source_system", 64), ("source_tenant", 128), ("source_id", 128),
        ("source_version", 128), ("actor_id", 128), ("reviewer_actor_id", 128), ("title", 240),
    )}
    result["proposed_reply"] = text(body.get("proposed_reply", ""), 12000)
    result["summary"] = text(body.get("summary", ""), 4000)
    result["classification"] = text(body.get("classification", "unclassified"), 80, True)
    result["replaces_run_id"] = text(body.get("replaces_run_id", ""), 128)
    missing = body.get("missing_information", [])
    if not isinstance(missing, list) or len(missing) > 20:
        raise CaseError("invalid_case_input", 400)
    result["missing_information"] = [text(item, 200, True) for item in missing]
    result["contract"] = CONTRACT
    return result


def validate_preset(version):
    steps = version.get("steps_json")
    if isinstance(steps, str):
        steps = json.loads(steps)
    allowlist = version.get("capability_allowlist_json")
    if isinstance(allowlist, str):
        allowlist = json.loads(allowlist)
    if steps != STEPS or allowlist != [] or version.get("compiled_state", "legacy") != "legacy":
        raise CaseError("case_preset_changed")


def resolve_binding(client, body, operation):
    """An external tenant/role can never choose its LocalOS business or user."""
    matches = [item for item in object_value(client.get("metadata_json")).get("inbound_case_bindings", [])
               if item.get("enabled") is True and item.get("source_system") == body.get("source_system")
               and item.get("source_tenant") == body.get("source_tenant")]
    if len(matches) != 1:
        raise CaseError("case_binding_required", 403)
    binding = matches[0]
    actor = binding.get("actors", {}).get(body.get("actor_id"))
    if not isinstance(actor, dict) or operation not in actor.get("operations", []):
        raise CaseError("case_actor_denied", 403)
    if not actor.get("user_id") or not binding.get("business_id") or not binding.get("version_id"):
        raise CaseError("case_binding_invalid", 403)
    return binding, {"user_id": actor["user_id"]}


def review_payload(case):
    return {"contract": CONTRACT, "title": case["title"], "summary": case["summary"],
            "classification": case["classification"], "classification_method": "source_preparation",
            "source_id": case["source_id"], "source_version": case["source_version"],
            "missing_information": case["missing_information"], "proposed_reply": case["proposed_reply"],
            "preparation_only": True, "external_dispatch_performed": False, "credits_spent": 0,
            "next_action": "review_draft" if case["proposed_reply"] else "provide_draft"}
