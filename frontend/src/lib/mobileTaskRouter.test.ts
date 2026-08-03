import { describe, expect, it } from 'vitest';
import { resolveMobileAttentionScreen } from './mobileTaskRouter';

describe('resolveMobileAttentionScreen', () => {
  it('prefers an explicit supported mobile destination', () => {
    expect(resolveMobileAttentionScreen({ screen: 'finance', category: 'reviews' })).toBe('finance');
  });

  it('routes canonical attention categories to the working screen', () => {
    expect(resolveMobileAttentionScreen({ category: 'reviews' })).toBe('reviews');
    expect(resolveMobileAttentionScreen({ category: 'content' })).toBe('content');
    expect(resolveMobileAttentionScreen({ category: 'maps' })).toBe('cards');
  });

  it('understands existing backend links during migration', () => {
    expect(resolveMobileAttentionScreen({ cta: { href: '/dashboard/card?tab=services' } })).toBe('services');
    expect(resolveMobileAttentionScreen({ cta: { href: '/dashboard/partnerships' } })).toBe('partnerships');
  });

  it('routes legacy draft and review task identifiers without a dead end', () => {
    expect(resolveMobileAttentionScreen({ id: 'drafts', title: '12 \u0447\u0435\u0440\u043d\u043e\u0432\u0438\u043a\u043e\u0432 \u0433\u043e\u0442\u043e\u0432\u044b' })).toBe('content');
    expect(resolveMobileAttentionScreen({ id: 'review_reply_drafts' })).toBe('reviews');
  });

  it('keeps an unknown operational task in the work queue', () => {
    expect(resolveMobileAttentionScreen({ id: 'custom_task' })).toBe('tasks');
  });
});
