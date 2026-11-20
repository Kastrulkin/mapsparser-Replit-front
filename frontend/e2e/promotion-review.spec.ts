import { expect, test } from '@playwright/test';

const routes = ['/', '/prodvizhenie-na-yandex-kartah', '/lokalnye-blogery', '/lokalnye-partnery'];

for (const route of routes) {
  test(`promotion page ${route} has one H1, coherent source and usable form`, async ({ page, request }) => {
    const response = await request.get(route);
    expect(response.ok()).toBeTruthy();
    const source = await response.text();
    expect(source).toContain('<h1');
    expect(source).toContain(`href="https://localos.pro${route}"`);
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`${route}?lang=ru`);
    await expect(page.locator('h1')).toHaveCount(1);
    await expect(page.locator('h1')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.getByRole('button', { name: 'Хочу клиентов', exact: true }).first().click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByLabel('Имя', { exact: true })).toBeFocused();
    await page.getByLabel('Имя', { exact: true }).fill('Тестовый просмотр');
    await page.getByLabel('Номер телефона').fill('+79991234567');
    await page.getByRole('checkbox').check();
    // Review server explicitly blocks all external sends; this is a real error path.
    await page.getByRole('button', { name: 'Отправить заявку' }).click();
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByLabel('Имя', { exact: true })).toHaveValue('Тестовый просмотр');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
    expect(errors).toEqual([]);
  });
}

test('direction selection preserves attribution and only sends one pending request', async ({ page }) => {
  await page.goto('/?lang=ru&utm_source=review&utm_campaign=neighbourhood');
  await page.locator('main article').first().getByRole('link', { name: 'Подробнее' }).click();
  await expect(page).toHaveURL(/prodvizhenie-na-yandex-kartah/);
  await page.getByRole('button', { name: 'Хочу клиентов', exact: true }).first().click();
  await page.getByLabel('Имя', { exact: true }).fill('Тест');
  await page.getByLabel('Номер телефона').fill('+79991234567');
  await page.getByRole('checkbox').check();
  let count = 0;
  let body: Record<string, unknown> = {};
  await page.route('**/api/public/contact', async (route) => {
    count += 1;
    body = route.request().postDataJSON();
    await new Promise((resolve) => setTimeout(resolve, 150));
    await route.fulfill({ status: 200, json: { success: true } });
  });
  const button = page.getByRole('button', { name: 'Отправить заявку' });
  await button.click();
  await expect(page.getByText('Спасибо! Заявка принята')).toBeVisible();
  expect(count).toBe(1);
  expect(body).toMatchObject({ direction: 'maps', page: '/prodvizhenie-na-yandex-kartah', attribution: { utm_source: 'review', utm_campaign: 'neighbourhood' } });
});

test('navigation, FAQ and alternate language remain available', async ({ page, isMobile }) => {
  await page.goto('/lokalnye-partnery?lang=ru');
  if (isMobile || (page.viewportSize()?.width || 0) < 640) {
    await page.getByRole('button', { name: 'Открыть меню' }).click();
    await page.locator('#public-mobile-menu summary').filter({ hasText: 'Направления' }).click();
    await page.locator('#public-mobile-menu').getByRole('link', { name: 'Локальные блогеры', exact: true }).click();
  } else {
    await page.getByRole('button', { name: 'Направления' }).focus();
    await page.keyboard.press('Enter');
    await page.getByRole('menuitem', { name: 'Локальные блогеры' }).click();
  }
  await expect(page).toHaveURL(/lokalnye-blogery/);
  await page.getByRole('link', { name: 'Вопросы и ответы', exact: true }).click();
  await expect(page).toHaveURL(/faq.*direction=bloggers/);
  await page.getByText('Как понять, что аудитория местная?', { exact: true }).click();
  await expect(page.getByText(/Оцениваем географию контента/)).toBeVisible();
  await page.goto('/lokalnye-blogery?lang=en');
  await expect(page.locator('h1')).toContainText('Reach people');
});

