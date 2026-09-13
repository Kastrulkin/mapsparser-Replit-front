import { expect, test } from '@playwright/test';

test('owner inspects failed voice input, reports feedback, then loses access', async ({ page }, testInfo) => {
  let feedback = 0;
  let revoked = false;
  const item = { id: 'request-one', input_summary: 'Покажи следующий пост', output_summary: '', status: 'failed', reason_code: 'execution',
    metadata_json: { input_type: 'voice', operator_channel: 'telegram' }, created_at: '2026-09-13T10:00:00Z' };
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 'voice-test'); localStorage.setItem('selectedBusinessId', 'voice-business'); localStorage.setItem('language', 'ru');
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 'voice-user', email: 'voice@example.test', businesses: [{ id: 'voice-business', name: 'Тестовый бизнес', subscription_tier: 'concierge', subscription_status: 'active' }] } });
    if (path === '/api/business/voice-business') return route.fulfill({ json: { id: 'voice-business', name: 'Тестовый бизнес', subscription_tier: 'concierge', subscription_status: 'active' } });
    if (path.endsWith('/requests/request-one/feedback')) {
      expect(route.request().postDataJSON()).toMatchObject({ business_id: 'voice-business', comment: 'Нужен ближайший пост' });
      feedback++;
      return route.fulfill({ json: { status: 'recorded' } });
    }
    if (path.startsWith('/api/operator/requests')) {
      if (revoked) return route.fulfill({ status: 403, json: { error: 'Нет доступа' } });
      return route.fulfill({ json: path.endsWith('/request-one') ? { ...item, audio: { transcript: item.input_summary } }
        : { items: [item], next_offset: null, people: [{ id: 'voice-user', name: 'Владелец' }] } });
    }
    if (path === '/api/operator/chat') throw new Error('Feedback must not execute a command');
    return route.fulfill({ json: { success: true, items: [], messages: [], businesses: [{ id: 'voice-business', name: 'Тестовый бизнес', subscription_tier: 'concierge', subscription_status: 'active' }] } });
  });
  await page.goto('/dashboard/operator');
  await page.getByText('История обращений', { exact: true }).focus();
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: /Покажи следующий пост/ }).click();
  await expect(page.getByRole('region', { name: 'Разбор обращения' })).toBeFocused();
  await page.getByLabel('Оператор понял неправильно').fill('Нужен ближайший пост');
  await page.getByRole('button', { name: 'Сохранить замечание' }).click();
  await expect(page.getByText(/Замечание сохранено/)).toBeVisible();
  expect(feedback).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('request-history.png'), fullPage: true });
  revoked = true;
  await page.getByRole('button', { name: 'Обновить', exact: true }).click();
  await expect(page.getByText('Нет доступа', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Покажи следующий пост/ })).toHaveCount(0);
});
