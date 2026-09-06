import { readFile } from 'node:fs/promises';
import { expect, test, type Page, type Route } from '@playwright/test';

const blueprint = { id: 'compiled-blueprint', business_id: 'business-1', name: 'Проверка прайса', status: 'draft', execution_mode: 'manual', lifecycle_state: 'draft', description: 'Проверяет строки прайса' };
const report = { received: 3, accepted: 1, duplicates: 1, invalid: 1, errors: [{ row: 2, code: 'duplicate' }, { row: 3, code: 'required', columns: ['email'] }] };
const artifact = {
  source: 'def process(input_payload): return input_payload', artifact_hash: 'artifact-1',
  manifest: { table_contract: { version: 2, columns: ['email', 'amount'], required_columns: ['email'], dedupe_columns: ['email'], version_name: 'Прайс' } },
  fixtures: [{ source: 'user', input: { rows: [{ email: 'anna@example.test', amount: '10' }, { email: 'anna@example.test', amount: '10' }, { email: '', amount: '5' }] } }],
};
const artifactV2 = {
  ...artifact,
  artifact_hash: 'artifact-2',
  manifest: { table_contract: { version: 2, columns: ['email', 'amount'], required_columns: ['email'], dedupe_columns: ['email'], version_name: 'Прайс V2' } },
};
const completedRun = { id: 'run-1', blueprint_id: blueprint.id, status: 'completed', output_json: { schema: 'localos_compiled_script_result_v1', rows: [{ email: 'anna@example.test', amount: '10' }], report } };
const mockedUser = { id: 'user-1', email: 'mocked@example.test', businesses: [{ id: 'business-1', name: 'Mocked business', subscription_tier: 'concierge', subscription_status: 'active' }] };
const emptyIntegrationPayload = { integrations: [], available_integrations: [], provider_catalog: [], external_auth_options: [], binding_status: [] };

const compiledVersion = (id: string, compiledState: string, versionArtifact: typeof artifact) => ({
  id,
  compiled_state: compiledState,
  compiled_artifact_json: versionArtifact,
  compiled_preview_json: { status: 'passed', fixture_digest: `fixture-${id}`, fixture_results: [{ source: 'user', passed: true }], result: { schema: 'localos_compiled_script_result_v1', report } },
});

const detail = ({ preview = true, execute = true, runs = [], approved = false, candidateVersion = null, compiledApprovedVersion = null }: { preview?: boolean; execute?: boolean; runs?: unknown[]; approved?: boolean; candidateVersion?: Record<string, unknown> | null; compiledApprovedVersion?: Record<string, unknown> | null } = {}) => ({
  blueprint, versions: [], runs, approval_queue: [],
  active_version: approved ? { id: 'version-1', compiled_state: 'approved', compiled_artifact_json: artifact, compiled_preview_json: { status: 'passed', fixture_digest: 'fixture-1', fixture_results: [{ source: 'user', passed: true }], result: { schema: 'localos_compiled_script_result_v1', report } } } : null,
  candidate_version: candidateVersion, compiled_approved_version: compiledApprovedVersion, compiled_access: { preview, execute }, execution_contract: {},
});

const installSession = async (page: Page, language = 'ru') => {
  await page.addInitScript((storedLanguage) => { window.localStorage.setItem('auth_token', 'mocked-agent-token'); window.localStorage.setItem('selectedBusinessId', 'business-1'); window.localStorage.setItem('language', storedLanguage); }, language);
};

const fulfillCommonAgentRequest = async (route: Route, path: string) => {
  if (path === '/api/auth/me') { await route.fulfill({ json: mockedUser }); return true; }
  if (path === '/api/agent-templates') { await route.fulfill({ json: { templates: [] } }); return true; }
  if (path === '/api/agent-blueprints/legacy-migration-plan') { await route.fulfill({ json: {} }); return true; }
  if (path === '/api/agent-blueprints/compiled-blueprint/review') { await route.fulfill({ json: { review: null } }); return true; }
  if (path === '/api/agent-blueprints/compiled-blueprint/sources/catalog') { await route.fulfill({ json: { catalog: [] } }); return true; }
  if (path === '/api/agent-blueprints/compiled-blueprint/integrations') { await route.fulfill({ json: emptyIntegrationPayload }); return true; }
  return false;
};

