import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

const read = (path) => readFileSync(resolve(root, path), 'utf8');

const files = {
  customer: read('frontend/src/components/ProspectingManagement.tsx'),
  partnerPage: read('frontend/src/pages/dashboard/PartnershipSearchPage.tsx'),
  partnerOverview: read('frontend/src/components/prospecting/PartnershipWorkspaceOverview.tsx'),
  partnerDrawer: read('frontend/src/components/prospecting/PartnershipLeadDetailDrawer.tsx'),
  partnerOps: read('frontend/src/components/prospecting/PartnershipOperationalSections.tsx'),
  partnerAnalytics: read('frontend/src/components/prospecting/PartnershipAnalyticsWorkspace.tsx'),
  chrome: read('frontend/src/components/prospecting/ProspectingWorkspaceChrome.tsx'),
};

const checks = [
  ['customer campaign overview', files.customer, 'Кампания поиска клиентов'],
  ['partner campaign overview', files.partnerOverview, 'Партнёрская кампания'],
  ['customer main tabs include candidates', files.customer, "{ value: 'raw', label: 'Кандидаты'"],
  ['customer main tabs include letters', files.customer, "{ value: 'outreach', label: 'Письма'"],
  ['customer main tabs include report', files.customer, "{ value: 'analytics', label: 'Отчёт'"],
  ['partner main tabs include candidates', files.partnerPage, "{ value: 'raw', label: 'Кандидаты'"],
  ['partner main tabs include letters', files.partnerPage, "{ value: 'drafts', label: 'Письма'"],
  ['partner main tabs include sending', files.partnerPage, "{ value: 'queue', label: 'Отправка'"],
  ['partner main tabs include report', files.partnerPage, "{ value: 'analytics', label: 'Отчёт'"],
  ['customer details use drawer', files.customer, '<Sheet open={Boolean(previewLead)}'],
  ['customer postpone/disqualify modal', files.customer, '<LeadStageDecisionModal'],
  ['customer postpone reason field', files.customer, 'postponed_reason'],
  ['customer return date field', files.customer, 'next_action_at'],
  ['partner details use drawer', files.partnerPage, '<PartnershipLeadDetailDrawer'],
  ['customer sequence first email', files.customer, 'Письмо 1'],
  ['customer sequence offer', files.customer, 'КП / предложение'],
  ['customer sequence follow-up', files.customer, 'Follow-up'],
  ['partner sequence first email', files.partnerOps, 'Письмо 1'],
  ['partner sequence offer', files.partnerOps, 'КП / конкретное предложение'],
  ['partner sequence follow-up', files.partnerOps, 'Follow-up'],
  ['customer sending queue tab', files.customer, "{ value: 'queue', label: 'Очередь'"],
  ['partner sending queue workspace', files.partnerPage, "workspaceView === 'queue'"],
  ['customer simple status candidate', files.customer, "return 'Кандидат'"],
  ['customer simple status first email sent', files.customer, "return 'Письмо 1 отправлено'"],
  ['customer simple status offer sent', files.customer, "return 'Предложение отправлено'"],
  ['customer simple status reply', files.customer, "return 'Есть ответ'"],
  ['partner simple status candidate', files.partnerPage, "label: 'Кандидат'"],
  ['partner simple status first email sent', files.partnerPage, "label: 'Письмо 1 отправлено'"],
  ['partner simple status offer sent', files.partnerPage, "label: 'КП отправлено'"],
  ['partner simple status reply', files.partnerPage, "label: 'Есть ответ'"],
  ['customer stage report', files.customer, 'Воронка по этапам'],
  ['partner stage report', files.partnerAnalytics, 'Отчёт по этапам кампании'],
  ['customer AI is secondary', files.customer, 'Дополнительно: обучение и рекомендации'],
  ['partner AI is secondary', files.partnerAnalytics, 'Дополнительно: обучение и рекомендации'],
];

const forbidden = [
  ['visible Apify Yandex', 'Apify Yandex'],
  ['visible Apify 2GIS', 'Apify 2GIS'],
  ['visible matched sources', 'Matched sources'],
  ['visible enrich title', 'Результат enrich'],
  ['fake follow-up save', 'Follow-up сохранён локально'],
  ['fake follow-up button', 'Сохранить follow-up'],
  ['old unprocessed label', 'Необработанные лиды'],
  ['old postpone prompt', 'Почему откладываем этого лида'],
  ['old disqualify prompt', 'Почему переносим лида'],
];

const failures = [];

for (const [name, source, needle] of checks) {
  if (!source.includes(needle)) {
    failures.push(`Missing: ${name} (${needle})`);
  }
}

const allSource = Object.values(files).join('\n');
for (const [name, needle] of forbidden) {
  if (allSource.includes(needle)) {
    failures.push(`Forbidden: ${name} (${needle})`);
  }
}

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(`Prospecting UI simplification checks passed: ${checks.length} required signals, ${forbidden.length} forbidden signals.`);
