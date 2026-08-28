import { describe, expect, it } from 'vitest';

import { extractMapSources } from './cardOverviewApi';

describe('extractMapSources', () => {
  it('deduplicates technical source aliases into one tab per map provider', () => {
    const result = extractMapSources(
      {
        mapLinks: [
          { url: 'https://yandex.com/maps/org/example' },
          { url: 'https://www.google.com/maps/place/example' },
        ],
      },
      [
        { source: 'yandex_maps' },
        { source: 'yandex_business' },
        { source: 'google_maps' },
        { source: 'google_business' },
      ],
    );

    expect(result.sources).toEqual(['yandex', 'google']);
    expect(result.hasConfiguredMapLink).toBe(true);
    expect(result.hasSupportedConfiguredMapLink).toBe(true);
  });
});
