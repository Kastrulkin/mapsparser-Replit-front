"""One-shot removal of exact inspected reclaimable, unshared BuildKit records."""

import json
from pathlib import Path
import shutil
import subprocess
import time


DOCKER = '/Applications/Docker.app/Contents/Resources/bin/docker'
SOCKET = 'unix:///Users/alexdemyanov/.docker/run/docker.sock'
TARGETS = (
    'soi9byac5ey11o1n9th581aol', 'idup0gjm4in3pxj4ipjiuu0y3',
    'ngbguqvenqmth90jp0109v0i3', '6tuhqz1zpraby0hbm9soktm9a',
    'vn8jydrvqd5rl1wxh8oae9c18', '99uldkqotnr6jmx7t9gojk26t',
    'lwck2gxy8s9wmnnbd33u1nm6d', 'habtlmko90iirr69u5p2uco26',
    'x23nmwhp3gbc8tit0wrt8hn17',
)
RESULT = Path(__file__).resolve().parents[1] / 'evidence/cache-buildkit-leaves-hflypi-20260921.json'
ENVIRONMENT = {'DOCKER_CONFIG': '/Users/alexdemyanov/.docker', 'PATH': '/usr/bin:/bin'}


def leaf_first(inventory, targets):
    remaining = {row['ID']: set(row.get('Parents') or []) for row in inventory}
    pending = set(targets)
    if len(remaining) != len(inventory) or len(pending) != len(targets) or not pending or not pending.issubset(remaining):
        raise RuntimeError('cache target inventory is missing or duplicated')
    order = []
    while pending:
        referenced = {parent for parents in remaining.values() for parent in parents}
        leaves = [target for target in targets if target in pending and target not in referenced]
        if not leaves:
            raise RuntimeError('cache target has retained children or cyclic dependencies')
        for leaf in leaves:
            order.append(leaf)
            pending.remove(leaf)
            del remaining[leaf]
    return order


def main(*, targets=TARGETS, result_path=RESULT):
    if result_path.exists():
        raise RuntimeError('refusing to overwrite cleanup evidence')
    payload = {'targets': list(targets), 'scope': 'BuildKit cache only; no image/container/volume removal',
               'commands': [], 'free_bytes_before': shutil.disk_usage('/private/tmp').free}

    def run(arguments):
        started = time.monotonic()
        if arguments[0] == 'buildx' and arguments[1] in {'du', 'prune'}:
            arguments = [*arguments, '--builder', 'desktop-linux']
        command = [DOCKER, '--context', 'desktop-linux', *arguments]
        result = subprocess.run(command, env=ENVIRONMENT, text=True, capture_output=True, timeout=45)
        payload['commands'].append({'command': command, 'exit': result.returncode,
                                    'seconds': round(time.monotonic() - started, 3),
                                    'stdout': result.stdout, 'stderr': result.stderr})
        result_path.write_text(json.dumps(payload, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError('cache command failed')
        return result.stdout

    def resource_ids():
        return {kind: sorted(set(run(args).splitlines())) for kind, args in (
            ('images', ['image', 'ls', '--no-trunc', '--quiet']),
            ('containers', ['container', 'ls', '--all', '--no-trunc', '--quiet']),
            ('volumes', ['volume', 'ls', '--quiet']),
        )}

    context = json.loads(run(['context', 'inspect', 'desktop-linux']))
    if context[0]['Endpoints']['docker']['Host'] != SOCKET:
        raise RuntimeError('Docker context is not the reviewed local socket')
    builder = run(['buildx', 'inspect', 'desktop-linux'])
    fields = {}
    for line in builder.splitlines():
        if line.startswith(('Name:', 'Driver:', 'Endpoint:', 'Status:')):
            key, value = line.split(':', 1)
            fields.setdefault(key, []).append(value.strip())
    if fields != {'Name': ['desktop-linux', 'desktop-linux'], 'Driver': ['docker'],
                  'Endpoint': ['desktop-linux'], 'Status': ['running']}:
        raise RuntimeError('builder is not the reviewed single local Docker node')
    payload['builder_identity'] = fields
    before = resource_ids()
    payload['resource_ids_before'] = before
    inventory = [json.loads(line) for line in run(['buildx', 'du', '--format=json']).splitlines() if line]
    by_id = {row['ID']: row for row in inventory}
    for target in targets:
        row = by_id.get(target)
        if not row or row.get('Shared') is not False or row.get('Reclaimable') is not True:
            raise RuntimeError('cache target is not exactly reclaimable and unshared: ' + target)
    payload['verified_records'] = [by_id[target] for target in targets]
    order = leaf_first(inventory, targets)
    payload['planned_leaf_first_order'] = order
    for target in order:
        current = [json.loads(line) for line in run(['buildx', 'du', '--filter', 'id=' + target, '--format=json']).splitlines() if line]
        if len(current) != 1 or current[0]['ID'] != target or current[0].get('Shared') is not False or current[0].get('Reclaimable') is not True:
            raise RuntimeError('cache target changed before removal: ' + target)
        run(['buildx', 'prune', '--force', '--filter', 'id=' + target])
    after = resource_ids()
    payload['resource_ids_after'] = after
    payload['resource_ids_unchanged'] = before == after
    payload['remaining_inventory'] = [json.loads(line) for line in run(['buildx', 'du', '--format=json']).splitlines() if line]
    initial_ids = set(by_id)
    final_ids = {row['ID'] for row in payload['remaining_inventory']}
    payload['removed_cache_ids'] = sorted(initial_ids - final_ids)
    payload['added_cache_ids'] = sorted(final_ids - initial_ids)
    exact = initial_ids - final_ids == set(targets) and not (set(targets) & final_ids) and not (final_ids - initial_ids)
    payload['cache_removal_exact'] = exact
    payload['free_bytes_after'] = shutil.disk_usage('/private/tmp').free
    payload['status'] = 'complete' if before == after and exact else 'inventory mismatch; inspect concurrent activity'
    result_path.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'status': payload['status'], 'free_bytes_after': payload['free_bytes_after']}))
    if before != after or not exact:
        raise RuntimeError('cleanup inventory verification failed')


if __name__ == '__main__':
    main()
