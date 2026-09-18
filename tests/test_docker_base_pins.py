from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

NODE_BASE = "node:22-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5"
PYTHON_BASE = "python:3.11-bookworm@sha256:35d3a4a3d5e42e02ab916d44513a050689f12c0533d45598d229672503fe77ca"


def test_app_build_stages_use_verified_multi_platform_base_indexes() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM " + NODE_BASE + " AS frontend-builder" in dockerfile
    assert "FROM " + PYTHON_BASE in dockerfile
    assert "FROM node:22-slim AS frontend-builder" not in dockerfile
    assert "FROM python:3.11-bookworm\n" not in dockerfile


def test_base_pin_provenance_does_not_overstate_reproducibility() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "historical f0cc182a BuildKit resolution" in dockerfile
    assert "Registry v2 metadata verification" in dockerfile
    assert "fully reproducible" not in dockerfile
