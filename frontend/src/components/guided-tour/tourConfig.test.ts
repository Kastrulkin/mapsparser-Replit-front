import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { workDestinations } from '@/lib/workNavigation';
import { GUIDED_TOUR_STEPS } from './tourConfig';

describe('demo matches the canonical navigation', () => {
  it('covers every current menu item once in menu order and on its own page', () => {
    const targets = new Set(workDestinations.map(item => 'nav-' + item.id));
    const steps = GUIDED_TOUR_STEPS.filter(step => step.target && targets.has(step.target));
    expect(steps.map(step => step.target)).toEqual(workDestinations.map(item => 'nav-' + item.id));
    steps.forEach((step, index) => {
      expect(step.route.split('?')[0]).toBe(workDestinations[index].path);
      expect(step.chapter).toBe(workDestinations[index].group);
    });
  });
  it('starts with Today and explains both ways to manage work', () => {
    expect(GUIDED_TOUR_STEPS[0].route).toBe('/dashboard/today');
    expect(GUIDED_TOUR_STEPS.find(step => step.key === 'today-overview')?.title).toBe('Следующий шаг');
    expect(GUIDED_TOUR_STEPS.find(step => step.key === 'operator-nav')?.body).toContain('обычными сообщениями');
    expect(GUIDED_TOUR_STEPS.find(step => step.key === 'operator-overview')?.body).toContain('поручение');
  });
  it('uses genuine maps tabs, not a fake AI visibility tab', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/dashboard/CardOverviewPage.tsx'), 'utf8');
    const tabs = GUIDED_TOUR_STEPS.filter(step => step.target?.startsWith('card-tab-'));
    expect(tabs.map(step => step.route)).toEqual([
      '/dashboard/card?tab=services', '/dashboard/card?tab=reviews&review_filter=all',
      '/dashboard/card?tab=news', '/dashboard/card?tab=keywords', '/dashboard/card?tab=competitors',
    ]);
    tabs.forEach(step => expect(source).toContain(`data-tour-target="${step.target}"`));
    expect(GUIDED_TOUR_STEPS.some(step => step.key === 'geo-promotion' || step.key === 'progress-focus-action')).toBe(false);
  });
  it('keeps content preparation, preview, save and review separate', () => {
    expect(GUIDED_TOUR_STEPS.filter(step => step.key.startsWith('content-plan-')).map(step => step.route)).toEqual([
      '/dashboard/content?demo_stage=setup', '/dashboard/content?demo_stage=preview',
      '/dashboard/content?demo_stage=saved', '/dashboard/content?demo_stage=review',
    ]);
  });
  it('opens utilities on their working screens', () => {
    const steps = GUIDED_TOUR_STEPS.filter(step => ['growth-paths', 'work-journal', 'chats-nav', 'telegram-radar'].includes(step.key));
    expect(steps).toHaveLength(4);
    expect(steps.map(step=>step.route)).toEqual(['/dashboard/growth-paths','/dashboard/work-journal','/dashboard/chats','/dashboard/telegram-radar']);
  });
  it('opens a public example of business knowledge rather than private records', () => {
    expect(GUIDED_TOUR_STEPS.find(step => step.key === 'business-knowledge')).toMatchObject({
      route: '/dashboard/profile?section=knowledge', target: 'business-knowledge',
    });
  });
});
