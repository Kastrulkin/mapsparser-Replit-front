import { describe, expect, it } from 'vitest';
import { promotionContextSearch, readPromotionDirection } from './promotionContent';

describe('promotion direction through pricing and FAQ', () => {
  it('preserves a selected direction and marketing source without arbitrary query fields', () => {
    const search = promotionContextSearch('?lang=ru&utm_source=search&token=private', 'bloggers');
    expect(search).toBe('?lang=ru&utm_source=search&direction=bloggers');
    expect(promotionContextSearch(search)).toBe(search);
    expect(readPromotionDirection(search)).toBe('bloggers');
  });
  it('lets an explicit route replace a stale selected direction', () => {
    expect(promotionContextSearch('?direction=maps&utm_source=search', 'partners')).toBe('?utm_source=search&direction=partners');
  });
  it('does not accept an unknown or external destination as a direction', () => {
    expect(readPromotionDirection('?direction=https://example.test')).toBeUndefined();
    expect(promotionContextSearch('?direction=unknown')).toBe('');
  });
});
