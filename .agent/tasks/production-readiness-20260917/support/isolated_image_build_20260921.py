"""Bounded canonical build of the explicitly authorized frozen test checkout."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


ROOT = Path('/private/tmp/localos-readiness-20260921.hfLYPi')
SOURCE = ROOT / 'source'
EVIDENCE = ROOT / 'evidence'
REVISION = '99849935de26e2932613f2a73cf515dff49104a1'
IMAGE = 'localos-audit-20260921:99849935-hflypi'
LABEL = 'production-readiness-20260917-hfLYPi'
GIB = 1024 ** 3


def main():
    if ROOT.is_symlink() or SOURCE.is_symlink() or not SOURCE.is_dir():
        raise SystemExit('Frozen checkout missing or unexpected symlink')
    if (SOURCE / '.env').exists() or (SOURCE / 'local.env').exists():
        raise SystemExit('Refusing environment file in build checkout')
    result_path = EVIDENCE / 'canonical-image-build.json'
    log_path = EVIDENCE / 'canonical-image-build.log'
    if result_path.exists() or log_path.exists():
        raise SystemExit('Refusing to overwrite existing build evidence')
    free_start = shutil.disk_usage(ROOT).free
    if free_start < 10 * GIB:
        raise SystemExit('Canonical image requires at least 10 GiB available')
    environment = {
        name: os.environ[name]
        for name in ('PATH', 'HOME', 'TMPDIR', 'LANG')
        if name in os.environ
    }
    docker = shutil.which('docker')
    if not docker:
        raise SystemExit('Docker CLI unavailable')
    existing = subprocess.run(
        [docker, '--context', 'desktop-linux', 'image', 'inspect', IMAGE],
        env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=20, check=False,
    )
    if existing.returncode == 0:
        raise SystemExit('Refusing to reuse existing image tag')
    command = [
        docker, '--context', 'desktop-linux', 'build', '--pull',
        '--platform', 'linux/arm64', '--progress', 'plain',
        '--build-arg', 'INSTALL_PLAYWRIGHT_BROWSER=true',
        '--label', f'localos.audit.owner={LABEL}',
        '--label', f'org.opencontainers.image.revision={REVISION}',
        '--tag', IMAGE, str(SOURCE),
    ]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    clock_start = time.monotonic()
    outcome = 'completed'
    samples = []
    stream = log_path.open('xb')
    try:
        process = subprocess.Popen(
            command, cwd=SOURCE, env=environment, stdout=stream,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        while process.poll() is None:
            free = shutil.disk_usage(ROOT).free
            elapsed = time.monotonic() - clock_start
            samples.append({'elapsed_seconds': round(elapsed, 2), 'free_bytes': free})
            if free < 2 * GIB or elapsed > 3600:
                outcome = 'disk_floor' if free < 2 * GIB else 'timeout'
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
                break
            time.sleep(5)
        returncode = process.wait(timeout=10)
    finally:
        stream.close()
    result = {
        'revision': REVISION, 'source': str(SOURCE), 'image': IMAGE,
        'ownership_label': LABEL, 'started_at': started,
        'duration_seconds': round(time.monotonic() - clock_start, 3),
        'command': command, 'outcome': outcome, 'exit_code': returncode,
        'platform': 'linux/arm64', 'browser_enabled': True,
        'cache_policy': 'clean Git export; ordinary Docker layer cache allowed',
        'free_start_bytes': free_start, 'free_end_bytes': shutil.disk_usage(ROOT).free,
        'free_samples': samples,
        'dockerfile_sha256': hashlib.sha256((SOURCE / 'Dockerfile').read_bytes()).hexdigest(),
        'constraints_sha256': hashlib.sha256((SOURCE / 'requirements.release.constraints.txt').read_bytes()).hexdigest(),
        'log_sha256': hashlib.sha256(log_path.read_bytes()).hexdigest(),
    }
    if returncode == 0 and outcome == 'completed':
        inspected = subprocess.run(
            [docker, '--context', 'desktop-linux', 'image', 'inspect',
             '--format', '{{.Id}} {{.Architecture}} {{.Config.User}}', IMAGE],
            env=environment, capture_output=True, text=True, timeout=20, check=True,
        )
        result['image_identity'] = inspected.stdout.strip()
    result_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'free_samples'}))
    raise SystemExit(0 if returncode == 0 and outcome == 'completed' else 1)


if __name__ == '__main__':
    main()
