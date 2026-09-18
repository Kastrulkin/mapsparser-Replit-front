"""Compiled browser fixtures require an explicit build-time staging opt-in."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
FLAG = "VITE_COMPILED_SCRIPT_PREVIEW_ENABLED"


def test_canonical_image_accepts_opt_in_without_enabling_it_by_default():
    frontend_stage = (ROOT / "Dockerfile").read_text().split("FROM python:", 1)[0]
    assert f"ARG {FLAG}=false" in frontend_stage
    assert f"ENV {FLAG}=${{{FLAG}}}" in frontend_stage
    assert frontend_stage.index(f"ENV {FLAG}=") < frontend_stage.index("RUN npm run build:all")


def test_staging_compose_passes_preview_opt_in_to_the_build():
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker Compose CLI required; no daemon needed")
    result = subprocess.run(
        [docker, "compose", "--env-file", "/dev/null", "-f", "docker-compose.yml",
         "-f", "docker-compose.staging.yml", "config", "--no-env-resolution", "--format", "json"],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "Compose rendering failed; do not expose rendered credentials"
    app = json.loads(result.stdout)["services"]["app"]
    assert app["build"]["args"].get(FLAG) == "true"