test.beforeEach(async ({ page }) => installSession(page));

test('compiled table run polls queued, running, and completed states without replacing the builder', async ({ page }, testInfo) => {
  let approved = false;
  let compiledApprovedVersionId: string | null = null;
  let firstRunPoll = 0;
  let runRequests = 0;
  const observedRunStates: string[] = [];
  const idempotencyKeys: string[] = [];
  const snapshotBodies: unknown[] = [];
  const compileBodies: unknown[] = [];
  await page.route('**/api/**', async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    const common = await fulfillCommonAgentRequest(route, path); if (common) return common;
    if (path === '/api/agent-blueprints') return route.fulfill({ json: { blueprints: [{ ...blueprint, compiled_approved_version_id: compiledApprovedVersionId }], today_summary: {} } });
    if (path === '/api/agent-blueprints/compiled-blueprint') return route.fulfill({ json: detail({ approved, runs: approved ? [completedRun] : [], compiledApprovedVersion: approved ? compiledVersion('version-1', 'approved', artifact) : null }) });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/compile') { compileBodies.push(request.postDataJSON()); return route.fulfill({ json: { success: true, candidate_version: { id: 'version-1' }, artifact } }); }
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/preview') return route.fulfill({ json: { success: true, version_id: 'version-1', approval_digest: 'approval-1', preview: { status: 'passed', fixture_digest: 'fixture-1', fixture_results: [{ source: 'user', passed: true }], result: { schema: 'localos_compiled_script_result_v1', report } } } });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/approve') { approved = true; compiledApprovedVersionId = 'version-1'; return route.fulfill({ json: { success: true, state: 'approved', version_id: 'version-1' } }); }
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/snapshots') { snapshotBodies.push(request.postDataJSON()); return route.fulfill({ json: { success: true, snapshot: { id: `snapshot-${snapshotBodies.length}`, hash: `hash-${snapshotBodies.length}` } } }); }
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/run') {
      const body = request.postDataJSON();
      if (body && typeof body === 'object' && !Array.isArray(body) && typeof body.idempotency_key === 'string') idempotencyKeys.push(body.idempotency_key);
      runRequests += 1;
      return route.fulfill({ json: { success: true, status: 'queued', run: { id: `run-${runRequests}` } } });
    }
    if (path === '/api/agent-runs/run-1') {
      firstRunPoll += 1;
      if (firstRunPoll === 1) { observedRunStates.push('queued'); return route.fulfill({ json: { run: { id: 'run-1', blueprint_id: blueprint.id, status: 'queued' } } }); }
      if (firstRunPoll === 2) { observedRunStates.push('running'); return route.fulfill({ json: { run: { id: 'run-1', blueprint_id: blueprint.id, status: 'running' } } }); }
      observedRunStates.push('completed');
      return route.fulfill({ json: { run: completedRun } });
    }
    if (path === '/api/agent-runs/run-2') return route.fulfill({ json: { run: { id: 'run-2', blueprint_id: blueprint.id, status: 'queued' } } });
    return route.fulfill({ json: {} });
  });

  await page.goto('/dashboard/agents');
  await page.getByRole('button', { name: /Сценарий|Scenario/ }).click();
  await expect(page.getByText('Готовые задачи')).toBeHidden();
  await page.getByLabel('1. Вставьте пример таблицы').fill('email\tamount\nanna@example.test\t10\nanna@example.test\t10\n\t5');
  await page.getByRole('checkbox').nth(0).check();
  await page.getByRole('checkbox').nth(2).check();
  await page.getByLabel('3. Подтвердите ожидаемый результат: 2').selectOption('duplicate');
  await page.getByLabel('3. Подтвердите ожидаемый результат: 3').selectOption('missing');
  await page.getByRole('button', { name: 'Подготовить версию' }).click();
  await page.getByRole('button', { name: 'Проверить на примере' }).click();
  await page.getByRole('button', { name: 'Подтвердить версию' }).click();
  await page.getByLabel('Новая таблица для запуска').fill('email\tamount\nanna@example.test\t10');
  await page.getByRole('button', { name: 'Запустить проверку' }).click();

  await expect(page.getByText('Фактический отчёт запуска')).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText('Дубликат строки').last()).toBeVisible();
  await expect(page.getByText('Не заполнены: email').last()).toBeVisible();
  const builderChildrenFitViewport = await page.locator('[aria-label="Проверьте таблицу без повторного обращения к ИИ"] > *').evaluateAll((elements) => elements.every((element) => element.getBoundingClientRect().right <= window.innerWidth + 1));
  expect(builderChildrenFitViewport).toBe(true);
  await expect.poll(() => firstRunPoll).toBe(3);
  expect(observedRunStates).toEqual(['queued', 'running', 'completed']);
  await expect.poll(() => compileBodies.length).toBe(1);
  expect(compileBodies[0]).toEqual(expect.objectContaining({ idempotency_key: expect.any(String) }));
  expect(compileBodies[0]).toEqual(expect.objectContaining({
    table_contract: expect.objectContaining({ version: 2 }),
    fixtures: [expect.objectContaining({
      expected: expect.objectContaining({
        report: expect.objectContaining({
          accepted: 1,
          duplicates: 1,
          invalid: 1,
          errors: [
            expect.objectContaining({ row: 2, code: 'duplicate' }),
            expect.objectContaining({ row: 3, code: 'required', columns: ['email'] }),
          ],
        }),
      }),
    })],
  }));
  expect(snapshotBodies).toHaveLength(1); expect(idempotencyKeys).toHaveLength(1);
  await page.screenshot({ path: `../.agent/tasks/localos-plan-20260906/raw/compiled-agent-e2e-${testInfo.project.name}.png`, fullPage: true });

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Скачать ошибки CSV' }).last().click();
  const completedDownload = await download;
  expect(completedDownload.suggestedFilename()).toBe('localos-table-errors.csv');
  const downloadPath = await completedDownload.path();
  expect(downloadPath).not.toBeNull();
  if (downloadPath) expect(await readFile(downloadPath, 'utf8')).toContain('"2","Дубликат строки","duplicate"');
  await page.getByLabel('Новая таблица для запуска').fill('email\tamount\nnew@example.test\t20');
  await page.getByRole('button', { name: 'Запустить проверку' }).click();
  await expect(page.getByText('Запуск run-2: queued.')).toBeVisible();
  await expect.poll(() => runRequests).toBe(2);
  expect(idempotencyKeys[0]).not.toBe(idempotencyKeys[1]); expect(snapshotBodies).toHaveLength(2);

  await page.reload();
  await page.getByRole('button', { name: /История|History/ }).click();
  const secondaryWorkspace = page.locator('summary', { hasText: 'Другие задачи и история' });
  await secondaryWorkspace.click();
  await expect(page.getByText('Готовые задачи')).toBeVisible();
  await secondaryWorkspace.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByText('Готовые задачи')).toBeHidden();
  await page.keyboard.press('Enter');
  await expect(page.getByText('Готовые задачи')).toBeVisible();
  await expect(page.getByRole('button', { name: /Проверка прайса/ })).toContainText('Готова к запуску');
  await page.getByRole('button', { name: /Рабочий запуск|Live run/ }).click();
  await expect(page.getByText('Фактический отчёт запуска')).toBeVisible();
  await expect(page.getByText('Не заполнены: email').last()).toBeVisible();
});

