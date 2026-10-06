import { test, expect } from '@playwright/test';

// Read-only production checkpoint: Riderra group 02.10, 42 raw results,
// 0 verified, 41 awaiting decision, 5 charged. Providers are not executed here.
const business = { id: 'edbd961a-273f-4f15-836e-33aacc0aa0e3', name: 'Riderra (Tallinn)', subscription_tier: 'concierge', subscription_status: 'active' };
const group = { id: 'e2252eb8-14f5-47bf-8256-f41c0ae10491', business_id: business.id, display_name: 'Индия → Пхукет · 02.10', revision: 'fixture-revision', status: 'waiting_for_review', stage: 'Недостаточно кредитов', config: { mode: 'find_only', audience: 'Турагентства Индии', queries: [], max_search_calls: 3, language: 'en', max_candidates: 50, target_count: 10 }, state: { started: true, lead_ids: ['company-1'], workstream_ids: ['ws-1'], blocker: 'insufficient_credits' }, report: { found: 42, imported: 41, eligible: 0 }, presentation: {
  phase: 'companies', status: 'needs_attention', label: 'Требуется действие', active: false,
  reason: 'Не хватает кредитов для следующего действия. Прогресс сохранён.',
  next_action: { kind: 'link', label: 'Пополнить баланс', href: `/dashboard/profile?business_id=${business.id}&focus=subscription#subscription` },
  metrics: { found: 42, eligible: 0, target: 10, needs_decision: 41, awaiting_check: 41, prepared: 0, queued: 0, sent: 0, replies: 0 }, expenses: { charged: 5, estimate: 65, estimate_only: true },
} };

let runtimeErrors: string[] = [];
test.beforeEach(async ({ page }) => {
  runtimeErrors = [];
  page.on('pageerror', error => runtimeErrors.push(error.message));
  await page.addInitScript(id => { localStorage.setItem('auth_token', 'read-only-fixture'); localStorage.setItem('selectedBusinessId', id); localStorage.setItem('language', 'ru'); }, business.id);
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/auth/me') return route.fulfill({ json: { id: 'fixture-user', email: 'fixture@example.test', is_superadmin: true, businesses: [business] } });
    if (url.pathname === '/api/businesses') return route.fulfill({ json: { businesses: [business] } });
    if (url.pathname === '/api/partnership/continuations') return route.fulfill({ json: { enabled: true, items: [group] } });
    if (url.pathname === `/api/partnership/continuations/${group.id}`) return route.fulfill({ json: group });
    if (url.pathname === '/api/partnership/leads') return route.fulfill({ json: { items: url.searchParams.get('company_filter') === 'suitable' ? [] : [{ id: 'company-1', name: 'Компания для проверки', business_id: business.id, pipeline_status: 'unprocessed', partnership_stage: 'imported' }], count: 1, access: { allowed: true } } });
    if (url.pathname.startsWith('/api/operator/conversations/')) return route.fulfill({ json: { conversation: null, messages: [] } });
    return route.fulfill({ json: { items: [], drafts: [], batches: [], reactions: [], access: { allowed: true }, summary: {}, counts: {} } });
  });
});

test('chat keeps selected group above history, separates goal and raw results, and does not resume after balance link', async ({ page }, testInfo) => {
  await page.goto(`/dashboard/operator?business_id=${business.id}&search_task_id=${group.id}`);
  await expect(page.getByText('Найдено кандидатов', { exact: true })).toBeVisible();
  await expect(page.getByText('0 / 10', { exact: true })).toBeVisible();
  await expect(page.getByText(/Списано: 5 кр./)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Пополнить баланс' })).toHaveAttribute('href', group.presentation.next_action.href);
  await expect(page.getByText('Отправка', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('outreach-chat.png'), fullPage: true });
});

test('companies filters and group survive navigation and reload', async ({ page }, testInfo) => {
  await page.goto(`/dashboard/partnerships?business_id=${business.id}&search_task_id=${group.id}&section=companies`);
  await expect(page.getByRole('button', { name: 'Выбрать для работы', exact: true })).toBeVisible();
  await expect(page.getByText('Страна компании: не проверено')).toBeVisible();
  const requests: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/partnership/leads')) requests.push(request.url()); });
  await page.getByRole('button', { name: 'Подходящие', exact: true }).click();
  await expect(page).toHaveURL(/company_filter=suitable/);
  await expect.poll(() => requests.some(url => url.includes('company_filter=suitable') && url.includes(`search_task_id=${group.id}`))).toBe(true);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Подходящие', exact: true })).toHaveAttribute('aria-pressed', 'true');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('outreach-companies.png'), fullPage: true });
});

 test.afterEach(() => { expect(runtimeErrors).toEqual([]); });
