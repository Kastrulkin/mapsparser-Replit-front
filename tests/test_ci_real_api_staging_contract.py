"""Contracts for the GitHub-hosted synthetic real-API staging launcher."""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import textwrap
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/staging-real-api-nightly.yml"
SCRIPT = ROOT / "scripts/ci_real_api_staging.sh"


def _write_executable(path: Path, content: str):
    path.write_text(textwrap.dedent(content))
    path.chmod(0o755)


def _fake_launcher_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    scripts = root / "scripts"
    frontend = root / "frontend"
    fake_bin = tmp_path / "bin"
    scripts.mkdir(parents=True)
    frontend.mkdir()
    fake_bin.mkdir()
    shutil.copy2(SCRIPT, scripts / "ci_real_api_staging.sh")
    (root / "docker-compose.yml").write_text("services: {}\n")
    (root / "docker-compose.staging.yml").write_text("services: {}\n")
    _write_executable(
        scripts / "staging_journey_up.sh",
        """\
        #!/bin/sh
        set -eu
        printf started > "$HOME/../fake-state"
        if [ -f "$HOME/../slow-seed" ]; then
          trap 'exit 1' TERM INT
          sleep 5
        fi
        if [ -f "$PWD/fail-seed" ]; then
          exit 19
        fi
        """,
    )
    _write_executable(
        fake_bin / "docker",
        """\
        #!/bin/sh
        set -eu
        artifact_dir="$HOME/.."
        state="$artifact_dir/fake-state"
        log="$artifact_dir/docker.log"
        printf '%s\\n' "$*" >> "$log"
        has_state=false
        [ -f "$state" ] && has_state=true
        if [ "$1" = compose ]; then
          shift
          case " $* " in
            *" ps -aq "*)
              if [ "$has_state" = true ]; then
                printf app-id
              elif [ -f "$artifact_dir/preexisting" ]; then
                printf foreign-id
              fi
              exit 0
              ;;
            *" ps -q app "*)
              [ "$has_state" = true ] && printf app-id
              exit 0
              ;;
            *" down "*)
              printf down > "$artifact_dir/down"
              exit 0
              ;;
          esac
          exit 0
        fi
        if [ -f "$artifact_dir/inventory-fail" ]; then
          exit 71
        fi
        case "$1 ${2:-}" in
          "ps -aq")
            if [ "$has_state" = true ]; then
              printf app-id
            fi
            ;;
          "volume ls")
            if [ "$has_state" = true ]; then
              printf localos-ci-e2e-123-1_pgdata
            fi
            ;;
          "network ls")
            if [ "$has_state" = true ]; then
              printf localos-ci-e2e-123-1_default
            fi
            ;;
          "inspect --format"|"volume inspect"|"network inspect")
            if [ -f "$artifact_dir/foreign-label" ]; then
              printf foreign-project
            else
              printf localos-ci-e2e-123-1
            fi
            ;;
        esac
        """,
    )
    _write_executable(
        fake_bin / "npx",
        """\
        #!/bin/sh
        set -eu
        artifact_dir="$HOME/.."
        printf '%s|%s|%s\\n' "$JOURNEY_STAGING_CONTAINER" "$PLAYWRIGHT_BROWSERS_PATH" "$DOCKER_CONFIG" > "$artifact_dir/npx.log"
        if [ -f "$artifact_dir/sleep-browser" ]; then
          trap 'exit 1' TERM INT
          sleep 5
        fi
        [ ! -f "$PWD/fail-browser" ] || exit 29
        """,
    )
    return root, fake_bin


def _environment(fake_bin: Path, run_temp: Path) -> dict[str, str]:
    return {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
        "RUNNER_TEMP": str(run_temp),
    }