test('a deep-linked compiled report stays selected until the user starts a new run', async ({ page }) => {
  const latestReport = { received: 1, accepted: 1, duplicates: 0, invalid: 0, errors: [] };
  const olderRun = { id: 'run-older', blueprint_id: blueprint.id, status: 'completed', output_json: { schema: 'localos_compiled_script_result_v1', rows: [{ email: 'anna@example.test', amount: '10' }], report } };
  const latestRun = { id: 'run-latest', blueprint_id: blueprint.id, status: 'completed', output_json: { schema: 'localos_compiled_script_result_v1', rows: [{ email: 'latest@example.test', amount: '20' }], report: latestReport } };
  const newReport = { received: 2, accepted: 2, duplicates: 0, invalid: 0, errors: [] };
  const newRun = { id: 'run-new', blueprint_id: blueprint.id, status: 'completed', output_json: { schema: 'localos_compiled_script_result_v1', rows: [{ email: 'new@example.test', amount: '30' }, { email: 'next@example.test', amount: '40' }], report: newReport } };
  await page.route('**/api/**', async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    const common = await fulfillCommonAgentRequest(route, path); if (common) return common;
    if (path === '/api/agent-blueprints') return route.fulfill({ json: { blueprints: [{ ...blueprint, compiled_approved_version_id: 'version-1' }], today_summary: {} } });
    if (path === '/api/agent-blueprints/compiled-blueprint') return route.fulfill({ json: detail({ approved: true, runs: [latestRun, olderRun], compiledApprovedVersion: compiledVersion('version-1', 'approved', artifact) }) });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/snapshots') return route.fulfill({ json: { success: true, snapshot: { id: 'snapshot-new', hash: 'hash-new' } } });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/run') return route.fulfill({ json: { success: true, status: 'queued', run: { id: 'run-new' } } });
    if (path === '/api/agent-runs/run-older') return route.fulfill({ json: { run: olderRun } });
    if (path === '/api/agent-runs/run-latest') return route.fulfill({ json: { run: latestRun } });
    if (path === '/api/agent-runs/run-new') return route.fulfill({ json: { run: newRun } });
    return route.fulfill({ json: {} });
  });

  await page.goto('/dashboard/agents?blueprint_id=compiled-blueprint&run_id=run-older');
  await expect(page.getByText('Фактический отчёт запуска')).toBeVisible();
  await expect(page.getByText('Строк: 3 · принято: 1 · дубли: 1 · ошибки: 1').last()).toBeVisible();
  await expect(page.getByText('Не заполнены: email').last()).toBeVisible();
  const inputBounds = await page.getByLabel('Новая таблица для запуска').boundingBox();
  expect(inputBounds).not.toBeNull();
  if (inputBounds) expect(inputBounds.x + inputBounds.width).toBeLessThanOrEqual((page.viewportSize()?.width || 0) + 1);
  await page.getByLabel('Новая таблица для запуска').fill('email\tamount\nnew@example.test\t30\nnext@example.test\t40');
  await page.getByRole('button', { name: 'Запустить проверку' }).click();
  await expect(page.getByText('Строк: 2 · принято: 2 · дубли: 0 · ошибки: 0').last()).toBeVisible();
  await expect(page.getByText('Строк: 1 · принято: 1 · дубли: 0 · ошибки: 0')).toHaveCount(0);
});

