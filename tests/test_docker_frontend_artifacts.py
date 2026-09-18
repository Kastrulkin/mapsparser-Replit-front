"""Both HTTP frontends must be built from the image's own source revision."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_image_builds_and_copies_both_frontends():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "RUN npm run build:all" in dockerfile
    assert "--from=frontend-builder /app/frontend/dist ./frontend/dist" in dockerfile
    assert "--from=frontend-builder /app/frontend/public-dist ./frontend/public-dist" in dockerfile


def test_frontend_builder_satisfies_the_locked_node_compatibility_floor():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    package_lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    jest_dom = package_lock["packages"]["node_modules/@testing-library/jest-dom"]
    assert "FROM node:22-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS frontend-builder" in dockerfile
    assert jest_dom["engines"]["node"] == ">=22"


def test_public_build_cannot_be_inherited_from_host_artifacts():
    exclusions = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "frontend/dist" in exclusions
    assert "frontend/public-dist" in exclusions
