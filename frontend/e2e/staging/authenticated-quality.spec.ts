import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { fixtureCommand } from './fixtureCommand';


const OWNER_EMAIL = 'owner@localos-e2e.invalid';
const OWNER_PASSWORD = 'LocalOS-E2E-2026!';

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

const routes = [
  '/dashboard/today',
  '/dashboard/growth-paths',
  '/dashboard/influencers',
  '/dashboard/promotion/partnerships',
  '/dashboard/content',
  '/dashboard/agents',
];

for (const path of routes) {
  test(`${path} has named controls and no unexpected API denial`, async ({ page }, testInfo) => {
    const businessId = fixtureCommand('owner-business-id');
    await loginOwner(page, businessId);
    const apiFailures: string[] = [];
    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 400) {
        apiFailures.push(`${response.status()} ${response.request().method()} ${response.url()}`);
      }
    });

    await page.goto(path);
    await expect(page.locator('main').first()).toBeVisible();
    await page.waitForTimeout(1200);
    const unnamedControls = await page.locator('button, a[href], input, select, textarea').evaluateAll((elements) => (
      elements.flatMap((element, index) => {
        const htmlElement = element instanceof HTMLElement ? element : null;
        if (!htmlElement) return [];
        const style = window.getComputedStyle(htmlElement);
        const rect = htmlElement.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0) return [];
        const labelledBy = htmlElement.getAttribute('aria-labelledby');
        const labelledText = labelledBy
          ? labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent || '').join(' ')
          : '';
        const input = htmlElement instanceof HTMLInputElement ? htmlElement : null;
        const associatedLabel = input?.labels
          ? Array.from(input.labels).map((label) => label.textContent || '').join(' ')
          : '';
        const name = [
          htmlElement.getAttribute('aria-label'),
          labelledText,
          associatedLabel,
          htmlElement.textContent,
          htmlElement.getAttribute('title'),
          input?.placeholder,
          htmlElement.querySelector('img')?.getAttribute('alt'),
        ].find((value) => Boolean(value?.trim()));
        if (name) return [];
        return [`${index}:${htmlElement.outerHTML.slice(0, 500)}`];
      })
    ));
    const unlabelledFields = await page.locator('input, textarea, select').evaluateAll((elements) => (
      elements.flatMap((element, index) => {
        const field = element instanceof HTMLInputElement
          || element instanceof HTMLTextAreaElement
          || element instanceof HTMLSelectElement
          ? element
          : null;
        if (!field) return [];
        const style = window.getComputedStyle(field);
        const rect = field.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0) return [];
        const labelText = field.labels
          ? Array.from(field.labels).map((label) => label.textContent || '').join(' ').trim()
          : '';
        const hasLabel = Boolean(
          field.getAttribute('aria-label')?.trim()
          || field.getAttribute('aria-labelledby')?.trim()
          || labelText,
        );
        return hasLabel ? [] : [`${index}:${field.outerHTML.slice(0, 500)}`];
      })
    ));
    const accessibilityScan = await new AxeBuilder({ page }).analyze();
    const seriousOrCriticalViolations = accessibilityScan.violations
      .filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')
      .map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        help: violation.help,
        targets: violation.nodes.map((node) => node.target),
      }));
    await page.keyboard.press('Tab');
    const keyboardFocus = await page.evaluate(() => {
      const element = document.activeElement;
      if (!(element instanceof HTMLElement) || element === document.body) {
        return { tag: null, focusVisible: false, hasVisibleIndicator: false };
      }
      const style = window.getComputedStyle(element);
      const outlineWidth = Number.parseFloat(style.outlineWidth || '0');
      return {
        tag: element.tagName.toLowerCase(),
        focusVisible: element.matches(':focus-visible'),
        hasVisibleIndicator: (
          (style.outlineStyle !== 'none' && outlineWidth > 0)
          || style.boxShadow !== 'none'
        ),
      };
    });
    const undersizedTouchTargets = testInfo.project.name === 'mobile'
      ? await page.locator('button, a[href], input, select, textarea, [role="tab"]').evaluateAll((elements) => (
        elements.flatMap((element, index) => {
          if (!(element instanceof HTMLElement)) return [];
          const input = element instanceof HTMLInputElement ? element : null;
          const labelledTarget = input && (input.type === 'checkbox' || input.type === 'radio')
            ? input.labels?.[0]
            : null;
          const touchTarget = labelledTarget instanceof HTMLElement ? labelledTarget : element;
          const style = window.getComputedStyle(touchTarget);
          const rect = touchTarget.getBoundingClientRect();
          if (style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0) return [];
          if (rect.width >= 40 && rect.height >= 40) return [];
          return [{
            index,
            tag: touchTarget.tagName.toLowerCase(),
            name: (
              touchTarget.getAttribute('aria-label')
              || touchTarget.textContent
              || touchTarget.getAttribute('title')
              || ''
            ).trim().slice(0, 120),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          }];
        }).slice(0, 25)
      ))
      : [];

    expect(
      {
        unnamedControls,
        unlabelledFields,
        seriousOrCriticalViolations,
        keyboardFocus,
        undersizedTouchTargets,
        apiFailures,
      },
      `Quality failures on ${path}`,
    ).toEqual({
      unnamedControls: [],
      unlabelledFields: [],
      seriousOrCriticalViolations: [],
      keyboardFocus: {
        tag: expect.any(String),
        focusVisible: true,
        hasVisibleIndicator: true,
      },
      undersizedTouchTargets: [],
      apiFailures: [],
    });
  });
}