test('a failed compiled preview renders its row error and cannot be approved', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    const common = await fulfillCommonAgentRequest(route, path); if (common) return common;
    if (path === '/api/agent-blueprints') return route.fulfill({ json: { blueprints: [blueprint], today_summary: {} } });
    if (path === '/api/agent-blueprints/compiled-blueprint') return route.fulfill({ json: detail() });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/compile') return route.fulfill({ json: { success: true, candidate_version: { id: 'version-1' }, artifact } });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/preview') return route.fulfill({ status: 422, json: { code: 'COMPILED_SCRIPT_PREVIEW_FAILED', message: 'Пример не прошёл проверку.', preview: { status: 'failed', fixture_results: [{ source: 'user', passed: false }], result: { schema: 'localos_compiled_script_result_v1', report } } } });
    return route.fulfill({ json: {} });
  });
  await page.goto('/dashboard/agents');
  await page.getByRole('button', { name: /Сценарий|Scenario/ }).click();
  await page.getByLabel('1. Вставьте пример таблицы').fill('email\tamount\nanna@example.test\t10');
  await page.locator('fieldset').filter({ hasText: 'Искать дубли по' }).getByRole('checkbox', { name: 'email' }).check();
  await page.getByRole('button', { name: 'Подготовить версию' }).click();
  await page.getByRole('button', { name: 'Проверить на примере' }).click();
  await expect(page.getByText('Проверка не пройдена')).toBeVisible();
  await expect(page.getByText('Не заполнены: email').last()).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Пример не прошёл проверку.');
  await expect(page.getByRole('button', { name: 'Подтвердить версию' })).toHaveCount(0);
});

