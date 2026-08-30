import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';


const OWNER_EMAIL = 'owner@localos-e2e.invalid';
const OWNER_PASSWORD = 'LocalOS-E2E-2026!';
const AUTOMATION_TOKEN = 'localos-e2e-automation-495c6e64fcd4524aa411da4e93f2d52e';

const fixtureCommand = (...args: string[]) => execFileSync(
  'docker',
  [
    'compose', '-p', 'localos-staging',
    '-f', 'docker-compose.yml',
    '-f', 'docker-compose.staging.yml',
    'exec', '-T', 'app', 'python', '/app/scripts/staging_fixture_cli.py',
    ...args,
  ],
  { cwd: resolve(process.cwd(), '..'), encoding: 'utf8' },
).trim();

const csrfHeaders = async (page: import('@playwright/test').Page) => {
  const csrfCookie = (await page.context().cookies()).find((cookie) => cookie.name === 'localos_csrf');
  expect(csrfCookie?.value).toBeTruthy();
  return { 'X-CSRF-Token': csrfCookie?.value || '' };
};

test('lost command response retries without stale action or duplicate transition', async ({ page }) => {
  fixtureCommand('reset-journey', 'automation');
  const businessId = fixtureCommand('owner-business-id');
  await page.addInitScript((selectedBusinessId) => {
    window.localStorage.setItem('language', 'ru');
    window.localStorage.setItem('selectedBusinessId', selectedBusinessId);
  }, businessId);
  await page.goto('/login');
  await page.locator('#login-email').fill(OWNER_EMAIL);
  await page.locator('#login-password').fill(OWNER_PASSWORD);
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  const headers = await csrfHeaders(page);
  const claimResponse = await page.request.post('/api/journeys/claim', {
    headers,
    data: { token: AUTOMATION_TOKEN, business_id: businessId, surface: 'web' },
  });
  const claimed = await claimResponse.json();
  await page.goto(`/dashboard/agents?journey_action=${claimed.action.id}`);
  const actionCard = page.locator('section[aria-label="Выбранное действие"]');
  const commandUrl = `/api/journey-actions/${claimed.action.id}/commands`;
  let lostResponse = false;
  await page.route(`**${commandUrl}`, async (route) => {
    if (!lostResponse) {
      lostResponse = true;
      const serverResponse = await route.fetch();
      expect(serverResponse.status()).toBe(200);
      await route.abort('failed');
      return;
    }
    await route.continue();
  });

  await actionCard.getByRole('button', { name: 'Сохранить настройку' }).click();
  await expect(actionCard.getByText(/Ошибка соединения/)).toBeVisible();
  const retryResponsePromise = page.waitForResponse((response) => (
    response.url().includes(commandUrl) && response.request().method() === 'POST'
  ));
  await actionCard.getByRole('button', { name: 'Сохранить настройку' }).click();
  const retryResponse = await retryResponsePromise;

  expect(retryResponse.status()).toBe(200);
  expect((await retryResponse.json()).idempotent_replay).toBe(true);
  await expect(page.getByText('Проверить план запуска').first()).toBeVisible();
});
