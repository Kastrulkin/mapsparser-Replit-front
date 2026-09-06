"""Executable compiled version is pinned independently of candidate drafts."""
from services.agent_run_queue import _validate_admission_state


def _blueprint(pointer, status="draft"):
    return {"id": "bp", "status": status, "compiled_approved_version_id": pointer, "metadata_json": {}}


def _version(version_id):
    return {"id": version_id, "compiled_state": "approved"}


def test_compiled_pointer_moves_only_on_new_approval_and_rejects_paused_blueprint():
    # Candidate v2 does not change the pointer; v1 remains executable.
    assert _validate_admission_state(_blueprint("v1"), _version("v1"), {}) is None
    assert _validate_admission_state(_blueprint("v1"), _version("v2"), {})["code"] == "AGENT_RUN_VERSION_STALE"
    # The approval transaction moves the protected pointer to v2.
    assert _validate_admission_state(_blueprint("v2"), _version("v1"), {})["code"] == "AGENT_RUN_VERSION_STALE"
    assert _validate_admission_state(_blueprint("v2"), _version("v2"), {}) is None
    for status in ("paused", "archived"):
        assert _validate_admission_state(_blueprint("v2", status), _version("v2"), {})["code"] == "AGENT_RUN_BLUEPRINT_NOT_ACTIVE"
