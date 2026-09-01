import { expect, test } from '@playwright/test';


const TELEGRAM_SDK_URL = 'https://telegram.org/js/telegram-web-app.js?63';


test('ordinary web login renders while the Telegram SDK is unavailable', async ({ page }) => {
  test.setTimeout(15_000);
  await page.route(TELEGRAM_SDK_URL, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 7_000));
    await route.abort();
  });

  const navigation = page.goto('/login', { waitUntil: 'domcontentloaded' });

  await expect(page.locator('#login-email')).toBeVisible({ timeout: 3_000 });
  await navigation;
});


test('private login does not request Yandex Metrika without tracking consent', async ({ page }) => {
  const metrikaRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().startsWith('https://mc.yandex.ru/')) metrikaRequests.push(request.url());
  });
  await page.route(TELEGRAM_SDK_URL, (route) => route.abort());
  await page.route('https://mc.yandex.ru/**', (route) => route.abort());

  await page.goto('/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(250);

  expect(await page.evaluate(() => window.localosTrackingConsent)).toBe(false);
  expect(metrikaRequests).toEqual([]);
});
