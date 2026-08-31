import { expect, test } from '@playwright/test';


const scenarios = [
  { flow: 'maps', token: 'localos-e2e-maps-e796eeb9a98652e78fd902c9f9c64ec7' },
  { flow: 'influencer', token: 'localos-e2e-influencer-a258132038fb5ac184707d1fcf4acadb' },
  { flow: 'partnership', token: 'localos-e2e-partnership-d1e0a7fbb26452e6b0b8d65c6bdb1be5' },
  { flow: 'content', token: 'localos-e2e-content-01257a9329e4565b8a59f87cfd6b4b14' },
  { flow: 'automation', token: 'localos-e2e-automation-495c6e64fcd4524aa411da4e93f2d52e' },
];

const parseRgb = (value: string) => {
  const channels = value.match(/[\d.]+/g)?.slice(0, 3).map(Number) || [];
  if (channels.length !== 3) throw new Error(`Unsupported computed color: ${value}`);
  return channels;
};

const relativeLuminance = (value: string) => {
  const channels = parseRgb(value).map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return (0.2126 * channels[0]) + (0.7152 * channels[1]) + (0.0722 * channels[2]);
};

const contrastRatio = (foreground: string, background: string) => {
  const lighter = Math.max(relativeLuminance(foreground), relativeLuminance(background));
  const darker = Math.min(relativeLuminance(foreground), relativeLuminance(background));
  return (lighter + 0.05) / (darker + 0.05);
};

const computedColors = async (locator: import('@playwright/test').Locator) => locator.evaluate((element) => {
  const foreground = window.getComputedStyle(element).color;
  let current: Element | null = element;
  let background = 'rgba(0, 0, 0, 0)';
  while (current && /rgba?\(0, 0, 0(?:, 0)?\)/.test(background)) {
    background = window.getComputedStyle(current).backgroundColor;
    current = current.parentElement;
  }
  return { foreground, background };
});

for (const scenario of scenarios) {
  test(`${scenario.flow}: primary action and approval note meet WCAG AA contrast`, async ({ page }) => {
    await page.goto(`/start/${scenario.token}`);

    const primaryAction = page.getByRole('button', { name: /Показать|Подготовить/ }).first();
    const approvalNote = page.getByText('Внешние отправки и изменения остаются под ручным подтверждением.');

    await expect(primaryAction).toBeVisible();
    await expect(approvalNote).toBeVisible();

    const actionColors = await computedColors(primaryAction);
    const noteColors = await computedColors(approvalNote);
    expect(contrastRatio(actionColors.foreground, actionColors.background), 'primary action contrast').toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(noteColors.foreground, noteColors.background), 'approval note contrast').toBeGreaterThanOrEqual(4.5);
  });
}
