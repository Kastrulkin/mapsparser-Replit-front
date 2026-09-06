import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { fixtureCommand } from './fixtureCommand';

test('Today saves the selected direction through the real API and preserves tenant boundaries', async ({ page }, testInfo) => {
  const businessId = fixtureCommand('owner-business-id');
  const networkFixture = JSON.parse(fixtureCommand('network-fixture'));
  await page.addInitScript((id) => {
    localStorage.setItem('language', 'ru');
    localStorage.setItem('selectedBusinessId', id);
  }, businessId);
  const login = await page.request.post('/api/auth/login', {
    data: { email: 'owner@localos-e2e.invalid', password: 'LocalOS-E2E-2026!' },
  });
  expect(login.status()).toBe(200);
  const session = await login.json();
  const bearerToken = typeof session.token === 'string' ? session.token : '';
  if (bearerToken) {
    await page.addInitScript((token) => localStorage.setItem('auth_token', token), bearerToken);
  }
  if (process.env.LOCALOS_EXPECT_AUTH_MODE) {
    expect(bearerToken ? 'bearer' : 'cookie').toBe(process.env.LOCALOS_EXPECT_AUTH_MODE);
  }
  const apiHeaders: Record<string, string> = bearerToken ? { Authorization: `Bearer ${bearerToken}` } : {};
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/dashboard/today');
  const preferences = page.locator('details').filter({ hasText: 'Что показывать первым на «Сегодня»' }).first();
  await expect(preferences).toBeVisible();
  await preferences.locator('summary').click();
  const completed = page.waitForResponse((response) => response.url().includes('/operator/today/preference') && response.request().method() === 'POST');
  await preferences.getByRole('button', { name: 'Инфлюенсеры', exact: true }).click();
  expect((await completed).status()).toBe(200);
  await expect(preferences.locator('summary')).toContainText('Инфлюенсеры');
  await page.reload();
  await expect(preferences.locator('summary')).toContainText('Инфлюенсеры');
  const timings: number[] = [];
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const started = Date.now();
    const overview = await page.request.get(`/api/operator/today?scope_type=business&scope_id=${businessId}`, { headers: apiHeaders });
    timings.push(Date.now() - started);
    expect(overview.status()).toBe(200);
    const payload = await overview.json();
    expect(payload.preference.primary_flow).toBe('influencers');
    expect(payload.priority_proposal).toBeNull();
  }
  const foreign = await page.request.get(`/api/operator/today?scope_type=business&scope_id=${networkFixture.foreign_business_id}`, { headers: apiHeaders });
  expect(foreign.status()).toBe(403);
  const network = await page.request.get(`/api/operator/today/preference?scope_type=network&scope_id=${networkFixture.network_id}`, { headers: apiHeaders });
  expect(network.status()).toBe(200);
  expect((await network.json()).preference.primary_flow).toBe('overview');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const scan = await new AxeBuilder({ page }).analyze();
  const serious = scan.violations.filter((violation) => violation.impact === 'serious' || violation.impact === 'critical');
  await testInfo.attach('real-api-timing-and-accessibility', {
    body: JSON.stringify({ authentication_mode: bearerToken ? 'bearer' : 'cookie', timings_ms: timings, serious, errors }, null, 2), contentType: 'application/json',
  });
  await page.screenshot({ path: testInfo.outputPath('today-real-api.png'), fullPage: true });
  expect(errors).toEqual([]);
  expect(serious).toEqual([]);
});
