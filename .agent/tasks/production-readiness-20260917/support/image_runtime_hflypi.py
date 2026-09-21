"""Nonroot, dependency and browser smoke for the newly built audit image."""

import json
import os
from pathlib import Path
import subprocess
import time


IMAGE = 'localos-audit-20260921:99849935-hflypi'
DOCKER = ['/Applications/Docker.app/Contents/Resources/bin/docker', '--context', 'desktop-linux']
RESULT = Path('/private/tmp/localos-readiness-20260921.hfLYPi/evidence/image-runtime-smoke.json')
ENVIRONMENT = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'LANG') if key in os.environ}
PROBE = '''
import json, os
from pathlib import Path
from importlib.metadata import distributions
from playwright.sync_api import sync_playwright
assert os.geteuid() == 10001, os.geteuid()
assert not Path('/app/.env').exists()
assert not Path('/app/.git').exists()
assert not Path('/app/.agent').exists()
for directory in ('/app/uploads', '/app/debug_data', '/app/operator_audio', '/home/localos/.cache'):
    probe = Path(directory) / 'audit-hflypi-write-probe'
    assert not probe.exists()
    probe.write_text('synthetic-only', encoding='utf-8')
    probe.unlink()
assert Path('/app/frontend/dist/index.html').stat().st_size > 0
assert Path('/app/frontend/public-dist/public-audit/index.html').stat().st_size > 0
manager = sync_playwright().start()
try:
    browser = manager.chromium.launch(headless=True)
    try:
        page = browser.new_page()
        page.set_content('<main><h1>hfLYPi isolated browser</h1></main>')
        assert page.get_by_role('heading').inner_text() == 'hfLYPi isolated browser'
        print(json.dumps({'uid': os.geteuid(), 'chromium': browser.version, 'browser_static_dom': True}))
    finally:
        browser.close()
finally:
    manager.stop()
print(json.dumps({'packages': sorted([(d.metadata['Name'], d.version) for d in distributions()])}))
'''


def main():
    if RESULT.exists():
        raise SystemExit('Refusing to overwrite image runtime evidence')
    checks = [
        ('dependencies', ['python', '-m', 'pip', 'check']),
        ('nonroot-browser', ['python', '-c', PROBE]),
        ('private-assets', ['bash', 'scripts/verify_frontend_dist_integrity.sh', 'frontend/dist']),
    ]
    results = []
    for label, arguments in checks:
        command = DOCKER + [
            'run', '--name', 'localos-readiness-hflypi-smoke-' + label,
            '--label', 'localos.audit.owner=production-readiness-20260917-hfLYPi',
            '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges:true', '--memory', '768m',
            '--pids-limit', '256', '--entrypoint', arguments[0], IMAGE,
        ] + arguments[1:]
        started = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180, env=ENVIRONMENT)
        result = {
            'label': label, 'command': command, 'exit_code': completed.returncode,
            'duration_seconds': round(time.monotonic() - started, 3),
            'stdout': completed.stdout, 'stderr': completed.stderr,
        }
        results.append(result)
        print(label, completed.returncode, flush=True)
        if completed.returncode:
            break
    RESULT.write_text(json.dumps({'image': IMAGE, 'checks': results}, indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if len(results) == len(checks) and all(row['exit_code'] == 0 for row in results) else 1)


if __name__ == '__main__':
    main()
