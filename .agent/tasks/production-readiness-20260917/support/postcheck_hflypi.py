"""Read-only resource and evidence checks after the synthetic rehearsal."""

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


TASK = Path(__file__).resolve().parents[1]
ARCHIVED = TASK / 'evidence/isolated-hflypi-20260921'
BASE = Path('/private/tmp/localos-readiness-20260921.hfLYPi')
RESULT = TASK / 'evidence/isolated-hflypi-postcheck-20260921.json'
DOCKER = ['/Applications/Docker.app/Contents/Resources/bin/docker', '--context', 'desktop-linux']
OWNER = 'production-readiness-20260917-hfLYPi'
ENVIRONMENT = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'LANG') if key in os.environ}


def command(arguments):
    return subprocess.check_output(DOCKER + arguments, text=True, env=ENVIRONMENT, timeout=30)


def main():
    if RESULT.exists():
        raise RuntimeError('refusing to overwrite postcheck')
    manifest = json.loads((ARCHIVED / 'manifest.json').read_text())
    for item in manifest['captures']:
        target = ARCHIVED / item['path']
        assert target.stat().st_size == item['bytes'], item['path']
        assert hashlib.sha256(target.read_bytes()).hexdigest() == item['sha256'], item['path']
    names = command(['ps', '-a', '--filter', 'label=localos.audit.owner=' + OWNER, '--format', '{{.Names}}']).splitlines()
    containers = []
    for name in names:
        detail = json.loads(command(['inspect', name]))[0]
        assert detail['Config']['Labels']['localos.audit.owner'] == OWNER
        containers.append({'name': name, 'image': detail['Image'],
                           'state': detail['State'], 'mounts': detail['Mounts'],
                           'ports': detail['HostConfig']['PortBindings'],
                           'networks': sorted(detail['NetworkSettings']['Networks'])})
    postgres = next(item for item in containers if item['name'] == 'localos-readiness-hflypi-postgres-1')
    assert postgres['state']['Running'] and postgres['state']['Health']['Status'] == 'healthy'
    assert postgres['ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '35418'}]}
    assert len(postgres['mounts']) == 1 and postgres['mounts'][0]['Name'] == 'localos-readiness-hflypi-pgdata'
    for item in containers:
        if item is not postgres:
            assert not item['state']['Running'], item['name']
            assert item['mounts'] == [], item['name']
    volume = json.loads(command(['volume', 'inspect', 'localos-readiness-hflypi-pgdata']))[0]
    assert volume['Labels']['localos.audit.owner'] == OWNER
    internal = json.loads(command(['network', 'inspect', 'localos-readiness-hflypi_internal']))[0]
    assert internal['Internal'] and internal['Labels']['localos.audit.owner'] == OWNER
    archive = BASE / 'synthetic-restore-hflypi-source.sql.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['synthetic_backup_retained_outside_git']['sha256']
    assert not (BASE / 'source/src/sitecustomize.py').exists()
    supports = sorted((TASK / 'support').glob('*hflypi*.py')) + [TASK / 'support/isolated_image_build_20260921.py']
    for support in supports:
        ast.parse(support.read_text(), filename=str(support))
    started = time.monotonic()
    comparator = subprocess.run(['/usr/local/bin/python3', '-I', '-B', str(TASK / 'support/restore_comparator_check_hflypi.py')], capture_output=True, text=True, timeout=30, env=ENVIRONMENT)
    assert comparator.returncode == 0
    payload = {'captures_verified': len(manifest['captures']), 'containers': containers,
               'owned_volume': volume['Name'], 'internal_network_verified': True,
               'backup_hash_verified': True, 'draft_guard_not_installed': True,
               'support_ast_files': len(supports), 'free_bytes': shutil.disk_usage(BASE).free,
               'native_frontend_ready': (BASE / 'source/frontend/node_modules').exists(),
               'comparator': {'exit_code': comparator.returncode, 'stdout': comparator.stdout,
                              'stderr': comparator.stderr, 'seconds': round(time.monotonic() - started, 3)}}
    RESULT.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'captures_verified': len(manifest['captures']), 'owned_containers': len(containers), 'free_bytes': payload['free_bytes']}))


if __name__ == '__main__':
    main()
