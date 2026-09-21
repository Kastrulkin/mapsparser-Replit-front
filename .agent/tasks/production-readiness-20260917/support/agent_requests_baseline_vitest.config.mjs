import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import managed from './managed_growth_vitest.config.mjs';

const repository = fileURLToPath(new URL('../../../../', import.meta.url));
const workspacePath = fileURLToPath(new URL('../../../../frontend/src/pages/dashboard/AgentBlueprintsWorkspace.tsx', import.meta.url));
const testPath = fileURLToPath(new URL('../../../../frontend/src/pages/dashboard/AgentBlueprintsWorkspace.requests.test.tsx', import.meta.url));
const parent = 'b9cb7dea2b3fcf651a976e64a6e986b306bf9ca9';
const source = execFileSync('/usr/bin/git', ['--no-replace-objects', 'show', `${parent}:frontend/src/pages/dashboard/AgentBlueprintsWorkspace.tsx`], { cwd: repository, encoding: 'utf8' });
const digest = value => createHash('sha256').update(value).digest('hex');
const sourceDigest = digest(source);
if (sourceDigest !== 'a2e7503d70b8d2b6e9250f09eb4ac68eb85dae38aff9231bf74883eab97fad01') throw new Error('Unexpected immutable workspace baseline');

export default {
  ...managed,
  plugins: [
    {
      name: 'readiness-agent-requests-parent',
      enforce: 'pre',
      load(id) {
        if (id.split('?')[0] !== workspacePath) return null;
        console.log(JSON.stringify({ baseline_injected: true, parent, workspace_sha256: sourceDigest, test_sha256: digest(readFileSync(testPath)) }));
        return source;
      },
    },
    ...managed.plugins,
  ],
};
