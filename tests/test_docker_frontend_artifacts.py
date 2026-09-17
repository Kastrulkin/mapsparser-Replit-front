"""Both HTTP frontends must be built from the image's own source revision."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_image_builds_and_copies_both_frontends():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "RUN npm run build:all" in dockerfile
    assert "--from=frontend-builder /app/frontend/dist ./frontend/dist" in dockerfile
    assert "--from=frontend-builder /app/frontend/public-dist ./frontend/public-dist" in dockerfile


def test_public_build_cannot_be_inherited_from_host_artifacts():
    exclusions = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "frontend/dist" in exclusions
    assert "frontend/public-dist" in exclusions
