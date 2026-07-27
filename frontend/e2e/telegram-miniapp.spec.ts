import { expect, test } from '@playwright/test';

test('daily mobile flow stays native and readable', async ({ page }) => {
  await page.goto('/telegram/control?preview=1');

  await expect(page.getByText('Сейчас важнее всего')).toBeVisible();
  await expect(page.getByRole('navigation')).toBeVisible();
  await expect(page.locator('a[href*="/dashboard"]')).toHaveCount(0);
  await expect(page.locator('main')).not.toHaveCSS('overflow-x', 'scroll');
});

test('content calendar opens inside Mini App', async ({ page }) => {
  await page.goto('/telegram/control?preview=1');
  await page.getByRole('button', { name: 'Ещё', exact: true }).click();
  await page.getByRole('button', { name: /Контент/ }).click();

  await expect(page.getByText('Контент-календарь')).toBeVisible();
  await expect(page.getByRole('button', { name: /Посты/ })).toBeVisible();
  await expect(page.locator('a[href*="/dashboard"]')).toHaveCount(0);
});

test('reviews expose concrete items and a single bulk confirmation', async ({ page }) => {
  await page.goto('/telegram/control?preview=1');
  await page.getByRole('button', { name: 'Отзывы', exact: true }).click();

  await expect(page.getByText('Отзыв от', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Выбрать отзыв' }).first().click();
  await page.getByRole('button', { name: 'Подготовить', exact: true }).click();

  await expect(page.getByRole('dialog', { name: 'Проверьте действие' })).toBeVisible();
  await expect(page.getByText('Объектов:')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Подготовить ответы' })).toHaveCount(1);
});

test('finance contains analytics and is not duplicated in navigation', async ({ page }) => {
  await page.goto('/telegram/control?preview=1');
  await page.getByRole('button', { name: 'Ещё', exact: true }).click();

  await expect(page.getByRole('button', { name: /Финансы/ })).toHaveCount(1);
  await expect(page.getByRole('button', { name: /^Аналитика/ })).toHaveCount(0);
  await page.getByRole('button', { name: /Финансы/ }).click();
  await expect(page.getByRole('tab', { name: 'Обзор', exact: true })).toBeVisible();
  await expect(page.getByText('Динамика выручки')).toBeVisible();
});
