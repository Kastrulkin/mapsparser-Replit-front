"""Controlled read-only probe; enable only the pilot after success."""
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from capabilities.outreach_mvp import web_read


def verify():
    pid = subprocess.check_output(['systemctl', 'show', 'openclaw-outreach-mvp', '-p', 'MainPID', '--value'], text=True).strip()
    environment = Path('/proc/' + pid + '/environ').read_bytes().split(b'\0')
    for entry in environment:
        if entry.startswith(b'OPENCLAW_INTERNAL_TOKEN='):
            os.environ['OPENCLAW_INTERNAL_TOKEN'] = entry.split(b'=', 1)[1].decode()
    headers = {'X-OpenClaw-Internal-Token': os.environ.get('OPENCLAW_INTERNAL_TOKEN', '')}
    target = web_read.CONFIG_PATH
    config = {'enabled': True, 'business_ids': ['cb674174-8b3d-41a3-8277-525c849935f2'],
              'verified_at': datetime.now(timezone.utc).isoformat()}
    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory) / 'candidate.json'
        candidate.write_text(json.dumps(config))
        web_read.CONFIG_PATH = candidate
        status, body = web_read.handle_web_read('POST', '/capabilities/browser_use.read_page', headers,
            {'business_id': config['business_ids'][0], 'url': 'https://example.com'})
        if status != 200 or not body.get('source', {}).get('text'):
            raise SystemExit('Read-only probe failed; pilot remains disabled')
    target.write_text(json.dumps(config))
    os.chmod(target, 0o600)
    print(json.dumps({'verified': True, 'source': body['source']['provider'],
                      'url': body['source']['url'], 'characters': len(body['source']['text']),
                      'business_ids': config['business_ids']}))


if __name__ == '__main__':
    verify()
