import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';


describe('legacy web analytics route', () => {
  it('redirects the old public path to the dashboard route', () => {
    const appSource = readFileSync(`${process.cwd()}/src/App.tsx`, 'utf8');

    expect(appSource).toContain(
      '<Route path="/web-analytics" element={<Navigate to="/dashboard/web-analytics" replace />} />',
    );
  });
});
