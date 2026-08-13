import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';
import { GUIDED_TOUR_STEPS } from './tourConfig';

describe('guided tour growth tools', () => {
  it('explains every dashboard menu item on the page it opens', () => {
    const menuTargets = GUIDED_TOUR_STEPS
      .filter((step) => step.target?.startsWith('nav-'))
      .map((step) => step.target);

    expect(menuTargets).toEqual([
      'nav-today',
      'nav-operator',
      'nav-profile',
      'nav-progress',
      'nav-finance',
      'nav-card',
      'nav-telegram-radar',
      'nav-average-ticket',
      'nav-ai-chat-promotion',
      'nav-content',
      'nav-agents',
      'nav-chats',
      'nav-partnerships',
      'nav-settings',
    ]);
  });

  it('keeps daily priorities on Today and natural-language tasks in Operator', () => {
    const todayOverview = GUIDED_TOUR_STEPS.find((step) => step.key === 'today-overview');
    const operatorOverview = GUIDED_TOUR_STEPS.find((step) => step.key === 'operator-overview');

    expect(todayOverview).toMatchObject({ route: '/dashboard/today', target: 'today-overview' });
    expect(todayOverview?.title).toBe('Что требует вашего решения');
    expect(operatorOverview).toMatchObject({ route: '/dashboard/operator', target: 'operator-overview' });
    expect(operatorOverview?.body).toContain('обычной фразой');
    expect(operatorOverview?.body).not.toContain('устаревшие данные карт');
  });

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

  it('keeps every maps workspace tour target attached to its real tab', () => {
    const cardOverviewSource = readFileSync(
      resolve(process.cwd(), 'src/pages/dashboard/CardOverviewPage.tsx'),
      'utf8',
    );
    const tabTargets = GUIDED_TOUR_STEPS
      .filter((step) => step.target?.startsWith('card-tab-'))
      .map((step) => step.target);

    tabTargets.forEach((target) => {
      expect(cardOverviewSource).toContain(`data-tour-target="${target}"`);
    });
  });

  it('opens content deterministically, visits agents, and only then moves to partnerships', () => {
    const flowStepKeys = ['content-calendar', 'content-plan-setup', 'content-plan-preview', 'content-plan-save', 'content-plan-review', 'agents-nav', 'agents-signals', 'agents-today', 'agents-employees', 'agents-control', 'agents-run', 'agents-review', 'agents-history', 'partnership-nav'];
    const flowSteps = GUIDED_TOUR_STEPS.filter((step) => flowStepKeys.includes(step.key));

    expect(flowSteps.map((step) => ({
      key: step.key,
      route: step.route,
      target: step.target,
    }))).toEqual([
      { key: 'content-calendar', route: '/dashboard/content?section=calendar', target: 'content-calendar' },
      { key: 'content-plan-setup', route: '/dashboard/content?demo_stage=setup', target: 'content-plan-setup' },
      { key: 'content-plan-preview', route: '/dashboard/content?demo_stage=preview', target: 'content-plan-preview' },
      { key: 'content-plan-save', route: '/dashboard/content?demo_stage=saved', target: 'content-plan-save' },
      { key: 'content-plan-review', route: '/dashboard/content?demo_stage=review', target: 'content-plan-review' },
      { key: 'agents-nav', route: '/dashboard/content?section=calendar', target: 'nav-agents' },
      { key: 'agents-signals', route: '/dashboard/agents', target: 'agents-workspace' },
      { key: 'agents-today', route: '/dashboard/agents', target: 'agents-today' },
      { key: 'agents-employees', route: '/dashboard/agents', target: 'agents-employees' },
      { key: 'agents-control', route: '/dashboard/agents', target: 'agents-control' },
      { key: 'agents-run', route: '/dashboard/agents', target: 'agents-run' },
      { key: 'agents-review', route: '/dashboard/agents', target: 'agents-review' },
      { key: 'agents-history', route: '/dashboard/agents', target: 'agents-history' },
      { key: 'partnership-nav', route: '/dashboard/partnerships?demo=romashka', target: 'nav-partnerships' },
    ]);
  });
});
