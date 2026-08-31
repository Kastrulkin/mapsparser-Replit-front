import { expect, test } from '@playwright/test';

const scenarios = [
  {
    flow: 'maps',
    token: 'localos-e2e-maps-e796eeb9a98652e78fd902c9f9c64ec7',
    title: 'Исправить часы работы',
  },
  {
    flow: 'influencer',
    token: 'localos-e2e-influencer-a258132038fb5ac184707d1fcf4acadb',
    title: 'Анна про район',
  },
  {
    flow: 'partnership',
    token: 'localos-e2e-partnership-d1e0a7fbb26452e6b0b8d65c6bdb1be5',
    title: 'Студия йоги рядом',
  },
  {
    flow: 'content',
    token: 'localos-e2e-content-01257a9329e4565b8a59f87cfd6b4b14',
    title: 'Как выбрать услугу впервые',
  },
  {
    flow: 'automation',
    token: 'localos-e2e-automation-495c6e64fcd4524aa411da4e93f2d52e',
    title: 'Разобрать новые отзывы',
  },
];

for (const scenario of scenarios) {
  test(`${scenario.flow}: public preview keeps one clear next action`, async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });

    await page.goto(`/start/${scenario.token}`);

    await expect(page.getByRole('heading', { name: scenario.title })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Как это работает' })).toBeVisible();
    const prepareButton = page.getByRole('button', { name: /Показать|Подготовить/ }).first();
    await expect(prepareButton).toBeVisible();
    await prepareButton.click();

    await expect(page.getByText('Открыть выбранное направление')).toBeVisible();
    const registrationLink = page.getByRole('link', { name: 'Продолжить в LocalOS' });
    await expect(registrationLink).toHaveAttribute('href', new RegExp(`journey_token=${scenario.token}`));
    expect(consoleErrors).toEqual([]);
  });
}
