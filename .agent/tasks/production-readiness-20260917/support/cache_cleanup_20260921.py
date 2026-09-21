"""Remove only inspected regenerable browser/npm cache, never user/app data."""

import json
from pathlib import Path
import shutil
import subprocess
import time


TARGETS = (
    '/Users/alexdemyanov/Library/Caches/ms-playwright/chromium-1208',
    '/Users/alexdemyanov/Library/Caches/ms-playwright/chromium-1234',
    '/Users/alexdemyanov/Library/Caches/ms-playwright/chromium_headless_shell-1208',
    '/Users/alexdemyanov/Library/Caches/ms-playwright/chromium_headless_shell-1234',
    '/Users/alexdemyanov/.npm/_cacache',
)
RESULT = Path(__file__).resolve().parents[1] / 'evidence/cache-cleanup-20260921.json'


def main():
    if RESULT.exists():
        raise RuntimeError('refusing to overwrite cleanup evidence')
    commands = subprocess.check_output(['/bin/ps', '-axo', 'comm'], text=True)
    for item in TARGETS:
        path = Path(item)
        if not path.is_dir() or path.is_symlink() or str(path.resolve()) != item:
            raise RuntimeError('cache target identity mismatch: ' + item)
        if item in commands:
            raise RuntimeError('browser cache executable is still running: ' + item)
        if path.name.startswith('chromium') and not (path / 'INSTALLATION_COMPLETE').is_file():
            raise RuntimeError('browser cache installation marker absent')
        if path.name == '_cacache' and {p.name for p in path.iterdir()} - {'content-v2', 'index-v5', 'tmp'}:
            raise RuntimeError('unexpected npm cache contents')
    sizes = []
    for item in TARGETS:
        output = subprocess.check_output(['/usr/bin/du', '-sk', item], text=True)
        sizes.append({'path': item, 'allocated_kib_before': int(output.split()[0])})
    payload = {'authorization': 'User requested cache cleanup and audit continuation on 2026-09-21.',
               'targets': sizes, 'free_bytes_before': shutil.disk_usage('/private/tmp').free,
               'scope': 'Only reinstallable Playwright revisions1208/1234 and npm content cache. No histories, profiles, sessions, runtime bundles, DBs, volumes or source.',
               'removed': []}
    RESULT.write_text(json.dumps(payload, indent=2) + '\n')
    started = time.monotonic()
    for item in TARGETS:
        shutil.rmtree(item)
        if Path(item).exists():
            raise RuntimeError('cache target still exists: ' + item)
        payload['removed'].append(item)
        RESULT.write_text(json.dumps(payload, indent=2) + '\n')
    payload['seconds'] = round(time.monotonic() - started, 3)
    payload['free_bytes_after'] = shutil.disk_usage('/private/tmp').free
    payload['removed_allocated_kib'] = sum(row['allocated_kib_before'] for row in sizes)
    payload['recovery'] = 'Not in Trash; reinstall matching Playwright browser revisions or allow npm to redownload cached packages.'
    RESULT.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'removed_allocated_kib': payload['removed_allocated_kib'], 'free_bytes_after': payload['free_bytes_after']}), flush=True)


if __name__ == '__main__':
    main()
