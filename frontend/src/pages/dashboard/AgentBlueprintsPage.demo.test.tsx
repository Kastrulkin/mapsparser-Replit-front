import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const source = readFileSync(resolve(process.cwd(), 'src/pages/dashboard/AgentBlueprintsPage.tsx'), 'utf8');

describe('AgentBlueprintsPage demo requests', () => {
  it('guards live migration and persona reads in demo mode', () => {
    expect(source).toMatch(
      /const loadLegacyMigrationPlan[\s\S]*?if \(!currentBusinessId \|\| demoMode\)[\s\S]*?\}, \[currentBusinessId, demoMode\]\);/,
    );
    expect(source).toMatch(
      /const loadPersonaAgents[\s\S]*?if \(!currentBusinessId \|\| demoMode\)[\s\S]*?\}, \[currentBusinessId, demoMode\]\);/,
    );
  });
});
