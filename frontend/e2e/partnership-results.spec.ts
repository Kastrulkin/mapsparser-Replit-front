import { test, expect } from '@playwright/test';

test('content export uses Telegram download and retains a browser fallback', async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    localStorage.setItem('localos-mini-onboarding-v3:export-user', 'completed');
    Object.defineProperty(window, 'Telegram', { configurable: true, value: { WebApp: {
      initData: 'signed-test', ready: () => {}, expand: () => {}, isVersionAtLeast: () => true,
      downloadFile: (params: { url: string; file_name: string }) => sessionStorage.setItem('test-download', JSON.stringify(params)),
    } } });
  });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/operator/telegram/bootstrap') return route.fulfill({ json: {
      success: true, user: { id: 'export-user' }, web_session_token: 'test-session', today_v2_enabled: false,
      selected_scope: { kind: 'business', id: 'b1', name: 'Органика', business_ids: ['b1'] }, summary: { attention_items: [] }, catalog: { businesses: [], networks: [], total_choices: 1 },
      resolved_deep_link: { screen: 'content' }, navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }, { key: 'content', label: 'Контент', group: 'more', status: 'available' }],
    } });
    if (path === '/api/operator/mobile/modules/content') return route.fulfill({ json: { items: [{ id: 'i1', plan_id: 'p1', plan_title: 'Контент-план на сентябрь', title: 'Знакомство с командой', scheduled_for: '2026-09-12', status: 'planned', business_id: 'b1' }] } });
    if (path === '/api/content-plans/p1/export') {
      expect(route.request().postDataJSON()).toEqual({ format: 'pdf' });
      return route.fulfill({ json: { download_url: '/api/content-plans/download/test-link', filename: 'content-plan.pdf' } });
    }
    return route.fulfill({ json: { items: [], summary: { attention_items: [] } } });
  });
  await page.goto('/telegram/control?screen=content');
  await page.getByRole('button', { name: 'PDF', exact: true }).click();
  await page.getByRole('button', { name: 'Сохранить файл', exact: true }).click();
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem('test-download') || '{}').file_name)).toBe('content-plan.pdf');
  await expect(page.getByRole('link', { name: /Если скачивание не началось/ })).toHaveAttribute('href', '/api/content-plans/download/test-link');
  await page.screenshot({ path: testInfo.outputPath('content-export.png'), fullPage: true });
});

test('owner sees the agreement and approved instructions in Mini App', async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    localStorage.setItem('localos-mini-onboarding-v3:results-user', 'completed');
    Object.defineProperty(window, 'Telegram', { configurable: true, value: { WebApp: { initData: 'signed-test', ready: () => {}, expand: () => {} } } });
  });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/operator/telegram/bootstrap') return route.fulfill({ json: {
      success: true, user: { id: 'results-user' }, web_session_token: 'test-session', today_v2_enabled: false,
      selected_scope: { kind: 'business', id: 'b1', name: 'Органика', business_ids: ['b1'] },
      summary: { attention_items: [] }, catalog: { businesses: [], networks: [], total_choices: 1 },
      resolved_deep_link: { screen: 'partnerships' },
      navigation: [{ key: 'today', label: 'Сегодня', group: 'primary', status: 'available' }, { key: 'partnerships', label: 'Партнёрства', group: 'more', status: 'available' }],
    } });
    if (path === '/api/partnership/results') return route.fulfill({ json: { items: [{
      id: 'w1', name: 'Кофейня рядом с салоном', client_business_id: 'b1', business_name: 'Органика',
      agreement_json: { revision: 3, status: 'confirmed', terms_version: 1, instruction_terms_version: 1,
        terms: { details: 'После посещения салона клиент получает купон на кофе', our_actions: 'Выдать купон', client_benefit: 'Кофе в подарок' },
        instruction: 'После оплаты выдайте клиенту купон. Объясните, где находится кофейня.',
      },
    }], counts: { partners: 1, launched: 0, preparing: 1, needs_decision: 0 } } });
    return route.fulfill({ json: { items: [], access: { allowed: true }, summary: { attention_items: [] } } });
  });
  await page.goto('/telegram/control?screen=partnerships');
  await expect(page.getByText('1 подтверждённых партнёров')).toBeVisible();
  await page.getByText('Кофейня рядом с салоном', { exact: true }).click();
  await expect(page.getByText('Инструкция сотрудникам', { exact: true })).toBeVisible();
  await page.getByText('Инструкция сотрудникам', { exact: true }).scrollIntoViewIfNeeded();
  await expect(page.getByRole('button', { name: 'Скопировать инструкцию' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('partner-instruction.png'), fullPage: true });
  await page.getByRole('button', { name: 'Назад к партнёрам' }).click();
  await expect(page.getByText('1 подтверждённых партнёров')).toBeVisible();
});
