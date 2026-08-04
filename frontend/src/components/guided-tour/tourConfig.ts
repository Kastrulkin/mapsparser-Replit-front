import type { Language } from '@/i18n/LanguageContext';

import { guidedTourCopyForLanguage } from './guidedTourCopy';

export type GuidedTourChapter = 'network-pulse' | 'card-content' | 'automation' | 'partnership';

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
export const GUIDED_TOUR_VERSION = 3;

export const GUIDED_TOUR_STEP_LAYOUTS: GuidedTourStepLayout[] = [
  { key: 'welcome', chapter: 'network-pulse', route: '/dashboard/operator' },
  { key: 'operator-nav', chapter: 'network-pulse', route: '/dashboard/operator', target: 'nav-operator' },
  { key: 'operator-overview', chapter: 'network-pulse', route: '/dashboard/operator', target: 'operator-overview' },
  { key: 'network-switcher', chapter: 'network-pulse', route: '/dashboard/operator', target: 'network-switcher' },
  { key: 'progress-nav', chapter: 'network-pulse', route: '/dashboard/progress', target: 'nav-progress' },
  { key: 'progress-overview', chapter: 'network-pulse', route: '/dashboard/progress', target: 'progress-summary' },
  { key: 'progress-focus-action', chapter: 'network-pulse', route: '/dashboard/progress', target: 'progress-focus-action' },
  { key: 'progress-areas', chapter: 'network-pulse', route: '/dashboard/progress', target: 'progress-areas' },
  { key: 'progress-maps', chapter: 'network-pulse', route: '/dashboard/progress', target: 'progress-area-maps' },
  { key: 'progress-recent-results', chapter: 'network-pulse', route: '/dashboard/progress', target: 'progress-recent-results' },
  { key: 'card-nav', chapter: 'card-content', route: '/dashboard/progress', target: 'nav-card' },
  { key: 'card-overview', chapter: 'card-content', route: '/dashboard/card', target: 'card-overview' },
  { key: 'card-services', chapter: 'card-content', route: '/dashboard/card?tab=services', target: 'card-tab-services' },
  { key: 'card-reviews', chapter: 'card-content', route: '/dashboard/card?tab=reviews&review_filter=all', target: 'card-tab-reviews' },
  { key: 'card-news', chapter: 'card-content', route: '/dashboard/card?tab=news', target: 'card-tab-news' },
  { key: 'card-seo', chapter: 'card-content', route: '/dashboard/card?tab=keywords', target: 'card-tab-keywords' },
  { key: 'card-competitors', chapter: 'card-content', route: '/dashboard/card?tab=competitors', target: 'card-tab-competitors' },
  { key: 'telegram-radar', chapter: 'card-content', route: '/dashboard/telegram-radar', target: 'nav-telegram-radar' },
  { key: 'average-ticket', chapter: 'card-content', route: '/dashboard/average-ticket', target: 'nav-average-ticket' },
  { key: 'geo-promotion', chapter: 'card-content', route: '/dashboard/ai-chat-promotion', target: 'nav-ai-chat-promotion' },
  { key: 'content-nav', chapter: 'card-content', route: '/dashboard/card', target: 'nav-content' },
  { key: 'content-calendar', chapter: 'card-content', route: '/dashboard/content?section=calendar', target: 'content-calendar' },
  { key: 'agents-nav', chapter: 'automation', route: '/dashboard/content?section=calendar', target: 'nav-agents' },
  { key: 'agents-signals', chapter: 'automation', route: '/dashboard/agents', target: 'agents-workspace' },
  { key: 'agents-today', chapter: 'automation', route: '/dashboard/agents', target: 'agents-today' },
  { key: 'agents-employees', chapter: 'automation', route: '/dashboard/agents', target: 'agents-employees' },
  { key: 'agents-control', chapter: 'automation', route: '/dashboard/agents', target: 'agents-control' },
  { key: 'partnership-nav', chapter: 'partnership', route: '/dashboard/partnerships?demo=romashka', target: 'nav-partnerships' },
  { key: 'partnership-workspace', chapter: 'partnership', route: '/dashboard/partnerships?demo=romashka', target: 'partnership-workspace' },
  { key: 'partnership-candidates', chapter: 'partnership', route: '/dashboard/partnerships?demo=romashka', target: 'partnership-candidates' },
  { key: 'finish', chapter: 'partnership', route: '/dashboard/partnerships?demo=romashka', final: true },
];

export const guidedTourStepsForLanguage = (language: Language): GuidedTourStep[] => {
  const copy = guidedTourCopyForLanguage(language);
  return GUIDED_TOUR_STEP_LAYOUTS.map((layout) => ({
    ...layout,
    chapterTitle: copy.chapters[layout.chapter],
    title: copy.steps[layout.key].title,
    body: copy.steps[layout.key].body,
  }));
};

export const GUIDED_TOUR_STEPS = guidedTourStepsForLanguage('ru');
