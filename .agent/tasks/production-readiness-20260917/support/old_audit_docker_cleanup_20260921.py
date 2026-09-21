"""One-shot, user-approved disposal of six completed synthetic app containers.

Never removes volumes, PG/Redis, running containers or the current audit lane.
Default invocation is read-only; --execute admits the fixed reviewed allowlist.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


DOCKER = '/Applications/Docker.app/Contents/Resources/bin/docker'
ENVIRONMENT = {'DOCKER_CONFIG': '/Users/alexdemyanov/.docker', 'PATH': '/usr/bin:/bin'}
SOCKET = 'unix:///Users/alexdemyanov/.docker/run/docker.sock'
TARGETS = [
    ('9f9fc7038195df46622f161a8fe310aca4e15be13dc6d93c1e0035514c341722',
     'localos-restore-proof-20260918-app-1', 'localos-restore-proof-20260918',
     'fd14a7bb7d7c1951139d392a72f079e238b1becaec0722e37ade72358675b50f', []),
    ('445e053b60ac2fcd386fdfd086096c3772ae36e3e6a4ec62816bfbd49c0ea0d2',
     'localos-readiness-compiled-20260918-app-1', 'localos-readiness-compiled-20260918',
     'b43efb29cbd176d75c97cfa769adbebe7e7e20a1d467cd1c0a561538305cc93d', []),
    ('00b6975716dcd2717fae873baf9762f68edce5c2f5a98fe0e80a1e6b1ce82957',
     'localos-readiness-20260917-app-1', 'localos-readiness-20260917',
     '3dc995eb73758128a56c4c1e42e43f3ca61c9c6725c70b3f12329958b12276f7', []),
    ('0bb0f079452ddc91787a3fa1e2679594639cdf82d17d3e4962815b0b5cf43095',
     'localos-readiness-20260917-audit-ingress-1', 'localos-readiness-20260917',
     'c4ff52d7d80a339781cedeb01af1009c450dae8a2b452c94e883d131d5600213', ['/tmp/audit_proxy.py']),
    ('e91c9d3d55bec6f5989eb4c6bbbc2e9d74419dc6cbabe9a962ab0287c1b6e3cd',
     'localos-readiness-compiled-20260918-compiled-script-runner-1', 'localos-readiness-compiled-20260918',
     '59bcb20b99892291c8db3c5ff9105139e35773c7bf4dccdd74f99ef5b027ea98', []),
    ('b3c8c79b921d22aa2a67ae5f7401a4969a151a191902311a803f5fc19e9133ed',
     'localos-readiness-compiled-20260918-audit-ingress-1', 'localos-readiness-compiled-20260918',
     '78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea', ['/opt/audit-proxy/proxy.py']),
]
EVIDENCE = Path(__file__).resolve().parents[1] / 'evidence'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    execute = parser.parse_args().execute
    output = EVIDENCE / ('old-audit-docker-cleanup-20260921.json' if execute else 'old-audit-docker-preflight-20260921.json')
    if output.exists():
        raise RuntimeError('refusing to overwrite one-shot evidence')
    payload = {'execute': execute, 'status': 'preflight', 'commands': [],
               'free_bytes_before': shutil.disk_usage('/private/tmp').free}

    def save():
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')

    def run(arguments):
        command = [DOCKER, '--context', 'desktop-linux', *arguments]
        started = time.monotonic()
        result = subprocess.run(command, env=ENVIRONMENT, capture_output=True, text=True, timeout=60)
        # Never persist raw inspect results: Config.Env can contain credentials.
        payload['commands'].append({'command': command, 'exit': result.returncode,
                                    'seconds': round(time.monotonic() - started, 3)})
        save()
        if result.returncode:
            raise RuntimeError('Docker command failed: ' + ' '.join(arguments[:2]))
        return result.stdout

    def containers():
        ids = run(['container', 'ls', '--all', '--quiet', '--no-trunc']).splitlines()
        rows = json.loads(run(['container', 'inspect', *ids])) if ids else []
        return {row['Id']: {
            'name': row['Name'].removeprefix('/'), 'image': row['Image'],
            'status': row['State']['Status'], 'running': row['State']['Running'],
            'started': row['State']['StartedAt'], 'finished': row['State']['FinishedAt'],
            'restarts': row['RestartCount'], 'created': row['Created'],
            'project': (row['Config'].get('Labels') or {}).get('com.docker.compose.project'),
            'mounts': [{key: mount.get(key) for key in ('Type', 'Source', 'Destination', 'RW', 'Name')}
                       for mount in row['Mounts']],
        } for row in rows}

    def snapshot():
        image_ids = sorted(set(run(['image', 'ls', '--quiet', '--no-trunc']).splitlines()))
        images = json.loads(run(['image', 'inspect', *image_ids])) if image_ids else []
        return {'containers': containers(),
                'images': {row['Id']: {'tags': sorted(row.get('RepoTags') or []), 'created': row['Created']}
                           for row in images},
                'volumes': sorted(run(['volume', 'ls', '--quiet']).splitlines()),
                'networks': sorted(run(['network', 'ls', '--quiet', '--no-trunc']).splitlines())}

    def check_targets(rows):
        for identity, name, project, image_id, binds in TARGETS:
            row = rows.get(identity)
            if not row or (row['name'], row['project'], row['image'], row['status'], row['running']) != (
                name, project, 'sha256:' + image_id, 'exited', False
            ):
                raise RuntimeError('target identity/state mismatch: ' + identity)
            mounts = row['mounts']
            if any(mount['Type'] != 'bind' or mount['RW'] is not False for mount in mounts):
                raise RuntimeError('target has writable or volume mount: ' + identity)
            if sorted(mount['Destination'] for mount in mounts) != binds:
                raise RuntimeError('target bind destinations differ: ' + identity)
            references = [key for key, value in rows.items() if value['image'] == row['image']]
            if references != [identity]:
                raise RuntimeError('image has another container reference: ' + image_id)

    before = None
    try:
        context = json.loads(run(['context', 'inspect', 'desktop-linux']))
        if context[0]['Endpoints']['docker']['Host'] != SOCKET:
            raise RuntimeError('not the reviewed local Docker socket')
        before = snapshot()
        payload['before'] = before
        check_targets(before['containers'])
        target_images = {'sha256:' + row[3] for row in TARGETS}
        if not target_images.issubset(before['images']):
            raise RuntimeError('target image missing')
        if execute:
            check_targets(containers())
            run(['container', 'rm', *[row[0] for row in TARGETS]])
            if any(row['image'] in target_images for row in containers().values()):
                raise RuntimeError('target image still referenced after container removal')
            run(['image', 'rm', '--no-prune', *sorted(target_images)])
        payload['status'] = 'removed' if execute else 'preflight_passed'
    except BaseException:
        payload['status'] = 'failed'
        payload['error_type'] = type(sys.exception()).__name__
    finally:
        try:
            after = snapshot()
            payload['after'] = after
            if before is not None:
                expected = dict(before)
                if execute and payload['status'] == 'removed':
                    target_ids = {row[0] for row in TARGETS}
                    target_images = {'sha256:' + row[3] for row in TARGETS}
                    expected['containers'] = {key: value for key, value in before['containers'].items() if key not in target_ids}
                    expected['images'] = {key: value for key, value in before['images'].items() if key not in target_images}
                payload['exact_inventory_match'] = after == expected
                if after != expected:
                    payload['status'] = 'verification_failed'
        except BaseException:
            payload['status'] = 'postcheck_failed'
            payload['postcheck_error_type'] = type(sys.exception()).__name__
        payload['free_bytes_after'] = shutil.disk_usage('/private/tmp').free
        save()
    print(json.dumps({'status': payload['status'], 'exact_inventory_match': payload.get('exact_inventory_match'),
                      'free_bytes_after': payload['free_bytes_after']}))
    return 0 if payload['status'] in {'removed', 'preflight_passed'} and payload.get('exact_inventory_match') else 1


if __name__ == '__main__':
    raise SystemExit(main())
