from pathlib import Path


def test_backend_hot_sync_blocks_dependency_drift() -> None:
    source = Path("scripts/deploy_backend_src.sh").read_text(encoding="utf-8")

    assert "git status --short -- Dockerfile" in source
    assert "requirements*.txt" in source
    assert "Backend hot-sync is blocked" in source
    assert "Build and deploy a new application image" in source
