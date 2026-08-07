import { describe, expect, it } from 'vitest';

import { matchesSelectedSignalKeys } from './leadSignalFilters';

describe('matchesSelectedSignalKeys', () => {
  it('matches a lead when any selected signal is present', () => {
    expect(matchesSelectedSignalKeys(
      ['active_social_with_map_gap'],
      ['active_social_with_map_gap', 'paid_map_promotion'],
    )).toBe(true);
  });

  it('does not match a lead without any selected signal', () => {
    expect(matchesSelectedSignalKeys(
      ['service_catalog_gap'],
      ['active_social_with_map_gap', 'paid_map_promotion'],
    )).toBe(false);
  });

  it('does not restrict the registry when no signal is selected', () => {
    expect(matchesSelectedSignalKeys(['service_catalog_gap'], [])).toBe(true);
  });
});
