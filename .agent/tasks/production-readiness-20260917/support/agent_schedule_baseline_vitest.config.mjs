import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import managed from './managed_growth_vitest.config.mjs';

const repository = fileURLToPath(new URL('../../../../', import.meta.url));
const workspacePath = fileURLToPath(new URL('../../../../frontend/src/pages/dashboard/AgentBlueprintsWorkspace.tsx', import.meta.url));
const testPath = fileURLToPath(new URL('../../../../frontend/src/pages/dashboard/AgentBlueprintsWorkspace.schedule.test.tsx', import.meta.url));
const parent = 'bd487501dd22733f92fa5cce80766ead60a554ec';
const source = execFileSync('/usr/bin/git', [
  '--no-replace-objects', 'show',
  `${parent}:frontend/src/pages/dashboard/AgentBlueprintsWorkspace.tsx`,
], { cwd: repository, encoding: 'utf8' });
const digest = (value) => createHash('sha256').update(value).digest('hex');
const sourceDigest = digest(source);
if (sourceDigest !== '5ea7bd7f63f04840afc709d9d575ed254ff8ecb156bca845ea0005cf031913ae') {
  throw new Error('Unexpected immutable workspace baseline');
}

export default {
  ...managed,
  plugins: [
    {
      name: 'readiness-agent-schedule-parent',
      enforce: 'pre',
      load(id) {
        if (id.split('?')[0] !== workspacePath) return null;
        console.log(JSON.stringify({
          baseline_injected: true,
          parent,
          workspace_sha256: sourceDigest,
          test_sha256: digest(readFileSync(testPath)),
        }));
        return source;
      },
    },
    ...managed.plugins,
  ],
};
