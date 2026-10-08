#!/usr/bin/env python3
"""Prepare a privately pinned runner; enable preview only, never delivery.

Run from /opt/seo-app in tmux. No database changes or Telegram calls.
The temporary image registry listens only on loopback and is stopped afterwards.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess

from check_compiled_runner_deployment import inspect, verify_container

ROOT = Path('/opt/seo-app')
EVIDENCE = ROOT / 'debug_data/releases/content-process-20261008'
REGISTRY = 'localos-content-image-registry-20261008'
REPOSITORY = '127.0.0.1:18851/localos-content-runner'
TAG = REPOSITORY + ':20261008'
PILOT_BUSINESS = 'cb674174-8b3d-41a3-8277-525c849935f2'


def run(*args, capture=False):
    return subprocess.run(args, cwd=ROOT, check=True, text=True,
        capture_output=capture).stdout


def update_environment(values):
    path = ROOT / '.env'
    text = path.read_text()
    backup = EVIDENCE / 'before-compiled-runtime.env'
    if not backup.exists():
        backup.write_text(text); os.chmod(backup, 0o600)
    remaining = dict(values)
    lines = []
    for line in text.splitlines():
        key = line.partition('=')[0].strip()
        if key in values:
            lines.append(key + '=' + values[key]); remaining.pop(key, None)
        else:
            lines.append(line)
    lines.extend(key + '=' + value for key,value in remaining.items())
    temporary = path.with_name('.env.content-runtime')
    temporary.write_text('\n'.join(lines)+'\n'); os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def main():
    if Path.cwd() != ROOT:
        raise RuntimeError('Run from /opt/seo-app')
    EVIDENCE.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.umask(0o077)
    environment_path = ROOT / '.env'
    original_environment = environment_path.read_text()
    current = dict(line.split('=', 1) for line in original_environment.splitlines()
        if '=' in line and not line.lstrip().startswith('#'))
    expected_compose = 'docker-compose.yml:docker/compiled-script-runner/compose.fragment.yml'
    if os.environ.get('COMPOSE_FILE') or current.get('COMPOSE_FILE', '').strip() not in ('', expected_compose):
        raise RuntimeError('Existing Compose override requires explicit reconciliation')
    existing = run('docker','ps','-a','--filter','name=^/'+REGISTRY+'$','--format','{{.ID}}',capture=True).strip()
    if existing:
        raise RuntimeError('Existing registry found; inspect before retry, do not replace it blindly')
    run('docker','run','-d','--name',REGISTRY,'--publish','127.0.0.1:18851:5000',
        '--memory','128m','--pids-limit','64','registry:2')
    try:
        run('docker','build','--tag',TAG,str(ROOT/'docker/compiled-script-runner'))
        run('docker','push',TAG)
        image = inspect('image',TAG)
        reference = next(value for value in image.get('RepoDigests',[]) if value.startswith(REPOSITORY+'@sha256:'))
        digest = reference.split('@',1)[1]
        run('docker','pull',reference)
    finally:
        run('docker','stop',REGISTRY)
    runtime_path = EVIDENCE/'compiled-runtime.env'
    secret = secrets.token_urlsafe(48)
    if runtime_path.exists():
        old = dict(line.split('=',1) for line in runtime_path.read_text().splitlines() if '=' in line)
        secret = old.get('COMPILED_SCRIPT_RUNNER_SHARED_SECRET') or secret
    values = {'COMPILED_SCRIPT_RUNNER_SHARED_SECRET':secret,
        'COMPILED_SCRIPT_RUNNER_IMAGE':reference,'COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST':digest,
        'COMPILED_SCRIPT_RUNNER_URL':'http://compiled-script-runner:8091',
        'COMPILED_SCRIPT_PREVIEW_ENABLED':'true','COMPILED_SCRIPT_EXECUTE_ENABLED':'false',
        'COMPILED_SCRIPT_PILOT_BUSINESS_IDS':PILOT_BUSINESS,
        'COMPILED_CONTENT_HANDOFF_BLUEPRINT_IDS':'',
        'COMPOSE_FILE':'docker-compose.yml:docker/compiled-script-runner/compose.fragment.yml'}
    runtime_path.write_text('\n'.join(key+'='+value for key,value in values.items())+'\n')
    os.chmod(runtime_path,0o600)
    update_environment(values)
    # The running app still has execution disabled. Attest the runner before
    # recreating only the three services that need its private network.
    try:
        run('docker','compose','up','-d','--no-deps','compiled-script-runner')
        container_id = run('docker','compose','ps','-q','compiled-script-runner',capture=True).strip()
        container = inspect('container',container_id)
        networks = {name:inspect('network',name) for name in container['NetworkSettings']['Networks']}
        proof = verify_container(container,reference,digest,inspect('image',reference),networks)
        (EVIDENCE/'runner-attestation.json').write_text(json.dumps(proof))
    except Exception:
        temporary = environment_path.with_name('.env.content-runtime-rollback')
        temporary.write_text(original_environment); os.chmod(temporary, 0o600)
        os.replace(temporary, environment_path)
        raise
    run('docker','compose','up','-d','--no-deps','app','worker','operator-worker')
    print(json.dumps({'status':'preview_ready','runner':proof,'execution_enabled':False}))


if __name__=='__main__':
    main()
