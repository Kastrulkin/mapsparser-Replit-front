import { randomUUID } from 'node:crypto';

import { expect, test } from '@playwright/test';

import { fixtureCommand } from './fixtureCommand';


const OWNER_EMAIL = 'owner@localos-e2e.invalid';
const OWNER_PASSWORD = 'LocalOS-E2E-2026!';
const TOKENS: Record<string, string> = {
  maps: 'localos-e2e-maps-e796eeb9a98652e78fd902c9f9c64ec7',
  influencer: 'localos-e2e-influencer-a258132038fb5ac184707d1fcf4acadb',
  partnership: 'localos-e2e-partnership-d1e0a7fbb26452e6b0b8d65c6bdb1be5',
  content: 'localos-e2e-content-01257a9329e4565b8a59f87cfd6b4b14',
  automation: 'localos-e2e-automation-495c6e64fcd4524aa411da4e93f2d52e',
};

type JourneyAction = {
  id: string;
  action_type: string;
  status: string;
  version: number;
  flow_type: string;
};

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

const csrfHeaders = async (page: import('@playwright/test').Page) => {
  const csrfCookie = (await page.context().cookies()).find((cookie) => cookie.name === 'localos_csrf');
  expect(csrfCookie?.value).toBeTruthy();
  return { 'X-CSRF-Token': csrfCookie?.value || '' };
};

const claimFlow = async (
  page: import('@playwright/test').Page,
  businessId: string,
  flow: string,
): Promise<JourneyAction> => {
  fixtureCommand('reset-journey', flow);
  const headers = await csrfHeaders(page);
  const response = await page.request.post('/api/journeys/claim', {
    headers,
    data: { token: TOKENS[flow], business_id: businessId, surface: 'web' },
  });
  const body = await response.text();
  expect(response.status(), body).toBe(200);
  return JSON.parse(body).action;
};

const runCommand = async (
  page: import('@playwright/test').Page,
  businessId: string,
  action: JourneyAction,
  command: string,
  payload: Record<string, unknown> = {},
): Promise<JourneyAction> => {
  const headers = {
    ...await csrfHeaders(page),
    'Idempotency-Key': `localos-e2e-${action.flow_type}-${command}-${randomUUID()}`,
  };
  const response = await page.request.post(`/api/journey-actions/${action.id}/commands`, {
    headers,
    data: {
      business_id: businessId,
      command,
      version: action.version,
      surface: 'web',
      payload,
    },
  });
  const body = await response.text();
  expect(response.status(), `${action.action_type}/${command}: ${body}`).toBe(200);
  const parsed = JSON.parse(body);
  return parsed.next_action;
};

const activeFlowAction = async (
  page: import('@playwright/test').Page,
  businessId: string,
  flow: string,
): Promise<JourneyAction> => {
  const response = await page.request.get(`/api/journey-actions?business_id=${encodeURIComponent(businessId)}`);
  const body = await response.text();
  expect(response.status(), body).toBe(200);
  const parsed = JSON.parse(body);
  const action = parsed.actions.find((candidate: JourneyAction) => candidate.flow_type === flow);
  expect(action).toBeTruthy();
  return action;
};

test.beforeEach(async ({ page }) => {
  const businessId = fixtureCommand('owner-business-id');
  await loginOwner(page, businessId);
});

test('maps journey reaches verified comparison and starts the next weekly cycle', async ({ page }) => {
  const businessId = fixtureCommand('owner-business-id');
  let action = await claimFlow(page, businessId, 'maps');
  expect(action.action_type).toBe('complete_map_task');
  await page.goto(`/dashboard/progress?journey_action=${action.id}`);
  await expect(page.getByText('Исправить часы работы').first()).toBeVisible();

  action = await runCommand(page, businessId, action, 'complete');
  expect(action.action_type).toBe('refresh_data');
  action = await runCommand(page, businessId, action, 'complete');
  expect(action.action_type).toBe('compare_snapshot');
  expect(action.status).toBe('waiting');
  fixtureCommand('complete-map-refresh');
  action = await activeFlowAction(page, businessId, 'maps');
  expect(action.action_type).toBe('compare_snapshot');
  expect(action.status).toBe('ready');
  action = await runCommand(page, businessId, action, 'complete');
  action = await runCommand(page, businessId, action, 'start_next_cycle');
  expect(action.action_type).toBe('complete_map_task');

  const domain = JSON.parse(fixtureCommand('journey-domain-state', 'maps'));
  expect(domain.action_type).toBe('complete_map_task');
  expect(domain.status).toBe('ready');
});

