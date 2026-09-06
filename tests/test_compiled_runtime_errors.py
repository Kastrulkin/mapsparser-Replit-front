import hashlib
import hmac
import http.client
import json

import pytest

from services import compiled_script_runtime
from tests.test_compiled_runner_load import artifact, runner


def test_real_runner_script_rejection_is_failed_preview_not_input_or_transport(runner):
    module, _server = runner
    from services.compiled_script_artifact import build_artifact
    good = artifact(module.IMAGE_DIGEST)
    candidate = build_artifact("def process(input_payload):\n    return missing_value", good["manifest"], good["fixtures"])
    outcome = compiled_script_runtime.preview(candidate, {})
    assert outcome["status"] == "failed"
    assert outcome["reason"] == "compiled_script_failed"
    assert outcome["result"]["artifact_hash"] == candidate["artifact_hash"]
    bad_output = build_artifact("def process(input_payload):\n    return {'value': 'not a number'}", good["manifest"], good["fixtures"])
    assert compiled_script_runtime.preview(bad_output, {})["reason"] == "output_schema_invalid"


@pytest.mark.parametrize("case,code", [
    ("malformed", "compiled_script_runner_response_invalid"),
    ("truncated", "compiled_script_runner_unreachable"),
    ("output", "compiled_script_runner_output_invalid"),
    ("unsigned_rejection", "compiled_script_runner_response_invalid"),
])
def test_invalid_http_responses_are_typed_runtime_errors(monkeypatch, case, code):
    digest = "sha256:" + "b" * 64
    secret = "test-only-secret" * 4
    program = artifact(digest)
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_URL", "http://runner")
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_SHARED_SECRET", secret)
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", digest)
    raw = b"{broken" if case == "malformed" else json.dumps({"value": "wrong", "artifact_hash": program["artifact_hash"], "runtime_ai_calls": 0, "external_effects": []}).encode()
    closed = []

    class Response:
        status = 422 if case == "unsigned_rejection" else 200
        def read(self, _limit):
            if case == "truncated":
                raise http.client.IncompleteRead(b"partial", 100)
            return raw
        def getheader(self, key, default=None):
            if key == "X-Compiled-Image-Digest":
                return digest
            if key == "X-Compiled-Signature":
                return "invalid" if case == "unsigned_rejection" else hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
            return default

    class Connection:
        def __init__(self, *_args, **_kwargs):
            pass
        def request(self, *_args, **_kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            closed.append(True)

    monkeypatch.setattr(compiled_script_runtime.http.client, "HTTPConnection", Connection)
    with pytest.raises(compiled_script_runtime.CompiledRuntimeUnavailable, match=code):
        compiled_script_runtime.preview(program, {})
    assert closed == [True]
