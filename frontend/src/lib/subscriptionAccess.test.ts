import { describe, expect, it } from 'vitest';

import { getCapabilityAccessForBusiness } from './subscriptionAccess';

const business = (subscription_tier: string, subscription_status = 'active', subscription_ends_at?: string) => ({
  subscription_tier,
  subscription_status,
  subscription_ends_at,
});

describe('subscription capability matrix', () => {
  it('uses the backend capability contract when it is present', () => {
    const payload = {
      subscription_tier: 'concierge',
      subscription_status: 'active',
      subscription_access: {
        tier: 'starter',
        tier_name: 'Карты',
        status: 'active',
        active: true,
        capabilities: ['maps', 'maps.news'],
      },
    };

    expect(getCapabilityAccessForBusiness(payload, 'maps.news').allowed).toBe(true);
    expect(getCapabilityAccessForBusiness(payload, 'influencers').allowed).toBe(false);
  });

  it('opens maps, radar and web analytics on Maps', () => {
    expect(getCapabilityAccessForBusiness(business('starter'), 'maps').allowed).toBe(true);
    expect(getCapabilityAccessForBusiness(business('starter'), 'maps.services').allowed).toBe(true);
    expect(getCapabilityAccessForBusiness(business('starter'), 'maps.reviews').allowed).toBe(true);
    expect(getCapabilityAccessForBusiness(business('starter'), 'maps.news').allowed).toBe(true);
    expect(getCapabilityAccessForBusiness(business('starter'), 'telegram_radar').allowed).toBe(true);
    expect(getCapabilityAccessForBusiness(business('starter'), 'web_analytics').allowed).toBe(true);
    expect(getCapabilityAccessForBusiness(business('starter'), 'influencers').allowed).toBe(false);
    expect(getCapabilityAccessForBusiness(business('starter'), 'social_content').allowed).toBe(false);
  });

  it('opens acquisition but not management on Acquisition', () => {
    expect(getCapabilityAccessForBusiness(business('professional'), 'partnerships').allowed).toBe(true);
    expect(getCapabilityAccessForBusiness(business('professional'), 'ai_visibility').allowed).toBe(true);
    expect(getCapabilityAccessForBusiness(business('professional'), 'finance').allowed).toBe(false);
    expect(getCapabilityAccessForBusiness(business('professional'), 'average_ticket').allowed).toBe(false);
  });

  it('opens management for concierge, promo, elite and the enterprise alias', () => {
    for (const tier of ['concierge', 'promo', 'elite', 'enterprise']) {
      expect(getCapabilityAccessForBusiness(business(tier), 'automation').allowed).toBe(true);
    }
  });

  it('closes expired and inactive subscriptions', () => {
    expect(getCapabilityAccessForBusiness(business('concierge', 'inactive'), 'finance').allowed).toBe(false);
    expect(getCapabilityAccessForBusiness(business('concierge', 'active', '2000-01-01'), 'finance').allowed).toBe(false);
  });
});
