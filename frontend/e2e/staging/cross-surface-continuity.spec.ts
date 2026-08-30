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

const loginOwner = async (page: import('@playwright/test').Page, businessId: string) => {
  await page.addInitScript((selectedBusinessId) => {
    window.localStorage.setItem('language', 'ru');
    window.localStorage.setItem('selectedBusinessId', selectedBusinessId);
  }, businessId);
  await page.goto('/login');
  await page.locator('#login-email').fill(OWNER_EMAIL);
  await page.locator('#login-password').fill(OWNER_PASSWORD);
  const authenticatedProfile = page.waitForResponse((response) => (
    response.url().endsWith('/api/auth/me') && response.status() === 200
  ));
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await authenticatedProfile;
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem('auth_token'))).toBeTruthy();
};

test('one journey action continues from web to Mini App and back without diverging', async ({ page }) => {
  fixtureCommand('reset-journey', 'automation');
  const businessId = fixtureCommand('owner-business-id');
  await loginOwner(page, businessId);
  const authToken = await page.evaluate(() => window.localStorage.getItem('auth_token'));
  const headers = { Authorization: `Bearer ${authToken}` };
  const claimResponse = await page.request.post('/api/journeys/claim', {
    headers,
    data: { token: AUTOMATION_TOKEN, business_id: businessId, surface: 'web' },
  });
  expect(claimResponse.status()).toBe(200);
  const claimed = await claimResponse.json();
  expect(claimed.action.action_type).toBe('configure_automation');

  await page.goto(`/dashboard/agents?journey_action=${claimed.action.id}`);
  const webAction = page.locator('section[aria-label="Выбранное действие"]');
  await expect(webAction.getByText('Настроить первую задачу')).toBeVisible();
  const webCommand = page.waitForResponse((response) => (
    response.url().includes(`/api/journey-actions/${claimed.action.id}/commands`)
    && response.request().method() === 'POST'
  ));
  await webAction.getByRole('button', { name: 'Сохранить настройку' }).click();
  const webCommandResponse = await webCommand;
  expect(webCommandResponse.status()).toBe(200);
  const webResult = await webCommandResponse.json();
  expect(webResult.next_action.action_type).toBe('review_automation_preflight');

  const initData = fixtureCommand('telegram-init-data');
  const ownerId = fixtureCommand('owner-user-id');
  await page.route('https://telegram.org/js/telegram-web-app.js?63', (route) => route.abort());
  await page.addInitScript(({ signedInitData, userId }) => {
    window.localStorage.setItem(`localos-mini-onboarding-v3:${userId}`, 'completed');
    Object.defineProperty(window, 'Telegram', {
      configurable: true,
      value: {
        WebApp: {
          initData: signedInitData,
          initDataUnsafe: {},
          ready: () => undefined,
          expand: () => undefined,
        },
      },
    });
  }, { signedInitData: initData, userId: ownerId });
  await page.goto(`/telegram/control?screen=today&item_type=journey_action&item_id=${webResult.next_action.id}&scope_type=business&scope_id=${businessId}`);
  await expect(page.getByText('Проверить план запуска').first()).toBeVisible();
  const miniCommand = page.waitForResponse((response) => (
    response.url().includes(`/api/journey-actions/${webResult.next_action.id}/commands`)
    && response.request().method() === 'POST'
  ));
  await page.getByRole('button', { name: 'Подтвердить план' }).first().click();
  const miniCommandResponse = await miniCommand;
  expect(miniCommandResponse.status()).toBe(200);
  const miniResult = await miniCommandResponse.json();
  expect(miniResult.next_action.action_type).toBe('run_automation');

  await page.goto(`/dashboard/agents?journey_action=${miniResult.next_action.id}`);
  await expect(page.getByText('Запустить проверенную задачу').first()).toBeVisible();
  const actionsResponse = await page.request.get(`/api/journey-actions?business_id=${businessId}`, { headers });
  expect(actionsResponse.status()).toBe(200);
  const actionsPayload = await actionsResponse.json();
  const activeAutomation = actionsPayload.actions.filter((action: { flow_type: string }) => action.flow_type === 'automation');
  expect(activeAutomation).toHaveLength(1);
  expect(activeAutomation[0].action_type).toBe('run_automation');
});

test('same idempotency key replays once and an old version is rejected', async ({ page }) => {
  fixtureCommand('reset-journey', 'automation');
  const businessId = fixtureCommand('owner-business-id');
  await loginOwner(page, businessId);
  const authToken = await page.evaluate(() => window.localStorage.getItem('auth_token'));
  const headers = { Authorization: `Bearer ${authToken}` };
  const claimResponse = await page.request.post('/api/journeys/claim', {
    headers,
    data: { token: AUTOMATION_TOKEN, business_id: businessId, surface: 'web' },
  });
  const claimed = await claimResponse.json();
  const commandHeaders = { ...headers, 'Idempotency-Key': 'localos-e2e-same-command' };
  const commandData = {
    business_id: businessId,
    command: 'save_configuration',
    version: claimed.action.version,
    surface: 'web',
    payload: { use_case: 'weekly_summary', expected_result: 'Недельная сводка для проверки' },
  };
  const first = await page.request.post(`/api/journey-actions/${claimed.action.id}/commands`, {
    headers: commandHeaders,
    data: commandData,
  });
  expect(first.status()).toBe(200);
  expect((await first.json()).idempotent_replay).toBe(false);

  const replay = await page.request.post(`/api/journey-actions/${claimed.action.id}/commands`, {
    headers: commandHeaders,
    data: commandData,
  });
  expect(replay.status()).toBe(200);
  expect((await replay.json()).idempotent_replay).toBe(true);

  const stale = await page.request.post(`/api/journey-actions/${claimed.action.id}/commands`, {
    headers: { ...headers, 'Idempotency-Key': 'localos-e2e-stale-command' },
    data: commandData,
  });
  expect(stale.status()).toBe(409);
  expect((await stale.json()).code).toBe('stale_action');
});
