"""Capture canonical Gunicorn HTTP/start/stop proof for the owned local image."""

import json
import os
from pathlib import Path
import subprocess
import time


BASE = Path('/private/tmp/localos-readiness-20260921.hfLYPi')
RESULT = BASE / 'evidence/web-runtime.json'
DOCKER = ['/Applications/Docker.app/Contents/Resources/bin/docker', '--context', 'desktop-linux']
OWNER = 'production-readiness-20260917-hfLYPi'
WEB = 'localos-readiness-hflypi-web-1'
ENVIRONMENT = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'LANG') if key in os.environ}
PROBE = '''
import json, os, urllib.request
assert os.geteuid() == 10001
results = []
for route in ('/health', '/ready', '/', '/about'):
    response = urllib.request.urlopen('http://127.0.0.1:8000' + route, timeout=10)
    try:
        body = response.read(4096)
        assert response.status == 200, (route, response.status)
        results.append({'route': route, 'status': response.status, 'body_prefix': body[:250].decode('utf-8')})
    finally:
        response.close()
print(json.dumps({'uid': os.geteuid(), 'routes': results}))
'''


def command(arguments, timeout=30):
    started = time.monotonic()
    completed = subprocess.run(DOCKER + arguments, env=ENVIRONMENT, capture_output=True, text=True, timeout=timeout)
    return {'command': DOCKER + arguments, 'exit_code': completed.returncode,
            'duration_seconds': round(time.monotonic() - started, 3),
            'stdout': completed.stdout, 'stderr': completed.stderr}


def inspect(name):
    observed = command(['inspect', name])
    if observed['exit_code']:
        raise RuntimeError('could not inspect ' + name)
    detail = json.loads(observed['stdout'])[0]
    if detail['Config']['Labels'].get('localos.audit.owner') != OWNER:
        raise RuntimeError('foreign container identity: ' + name)
    return detail


def main():
    if RESULT.exists():
        raise RuntimeError('refusing to overwrite web runtime capture')
    previous = inspect('localos-readiness-hflypi-app-1')
    detail = inspect(WEB)
    if detail['Mounts'] or set(detail['NetworkSettings']['Networks']) != {'localos-readiness-hflypi_internal'}:
        raise RuntimeError('web isolation mismatch')
    if not detail['State']['Running'] or 'exec gunicorn' not in ' '.join(detail['Config']['Cmd']):
        raise RuntimeError('not the running canonical Gunicorn command')
    payload = {'scope': 'owned local ARM64 Gunicorn; synthetic DB only',
               'image_id': detail['Image'], 'command': detail['Config']['Cmd'],
               'networks': sorted(detail['NetworkSettings']['Networks']),
               'mounts': detail['Mounts'], 'checks': [],
               'prior_bare_flask_shutdown': {
                   'command': previous['Config']['Cmd'], 'state': previous['State'],
                   'limitation': 'Dockerfile development Python command exited 137 after 10-second SIGTERM deadline; production Compose uses Gunicorn instead.'}}
    payload['checks'].append(command(['exec', WEB, 'python', '-c', PROBE]))
    payload['checks'].append(command(['logs', '--tail', '160', WEB]))
    payload['checks'].append(command(['stop', '--time', '15', WEB]))
    final = inspect(WEB)
    payload['final_state'] = final['State']
    payload['checks'].append(command(['logs', '--tail', '40', WEB]))
    passed = all(item['exit_code'] == 0 for item in payload['checks']) and not final['State']['Running'] and final['State']['ExitCode'] == 0 and not final['State']['OOMKilled']
    payload['passed'] = passed
    RESULT.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'passed': passed, 'state': final['State']}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
