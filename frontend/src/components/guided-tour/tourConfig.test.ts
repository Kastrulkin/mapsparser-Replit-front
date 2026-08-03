import { describe, expect, it } from 'vitest';
import { GUIDED_TOUR_STEPS } from './tourConfig';

describe('guided tour growth tools', () => {
  it('opens each maps workspace tab and growth tool as a separate step', () => {
    const growthStepKeys = [
      'card-overview',
      'card-services',
      'card-reviews',
      'card-news',
      'card-seo',
      'card-competitors',
      'telegram-radar',
      'average-ticket',
      'geo-promotion',
    ];
    const growthSteps = GUIDED_TOUR_STEPS.filter((step) => growthStepKeys.includes(step.key));

    expect(growthSteps.map((step) => ({
      key: step.key,
      route: step.route,
      target: step.target,
    }))).toEqual([
      { key: 'card-overview', route: '/dashboard/card', target: 'card-overview' },
      { key: 'card-services', route: '/dashboard/card?tab=services', target: 'card-tab-services' },
      { key: 'card-reviews', route: '/dashboard/card?tab=reviews&review_filter=all', target: 'card-tab-reviews' },
      { key: 'card-news', route: '/dashboard/card?tab=news', target: 'card-tab-news' },
      { key: 'card-seo', route: '/dashboard/card?tab=keywords', target: 'card-tab-keywords' },
      { key: 'card-competitors', route: '/dashboard/card?tab=competitors', target: 'card-tab-competitors' },
      { key: 'telegram-radar', route: '/dashboard/telegram-radar', target: 'nav-telegram-radar' },
      { key: 'average-ticket', route: '/dashboard/average-ticket', target: 'nav-average-ticket' },
      { key: 'geo-promotion', route: '/dashboard/ai-chat-promotion', target: 'nav-ai-chat-promotion' },
    ]);
  });
});
