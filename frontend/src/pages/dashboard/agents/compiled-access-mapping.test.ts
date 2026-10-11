import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

describe('compiled content fields in the workspace response mapping', () => {
  it('retains the backend execution grant and approved version wherever candidate details are mapped', () => {
    const source = readFileSync('src/pages/dashboard/AgentBlueprintsWorkspace.tsx', 'utf8');
    const mappings = source.split('candidate_version: response.data?.candidate_version || null,').slice(1);
    expect(mappings.length).toBeGreaterThan(0);
    expect(source.match(/compiled_approved_version: response\.data\?\.compiled_approved_version/g)?.length).toBe(mappings.length);
    for (const mapping of mappings) {
      const adjacentFields = mapping.slice(0, 450);
      expect(adjacentFields).toContain('compiled_access: response.data?.compiled_access');
    }
  });
});
