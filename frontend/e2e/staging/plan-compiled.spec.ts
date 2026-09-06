import { readFile } from 'node:fs/promises';
import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import { fixtureCommand } from './fixtureCommand';

test.use({ baseURL: process.env.LOCALOS_STAGING_BASE_URL || 'http://127.0.0.1:18006' });

const businessId = () => fixtureCommand('owner-business-id');

const expectVisibleChildWithinViewport = async (page: Page, locator: Locator) => {
  await expect(locator).toBeVisible();
  const bounds = await locator.evaluate((element) => {
    const rectangle = element.getBoundingClientRect();
    return { left: rectangle.left, right: rectangle.right, width: rectangle.width };
  });
  const viewportWidth = await page.evaluate(() => window.innerWidth);
  expect(bounds.width).toBeGreaterThan(0);
  expect(bounds.left).toBeGreaterThanOrEqual(0);
  expect(bounds.right).toBeLessThanOrEqual(viewportWidth);
};

const newestCompletedCompiledRun = async (request: APIRequestContext) => {
  const response = await request.get(`/api/agent-blueprints?business_id=${businessId()}`);
  expect(response.status()).toBe(200);
  const payload = await response.json();
  const blueprints = Array.isArray(payload.blueprints) ? payload.blueprints : [];
  const configuredBlueprintId = process.env.LOCALOS_COMPILED_PROOF_BLUEPRINT_ID || '';
  const candidates = blueprints
    .filter((blueprint) => blueprint.name === '[E2E] Compiled table proof')
    .sort((left, right) => {
      if (left.id === configuredBlueprintId) return -1;
      if (right.id === configuredBlueprintId) return 1;
      return String(right.created_at || '').localeCompare(String(left.created_at || ''));
    });
  for (const blueprint of candidates) {
    if (!blueprint.id) continue;
    const detailsResponse = await request.get(`/api/agent-blueprints/${blueprint.id}`);
    expect(detailsResponse.status()).toBe(200);
    const details = await detailsResponse.json();
    if (!details.compiled_approved_version?.id) continue;
    const run = (Array.isArray(details.runs) ? details.runs : []).find((item) => {
      const report = item.output_json?.report;
      const errors = Array.isArray(report?.errors) ? report.errors : [];
      return item.status === 'completed'
        && item.output_json?.schema === 'localos_compiled_script_result_v1'
        && errors.some((error) => error.row === 2 && error.code === 'duplicate')
        && errors.some((error) => error.row === 3 && error.code === 'required');
    });
    if (run?.id) return { blueprintId: blueprint.id, runId: run.id, output: run.output_json || {} };
  }
  throw new Error('No approved synthetic compiled table run is available in isolated staging.');
};

test('approved compiled table version reloads and shows its real runner report', async ({ page }, testInfo) => {
  const selectedBusinessId = businessId();
  await page.addInitScript((id) => {
    localStorage.setItem('language', 'ru');
    localStorage.setItem('selectedBusinessId', id);
  }, selectedBusinessId);
  const login = await page.request.post('/api/auth/login', {
    data: { email: 'admin@localos-e2e.invalid', password: 'LocalOS-E2E-2026!' },
  });
  expect(login.status()).toBe(200);
  const chosen = await newestCompletedCompiledRun(page.request);
  const report = chosen.output.report;
  const errors = Array.isArray(report.errors) ? report.errors : [];
  expect(errors.some((item) => item.row === 2 && item.code === 'duplicate')).toBe(true);
  expect(errors.some((item) => item.row === 3 && item.code === 'required')).toBe(true);

  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.goto(`/dashboard/agents?business_id=${selectedBusinessId}&blueprint_id=${chosen.blueprintId}&run_id=${chosen.runId}`);
  await expect(page.getByText('Утверждённая версия готова')).toBeVisible();
  const builder = page.locator('section[aria-label="Проверьте таблицу без повторного обращения к ИИ"]');
  const actualReport = page.getByText('Фактический отчёт запуска', { exact: true }).locator('..');
  await expect(actualReport).toBeVisible();
  await expect(actualReport).toContainText('Строк: 3 · принято: 1 · дубли: 1 · ошибки: 1');
  await expect(actualReport.getByText('Дубликат строки')).toBeVisible();
  await expect(actualReport.getByText('Не заполнены: email')).toBeVisible();
  await expect(page.getByText('Данные запуска хранятся 7 дней. После этого остаётся отчёт без содержимого строк.')).toBeVisible();
  const actualReportDownload = actualReport.getByRole('button', { name: 'Скачать ошибки CSV' });
  const download = page.waitForEvent('download');
  await actualReportDownload.click();
  const completedDownload = await download;
  const downloadPath = await completedDownload.path();
  expect(downloadPath).not.toBeNull();
  if (downloadPath) {
    const csv = await readFile(downloadPath, 'utf8');
    expect(csv).toContain('"2","Дубликат строки","duplicate"');
    expect(csv).toContain('"3","Не заполнены: email","required","email"');
  }
  await expectVisibleChildWithinViewport(page, builder.getByLabel('Новая таблица для запуска'));
  await expectVisibleChildWithinViewport(page, builder.getByRole('button', { name: 'Запустить проверку' }));
  await expectVisibleChildWithinViewport(page, actualReport);
  const errorTable = actualReport.locator('table');
  await expect(errorTable).toBeVisible();
  const reportBounds = await actualReport.evaluate((element) => element.getBoundingClientRect().toJSON());
  const tableBounds = await errorTable.evaluate((element) => element.getBoundingClientRect().toJSON());
  expect(tableBounds.left).toBeGreaterThanOrEqual(reportBounds.left);
  expect(tableBounds.right).toBeLessThanOrEqual(reportBounds.right);
  await expectVisibleChildWithinViewport(page, actualReport.getByText('Не заполнены: email', { exact: true }));
  const secondaryWorkspace = page.locator('summary', { hasText: 'Другие задачи и история' });
  await expect(secondaryWorkspace).toBeVisible();
  expect(await secondaryWorkspace.evaluate((element) => element.parentElement?.open)).toBe(false);
  await secondaryWorkspace.click();
  await expect(page.getByText('Автоматизация задач', { exact: true }).last()).toBeVisible();
  await secondaryWorkspace.focus();
  await page.keyboard.press('Enter');
  expect(await secondaryWorkspace.evaluate((element) => element.parentElement?.open)).toBe(false);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await testInfo.attach('real-compiled-run', {
    body: JSON.stringify({
      blueprint_id: chosen.blueprintId,
      run_id: chosen.runId,
      report: { received: report.received, accepted: report.accepted, duplicates: report.duplicates, invalid: report.invalid, errors },
      page_errors: pageErrors,
    }, null, 2),
    contentType: 'application/json',
  });
  await page.screenshot({ path: testInfo.outputPath('compiled-real-report.png'), fullPage: true });
  expect(pageErrors).toEqual([]);
});
