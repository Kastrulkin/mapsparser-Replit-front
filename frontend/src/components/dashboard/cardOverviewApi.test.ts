import { describe, expect, it } from 'vitest';

import { extractMapSources } from './cardOverviewApi';

describe('extractMapSources', () => {
  it('groups only map providers and deduplicates their source aliases', () => {
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
        { source: 'apify_2gis' },
        { source: 'apple_maps' },
        { source: 'LocalOS' },
        { source: 'telegram_app' },
        { source: 'vk' },
      ],
    );

    expect(result.sources).toEqual(['yandex', 'google', '2gis', 'apple']);
    expect(result.hasConfiguredMapLink).toBe(true);
    expect(result.hasSupportedConfiguredMapLink).toBe(true);
  });
});
