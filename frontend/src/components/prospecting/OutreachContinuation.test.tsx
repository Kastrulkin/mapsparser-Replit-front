import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { newAuth } from '@/lib/auth_new';
import { OutreachContinuation } from './OutreachContinuation';

const task = { id: 'task-1', revision: 'revision-1', stage: 'Проверьте план', status: 'waiting_for_review', config: { audience: 'Agencies', offer: 'Transfers', language: 'en', queries: [{ query: 'agency', city: 'Delhi' }], max_search_calls: 1, max_candidates: 5, batch_size: 5, search_budget_cents: 100 }, state: {} };
describe('Outreach continuation', () => {
  afterEach(() => vi.restoreAllMocks());
  it('hides disabled feature and does not start any task', async () => {
    const request = vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: false, items: [] });
    render(<OutreachContinuation businessId="b" />);
    await act(async () => {});
    expect(screen.queryByText('Настроить поиск')).not.toBeInTheDocument();
    expect(request).toHaveBeenCalledWith('/partnership/continuations?business_id=b');
    expect(request).toHaveBeenCalledTimes(1);
  });
  it('starts only after explicit review action with current revision', async () => {
    const request = vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [task] });
    render(<OutreachContinuation businessId="b" />);
    await userEvent.click(await screen.findByRole('button', { name: 'Начать подготовку' }));
    expect(request).toHaveBeenCalledWith('/partnership/continuations/task-1', { method: 'POST', body: JSON.stringify({ business_id: 'b', action: 'start', revision: 'revision-1' }) });
  });
  it('offers explicit reconciliation instead of impossible resume', async () => {
    vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [{ ...task, state: { started: true, inflight_search: true, blocker: 'search_result_uncertain' } }] });
    render(<OutreachContinuation businessId="b" />);
    expect(await screen.findByRole('button', { name: 'Учесть использованный поиск и снять неопределённость' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Продолжить подготовку' })).not.toBeInTheDocument();
  });
  it('ignores delayed data from the previous business', async () => {
    let finish: (value: object) => void = () => {};
    const delayed = new Promise(resolve => { finish = resolve; });
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async path => String(path).endsWith('=old') ? delayed : { enabled: true, items: [{ ...task, config: { ...task.config, audience: 'New business' } }] });
    const view = render(<OutreachContinuation businessId="old" />);
    view.rerender(<OutreachContinuation businessId="new" />);
    expect(await screen.findByText('New business')).toBeVisible();
    await act(async () => finish({ enabled: true, items: [task] }));
    expect(screen.queryByText('Agencies')).not.toBeInTheDocument();
  });
});

it('shows first-load failure rather than silently hiding an unavailable service', async () => {
  vi.spyOn(newAuth, 'makeRequest').mockRejectedValue(new Error('offline'));
  render(<OutreachContinuation businessId="b" />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить задачи');
  vi.restoreAllMocks();
});

it('provides recovery for interrupted drafting while keeping resume blocked', async () => {
  const request = vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [{ ...task, state: { started: true, blocker: 'campaign_result_uncertain', campaign_results: { ws: { status: 'preparing' } } } }] });
  render(<OutreachContinuation businessId="b" />);
  await userEvent.click(await screen.findByRole('button', { name: 'Сверить и повторить прерванные шаги' }));
  expect(request).toHaveBeenCalledWith('/partnership/continuations/task-1', { method: 'POST', body: JSON.stringify({ business_id: 'b', action: 'retry_failed', revision: 'revision-1' }) });
  expect(screen.queryByRole('button', { name: 'Продолжить подготовку' })).not.toBeInTheDocument();
  vi.restoreAllMocks();
});

it('shows shortage replenishment only when this business supports it', async () => {
  vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, supports_shortage_replenishment: true, items: [] });
  render(<OutreachContinuation businessId="riderra" />);
  await userEvent.click(await screen.findByRole('button', { name: 'Настроить поиск' }));
  const option = screen.getByRole('checkbox', { name: 'Пополнять базу только при нехватке готовых кандидатов Riderra' });
  expect(option).not.toBeChecked();
  await userEvent.click(option);
  expect(option).toBeChecked();
  vi.restoreAllMocks();
});
