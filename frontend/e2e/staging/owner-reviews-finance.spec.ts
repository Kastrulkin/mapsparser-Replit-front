import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';


const OWNER_EMAIL = 'owner@localos-e2e.invalid';
const OWNER_PASSWORD = 'LocalOS-E2E-2026!';
const FINANCE_FILE_NAME = 'localos-e2e-finance.csv';
const FINANCE_CSV = [
  'record_type,date,type,category,amount,comment,external_id',
  'entry,2026-08-29,revenue,sales,5000,E2E,e2e-income',
  'entry,2026-08-29,expense,materials,1000,E2E,e2e-expense',
  '',
].join('\n');

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

const loginOwner = async (page: import('@playwright/test').Page) => {
  const businessId = fixtureCommand('owner-business-id');
  await page.goto('/login');
  await page.locator('#login-email').fill(OWNER_EMAIL);
  await page.locator('#login-password').fill(OWNER_PASSWORD);
  const authenticatedProfile = page.waitForResponse((response) => (
    response.url().endsWith('/api/auth/me') && response.status() === 200
  ));
  await page.getByRole('button', { name: /^(Войти|Sign in)$/ }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await authenticatedProfile;
  expect(await page.evaluate(() => window.localStorage.getItem('auth_token'))).toBeNull();
  await expect.poll(async () => (
    await page.context().cookies()
  ).some((cookie) => cookie.name === 'localos_session' && cookie.httpOnly)).toBe(true);
  await page.evaluate((selectedBusinessId) => {
    window.localStorage.setItem('selectedBusinessId', selectedBusinessId);
  }, businessId);
  return businessId;
};

const observeRuntimeErrors = (page: import('@playwright/test').Page) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    const sourceUrl = message.location().url;
    if (message.type() === 'error' && (!sourceUrl || sourceUrl.startsWith('http://127.0.0.1:18000'))) {
      errors.push(message.text());
    }
  });
  return errors;
};

test('owner reviews: unanswered review opens with a prepared manual draft', async ({ page }) => {
  const runtimeErrors = observeRuntimeErrors(page);
  await loginOwner(page);

  await page.goto('/dashboard/card?tab=reviews&review_filter=needs_reply');
  await expect(page.getByText('Мария Тестова').first()).toBeVisible();
  await expect(page.getByText('Черновик LocalOS: draft')).toBeVisible();
  const preparedReply = 'Мария, спасибо за отзыв! Напишите нам в удобном канале, и мы подберём время для повторной записи.';
  await expect.poll(() => page.locator('textarea').evaluateAll(
    (elements, expectedReply) => elements.some((element) => (
      element instanceof HTMLTextAreaElement && element.value === expectedReply
    )),
    preparedReply,
  )).toBe(true);
  await expect(page.getByText(/Публикация в карты вручную/)).toBeVisible();
  await expect(page.getByRole('button', { name: /Скопировать/ })).toBeVisible();
  expect(runtimeErrors).toEqual([]);
});

test('owner finance: preview, explicit import, and duplicate retry stay consistent', async ({ page }) => {
  fixtureCommand('reset-finance');
  const runtimeErrors = observeRuntimeErrors(page);
  await loginOwner(page);

  await page.goto('/dashboard/finance?tab=import');
  const fileInput = page.getByLabel('Файл из CRM');
  await fileInput.setInputFiles({
    name: FINANCE_FILE_NAME,
    mimeType: 'text/csv',
    buffer: Buffer.from(FINANCE_CSV),
  });
  await page.getByRole('button', { name: 'Проверить файл' }).click();
  await expect(page.getByText(/Готово к импорту: 2\. Ошибок: 0/)).toBeVisible();
  await expect(page.getByText('2. Preview проверен')).toBeVisible();
  await page.getByRole('button', { name: 'Импортировать проверенные строки' }).click();
  await expect(page.getByText('Импортировано: 2. Пропущено дублей: 0. Ошибок: 0.')).toBeVisible();

  await fileInput.setInputFiles({
    name: FINANCE_FILE_NAME,
    mimeType: 'text/csv',
    buffer: Buffer.from(FINANCE_CSV),
  });
  await page.getByRole('button', { name: 'Проверить файл' }).click();
  await expect(page.getByText(/Готово к импорту: 2\. Ошибок: 0/)).toBeVisible();
  await page.getByRole('button', { name: 'Импортировать проверенные строки' }).click();
  await expect(page.getByText('Импортировано: 0. Пропущено дублей: 2. Ошибок: 0.')).toBeVisible();
  expect(runtimeErrors).toEqual([]);
});
