import importlib.util
from pathlib import Path
import sys


WORKER_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "ops"
    / "production"
    / "communication_compliance_worker.py"
)


def _load_worker():
    spec = importlib.util.spec_from_file_location(
        "production_communication_compliance_worker",
        WORKER_SOURCE,
    )
    assert spec is not None
    assert spec.loader is not None
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return worker


def test_archive_worker_only_claims_archive_owned_object_kinds():
    source = WORKER_SOURCE.read_text(encoding="utf-8")

    assert "object_kind IN ('metadata','content','attachment')" in source
    assert "status IN ('pending','retry')" in source


def test_archive_worker_is_self_contained_and_reports_provisional_mode(monkeypatch):
    monkeypatch.setenv("COMMUNICATION_ARCHIVE_BUCKET", "archive-test")
    monkeypatch.setenv("COMMUNICATION_ARCHIVE_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("COMMUNICATION_ARCHIVE_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("COMMUNICATION_COMPLIANCE_READY", "false")

    worker = _load_worker()

    assert worker.archive_capability_report() == {
        "backend": "provisional_s3",
        "configured": True,
        "compliance_ready": False,
    }
    assert worker.sha256_text(b"archive") == worker.sha256_text("archive")


def test_archive_worker_uploads_and_verifies_content(monkeypatch):
    fake_client = _FakeS3Client()
    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3(fake_client))
    monkeypatch.setenv("COMMUNICATION_ARCHIVE_BUCKET", "archive-test")
    monkeypatch.setenv("COMMUNICATION_ARCHIVE_PREFIX", "evidence")
    monkeypatch.setenv("COMMUNICATION_ARCHIVE_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("COMMUNICATION_ARCHIVE_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("COMMUNICATION_COMPLIANCE_READY", "false")
    worker = _load_worker()
    content = b"verified-content"

    result = worker.ProvisionalS3Archive().append_content(
        "2026/09/event/metadata.json",
        content,
        worker.sha256_text(content),
    )

    assert result["backend"] == "provisional_s3"
    assert result["key"] == "evidence/2026/09/event/metadata.json"
    assert result["compliance_ready"] is False
    assert fake_client.objects[("archive-test", result["key"])]["body"] == content


class _FakeS3Client:
    def __init__(self):
        self.objects = {}

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = {
            "body": kwargs["Body"],
            "metadata": kwargs["Metadata"],
        }

    def head_object(self, **kwargs):
        item = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        return {
            "ContentLength": len(item["body"]),
            "Metadata": item["metadata"],
        }


class _FakeBoto3:
    def __init__(self, client):
        self.client_instance = client

    def client(self, *_args, **_kwargs):
        return self.client_instance
