"""Apply only staged content hook and verified catalog; run from /opt/seo-app.

Caller must restart only app/operator-worker/worker after import preflight.
This installer never changes DB records, Compose or schedule flags.
"""
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/opt/seo-app')
ASSETS = Path(__file__).parent


def install():
    expected = {
        'services/content_plan_service.py': 'df704e3bc7393c276715d5a1a2107a9c41927af0001ec91957bc76a5a1451237',
        'services/openclaw_capability_catalog.py': '6bb6d9d21b8befb88d4affb58ecf55ddf209e920cdb66db1add8eb42b2ca149e',
        'services/agent_openclaw_workflow_refs.py': 'dfb7489ff852ad1e1977f73ec3a78f718e0ba06ef3d637f143ad637e771e4c82',
    }
    for name, digest in expected.items():
        if hashlib.sha256((ROOT / 'src' / name).read_bytes()).hexdigest() != digest:
            raise SystemExit('Production changed since inspection; no runtime files replaced')
    config = ROOT / 'debug_data/openclaw-web-read.json'
    reader = ROOT / 'src/services/openclaw_website_reader.py'
    if config.exists() or reader.exists():
        raise SystemExit('Existing rollout found; inspect rather than overwrite')
    content = (ROOT / 'backups/openclaw-web-read-candidate/content_plan_service.candidate.py').read_text()
    refs = (ROOT / 'src/services/agent_openclaw_workflow_refs.py').read_text()
    before = 'if str(action.get("status") or "available") == "available"'
    if refs.count(before) != 1:
        raise SystemExit('Unexpected workflow selector; no runtime files replaced')
    refs = refs.replace(before, 'if action.get("execution_ready") is True', 1)
    replacements = {
        'services/content_plan_service.py': content,
        'services/openclaw_capability_catalog.py': (ASSETS / 'catalog.release.py').read_text(),
        'services/openclaw_website_reader.py': (ASSETS / 'website_reader.release.py').read_text(),
        'services/agent_openclaw_workflow_refs.py': refs,
    }
    for name, text in replacements.items():
        compile(text, name, 'exec')
    backup = ROOT / 'backups' / ('openclaw-content-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(mode=0o700)
    for name in expected:
        shutil.copy2(ROOT / 'src' / name, backup / Path(name).name)
    for name, text in replacements.items():
        (ROOT / 'src' / name).write_text(text)
    config.write_text(json.dumps({'enabled': False,
        'business_ids': ['cb674174-8b3d-41a3-8277-525c849935f2'],
        'catalog_url': 'http://192.168.0.177:8091/capabilities/catalog'}))
    os.chmod(config, 0o600)
    print(json.dumps({'installed': list(replacements), 'enabled': False, 'backup': str(backup)}))


if __name__ == '__main__':
    install()
