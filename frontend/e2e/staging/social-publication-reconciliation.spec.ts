import { expect, test } from '@playwright/test';

import { fixtureCommand } from './fixtureCommand';


const OWNER_EMAIL = 'owner@localos-e2e.invalid';
const OWNER_PASSWORD = 'LocalOS-E2E-2026!';
const RECEIPT_URL = 'https://example.invalid/localos-e2e-publication-receipt';

type ReconciliationFixture = {
  business_id: string;
  plan_id: string;
  item_id: string;
  post_id: string;
  attempt_id: string;
};

const resetFixture = (): ReconciliationFixture => JSON.parse(
  fixtureCommand('reset-social-publication-reconciliation'),
);

const inspectFixture = () => JSON.parse(fixtureCommand('inspect-social-publication-reconciliation'));

const loginOwner = async (page: import('@playwright/test').Page, businessId: string) => {
  await page.addInitScript((selectedBusinessId) => {
    window.localStorage.setItem('language', 'ru');
    window.localStorage.setItem('selectedBusinessId', selectedBusinessId);
  }, businessId);
  const response = await page.request.post('/api/auth/login', {
    data: { email: OWNER_EMAIL, password: OWNER_PASSWORD },
  });
  expect(response.status(), await response.text()).toBe(200);
};

test('publishing hold reconciles one confirmed receipt without another provider send', async ({ page }, testInfo) => {
  expect(testInfo.config.workers).toBe(1);
  const fixture = resetFixture();
  const mutationPaths: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (request.method() === 'POST' && url.pathname.startsWith('/api/social-posts/')) {
      mutationPaths.push(url.pathname);
    }
  });
  await loginOwner(page, fixture.business_id);

  await page.goto(`/dashboard/content?plan_id=${encodeURIComponent(fixture.plan_id)}&item_id=${encodeURIComponent(fixture.item_id)}`);
  await page.getByRole('button', { name: 'Список' }).click();
  await page.getByRole('button', { name: 'E2E сверка публикации' }).click();
  await page.getByRole('button', { name: /Тексты для каналов/ }).click();
  await expect(page.getByText(/не отправляйте пост повторно/i)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Разместить вручную' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Запланировать отправку|Запланировано/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Изменить текст/ })).toHaveCount(0);

  const receipt = page.getByLabel('Ссылка или ID уже опубликованного поста');
  const confirmation = page.getByRole('checkbox', { name: /Проверил на площадке: это тот же пост/ });
  const confirmButton = page.getByRole('button', { name: 'Подтвердить существующую публикацию' });
  await expect(confirmButton).toBeDisabled();
  await receipt.fill(RECEIPT_URL);
  await expect(confirmButton).toBeDisabled();
  await confirmation.check();
  await expect(confirmButton).toBeEnabled();

  const response = page.waitForResponse((candidate) => (
    candidate.url().includes(`/api/social-posts/${fixture.post_id}/mark-manual-published`)
    && candidate.request().method() === 'POST'
  ));
  await confirmButton.evaluate((element) => {
    if (element instanceof HTMLButtonElement) {
      element.click();
      element.click();
    }
  });
  expect((await response).status()).toBe(200);
  await expect(page.getByRole('button', { name: 'Подтвердить существующую публикацию' })).toHaveCount(0);

  expect(mutationPaths).toEqual([`/api/social-posts/${fixture.post_id}/mark-manual-published`]);
  const stored = inspectFixture();
  expect(stored.post_id).toBe(fixture.post_id);
  expect(stored.status).toBe('published');
  expect(stored.provider_post_url).toBe(RECEIPT_URL);
  expect(stored.provider_post_id).toBeNull();
  expect(stored.metadata_json.publish_attempt?.id).toBe(fixture.attempt_id);
  expect(stored.metadata_json.publish_attempt?.state).toBe('manual_confirmed');
});
