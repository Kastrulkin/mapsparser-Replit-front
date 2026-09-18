"""Safety contract for the deployment-coupled OpenClaw ops smoke helper."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HELPER_SOURCE = REPOSITORY_ROOT / "scripts" / "openclaw_ops_smoke_recover.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _prepare_fake_repo(tmp_path: Path) -> tuple[Path, Path]:
    fake_root = tmp_path / "fake-repo"
    scripts_dir = fake_root / "scripts"
    bin_dir = fake_root / "bin"
    scripts_dir.mkdir(parents=True)
    bin_dir.mkdir()
    shutil.copy2(HELPER_SOURCE, scripts_dir / HELPER_SOURCE.name)
    copied_helper = scripts_dir / HELPER_SOURCE.name
    helper_text = copied_helper.read_text(encoding="utf-8")
    fixed_scratch_path = "/tmp/openclaw_dispatch_recover.json"
    scratch_path_count = helper_text.count(fixed_scratch_path)
    assert scratch_path_count in {0, 2}
    copied_helper.write_text(
        helper_text.replace(fixed_scratch_path, str(tmp_path / "dispatch_recover.json")) if scratch_path_count else helper_text,
        encoding="utf-8",
    )
    copied_helper.chmod(0o755)

    for script_name in (
        "smoke_openclaw_m2m_capabilities.sh",
        "smoke_openclaw_m2m_outbox.sh",
        "diagnose_openclaw_integration.sh",
    ):
        _write_executable(
            scripts_dir / script_name,
            "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'subsmoke %s\\n' \"$0\" >> \"${FAKE_CALL_LOG:?}\"\n",
        )
    _write_executable(
        scripts_dir / "manage_openclaw_outbox.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'manage %s\\n' \"$*\" >> \"${FAKE_CALL_LOG:?}\"\n",
    )
    _write_executable(
        bin_dir / "curl",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'curl %s\\n' "$*" >> "${FAKE_CALL_LOG:?}"
if [[ "$*" == *"/callbacks/metrics?"* ]]; then
  printf '%s\\n' "${FAKE_METRICS_JSON:?}"
elif [[ "$*" == *"/callbacks/outbox?"* ]]; then
  printf '%s\\n' "${FAKE_OUTBOX_JSON:?}"
elif [[ "$*" == *"incident-snapshot?"* ]]; then
  printf '%s\\n' '{"overview": {}, "recent_timeline": []}'
elif [[ "$*" == *"/callbacks/dispatch"* ]]; then
  printf '%s\\n' '{"success": true}'
else
  printf '%s\\n' '{}'
fi
""",
    )
    _write_executable(bin_dir / "sleep", "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n")
    return fake_root, bin_dir


def _run_helper(
    tmp_path: Path,
    *,
    metrics_json: str,
    strict: str,
    outbox_json: str = '{"items": []}',
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    fake_root, bin_dir = _prepare_fake_repo(tmp_path)
    call_log = tmp_path / "calls.log"
    environment = os.environ.copy()
    environment.update(
        {
            "BASE_URL": "http://callback-smoke.invalid",
            "TENANT_ID": "tenant-synthetic",
            "OPENCLAW_TOKEN": "synthetic-token",
            "STRICT": strict,
            "SEND_TELEGRAM_REPORT": "0",
            "TMPDIR": str(tmp_path / "tmp"),
            "FAKE_CALL_LOG": str(call_log),
            "FAKE_METRICS_JSON": metrics_json,
            "FAKE_OUTBOX_JSON": outbox_json,
            "PATH": f"{bin_dir}{os.pathsep}{environment['PATH']}",
        }
    )
    result = subprocess.run(
        ["bash", "./scripts/openclaw_ops_smoke_recover.sh"],
        cwd=fake_root,
        env=environment,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    calls = call_log.read_text(encoding="utf-8").splitlines() if call_log.exists() else []
    return result, calls


def _assert_normal_subsmokes_run(calls: list[str]) -> None:
    assert any("smoke_openclaw_m2m_capabilities.sh" in line for line in calls)
    assert any("smoke_openclaw_m2m_outbox.sh" in line for line in calls)


@pytest.mark.parametrize("alert_code", ["UNCERTAIN_DELIVERY", "DLQ_THRESHOLD", "STUCK_RETRY"])
def test_ops_smoke_alert_has_no_alert_triggered_replay_or_direct_recovery_dispatch_when_not_strict(tmp_path, alert_code):
    result, calls = _run_helper(
        tmp_path,
        metrics_json=f'{{"alerts":[{{"code":"{alert_code}"}}]}}',
        strict="0",
    )

    assert result.returncode == 0, result.stderr
    assert not any(line.startswith("manage ") for line in calls)
    assert not any("/api/openclaw/callbacks/dispatch" in line for line in calls)
    _assert_normal_subsmokes_run(calls)


def test_ops_smoke_uncertain_alert_is_strict_failure_without_alert_triggered_recovery(tmp_path):
    result, calls = _run_helper(
        tmp_path,
        metrics_json='{"alerts":[{"code":"UNCERTAIN_DELIVERY"}]}',
        strict="1",
    )

    assert result.returncode == 2
    assert not any(line.startswith("manage ") for line in calls)
    assert not any("/api/openclaw/callbacks/dispatch" in line for line in calls)
    _assert_normal_subsmokes_run(calls)


def test_ops_smoke_no_alert_has_no_extra_recovery_and_keeps_ordinary_subsmokes(tmp_path):
    result, calls = _run_helper(tmp_path, metrics_json='{"alerts":[]}', strict="1")

    assert result.returncode == 0, result.stderr
    assert not any(line.startswith("manage ") for line in calls)
    assert not any("/api/openclaw/callbacks/dispatch" in line for line in calls)
    _assert_normal_subsmokes_run(calls)


def test_ops_smoke_collects_before_and_after_snapshots_for_outbox_action_without_json_error(tmp_path):
    result, calls = _run_helper(
        tmp_path,
        metrics_json='{"alerts":[]}',
        strict="1",
        outbox_json='{"items":[{"action_id":"action-synthetic","status":"dlq"}]}',
    )

    assert result.returncode == 0, result.stderr
    assert "JSONDecodeError" not in result.stderr
    snapshot_calls = [line for line in calls if "incident-snapshot?" in line]
    assert len(snapshot_calls) == 2
    assert all("/actions/action-synthetic/incident-snapshot?" in line for line in snapshot_calls)
