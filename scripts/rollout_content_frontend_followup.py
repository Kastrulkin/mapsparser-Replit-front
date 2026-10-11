"""One guarded frontend-only follow-up, retaining all prior assets."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

root=Path('/opt/seo-app')
if Path.cwd()!=root:
    raise SystemExit('Run from /opt/seo-app')
package=Path(sys.argv[1])
manifest=json.loads((package/'manifest.json').read_text())
relative=Path('frontend/src/components/agents/ContentHandoffProgram.tsx')
target=root/relative
expected=next(row['after'] for row in manifest['frontend_sources'] if row['path']==str(relative))
index=root/'frontend/dist/index.html'
if hashlib.sha256(target.read_bytes()).hexdigest()!=expected or manifest.get('expected_frontend_asset','index-z9-gMnJc.js') not in index.read_text():
    raise SystemExit('Frontend changed; no files replaced')
backup=root/('backups/content-network-frontend-followup-'+hashlib.sha256((package/'dist/index.html').read_bytes()).hexdigest()[:12])
backup.mkdir(mode=0o700)
shutil.copy2(target,backup/'ContentHandoffProgram.tsx')
shutil.copy2(index,backup/'index.html')
shutil.copy2(package/'ContentHandoffProgram.tsx',target)
for source in (package/'dist').rglob('*'):
    if source.is_file() and source.name!='index.html':
        dest=root/'frontend/dist'/source.relative_to(package/'dist')
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)
temporary=index.with_name('index.html.network-followup')
shutil.copy2(package/'dist/index.html',temporary)
temporary.replace(index)
print(json.dumps({'backup':str(backup),'services_restarted':False}))
