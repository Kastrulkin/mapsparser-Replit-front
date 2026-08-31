import { expect, test } from '@playwright/test';

import { fixtureCommand } from './fixtureCommand';


const scenarios = [
  {
    flow: 'maps',
    token: 'localos-e2e-maps-e796eeb9a98652e78fd902c9f9c64ec7',
    route: /\/dashboard\/card\?journey_action=[0-9a-f-]+$/,
  },
  {
    flow: 'influencer',
    token: 'localos-e2e-influencer-a258132038fb5ac184707d1fcf4acadb',
    route: /\/dashboard\/influencers\?journey_action=[0-9a-f-]+$/,
  },
  {
    flow: 'partnership',
    token: 'localos-e2e-partnership-d1e0a7fbb26452e6b0b8d65c6bdb1be5',
    route: /\/dashboard\/promotion\/partnerships\?journey_action=[0-9a-f-]+$/,
  },
  {
    flow: 'content',
    token: 'localos-e2e-content-01257a9329e4565b8a59f87cfd6b4b14',
    route: /\/dashboard\/content\?journey_action=[0-9a-f-]+$/,
  },
  {
    flow: 'automation',
    token: 'localos-e2e-automation-495c6e64fcd4524aa411da4e93f2d52e',
    route: /\/dashboard\/agents\?journey_action=[0-9a-f-]+$/,
  },
];

for (const scenario of scenarios) {
  test(`${scenario.flow}: registration and email verification resume the selected action`, async ({ page }) => {
    fixtureCommand('reset-journey', scenario.flow);
    const email = `continuity-${scenario.flow}-${Date.now()}@localos-e2e.invalid`;

    await page.goto(`/start/${scenario.token}`);
    const journeySection = page.locator('section').filter({ hasText: 'Что произойдёт после нажатия' }).first();
    await journeySection.getByRole('button').first().click();
    await page.getByRole('link', { name: /Завершить действие/ }).click();

    await expect(page).toHaveURL(new RegExp(`/login\\?.*journey_token=${scenario.token}`));
    await page.locator('#register-name').fill('E2E Новый владелец');
    await page.locator('#register-email').fill(email);
    await page.locator('#register-password').fill('LocalOS-E2E-2026!');
    await page.locator('#register-business-name').fill(`[E2E] Новый бизнес ${scenario.flow}`);
    await page.locator('#register-business-address').fill('Тестовая улица, 10');
    await page.locator('#register-business-city').fill('Санкт-Петербург');
    await page.locator('input[type="checkbox"]').check();
    await page.getByRole('button', { name: /Зарегистрироваться|Sign up/ }).click();

    await expect(page.getByText(/Регистрация почти завершена|Registration is almost complete|pending moderation/).first()).toBeVisible();
    const verificationToken = fixtureCommand('verification-token', email);
    await page.goto(`/verify-email?token=${encodeURIComponent(verificationToken)}`);

    await expect(page).toHaveURL(scenario.route, { timeout: 10_000 });
    expect(await page.evaluate(() => localStorage.getItem('auth_token'))).toBeNull();
    const cookies = await page.context().cookies();
    expect(cookies.some((cookie) => cookie.name === 'localos_session' && cookie.httpOnly)).toBe(true);
  });
}
