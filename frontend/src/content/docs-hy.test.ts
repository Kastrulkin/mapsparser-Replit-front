import { describe, expect, it } from 'vitest';

import docsHy from './docs-hy.json';

describe('Armenian public documentation', () => {
  it('keeps stable routes and technical status codes while translating visible content', () => {
    expect(docsHy.sections.map((section) => section.slug)).toEqual([
      'overview', 'capabilities', 'approval-policy', 'security-model',
      'api', 'agent-use-cases', 'gaps',
    ]);

    for (const section of docsHy.sections) {
      expect(section.title).toMatch(/[\u0531-\u058F]/);
      expect(section.summary).toMatch(/[\u0531-\u058F]/);
      for (const item of section.items) {
        expect(item.title).toMatch(/[\u0531-\u058F]/);
        expect(item.text).toMatch(/[\u0531-\u058F]/);
      }
    }

    expect(docsHy.sections.find((section) => section.slug === 'security-model')?.items
      .find((item) => item.title === 'Նվազագույն շրջանակներ')?.text)
      .toContain('publish:request');
    expect(docsHy.sections.find((section) => section.slug === 'api')?.items
      .find((item) => item.title === 'Sandbox ինքնափորձարկում')?.text)
      .toContain('POST /api/agent-api/self-test');
  });
});
