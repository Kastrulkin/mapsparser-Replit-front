"""Archive enumerated isolated-run evidence without replacing prior captures."""

import hashlib
import json
from pathlib import Path
import shutil


PRIVATE = Path('/private/tmp/localos-readiness-20260921.hfLYPi')
TASK = Path(__file__).resolve().parents[1]
FILES = [
    'compose.audit.yaml',
    'evidence/canonical-image-build.json', 'evidence/canonical-image-build.log',
    'evidence/image-supervisor.log', 'evidence/image-runtime-smoke.json',
    'evidence/image-runtime-supervisor.log', 'evidence/postgres-start.log',
    'evidence/migrate-source.log', 'evidence/migration-checks.json',
    'evidence/migration-checks-supervisor.log',
    'evidence/synthetic-restore-supervisor.log',
    'evidence/synthetic-restore-supervisor-v2.log',
    'evidence/synthetic-restore-compare.log', 'evidence/synthetic-restore-hflypi.json',
    'evidence/app-runtime-http.json', 'evidence/app-start.log',
    'evidence/web-start.log', 'evidence/web-runtime.json',
    'evidence/web-runtime-supervisor.log',
    'evidence/old-build-context-cache-prune.log',
    'evidence/old-build-copy-cache-prune.log',
    'evidence/old-build-copy-parents-cache-prune.log',
    'evidence/old-build-dependency-cache-prune.log',
    'evidence/completed-frontend-cache-prune.log',
]


def main():
    destination = TASK / 'evidence/isolated-hflypi-20260921'
    if destination.exists():
        raise RuntimeError('refusing to overwrite archived evidence')
    native_evidence = PRIVATE / 'native/evidence'
    files = FILES + [str(path.relative_to(PRIVATE)) for path in sorted(native_evidence.iterdir()) if path.is_file()]
    if any(not (PRIVATE / relative).is_file() for relative in files):
        raise RuntimeError('a required capture is missing')
    manifest = []
    for relative in files:
        source = PRIVATE / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest.append({'path': relative, 'bytes': target.stat().st_size,
                         'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    archive = PRIVATE / 'synthetic-restore-hflypi-source.sql.gz'
    payload = {'source_revision': '99849935de26e2932613f2a73cf515dff49104a1',
               'private_root': str(PRIVATE), 'captures': manifest,
               'synthetic_backup_retained_outside_git': {
                   'path': str(archive), 'bytes': archive.stat().st_size,
                   'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}}
    (destination / 'manifest.json').write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'archived_captures': len(files), 'destination': str(destination)}))


if __name__ == '__main__':
    main()
