import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';


const MAPS_TOKEN = 'localos-e2e-maps-e796eeb9a98652e78fd902c9f9c64ec7';

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


test('guest registration and email verification resume the selected maps action', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Single-claim continuity is exercised once per run.');
  fixtureCommand('reset-journey', 'maps');
  const email = `continuity-${Date.now()}@localos-e2e.invalid`;

  await page.goto(`/start/${MAPS_TOKEN}`);
  const journeySection = page.locator('section').filter({ hasText: 'Что произойдёт после нажатия' }).first();
  await journeySection.getByRole('button').first().click();
  await page.getByRole('link', { name: /Завершить действие/ }).click();

  await expect(page).toHaveURL(new RegExp(`/login\\?.*journey_token=${MAPS_TOKEN}`));
  await page.locator('#register-name').fill('E2E Новый владелец');
  await page.locator('#register-email').fill(email);
  await page.locator('#register-password').fill('LocalOS-E2E-2026!');
  await page.locator('#register-business-name').fill('[E2E] Новый салон');
  await page.locator('#register-business-address').fill('Тестовая улица, 10');
  await page.locator('#register-business-city').fill('Санкт-Петербург');
  await page.locator('input[type="checkbox"]').check();
  await page.getByRole('button', { name: /Зарегистрироваться|Sign up/ }).click();

  await expect(page.getByText(/Регистрация почти завершена|Registration is almost complete|pending moderation/).first()).toBeVisible();
  const verificationToken = fixtureCommand('verification-token', email);
  await page.goto(`/verify-email?token=${encodeURIComponent(verificationToken)}`);

  await expect(page.getByText('Email подтверждён. Возвращаемся к выбранному действию...')).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard\/card\?journey_action=[0-9a-f-]+$/, { timeout: 10_000 });
  expect(await page.evaluate(() => localStorage.getItem('auth_token'))).toBeTruthy();
});
