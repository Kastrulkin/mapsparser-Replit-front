"""Scoped production rollout. Run from /opt/seo-app with a prepared package.

Does not enable dispatch or modify schedules. Keeps old frontend assets for
open tabs and backs up configuration before adding the scheduler allowlist.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def main(package):
    root = Path('/opt/seo-app')
    if Path.cwd() != root:
        raise SystemExit('Run from /opt/seo-app')
    index = root / 'frontend/dist/index.html'
    if 'index-BJLPiouM.js' not in index.read_text():
        raise SystemExit('Frontend baseline changed; re-port before deploying')
    result = subprocess.run(['python3', str(package / 'install.py'), 'install', str(package)], check=True, capture_output=True, text=True)
    backup = Path(json.loads(result.stdout)['backup'])
    for relative in ['.env', 'docker/compiled-script-runner/compose.fragment.yml', 'frontend/dist/index.html']:
        source = root / relative
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, saved)
        os.chmod(saved, 0o600)
    fragment = root / 'docker/compiled-script-runner/compose.fragment.yml'
    value = fragment.read_text()
    needle = '      AGENT_RUN_QUEUE_BLUEPRINT_IDS: ${AGENT_RUN_QUEUE_BLUEPRINT_IDS:-}\n'
    if needle not in value:
        raise SystemExit('Worker configuration changed; dispatch remains disabled')
    if 'AGENT_SCHEDULE_BLUEPRINT_IDS:' not in value:
        fragment.write_text(value.replace(needle, needle+'      AGENT_SCHEDULE_BLUEPRINT_IDS: ${AGENT_SCHEDULE_BLUEPRINT_IDS:-}\n', 1))
    updates = {
        'COMPILED_SCRIPT_PILOT_BUSINESS_IDS': 'cb674174-8b3d-41a3-8277-525c849935f2,0f67ac22-132f-41e7-b473-667c46f364fa',
        'AGENT_SCHEDULE_BLUEPRINT_IDS': 'd61580b3-55f9-5cef-97ba-59f702a14216',
        'AGENT_RUN_QUEUE_BLUEPRINT_IDS': 'd61580b3-55f9-5cef-97ba-59f702a14216',
        'AGENT_SCHEDULE_DISPATCH_ENABLED': 'false',
    }
    env = root / '.env'
    lines = env.read_text().splitlines()
    for key, setting in updates.items():
        lines = [line for line in lines if not line.startswith(key+'=')]
        lines.append(key+'='+setting)
    env.write_text('\n'.join(lines)+'\n')
    os.chmod(env, 0o600)
    dist = root / 'frontend/dist'
    for source in (package / 'dist').rglob('*'):
        if not source.is_file() or source.name == 'index.html':
            continue
        target = dist / source.relative_to(package / 'dist')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    temporary = index.with_name('index.html.network-release')
    shutil.copy2(package / 'dist/index.html', temporary)
    os.replace(temporary, index)
    subprocess.run(['docker', 'compose', 'up', '-d', '--no-deps', 'app', 'worker', 'operator-worker'], check=True)
    # Bind-mounted source changed, so explicitly restart unchanged containers too.
    subprocess.run(['docker', 'compose', 'restart', 'app', 'worker', 'operator-worker'], check=True)
    print(json.dumps({'backup': str(backup), 'dispatcher_enabled': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path)
    main(parser.parse_args().package.resolve())
