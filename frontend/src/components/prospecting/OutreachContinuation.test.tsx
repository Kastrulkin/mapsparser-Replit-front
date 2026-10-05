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
    expect(screen.queryByText('Новый поиск')).not.toBeInTheDocument();
    expect(request).toHaveBeenCalledWith('/partnership/continuations?business_id=b');
    expect(request).toHaveBeenCalledTimes(1);
  });
  it('starts only after explicit review action with current revision', async () => {
    const request = vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [task] });
    render(<OutreachContinuation businessId="b" />);
    await userEvent.click(await screen.findByRole('button', { name: 'Начать поиск' }));
    expect(request).toHaveBeenCalledWith('/partnership/continuations/task-1', { method: 'POST', body: JSON.stringify({ business_id: 'b', action: 'start', revision: 'revision-1' }) });
  });
  it('previews a new search and starts it with one confirmation', async () => {
    const request = vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (path, options) => {
      if (path === '/partnership/continuations' && options?.method === 'POST') return {
        config: { target_count: 10, agency_country: 'India', sold_destination: 'Phuket', mode: 'find_only' },
        credit_quote: { total_max: 65 }, approval: { action_id: 'approval-1' },
      };
      if (path === '/operator/actions/approval-1/confirm') return { operator_result: { status: 'completed' } };
      return { enabled: true, items: [] };
    });
    render(<OutreachContinuation businessId="b" />);
    await userEvent.click(await screen.findByRole('button', { name: 'Новый поиск' }));
    await userEvent.click(screen.getByRole('radio', { name: 'Только найти и проверить компании' }));
    await userEvent.type(screen.getByLabelText('Кого ищем'), 'Travel agencies selling Phuket');
    await userEvent.clear(screen.getByLabelText('Сколько новых подходящих компаний найти'));
    await userEvent.type(screen.getByLabelText('Сколько новых подходящих компаний найти'), '10');
    await userEvent.type(screen.getByLabelText('Страна компаний'), 'India');
    await userEvent.type(screen.getByLabelText('Какое направление они продают'), 'Phuket');
    await userEvent.type(screen.getByLabelText('Поисковый запрос'), 'travel agency Phuket');
    await userEvent.type(screen.getByLabelText('Города поиска — по одному на строку'), 'India');
    await userEvent.click(screen.getByRole('button', { name: 'Проверить план' }));
    expect(await screen.findByText(/Ориентир расходов — до 65 кредитов/)).toBeInTheDocument();
    expect(request).not.toHaveBeenCalledWith('/operator/actions/approval-1/confirm', expect.anything());
    await userEvent.click(screen.getByRole('button', { name: 'Начать поиск' }));
    expect(request).toHaveBeenCalledWith('/operator/actions/approval-1/confirm', expect.objectContaining({ method: 'POST' }));
  });
  it('shares the saved search membership with the candidate list', async () => {
    const onTasksChange = vi.fn();
    vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [{ ...task, state: { lead_ids: ['lead-1'] } }] });
    render(<OutreachContinuation businessId="b" onTasksChange={onTasksChange} />);
    await act(async () => {});
    expect(onTasksChange).toHaveBeenCalledWith([expect.objectContaining({ id: 'task-1', state: { lead_ids: ['lead-1'] } })]);
  });
  it('separates raw results from confirmed partners and keeps completed shortfall actionable', async () => {
    vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [{
      ...task,
      status: 'completed',
      config: { ...task.config, target_count: 2, mode: 'find_only' },
      stage: 'Поиск завершён с недобором; проверьте причины и результаты',
      report: { found: 10, imported: 3, eligible: 0, excluded: 10, duplicates: 7, credits_charged: 9, credit_limit: 15, credit_estimate_only: true },
      state: { search_calls: 1 },
    }] });
    render(<OutreachContinuation businessId="b" />);
    expect(await screen.findByText('Завершён · недобор')).toBeVisible();
    expect(screen.getByText('Найдено всего').previousElementSibling).toHaveTextContent('10');
    expect(screen.getByText('Новые кандидаты').previousElementSibling).toHaveTextContent('3');
    expect(screen.getByText('Подтверждены · цель').previousElementSibling).toHaveTextContent('0 / 2');
    expect(screen.getByRole('link', { name: 'Посмотреть кандидатов' })).toHaveAttribute('href', '/dashboard/partnerships?business_id=b&search_task_id=task-1');
    expect(screen.queryByText('Условия поручения')).not.toBeInTheDocument();
  });
  it('offers explicit reconciliation instead of impossible resume', async () => {
    vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [{ ...task, state: { started: true, inflight_search: true, blocker: 'search_result_uncertain' } }] });
    render(<OutreachContinuation businessId="b" />);
    expect(await screen.findByRole('button', { name: 'Учесть поиск и списать до 10 кредитов' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Продолжить поиск' })).not.toBeInTheDocument();
  });
  it('does not offer a retry while the provider minimum exceeds the approved limit', async () => {
    vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [{ ...task,
      stage: 'Нужны новые условия поиска',
      state: { started: true, inflight_search: false, blocker: 'search_provider_minimum_exceeds_call_limit' },
    }] });
    render(<OutreachContinuation businessId="b" />);
    expect(await screen.findByText('Нужны новые условия поиска')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Продолжить поиск' })).not.toBeInTheDocument();
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
  await userEvent.click(await screen.findByRole('button', { name: 'Повторить неудавшиеся проверки' }));
  expect(request).toHaveBeenCalledWith('/partnership/continuations/task-1', { method: 'POST', body: JSON.stringify({ business_id: 'b', action: 'retry_failed', revision: 'revision-1' }) });
  expect(screen.queryByRole('button', { name: 'Продолжить поиск' })).not.toBeInTheDocument();
  vi.restoreAllMocks();
});

