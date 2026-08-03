export type MobileAttentionTarget = {
  id?: string;
  title?: string;
  description?: string;
  category?: string;
  screen?: string;
  cta?: { href?: string };
};

const knownScreens = new Set([
  'tasks',
  'reviews',
  'progress',
  'cards',
  'content',
  'services',
  'finance',
  'partnerships',
  'agents',
  'settings',
  'diagnostics',
  'companies',
  'community_sources',
]);

const categoryScreens: Record<string, string> = {
  reviews: 'reviews',
  content: 'content',
  maps: 'cards',
  cards: 'cards',
  services: 'services',
  finance: 'finance',
  partnerships: 'partnerships',
  agents: 'agents',
  approvals: 'tasks',
  diagnostics: 'diagnostics',
  status: 'progress',
};

const hrefScreens: [string, string][] = [
  ['/dashboard/card?tab=reviews', 'reviews'],
  ['/dashboard/card?tab=services', 'services'],
  ['/dashboard/card', 'cards'],
  ['/dashboard/content', 'content'],
  ['/dashboard/finance', 'finance'],
  ['/dashboard/partnerships', 'partnerships'],
  ['/dashboard/agents', 'agents'],
  ['/dashboard/settings', 'settings'],
  ['/dashboard/progress', 'progress'],
];

const textScreens: [RegExp, string][] = [
  [/review|review_reply|reviews?|\u043e\u0442\u0437\u044b\u0432/i, 'reviews'],
  [/content|news|post|draft|\u043a\u043e\u043d\u0442\u0435\u043d\u0442|\u043d\u043e\u0432\u043e\u0441\u0442|\u043f\u043e\u0441\u0442|\u0447\u0435\u0440\u043d\u043e\u0432\u0438\u043a/i, 'content'],
  [/map|card|parse|yandex|2gis|\u043a\u0430\u0440\u0442|\u044f\u043d\u0434\u0435\u043a\u0441|2\u0433\u0438\u0441/i, 'cards'],
  [/partner|outreach|\u043f\u0430\u0440\u0442\u043d\u0451\u0440|\u043f\u0430\u0440\u0442\u043d\u0435\u0440/i, 'partnerships'],
  [/finance|sale|payment|order|\u0444\u0438\u043d\u0430\u043d\u0441|\u043f\u0440\u043e\u0434\u0430\u0436|\u043e\u043f\u043b\u0430\u0442|\u0437\u0430\u043a\u0430\u0437/i, 'finance'],
  [/service|menu|\u0443\u0441\u043b\u0443\u0433|\u043c\u0435\u043d\u044e/i, 'services'],
  [/agent|automation|\u0430\u0433\u0435\u043d\u0442|\u0430\u0432\u0442\u043e\u043c\u0430\u0442/i, 'agents'],
  [/diagnostic|failed_job|\u0434\u0438\u0430\u0433\u043d\u043e\u0441\u0442|\u043e\u0448\u0438\u0431\u043a/i, 'diagnostics'],
];

export function resolveMobileAttentionScreen(item: MobileAttentionTarget): string {
  const explicit = String(item.screen || '').trim();
  if (knownScreens.has(explicit)) return explicit;

  const category = String(item.category || '').trim().toLowerCase();
  if (categoryScreens[category]) return categoryScreens[category];

  const href = String(item.cta?.href || '').trim().toLowerCase();
  const hrefMatch = hrefScreens.find(([pattern]) => href.startsWith(pattern));
  if (hrefMatch) return hrefMatch[1];

  const searchable = [item.id, item.title, item.description].filter(Boolean).join(' ');
  const textMatch = textScreens.find(([pattern]) => pattern.test(searchable));
  return textMatch?.[1] || 'tasks';
}