test('the English compiled-table flow reviews, approves, runs, and downloads its row report', async ({ page }) => {
  await installSession(page, 'en');
  let approved = false;
  await page.route('**/api/**', async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    const common = await fulfillCommonAgentRequest(route, path); if (common) return common;
    if (path === '/api/agent-blueprints') return route.fulfill({ json: { blueprints: [blueprint], today_summary: {} } });
    if (path === '/api/agent-blueprints/compiled-blueprint') return route.fulfill({ json: detail({ approved, runs: approved ? [completedRun] : [], compiledApprovedVersion: approved ? compiledVersion('version-1', 'approved', artifact) : null }) });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/compile') return route.fulfill({ json: { success: true, candidate_version: { id: 'version-1' }, artifact } });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/preview') return route.fulfill({ json: { success: true, version_id: 'version-1', approval_digest: 'approval-1', preview: { status: 'passed', fixture_digest: 'fixture-1', fixture_results: [{ source: 'user', passed: true }], result: { schema: 'localos_compiled_script_result_v1', report } } } });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/approve') { approved = true; return route.fulfill({ json: { success: true, state: 'approved', version_id: 'version-1' } }); }
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/snapshots') return route.fulfill({ json: { success: true, snapshot: { id: 'snapshot-1', hash: 'hash-1' } } });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/run') return route.fulfill({ json: { success: true, status: 'queued', run: { id: 'run-1' } } });
    if (path === '/api/agent-runs/run-1') return route.fulfill({ json: { run: completedRun } });
    return route.fulfill({ json: {} });
  });

  await page.goto('/dashboard/agents');
  await page.getByRole('button', { name: /Scenario/ }).click();
  await expect(page.getByText('Check a table without asking AI again')).toBeVisible();
  await page.getByLabel('1. Paste an example table').fill('email\tamount\nanna@example.test\t10\nanna@example.test\t10\n\t5');
  await page.getByRole('checkbox').nth(0).check();
  await page.getByRole('checkbox').nth(2).check();
  await page.getByLabel('3. Confirm the expected result: 2').selectOption('duplicate');
  await page.getByLabel('3. Confirm the expected result: 3').selectOption('missing');
  await page.getByRole('button', { name: 'Prepare version' }).click();
  await page.getByRole('button', { name: 'Check with the example' }).click();
  await expect(page.getByText('Duplicate row').last()).toBeVisible();
  await page.getByRole('button', { name: 'Approve version' }).click();
  await page.getByLabel('New table for this run').fill('email\tamount\nanna@example.test\t10');
  await page.getByRole('button', { name: 'Run check' }).click();
  await expect(page.getByText('Actual run report')).toBeVisible({ timeout: 5_000 });
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download errors CSV' }).last().click();
  const completedDownload = await download;
  const downloadPath = await completedDownload.path();
  expect(downloadPath).not.toBeNull();
  if (downloadPath) expect(await readFile(downloadPath, 'utf8')).toContain('"Duplicate row"');
});

