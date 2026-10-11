"""Prepare only the follow-up's changed production files and exact UI sources."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from deploy_content_network_release import prepare

package, port, ui, baseline_ui = [Path(value) for value in sys.argv[1:]]
package.mkdir(mode=0o700)
for name in ['agent_blueprint_creation.py', 'compiled_content_program.py']:
    target = package / 'src/services' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(port / 'src/services' / name, target)
shutil.copy2(port / 'followup-baseline.tgz', package / 'baseline.tgz')
prepare(package)
manifest = json.loads((package / 'manifest.json').read_text())
manifest['expected_frontend_asset'] = 'index-CPNgTZaj.js'
manifest['frontend_sources'] = []
for name in ['src/pages/dashboard/agents/view.tsx', 'src/pages/dashboard/agents/types.ts', 'src/components/agents/ContentHandoffProgram.tsx']:
    target = package / 'frontend' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ui / name, target)
    before = baseline_ui / name
    manifest['frontend_sources'].append({'path': 'frontend/'+name,
        'before': hashlib.sha256(before.read_bytes()).hexdigest() if before.exists() else None,
        'after': hashlib.sha256(target.read_bytes()).hexdigest()})
(package / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
shutil.copytree(ui / 'dist', package / 'dist')
scripts = Path(__file__).parent
shutil.copy2(scripts / 'deploy_content_network_release.py', package / 'install.py')
shutil.copy2(scripts / 'finish_content_network_deploy.py', package / 'deploy.py')
