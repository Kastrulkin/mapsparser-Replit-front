import { expect, test } from '@playwright/test';

import { fixtureCommand } from './fixtureCommand';


const ADMIN_EMAIL = 'admin@localos-e2e.invalid';
const ADMIN_PASSWORD = 'LocalOS-E2E-2026!';
const LEAD_NAME = '[E2E] Influencer Journey';

const loginAdmin = async (page: import('@playwright/test').Page) => {
  await page.addInitScript(() => window.localStorage.setItem('language', 'ru'));
  await page.goto('/login');
  await page.locator('#login-email').fill(ADMIN_EMAIL);
  await page.locator('#login-password').fill(ADMIN_PASSWORD);
  const authenticatedProfile = page.waitForResponse((response) => (
    response.url().endsWith('/api/auth/me') && response.status() === 200
  ));
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await authenticatedProfile;
};

test.beforeEach(() => {
  fixtureCommand('cleanup-admin-journeys');
});

test.afterEach(() => {
  fixtureCommand('cleanup-admin-journeys');
});

test('superadmin creates, previews and revokes one selected client route', async ({ page }) => {
  const consoleErrors: string[] = [];
  await page.route('https://hdrc.yandex.net/**', (route) => route.fulfill({ status: 204, body: '' }));
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });

  await loginAdmin(page);
  await page.goto('/dashboard/bazich/journeys');
  await expect(page.getByRole('heading', { name: 'Маршрут клиента' })).toBeVisible();

  const clientStep = page.locator('section').filter({ hasText: 'Для кого создаём маршрут' }).first();
  await clientStep.getByRole('combobox').click();
  await page.getByRole('option', { name: `${LEAD_NAME} · Санкт-Петербург`, exact: true }).click();
  await clientStep.getByRole('button', { name: /Выбрать проблему/ }).click();

  await page.getByRole('button', { name: /Найти автора, которому доверяют ваши клиенты/ }).click();
  await page.getByLabel('Название услуги').fill('Укладка');
  await expect(page.getByText(/Автор рассказывает о бизнесе/)).toBeVisible();

  const createResponsePromise = page.waitForResponse((response) => (
    response.url().endsWith('/api/journeys')
    && response.request().method() === 'POST'
  ));
  await page.getByRole('button', { name: /Создать персональную ссылку/ }).click();
  const createResponse = await createResponsePromise;
  expect(createResponse.status()).toBe(201);
  const created = await createResponse.json();
  expect(created.journey.selected_flow).toBe('influencer');
  const selectedTitle = created.journey.opportunities.find((item: { flow_type: string }) => item.flow_type === 'influencer').title;
  await expect(page.getByText('Персональная ссылка создана')).toBeVisible();

  const publicApiPath = `/api/journeys/public/${encodeURIComponent(created.public_token)}`;
  const publicResponse = await page.request.get(publicApiPath);
  expect(publicResponse.status()).toBe(200);
  const publicPayload = await publicResponse.json();
  expect(publicPayload.journey.selected_flow).toBe('influencer');
  expect(JSON.stringify(publicPayload)).not.toMatch(/password|private_email|full_message|contact/i);

  await page.goto(created.public_path);
  await expect(page.getByRole('heading', { name: selectedTitle })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Как это работает' })).toBeVisible();

  await page.goto('/dashboard/bazich/journeys');
  const history = page.locator('section').filter({ hasText: 'Последние маршруты' }).first();
  const latestJourney = history.locator('.divide-y > div').first();
  await expect(latestJourney).toContainText(LEAD_NAME);
  await latestJourney.getByRole('button', { name: 'Отозвать' }).click();
  await expect(latestJourney.getByRole('button', { name: 'Отозвана' })).toBeVisible();

  const revokedResponse = await page.request.get(publicApiPath);
  expect(revokedResponse.status()).toBe(410);
  expect((await revokedResponse.json()).code).toBe('journey_revoked');
  expect(consoleErrors).toEqual([]);
});
