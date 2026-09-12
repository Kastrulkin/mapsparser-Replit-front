import { expect, test } from '@playwright/test';

const managedProgress = {
  success: true,
  status: 'available',
  scope: { kind: 'business', id: 'business-1', name: 'Тестовая школа', business_ids: ['business-1'], locations: [{ id: 'business-1', name: 'Тестовая школа' }] },
  summary: { completed_milestones: 2, total_milestones: 5, active_areas: 1, needs_attention: 1, locations_count: 1 },
  areas: [],
  recent_results: [],
  policy_version: '2026-09-11.1',
  goal: { value: 'bookings', label: 'Больше записей', status: 'confirmed', options: [{ value: 'bookings', label: 'Больше записей' }] },
  card_state: {
    status: 'needs_attention',
    locations: [{
      business_id: 'business-1', business_name: 'Тестовая школа', critical: true,
      providers: [{
        provider: 'yandex', provider_label: 'Яндекс', source_state: 'observed', observed_at: '2026-09-10T10:00:00Z',
        facts: {
          access: { state: 'observed', value: true },
          category: { state: 'missing', value: null },
          prices: { state: 'unknown', value: null },
          publications: { state: 'observed', value: 3 },
        },
        benchmark: { status: 'ready', sample_size: 14, period_days: 90, scope: 'city_category' },
      }],
    }],
  },
  baseline: { status: 'observed', period: { start: '2026-08-14', end: '2026-09-10', days: 28 }, providers: { yandex: { views: 420, clicks: 37, actions: 37 } } },
  focus_action: { id: 'focus-1', title: 'Уточните основную категорию в Яндекс', reason: 'Категория должна точно описывать основную деятельность этой точки.', expected_outcome: 'Упростить запись и проверить изменение записей или обращений.', cta_label: 'Проверить категорию', screen: 'cards', priority: 9096 },
  next_actions: [{ id: 'next-1', title: 'Добавьте понятный путь обращения в Яндекс', business_name: 'Тестовая школа', gate_label: 'Можно обратиться' }],
  measurement: { status: 'active', checkpoints: [{ days: 14, due_at: '2026-09-25T10:00:00Z', status: 'waiting' }] },
};

test('managed card path is readable in the web progress screen', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 'managed-growth-test');
    localStorage.setItem('selectedBusinessId', 'business-1');
    localStorage.setItem('language', 'ru');
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'user-1', email: 'owner@example.test', businesses: [{ id: 'business-1', name: 'Тестовая школа', subscription_tier: 'concierge', subscription_status: 'active' }] } });
    if (path === '/api/business/business-1') return route.fulfill({ json: { id: 'business-1', name: 'Тестовая школа', subscription_tier: 'concierge', subscription_status: 'active' } });
    if (path === '/api/operator/progress') return route.fulfill({ json: managedProgress });
    if (path === '/api/journey-actions') return route.fulfill({ json: { actions: [] } });
    if (path === '/api/business/business-1/parse-status') return route.fulfill({ json: { success: true, status: 'completed' } });
    return route.fulfill({ json: { success: true, items: [], businesses: [] } });
  });

  await page.goto('/dashboard/progress');
  await expect(page.getByRole('heading', { name: 'Цель и состояние карточек' })).toBeVisible();
  await expect(page.getByText('Уточните основную категорию в Яндекс', { exact: true })).toBeVisible();
  await expect(page.getByText('Базовые 28 дней', { exact: true })).toBeVisible();
  await page.getByRole('group').filter({ hasText: 'Яндекс' }).click();
  await expect(page.getByText('Нужно заполнить', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('managed card path uses the same contract in Telegram Mini App', async ({ page }) => {
  await page.route('https://telegram.org/js/telegram-web-app.js*', route => route.fulfill({ contentType: 'application/javascript', body: '' }));
  await page.addInitScript(() => {
    localStorage.setItem('localos-mini-onboarding-v3:user-1', 'completed');
    Object.defineProperty(window, 'Telegram', { configurable: true, value: { WebApp: { initData: 'signed-test', ready: () => {}, expand: () => {} } } });
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/operator/telegram/bootstrap') return route.fulfill({ json: {
      success: true, user: { id: 'user-1' }, web_session_token: 'managed-growth-test', today_v2_enabled: false,
      selected_scope: { kind: 'business', id: 'business-1', name: 'Тестовая школа', business_ids: ['business-1'] },
      summary: { attention_items: [] }, catalog: { businesses: [], networks: [], total_choices: 1 }, resolved_deep_link: { screen: 'progress' },
      navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }, { key: 'progress', label: 'Прогресс', group: 'primary', status: 'available' }],
    } });
    if (path === '/api/operator/mobile/progress') return route.fulfill({ json: managedProgress });
    return route.fulfill({ json: { success: true, items: [], summary: { attention_items: [] } } });
  });

  await page.goto('/telegram/control?screen=progress');
  await expect(page.getByText('Больше записей', { exact: true })).toBeVisible();
  await expect(page.getByText('Уточните основную категорию в Яндекс', { exact: true })).toBeVisible();
  await expect(page.getByText('Базовые 28 дней', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