def _run_launcher(tmp_path: Path):
    root, fake_bin = _fake_launcher_root(tmp_path)
    run_temp = tmp_path / "runner-temp"
    run_temp.mkdir()
    completed = subprocess.run(
        [str(root / "scripts/ci_real_api_staging.sh")],
        cwd=root,
        env=_environment(fake_bin, run_temp),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed, root, run_temp / "localos-ci-real-api-123-1"


def test_workflow_is_separate_bounded_and_artifact_safe():
    text = WORKFLOW.read_text()
    assert "schedule:" in text
    assert "workflow_dispatch:" in text
    assert "contents: read" in text
    assert "timeout-minutes: 45" in text
    assert "cancel-in-progress: false" in text
    assert "bash scripts/ci_real_api_staging.sh" in text
    assert "if: always()" in text
    assert "frontend/test-results" in text
    assert "frontend/playwright-report" in text
    assert "npx --no-install playwright install --with-deps chromium" in text
    assert "PLAYWRIGHT_BROWSERS_PATH: ${{ runner.temp }}/ms-playwright" in text
    assert 'browser_path="$RUNNER_TEMP/ms-playwright"' in SCRIPT.read_text()
    assert "secrets." not in text
    assert "quality-nightly.yml" not in text


def test_launcher_uses_sanitized_docker_and_browser_context_and_owned_cleanup(tmp_path):
    completed, _root, artifact_dir = _run_launcher(tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert (artifact_dir / "down").read_text() == "down"
    app_id, browser_path, docker_config = (artifact_dir / "npx.log").read_text().strip().split("|")
    assert app_id == "app-id"
    assert browser_path == str(tmp_path / "runner-temp/ms-playwright")
    assert docker_config == str(artifact_dir / "docker-home/config")
    docker_log = (artifact_dir / "docker.log").read_text()
    assert "compose --project-name localos-ci-e2e-123-1 --env-file /dev/null" in docker_log
    assert "volume ls -q --filter name=^localos-ci-e2e-123-1_pgdata$" in docker_log
    assert "network ls -q --filter name=^localos-ci-e2e-123-1_default$" in docker_log
    assert "ps -aq --filter name=^/localos-ci-e2e-123-1-app-1$" in docker_log


def test_launcher_rejects_ambient_docker_configuration_before_any_start(tmp_path):
    root, fake_bin = _fake_launcher_root(tmp_path)
    run_temp = tmp_path / "runner-temp"
    run_temp.mkdir()
    environment = _environment(fake_bin, run_temp)
    environment["DOCKER_CONFIG"] = "/unsafe"
    completed = subprocess.run(
        [str(root / "scripts/ci_real_api_staging.sh")],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 2
    assert "ambient override is forbidden: DOCKER_CONFIG" in completed.stderr


def test_launcher_fails_closed_outside_github_hosted_runner(tmp_path):
    root, fake_bin = _fake_launcher_root(tmp_path)
    run_temp = tmp_path / "runner-temp"
    run_temp.mkdir()
    environment = _environment(fake_bin, run_temp)
    environment["GITHUB_ACTIONS"] = ""
    completed = subprocess.run(
        [str(root / "scripts/ci_real_api_staging.sh")],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 2
    assert "requires a fresh github-hosted runner" in completed.stderr


@pytest.mark.parametrize(
    ("marker", "expected"),
    (
        ("preexisting", "refusing pre-existing compose project"),
        ("inventory-fail", "cannot inspect labelled volume"),
        ("foreign-label", "refusing cleanup of resource outside owned project"),
    ),
)
def test_launcher_refuses_preexisting_inventory_failures_and_foreign_cleanup(tmp_path, marker, expected):
    root, fake_bin = _fake_launcher_root(tmp_path)
    run_temp = tmp_path / "runner-temp"
    run_temp.mkdir()
    artifact_dir = run_temp / "localos-ci-real-api-123-1"
    artifact_dir.mkdir()
    (artifact_dir / marker).write_text("1")
    completed = subprocess.run(
        [str(root / "scripts/ci_real_api_staging.sh")],
        cwd=root,
        env=_environment(fake_bin, run_temp),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode != 0
    assert expected in completed.stderr
    assert not (artifact_dir / "down").exists()


@pytest.mark.parametrize(("failure_file", "expected_status"), (("fail-seed", 19), ("fail-browser", 29)))
def test_launcher_cleans_only_started_project_after_seed_or_browser_failure(tmp_path, failure_file, expected_status):
    root, fake_bin = _fake_launcher_root(tmp_path)
    if failure_file == "fail-seed":
        (root / failure_file).write_text("1")
    else:
        (root / "frontend" / failure_file).write_text("1")
    run_temp = tmp_path / "runner-temp"
    run_temp.mkdir()
    completed = subprocess.run(
        [str(root / "scripts/ci_real_api_staging.sh")],
        cwd=root,
        env=_environment(fake_bin, run_temp),
        capture_output=True,
        text=True,
        timeout=10,
    )
    artifact_dir = run_temp / "localos-ci-real-api-123-1"
    assert completed.returncode == expected_status
    assert (artifact_dir / "down").read_text() == "down"


def test_launcher_signal_is_nonzero_and_runs_owned_cleanup(tmp_path):
    root, fake_bin = _fake_launcher_root(tmp_path)
    run_temp = tmp_path / "runner-temp"
    run_temp.mkdir()
    artifact_dir = run_temp / "localos-ci-real-api-123-1"
    artifact_dir.mkdir()
    (artifact_dir / "sleep-browser").write_text("1")
    process = subprocess.Popen(
        [str(root / "scripts/ci_real_api_staging.sh")],
        cwd=root,
        env=_environment(fake_bin, run_temp),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 3
    while not (artifact_dir / "npx.log").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    process.send_signal(signal.SIGTERM)
    _stdout, stderr = process.communicate(timeout=8)
    assert process.returncode != 0, stderr
    assert (artifact_dir / "down").read_text() == "down"


def test_launcher_signal_during_seed_never_starts_browser_phase(tmp_path):
    root, fake_bin = _fake_launcher_root(tmp_path)
    run_temp = tmp_path / "runner-temp"
    run_temp.mkdir()
    artifact_dir = run_temp / "localos-ci-real-api-123-1"
    artifact_dir.mkdir()
    (artifact_dir / "slow-seed").write_text("1")
    process = subprocess.Popen(
        [str(root / "scripts/ci_real_api_staging.sh")],
        cwd=root,
        env=_environment(fake_bin, run_temp),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 3
    while not (artifact_dir / "fake-state").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    process.send_signal(signal.SIGTERM)
    _stdout, stderr = process.communicate(timeout=8)
    assert process.returncode != 0, stderr
    assert (artifact_dir / "down").read_text() == "down"
    assert not (artifact_dir / "npx.log").exists()