test('an unfinished next version does not hide the approved version after reload', async ({ page }) => {
  let phase: 'checking' | 'needs_fix' | 'ready_approval' | 'approved' = 'needs_fix';
  const runVersionIds: string[] = [];
  const previewVersionIds: string[] = [];
  const versionOne = compiledVersion('version-1', 'approved', artifact);
  const versionTwoChecking = compiledVersion('version-2', 'checking', artifactV2);
  const versionTwoDraft = { ...compiledVersion('version-2', 'needs_fix', artifactV2), compiled_preview_json: { status: 'failed', fixture_digest: 'fixture-version-2', fixture_results: [{ source: 'user', passed: false }], result: { schema: 'localos_compiled_script_result_v1', report } } };
  const versionTwoReady = compiledVersion('version-2', 'ready_approval', artifactV2);
  const versionTwoApproved = compiledVersion('version-2', 'approved', artifactV2);
  await page.route('**/api/**', async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    const common = await fulfillCommonAgentRequest(route, path); if (common) return common;
    if (path === '/api/agent-blueprints') return route.fulfill({ json: { blueprints: [blueprint], today_summary: {} } });
    if (path === '/api/agent-blueprints/compiled-blueprint') {
      const candidateVersion = phase === 'checking' ? versionTwoChecking : phase === 'needs_fix' ? versionTwoDraft : phase === 'ready_approval' ? versionTwoReady : versionTwoApproved;
      return route.fulfill({ json: detail({ candidateVersion, compiledApprovedVersion: phase === 'approved' ? versionTwoApproved : versionOne }) });
    }
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/preview') {
      const body = request.postDataJSON();
      if (body && typeof body === 'object' && !Array.isArray(body) && typeof body.version_id === 'string') previewVersionIds.push(body.version_id);
      return route.fulfill({ json: { success: true, version_id: 'version-2', approval_digest: 'approval-v2', preview: { status: 'failed', fixture_digest: 'fixture-version-2', fixture_results: [{ source: 'user', passed: false }], result: { schema: 'localos_compiled_script_result_v1', report } } } });
    }
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/snapshots') return route.fulfill({ json: { success: true, snapshot: { id: `snapshot-${runVersionIds.length + 1}` } } });
    if (path === '/api/agent-blueprints/compiled-blueprint/compiled-script/run') {
      const body = request.postDataJSON();
      if (body && typeof body === 'object' && !Array.isArray(body) && typeof body.version_id === 'string') runVersionIds.push(body.version_id);
      return route.fulfill({ json: { success: true, status: 'queued', run: { id: `run-${runVersionIds.length}` } } });
    }
    return route.fulfill({ json: {} });
  });

  await page.goto('/dashboard/agents');
  await page.getByRole('button', { name: /Сценарий|Scenario/ }).click();
  await expect(page.getByText('Проверка не пройдена')).toBeVisible();
  await page.getByRole('button', { name: 'Проверить на примере' }).click();
  await expect.poll(() => previewVersionIds).toEqual(['version-2']);
  await expect(page.getByRole('button', { name: 'Вернуться к утверждённой версии' })).toBeVisible();
  await page.getByRole('button', { name: 'Вернуться к утверждённой версии' }).click();
  await page.getByLabel('Новая таблица для запуска').fill('email\tamount\nfirst@example.test\t10');
  await page.getByRole('button', { name: 'Запустить проверку' }).click();
  await expect.poll(() => runVersionIds).toEqual(['version-1']);

  phase = 'checking';
  await page.reload();
  await page.getByRole('button', { name: /Сценарий|Scenario/ }).click();
  await page.getByRole('button', { name: 'Проверить на примере' }).click();
  await expect.poll(() => previewVersionIds).toEqual(['version-2', 'version-2']);
  await expect(page.getByRole('button', { name: 'Вернуться к утверждённой версии' })).toBeVisible();

  phase = 'ready_approval';
  await page.reload();
  await page.getByRole('button', { name: /Сценарий|Scenario/ }).click();
  await expect(page.getByRole('button', { name: 'Подтвердить версию' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Вернуться к утверждённой версии' })).toBeVisible();
  await page.getByRole('button', { name: 'Вернуться к утверждённой версии' }).click();

  phase = 'approved';
  await page.reload();
  await page.getByRole('button', { name: /Сценарий|Scenario/ }).click();
  await page.getByLabel('Новая таблица для запуска').fill('email\tamount\nsecond@example.test\t20');
  await page.getByRole('button', { name: 'Запустить проверку' }).click();
  await expect.poll(() => runVersionIds).toEqual(['version-1', 'version-2']);
});

test('a user outside the compiled cohort keeps the existing scenario UI', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const common = await fulfillCommonAgentRequest(route, path); if (common) return common;
    if (path === '/api/agent-blueprints') return route.fulfill({ json: { blueprints: [blueprint], today_summary: {} } });
    if (path === '/api/agent-blueprints/compiled-blueprint') return route.fulfill({ json: detail({ preview: false, execute: false }) });
    return route.fulfill({ json: {} });
  });
  await page.goto('/dashboard/agents');
  await page.getByRole('button', { name: /Сценарий|Scenario/ }).click();
  await expect(page.getByLabel('1. Вставьте пример таблицы')).toHaveCount(0);
});

test('a paused blueprint keeps its paused status even with a compiled approval marker', async ({ page }) => {
  const pausedBlueprint = { ...blueprint, status: 'paused', lifecycle_state: 'paused', compiled_approved_version_id: 'version-1' };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const common = await fulfillCommonAgentRequest(route, path); if (common) return common;
    if (path === '/api/agent-blueprints') return route.fulfill({ json: { blueprints: [pausedBlueprint], today_summary: {} } });
    if (path === '/api/agent-blueprints/compiled-blueprint') return route.fulfill({ json: detail({ preview: false, execute: false, compiledApprovedVersion: compiledVersion('version-1', 'approved', artifact) }) });
    return route.fulfill({ json: {} });
  });
  await page.goto('/dashboard/agents');
  await expect(page.getByRole('button', { name: /Проверка прайса/ })).toContainText('Пауза');
  await expect(page.getByText('Готова к запуску')).toHaveCount(0);
});
