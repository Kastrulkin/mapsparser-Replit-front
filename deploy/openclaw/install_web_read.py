"""Guarded, reversible extension of the existing bridge; run on OpenClaw."""
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/openclaw_runtime')
SERVER = ROOT / 'capabilities/outreach_mvp/http_server.py'
EXPECTED = '3425c3d3d8498270399f22ebd31fbfb0291d805758af8c5c2a9c809871602a35'


def install():
    current = SERVER.read_text()
    if 'from .web_read import handle_web_read' in current:
        raise SystemExit('Already installed; verify existing release rather than overwrite')
    if hashlib.sha256(SERVER.read_bytes()).hexdigest() != EXPECTED:
        raise SystemExit('Bridge changed since inspection; no files changed')
    backup = ROOT / 'backups' / ('web-read-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(SERVER, backup / SERVER.name)
    gateway_path = Path('/root/.openclaw-localos/openclaw.json')
    shutil.copy2(gateway_path, backup / 'gateway.json')
    os.chmod(backup / 'gateway.json', 0o600)
    gateway = json.loads(gateway_path.read_text())
    gateway.setdefault('tools', {}).setdefault('web', {}).setdefault('fetch', {}).setdefault('firecrawl', {})['enabled'] = False
    replacement = current.replace('from .service import run_capability',
        'from .service import run_capability\nfrom .web_read import handle_web_read', 1)
    replacement = replacement.replace('    headers = headers or {}\n',
        '    headers = headers or {}\n    web_result = handle_web_read(method, path, headers, payload)\n'
        '    if web_result is not None:\n        return web_result\n', 1)
    replacement = replacement.replace('handle_request("GET", self.path)',
        'handle_request("GET", self.path, dict(self.headers.items()))', 1)
    compile(replacement, str(SERVER), 'exec')
    helper = Path(__file__).with_name('web_read.py')
    compile(helper.read_text(), str(helper), 'exec')
    shutil.copy2(helper, ROOT / 'capabilities/outreach_mvp/web_read.py')
    gateway_path.write_text(json.dumps(gateway, ensure_ascii=False, indent=2))
    os.chmod(gateway_path, 0o600)
    SERVER.write_text(replacement)
    config = ROOT / 'var/localos-web-read.json'
    config.parent.mkdir(exist_ok=True, mode=0o700)
    # Fail closed until a successful controlled live probe, never mark installed=verified.
    config.write_text(json.dumps({'enabled': False, 'business_ids': [], 'verified_at': '2000-01-01T00:00:00Z'}))
    os.chmod(config, 0o600)
    print(json.dumps({'installed': True, 'enabled': False, 'backup': str(backup)}))


if __name__ == '__main__':
    install()