test('keeps navigation visible in a narrow desktop window and resets the mobile menu on resize', async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 900 });
  await page.goto('/lokalnye-blogery?lang=ru');
  const navigation = page.getByRole('navigation', { name: 'Основная навигация' });
  await expect(navigation).toBeVisible();
  await expect(navigation.getByRole('link', { name: 'Как работаем' })).toBeVisible();
  await expect(navigation.getByRole('link', { name: 'Тарифы', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Открыть меню' })).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.setViewportSize({ width: 360, height: 800 });
  await page.getByRole('button', { name: 'Открыть меню' }).click();
  await expect(page.locator('#public-mobile-menu')).toBeVisible();
  await page.setViewportSize({ width: 900, height: 900 });
  await expect(navigation).toBeVisible();
  await page.setViewportSize({ width: 360, height: 800 });
  await expect(page.locator('#public-mobile-menu')).toBeHidden();
});


test('home is a short direction chooser and the landing has a different hero', async ({ page }) => {
  await page.goto('/?lang=ru');
  await expect(page.getByRole('link', { name: 'Выбрать направление', exact: true })).toBeVisible();
  await expect(page.locator('.promotion-visual')).toHaveCount(1);
  await expect(page.locator('.promotion-case')).toHaveCount(1);
  await expect(page.locator('main details')).toHaveCount(0);
  await expect(page.locator('#cost')).toHaveCount(0);
  await page.getByRole('link', { name: 'Выбрать направление', exact: true }).click();
  await expect(page).toHaveURL(/#directions$/);
  await page.locator('#directions article').first().getByRole('link', { name: 'Подробнее' }).click();
  await expect(page).toHaveURL(/prodvizhenie-na-yandex-kartah/);
  await expect(page.getByRole('navigation', { name: 'Хлебные крошки' })).toContainText('Карты');
  await expect(page.locator('.promotion-visual')).toHaveCount(0);
  await expect(page.locator('.promotion-listing-preview')).toBeVisible();
  await expect(page.locator('main details')).toHaveCount(0);
});

test('pricing and FAQ preserve the selected direction and source through the request', async ({ page }) => {
  await page.goto('/lokalnye-partnery?lang=ru&utm_source=review');
  await page.getByRole('link', { name: 'Посмотреть тарифы', exact: true }).click();
  await expect(page).toHaveURL(/pricing.*direction=partners/);
  await expect(page.getByRole('button', { name: 'Обсудить направление' })).toBeVisible();
  await page.getByRole('link', { name: 'Вернуться: Локальные партнёры' }).click();
  await page.getByRole('link', { name: 'Вопросы и ответы', exact: true }).click();
  await expect(page).toHaveURL(/faq.*direction=partners.*#partners/);
  await expect(page.getByText('Вы выбрали:')).toBeVisible();
  await page.getByRole('button', { name: 'Задать вопрос', exact: true }).click();
  await page.getByLabel('Имя', { exact: true }).fill('Тест');
  await page.getByLabel('Номер телефона').fill('+79991234567');
  await page.getByRole('checkbox').check();
  let body: Record<string, unknown> = {};
  await page.route('**/api/public/contact', async (route) => {
    body = route.request().postDataJSON();
    await route.fulfill({ status: 200, json: { success: true } });
  });
  await page.getByRole('button', { name: 'Отправить заявку' }).click();
  await expect(page.getByText('Спасибо! Заявка принята')).toBeVisible();
  expect(body).toMatchObject({ direction: 'partners', page: '/lokalnye-partnery', attribution: { utm_source: 'review' } });
});

test('FAQ opens directly and rejects an unknown selected direction', async ({ page, request }) => {
  const response = await request.get('/faq');
  expect(response.ok()).toBeTruthy();
  expect(await response.text()).toContain('Вопросы и ответы');
  await page.goto('/faq?lang=ru&direction=unknown');
  await expect(page.locator('h1')).toHaveText('Вопросы и ответы');
  await page.getByRole('button', { name: 'Задать вопрос', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Помогите выбрать');
});

test('direction artwork is clickable and keyboard links preserve attribution', async ({ page }) => {
  await page.goto('/?lang=ru&utm_source=polish');
  await page.locator('#directions article').first().click({ position: { x: 24, y: 24 } });
  await expect(page).toHaveURL(/prodvizhenie-na-yandex-kartah.*utm_source=polish/);
  await page.goto('/?lang=ru&utm_source=polish');
  const creators = page.locator('#directions article').nth(1).getByRole('link');
  await creators.focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/lokalnye-blogery.*utm_source=polish/);
});

test('pricing explains team services and keeps credits in an accessible disclosure', async ({ page }) => {
  await page.goto('/pricing?lang=ru');
  await expect(page.getByText(/Здесь указана стоимость подписки LocalOS/)).toBeVisible();
  const disclosure = page.locator('.public-plan-credits').first();
  await expect(disclosure.locator('p')).toBeHidden();
  await disclosure.locator('summary').focus();
  await page.keyboard.press('Enter');
  await expect(disclosure.locator('p')).toBeVisible();
  await expect(page.locator('.public-plan-price').first()).toContainText('1 200');
  await page.getByRole('button', { name: 'Начать', exact: true }).click();
  await expect(page).toHaveURL(/login.*tier=starter/);
});
