import { describe, expect, it } from 'vitest';
import { resolveMobileRoute } from './mobileDeepLinkRouter';

const navigation = [
  { key: 'today', status: 'available' },
  { key: 'reviews', status: 'available' },
  { key: 'progress', status: 'available' },
  { key: 'finance', status: 'available' },
  { key: 'diagnostics', status: 'hidden' },
] satisfies Parameters<typeof resolveMobileRoute>[1];

describe('resolveMobileRoute', () => {
  it('opens a verified object inside its native module', () => {
    expect(resolveMobileRoute({ screen: 'finance', item_id: 'sale-1' }, navigation)).toMatchObject({ tab: 'more', module: 'finance', itemId: 'sale-1' });
  });

  it('falls back from hidden modules to Today', () => {
    expect(resolveMobileRoute({ screen: 'diagnostics', item_id: 'job-1' }, navigation)).toMatchObject({ tab: 'today', module: '', itemId: '' });
  });

  it('keeps review filters and the verified review id', () => {
    expect(resolveMobileRoute({ screen: 'reviews', item_type: 'review', item_id: 'review-1', filters: { status: 'unanswered' } }, navigation)).toEqual({
      tab: 'reviews', module: '', itemId: 'review-1', reviewId: 'review-1', filters: { status: 'unanswered' },
    });
  });

  it('opens progress as a primary mobile destination', () => {
    expect(resolveMobileRoute({ screen: 'progress' }, navigation)).toMatchObject({ tab: 'progress', module: '' });
  });
});
