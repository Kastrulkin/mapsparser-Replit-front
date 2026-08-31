import { expect, test } from '@playwright/test';

import { fixtureCommand } from './fixtureCommand';


const OWNER_EMAIL = 'owner@localos-e2e.invalid';
const OWNER_PASSWORD = 'LocalOS-E2E-2026!';
const PRIMARY_BUSINESS_NAME = '[E2E] Салон Север';
const SECOND_BUSINESS_NAME = '[E2E] Салон Центр';

const loadFixture = () => JSON.parse(fixtureCommand('network-fixture'));

const loginOwner = async (page: import('@playwright/test').Page, primaryBusinessId: string) => {
  await page.addInitScript((businessId) => {
    window.localStorage.setItem('language', 'ru');
    window.localStorage.setItem('selectedBusinessId', businessId);
    window.localStorage.removeItem('dashboard_control_scope');
  }, primaryBusinessId);
  await page.goto('/login');
  await page.locator('#login-email').fill(OWNER_EMAIL);
  await page.locator('#login-password').fill(OWNER_PASSWORD);
  const authenticatedProfile = page.waitForResponse((response) => (
    response.url().endsWith('/api/auth/me') && response.status() === 200
  ));
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await authenticatedProfile;
  expect(await page.evaluate(() => window.localStorage.getItem('auth_token'))).toBeNull();
  await expect.poll(async () => (
    await page.context().cookies()
  ).some((cookie) => cookie.name === 'localos_session' && cookie.httpOnly)).toBe(true);
};

test('network owner switches aggregate and location scopes without foreign tenant data', async ({ page }) => {
  const fixture = loadFixture();
  const primaryIndex = fixture.business_names.indexOf(PRIMARY_BUSINESS_NAME);
  const primaryBusinessId = fixture.business_ids[primaryIndex];
  const secondIndex = fixture.business_names.indexOf(SECOND_BUSINESS_NAME);
  const secondBusinessId = fixture.business_ids[secondIndex];
  expect(primaryBusinessId).toBeTruthy();
  expect(secondBusinessId).toBeTruthy();

  await loginOwner(page, primaryBusinessId);
  await page.goto('/dashboard/today');

  const networkToday = page.waitForResponse((response) => (
    response.url().includes('/api/operator/today?')
    && response.url().includes('scope_type=network')
    && response.url().includes(`scope_id=${fixture.network_id}`)
  ));
  await page.getByRole('combobox', { name: 'Бизнес' }).click();
  await page.getByRole('option', { name: 'Вся сеть' }).click();
  const networkResponse = await networkToday;
  expect(networkResponse.status()).toBe(200);
  const networkPayload = await networkResponse.json();
  expect(networkPayload.scope.kind).toBe('network');
  expect(networkPayload.scope.business_ids.sort()).toEqual([...fixture.business_ids].sort());
  expect(JSON.stringify(networkPayload)).not.toContain(fixture.foreign_business_name);

  const locationSwitcher = page.locator('[data-tour-target="network-switcher"]');
  await locationSwitcher.getByRole('button').first().click();
  const locationToday = page.waitForResponse((response) => (
    response.url().includes('/api/operator/today?')
    && response.url().includes('scope_type=business')
    && response.url().includes(`scope_id=${secondBusinessId}`)
  ));
  await locationSwitcher.getByRole('button', { name: SECOND_BUSINESS_NAME }).click();
  const locationResponse = await locationToday;
  expect(locationResponse.status()).toBe(200);
  await expect(locationSwitcher.getByRole('button').first()).toContainText(SECOND_BUSINESS_NAME);

  const restoredNetworkToday = page.waitForResponse((response) => (
    response.url().includes('/api/operator/today?')
    && response.url().includes('scope_type=network')
    && response.url().includes(`scope_id=${fixture.network_id}`)
  ));
  await page.getByRole('combobox', { name: 'Бизнес' }).click();
  await page.getByRole('option', { name: 'Вся сеть' }).click();
  expect((await restoredNetworkToday).status()).toBe(200);
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem('dashboard_control_scope'))).toContain(fixture.network_id);

  const foreignBusiness = await page.request.get(
    `/api/operator/today?scope_type=business&scope_id=${fixture.foreign_business_id}`,
  );
  const foreignNetwork = await page.request.get(
    `/api/operator/today?scope_type=network&scope_id=${fixture.foreign_network_id}`,
  );
  expect(foreignBusiness.status()).toBe(403);
  expect(foreignNetwork.status()).toBe(403);

  const locationsResponse = await page.request.get(
    `/api/operator/mobile/network-locations?network_id=${fixture.network_id}`,
  );
  expect(locationsResponse.status()).toBe(200);
  const locationsPayload = await locationsResponse.json();
  expect(locationsPayload.items.map((item: { id: string }) => item.id).sort()).toEqual([...fixture.business_ids].sort());
  expect(JSON.stringify(locationsPayload)).not.toContain(fixture.foreign_business_name);
});
