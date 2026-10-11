"""Install a pre-ported content release only when every production preimage matches.

Run from /opt/seo-app. Does not change configuration, DB, schedules or services.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tarfile


def digest(value):
    return hashlib.sha256(value).hexdigest()


def prepare(package):
    with tarfile.open(package / 'baseline.tgz') as archive:
        baseline = {member.name: digest(archive.extractfile(member).read())
                    for member in archive.getmembers() if member.isfile()}
    files = []
    for path in sorted((package / 'src').rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        name = str(path.relative_to(package))
        files.append({'path': name, 'before': baseline.get(name), 'after': digest(path.read_bytes())})
    (package / 'manifest.json').write_text(json.dumps({'files': files}, indent=2)+'\n')


def install(package):
    root = Path('/opt/seo-app')
    if Path.cwd() != root:
        raise SystemExit('Run from /opt/seo-app')
    manifest = json.loads((package / 'manifest.json').read_text())
    for row in manifest['files']:
        relative = Path(row['path'])
        if not relative.is_relative_to('src') or '..' in relative.parts or relative.suffix != '.py':
            raise SystemExit('Invalid release path')
        source, current = package / relative, root / relative
        if digest(source.read_bytes()) != row['after']:
            raise SystemExit(f'Package changed: {relative}')
        observed = digest(current.read_bytes()) if current.exists() else None
        if observed != row['before']:
            raise SystemExit(f'Production changed since preflight: {relative}')
    backup = root / 'backups' / ('content-network-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(package / 'manifest.json', backup / 'manifest.json')
    for row in manifest['files']:
        relative = Path(row['path'])
        target = root / relative
        if target.exists():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name+'.network-release')
        shutil.copy2(package / relative, temporary)
        os.chmod(temporary, target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.replace(temporary, target)
    print(json.dumps({'backup': str(backup), 'files': len(manifest['files'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare','install'])
    parser.add_argument('package', type=Path)
    args = parser.parse_args()
    (prepare if args.mode == 'prepare' else install)(args.package.resolve())