it('shows shortage replenishment only when this business supports it', async () => {
  vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, supports_shortage_replenishment: true, items: [] });
  render(<OutreachContinuation businessId="riderra" />);
  await userEvent.click(await screen.findByRole('button', { name: 'Новый поиск' }));
  const option = screen.getByRole('checkbox', { name: 'Пополнять базу только при нехватке готовых кандидатов Riderra' });
  expect(option).not.toBeChecked();
  await userEvent.click(option);
  expect(option).toBeChecked();
  vi.restoreAllMocks();
});

it('explains shared-balance actual billing and hides estimate-only settlement', async () => {
  vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [{ ...task,
    config: { ...task.config, billing_mode: 'shared_balance_actual', search_call_cap_cents: 50 },
    report: { credits_charged: 0, credit_limit: 65, credit_estimate_only: true },
    state: { started: true, inflight_search: true, search_credit_reservation_id: 'reservation' },
  }] });
  render(<OutreachContinuation businessId="b" />);
  expect(await screen.findByText(/ориентир до 65 кр./)).toBeVisible();
  expect(screen.queryByRole('button', { name: /Учесть поиск/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Остановить поиск' })).not.toBeInTheDocument();
  vi.restoreAllMocks();
});

it('find-only does not require an offer and retains the qualified target in the saved plan', async () => {
  const request = vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [] });
  render(<OutreachContinuation businessId="b" />);
  await userEvent.click(await screen.findByRole('button', { name: 'Новый поиск' }));
  await userEvent.click(screen.getByRole('radio', { name: 'Только найти и проверить компании' }));
  expect(screen.queryByLabelText('Что предлагаем')).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Кого ищем'), 'Travel agencies');
  await userEvent.type(screen.getByLabelText('Поисковый запрос'), 'Travel agency');
  await userEvent.type(screen.getByLabelText('Города поиска — по одному на строку'), 'Delhi');
  await userEvent.click(screen.getByRole('button', { name: 'Проверить план' }));
  const saved = request.mock.calls.find(([path, options]) => path === '/partnership/continuations' && options?.method === 'POST');
  expect(saved).toBeDefined();
  const payload = JSON.parse(String(saved?.[1]?.body));
  expect(payload.config.mode).toBe('find_only');
  expect(payload.config.target_count).toBe(100);
  expect(payload.config.offer).toBe('');
  expect(payload.config.billing_mode).toBe('shared_balance_actual');
  expect(payload.config.search_call_cap_cents).toBe(50);
  vi.restoreAllMocks();
});