test('influencer journey uses a real shortlist and completes placement result', async ({ page }) => {
  const businessId = fixtureCommand('owner-business-id');
  let action = await claimFlow(page, businessId, 'influencer');
  expect(action.action_type).toBe('browse_creators');
  await page.goto(`/dashboard/influencers?journey_action=${action.id}`);
  await expect(page.getByText('Анна про район').first()).toBeVisible();

  action = await runCommand(page, businessId, action, 'complete');
  action = await runCommand(page, businessId, action, 'mark_sent');
  action = await runCommand(page, businessId, action, 'record_reply', { outcome: 'barter' });
  action = await runCommand(page, businessId, action, 'save_terms', { details: 'Три клиента — услуга в подарок' });
  action = await runCommand(page, businessId, action, 'mark_published', { publication_url: 'https://t.me/localos_e2e_anna/42' });
  action = await runCommand(page, businessId, action, 'add_result', { inquiries: 4, sales: 2, note: 'Подтверждено вручную' });
  action = await runCommand(page, businessId, action, 'start_next_cycle');
  expect(action.action_type).toBe('send_message');

  const domain = JSON.parse(fixtureCommand('journey-domain-state', 'influencer'));
  expect(domain.shortlisted_count).toBeGreaterThanOrEqual(1);
});

test('partnership journey stores launch mechanic and measured result', async ({ page }) => {
  const businessId = fixtureCommand('owner-business-id');
  let action = await claimFlow(page, businessId, 'partnership');
  expect(action.action_type).toBe('send_message');
  await page.goto(`/dashboard/promotion/partnerships?journey_action=${action.id}`);
  await expect(page.getByText('Студия йоги рядом').first()).toBeVisible();

  action = await runCommand(page, businessId, action, 'mark_sent');
  action = await runCommand(page, businessId, action, 'record_reply', { outcome: 'interested' });
  action = await runCommand(page, businessId, action, 'save_terms', { details: 'Общий сертификат для соседей' });
  action = await runCommand(page, businessId, action, 'mark_launched', { mechanic: 'Взаимный сертификат', promo_code: 'LOCALOS-E2E' });
  action = await runCommand(page, businessId, action, 'add_result', { inquiries: 6, sales: 3, note: 'Сверено владельцем' });
  action = await runCommand(page, businessId, action, 'start_next_cycle');
  expect(action.action_type).toBe('send_message');

  const domain = JSON.parse(fixtureCommand('journey-domain-state', 'partnership'));
  expect(domain.partnership_launched_at).toBeTruthy();
  expect(domain.partnership_outcome_json.result.sales).toBe(3);
});

test('content journey preserves draft, publication and result evidence', async ({ page }) => {
  const businessId = fixtureCommand('owner-business-id');
  let action = await claimFlow(page, businessId, 'content');
  expect(action.action_type).toBe('prepare_content');
  await page.goto(`/dashboard/content?journey_action=${action.id}`);
  await expect(page.getByText('Как выбрать услугу впервые').first()).toBeVisible();

  action = await runCommand(page, businessId, action, 'prepare');
  action = await runCommand(page, businessId, action, 'save_draft', { draft_text: 'Три факта, которые помогут выбрать первую услугу.' });
  action = await runCommand(page, businessId, action, 'schedule', { scheduled_for: '2026-09-15' });
  action = await runCommand(page, businessId, action, 'mark_published', { publication_url: 'https://example.invalid/localos-e2e-content' });
  action = await runCommand(page, businessId, action, 'add_result', { views: 120, inquiries: 5, note: 'Статистика внесена вручную' });
  action = await runCommand(page, businessId, action, 'start_next_cycle');
  expect(action.action_type).toBe('prepare_content');

  const domain = JSON.parse(fixtureCommand('journey-domain-state', 'content'));
  expect(domain.status).toBe('published');
  expect(domain.draft_text).toContain('Три факта');
  expect(domain.metadata_json.journey_result.views).toBe(120);
});

test('automation journey requires approval and links only a completed run', async ({ page }) => {
  const businessId = fixtureCommand('owner-business-id');
  let action = await claimFlow(page, businessId, 'automation');
  expect(action.action_type).toBe('configure_automation');
  await page.goto(`/dashboard/agents?journey_action=${action.id}`);
  await expect(page.getByText('Настроить первую задачу').first()).toBeVisible();

  action = await runCommand(page, businessId, action, 'save_configuration', {
    use_case: 'review_drafts',
    expected_result: 'Черновики ответов для ручной проверки',
  });
  action = await runCommand(page, businessId, action, 'approve', { confirmed: true });
  const runId = fixtureCommand('complete-automation-run');
  action = await runCommand(page, businessId, action, 'link_run', { run_id: runId });
  action = await runCommand(page, businessId, action, 'add_result', { result_summary: 'Черновики проверены владельцем' });
  action = await runCommand(page, businessId, action, 'start_next_cycle');
  expect(action.action_type).toBe('configure_automation');

  const domain = JSON.parse(fixtureCommand('journey-domain-state', 'automation'));
  expect(domain.id).toBe(runId);
  expect(domain.status).toBe('completed');
});
