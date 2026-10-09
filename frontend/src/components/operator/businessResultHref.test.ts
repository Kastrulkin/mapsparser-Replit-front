import { describe, expect, it } from 'vitest';
import { businessResultHref } from './businessResultHref';

describe('businessResultHref', () => {
  it('preserves result tab and fragment while carrying business selection', () => {
    expect(businessResultHref('/dashboard/card?tab=services#preview', 'root')).toBe('/dashboard/card?tab=services&business_id=root#preview');
  });
  it('replaces stale business selection', () => {
    expect(businessResultHref('/dashboard/profile?business_id=other', 'branch')).toBe('/dashboard/profile?business_id=branch');
  });
  it('leaves external destinations and missing scope intact', () => {
    expect(businessResultHref('https://example.com', 'root')).toBe('https://example.com');
    expect(businessResultHref('/dashboard/card?tab=reviews')).toBe('/dashboard/card?tab=reviews');
  });
});
