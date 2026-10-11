"""Guarded adapter repair for the current production frontend, without rebuilding old source."""
import hashlib
from pathlib import Path
import shutil
import sys

root = Path('/opt/seo-app')
if Path.cwd() != root:
    raise SystemExit('Run from /opt/seo-app')
package = Path(sys.argv[1])
expected_hash = sys.argv[2]
expected_asset = sys.argv[3]
target = root / 'frontend/src/pages/dashboard/AgentBlueprintsPage.tsx'
index = root / 'frontend/dist/index.html'
source = target.read_text()
needle = '        candidate_version: response.data?.candidate_version || null,\n'
replacement = needle + (
    '        compiled_approved_version: response.data?.compiled_approved_version || null,\n'
    "        compiled_access: response.data?.compiled_access && typeof response.data.compiled_access === 'object' ? response.data.compiled_access : undefined,\n"
)
if hashlib.sha256(target.read_bytes()).hexdigest() != expected_hash or expected_asset not in index.read_text():
    raise SystemExit('Current frontend changed; nothing replaced')
if source.count(needle) != 1 or 'compiled_access:' in source:
    raise SystemExit('Adapter shape changed; nothing replaced')
backup = root / ('backups/content-execution-access-' + hashlib.sha256((package / 'dist/index.html').read_bytes()).hexdigest()[:12])
backup.mkdir(mode=0o700)
shutil.copy2(target, backup / target.name)
shutil.copy2(index, backup / 'index.html')
target.write_text(source.replace(needle, replacement))
for asset in (package / 'dist').rglob('*'):
    if asset.is_file() and asset.name != 'index.html':
        dest = root / 'frontend/dist' / asset.relative_to(package / 'dist')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, dest)
temporary = index.with_name('index.html.content-access')
shutil.copy2(package / 'dist/index.html', temporary)
temporary.replace(index)
print('Patched adapter and switched compatible frontend; backup:', backup)
