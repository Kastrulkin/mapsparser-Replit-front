import { workNavigationCopy, type WorkGroup } from '@/lib/workNavigation';
import type { Language } from '@/i18n/LanguageContext.logic';

import { guidedTourCopyForLanguage } from './guidedTourCopy';

export type GuidedTourChapter = WorkGroup;

export type GuidedTourStep = {
  key: string;
  chapter: GuidedTourChapter;
  chapterTitle: string;
  title: string;
  body: string;
  route: string;
  target?: string;
  final?: boolean;
};

type GuidedTourStepLayout = Omit<GuidedTourStep, 'chapterTitle' | 'title' | 'body'>;

export const GUIDED_TOUR_KEY = 'roga-i-kopyta-v1';
export const GUIDED_TOUR_VERSION = 7;

export const GUIDED_TOUR_STEP_LAYOUTS: GuidedTourStepLayout[] = [
  { key: 'welcome', chapter: 'daily', route: '/dashboard/today' },
  { key: 'today-nav', chapter: 'daily', route: '/dashboard/today', target: 'nav-today' },
  { key: 'today-overview', chapter: 'daily', route: '/dashboard/today', target: 'today-overview' },
  { key: 'operator-nav', chapter: 'daily', route: '/dashboard/operator', target: 'nav-operator' },
  { key: 'operator-overview', chapter: 'daily', route: '/dashboard/operator', target: 'operator-overview' },
  { key: 'network-switcher', chapter: 'daily', route: '/dashboard/operator', target: 'network-switcher' },
  { key: 'card-nav', chapter: 'directions', route: '/dashboard/card', target: 'nav-maps' },
  { key: 'card-overview', chapter: 'directions', route: '/dashboard/card', target: 'card-overview' },
  { key: 'card-services', chapter: 'directions', route: '/dashboard/card?tab=services', target: 'card-tab-services' },
  { key: 'card-reviews', chapter: 'directions', route: '/dashboard/card?tab=reviews&review_filter=all', target: 'card-tab-reviews' },
  { key: 'card-news', chapter: 'directions', route: '/dashboard/card?tab=news', target: 'card-tab-news' },
  { key: 'card-seo', chapter: 'directions', route: '/dashboard/card?tab=keywords', target: 'card-tab-keywords' },
  { key: 'card-competitors', chapter: 'directions', route: '/dashboard/card?tab=competitors', target: 'card-tab-competitors' },
  { key: 'content-nav', chapter: 'directions', route: '/dashboard/content', target: 'nav-content' },
  { key: 'content-calendar', chapter: 'directions', route: '/dashboard/content?section=calendar', target: 'content-calendar' },
  { key: 'content-plan-setup', chapter: 'directions', route: '/dashboard/content?demo_stage=setup', target: 'content-plan-setup' },
  { key: 'content-plan-preview', chapter: 'directions', route: '/dashboard/content?demo_stage=preview', target: 'content-plan-preview' },
  { key: 'content-plan-save', chapter: 'directions', route: '/dashboard/content?demo_stage=saved', target: 'content-plan-save' },
  { key: 'content-plan-review', chapter: 'directions', route: '/dashboard/content?demo_stage=review', target: 'content-plan-review' },
  { key: 'partnership-nav', chapter: 'directions', route: '/dashboard/partnerships?demo=romashka', target: 'nav-partnerships' },
  { key: 'partnership-workspace', chapter: 'directions', route: '/dashboard/partnerships?demo=romashka', target: 'partnership-workspace' },
  { key: 'partnership-candidates', chapter: 'directions', route: '/dashboard/partnerships?demo=romashka', target: 'partnership-candidates' },
  { key: 'influencers-nav', chapter: 'directions', route: '/dashboard/influencers', target: 'nav-influencers' },
  { key: 'average-ticket', chapter: 'directions', route: '/dashboard/average-ticket', target: 'nav-upsells' },
  { key: 'agents-nav', chapter: 'directions', route: '/dashboard/agents', target: 'nav-automation' },
  { key: 'agents-signals', chapter: 'directions', route: '/dashboard/agents', target: 'agents-workspace' },
  { key: 'agents-today', chapter: 'directions', route: '/dashboard/agents', target: 'agents-today' },
  { key: 'agents-employees', chapter: 'directions', route: '/dashboard/agents', target: 'agents-employees' },
  { key: 'agents-control', chapter: 'directions', route: '/dashboard/agents', target: 'agents-control' },
  { key: 'agents-run', chapter: 'directions', route: '/dashboard/agents', target: 'agents-run' },
  { key: 'agents-review', chapter: 'directions', route: '/dashboard/agents', target: 'agents-review' },
  { key: 'agents-history', chapter: 'directions', route: '/dashboard/agents', target: 'agents-history' },
  { key: 'progress-nav', chapter: 'control', route: '/dashboard/progress', target: 'nav-progress' },
  { key: 'progress-overview', chapter: 'control', route: '/dashboard/progress', target: 'progress-summary' },
  { key: 'progress-areas', chapter: 'control', route: '/dashboard/progress', target: 'progress-areas' },
  { key: 'progress-maps', chapter: 'control', route: '/dashboard/progress', target: 'progress-area-maps' },
  { key: 'progress-recent-results', chapter: 'control', route: '/dashboard/progress', target: 'progress-recent-results' },
  { key: 'finance-nav', chapter: 'control', route: '/dashboard/finance', target: 'nav-finance' },
  { key: 'profile-nav', chapter: 'service', route: '/dashboard/profile', target: 'nav-profile' },
  { key: 'business-knowledge', chapter: 'service', route: '/dashboard/profile?section=knowledge', target: 'business-knowledge' },
  { key: 'settings-nav', chapter: 'service', route: '/dashboard/settings', target: 'nav-settings' },
  { key: 'more-nav', chapter: 'service', route: '/dashboard/more', target: 'nav-more' },
  { key: 'growth-paths', chapter: 'service', route: '/dashboard/growth-paths', target: 'growth-paths-overview' },
  { key: 'work-journal', chapter: 'service', route: '/dashboard/work-journal', target: 'work-journal-overview' },
  { key: 'chats-nav', chapter: 'service', route: '/dashboard/chats', target: 'chats-overview' },
  { key: 'telegram-radar', chapter: 'service', route: '/dashboard/telegram-radar', target: 'radar-overview' },
  { key: 'finish', chapter: 'directions', route: '/dashboard/partnerships?demo=romashka', final: true },
];

export const guidedTourStepsForLanguage = (language: Language): GuidedTourStep[] => {
  const copy = guidedTourCopyForLanguage(language);
  return GUIDED_TOUR_STEP_LAYOUTS.map((layout) => ({
    ...layout,
    chapterTitle: workNavigationCopy(language).groups[layout.chapter],
    title: copy.steps[layout.key].title,
    body: copy.steps[layout.key].body,
  }));
};

export const GUIDED_TOUR_STEPS = guidedTourStepsForLanguage('ru');
