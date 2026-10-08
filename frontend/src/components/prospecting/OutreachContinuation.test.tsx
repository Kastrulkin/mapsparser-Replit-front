import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { newAuth } from '@/lib/auth_new';
import { OutreachContinuation } from './OutreachContinuation';

afterEach(() => vi.restoreAllMocks());

const presentation = { phase: 'companies', status: 'ready', label: 'Ожидает запуска', active: false, next_action: { kind: 'control', action: 'start', label: 'Начать поиск' }, metrics: { found: 0, eligible: 0, target: 10, needs_decision: 0, prepared: 0, queued: 0, sent: 0, replies: 0 }, expenses: { charged: 0 } };
const task = { presentation, id: 'task-1', revision: 'revision-1', stage: 'Проверьте план', status: 'waiting_for_review', config: { audience: 'Agencies', offer: 'Transfers', language: 'en', queries: [{ query: 'agency', city: 'Delhi' }], max_search_calls: 1, max_candidates: 5, batch_size: 5, search_budget_cents: 100 }, state: {} };
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
      if (path === '/operator/actions/approval-1/confirm') return { operator_result: { status: 'completed', task: { id: 'created-task' } } };
      return { enabled: true, items: [] };
    });
    const onTaskConfirmed = vi.fn();
    render(<OutreachContinuation businessId="b" onTaskConfirmed={onTaskConfirmed} />);
    await userEvent.click(await screen.findByRole('button', { name: 'Новый поиск' }));
    await userEvent.click(screen.getByRole('radio', { name: 'Контакты подходящих компаний или специалистов' }));
    await userEvent.type(screen.getByLabelText('Кого ищем'), 'Travel agencies selling Phuket');
    await userEvent.clear(screen.getByLabelText('Сколько найти'));
    await userEvent.type(screen.getByLabelText('Сколько найти'), '10');
    await userEvent.type(screen.getByLabelText('Требования'), 'Продают туры на Пхукет');
    await userEvent.type(screen.getByLabelText('Поисковый запрос'), 'travel agency Phuket');
    await userEvent.type(screen.getByLabelText('Где ищем'), 'India');
    await userEvent.click(screen.getByRole('button', { name: 'Проверить план' }));
    expect(await screen.findByText(/Ориентир расходов — до 65 кредитов/)).toBeInTheDocument();
    expect(request).not.toHaveBeenCalledWith('/operator/actions/approval-1/confirm', expect.anything());
    await userEvent.click(screen.getByRole('button', { name: 'Начать новый поиск' }));
    expect(request).toHaveBeenCalledWith('/operator/actions/approval-1/confirm', expect.objectContaining({ method: 'POST' }));
    expect(onTaskConfirmed).toHaveBeenCalledWith('created-task');
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
      presentation: { ...presentation, status: 'completed', label: 'Результаты готовы', next_action: { kind: 'link', label: 'Посмотреть компании', href: '/dashboard/partnerships?business_id=b&search_task_id=task-1&section=companies' }, metrics: { ...presentation.metrics, found: 10, target: 2, needs_decision: 3 } },
      config: { ...task.config, target_count: 2, mode: 'find_only' },
      stage: 'Поиск завершён с недобором; проверьте причины и результаты',
      report: { found: 10, imported: 3, eligible: 0, excluded: 10, duplicates: 7, credits_charged: 9, credit_limit: 15, credit_estimate_only: true },
      state: { search_calls: 1 },
    }] });
    render(<OutreachContinuation businessId="b" />);
    expect(await screen.findByText('Результаты готовы')).toBeVisible();
    expect(screen.getByText('Найдено кандидатов').nextElementSibling).toHaveTextContent('10');
    expect(screen.getByText('Нужно решение').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('Подтверждены · цель').nextElementSibling).toHaveTextContent('0 / 2');
    expect(screen.getByRole('link', { name: 'Посмотреть компании' })).toHaveAttribute('href', '/dashboard/partnerships?business_id=b&search_task_id=task-1&section=companies');
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
    expect(await screen.findByText('Нужны новые условия поиска')).toBeInTheDocument();
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

it('does not replay interrupted drafting before reconciliation', async () => {
  vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [{ ...task, presentation: { ...presentation, next_action: { kind: 'link', label: 'Посмотреть компании', href: '/dashboard/partnerships' } }, state: { started: true, blocker: 'campaign_result_uncertain', campaign_results: { ws: { status: 'preparing' } } } }] });
  render(<OutreachContinuation businessId="b" />);
  await screen.findByRole('link', { name: 'Посмотреть компании' });
  expect(screen.queryByRole('button', { name: 'Повторить неудавшиеся проверки' })).not.toBeInTheDocument();
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
    presentation: { ...presentation, expenses: { charged: 0, estimate: 65, estimate_only: true } },
    report: { credits_charged: 0, credit_limit: 65, credit_estimate_only: true },
    state: { started: true, inflight_search: true, search_credit_reservation_id: 'reservation' },
  }] });
  render(<OutreachContinuation businessId="b" />);
  expect(await screen.findByText(/оценка до 65 кр./)).toBeVisible();
  expect(screen.queryByRole('button', { name: /Учесть поиск/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Остановить поиск' })).not.toBeInTheDocument();
  vi.restoreAllMocks();
});

it('find-only does not require an offer and retains the qualified target in the saved plan', async () => {
  const request = vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [] });
  render(<OutreachContinuation businessId="b" />);
  await userEvent.click(await screen.findByRole('button', { name: 'Новый поиск' }));
  await userEvent.click(screen.getByRole('radio', { name: 'Контакты подходящих компаний или специалистов' }));
  expect(screen.queryByLabelText('Что предлагаем')).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Кого ищем'), 'Travel agencies');
  await userEvent.type(screen.getByLabelText('Поисковый запрос'), 'Travel agency');
  await userEvent.type(screen.getByLabelText('Где ищем'), 'Delhi');
  await userEvent.click(screen.getByRole('button', { name: 'Проверить план' }));
  const saved = request.mock.calls.find(([path, options]) => path === '/partnership/continuations' && options?.method === 'POST');
  expect(saved).toBeDefined();
  const payload = JSON.parse(String(saved?.[1]?.body));
  expect(payload.config.mode).toBe('find_only');
  expect(payload.config.target_count).toBe(10);
  expect(payload.config.offer).toBe('');
  expect(payload.config.billing_mode).toBe('shared_balance_actual');
  expect(payload.config.search_call_cap_cents).toBe(50);
  vi.restoreAllMocks();
});
it('compact overview keeps reading all groups but never silently chooses one', async () => {
  const onTasksChange = vi.fn();
  const request = vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [task] });
  render(<OutreachContinuation compact businessId="b" onTasksChange={onTasksChange} />);
  await screen.findByRole('button', { name: 'Новый поиск' });
  expect(screen.queryByText('Agencies')).not.toBeInTheDocument();
  expect(onTasksChange).toHaveBeenCalledWith([task]);
  expect(request).toHaveBeenCalledTimes(1);
  vi.restoreAllMocks();
});

 it('opens saved conditions immediately and restores focus on Escape', async () => {
    const request = vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [task] });
    render(<OutreachContinuation businessId="b" />);
    const edit = await screen.findByRole('button', { name: 'Изменить условия поиска' });
    await userEvent.click(edit);
    expect(screen.getByRole('dialog')).toBeVisible();
    expect(screen.getByLabelText('Кого ищем')).toHaveValue('Agencies');
    expect(screen.queryByLabelText('Какое направление они продают')).not.toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(1);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(edit).toHaveFocus();
    vi.restoreAllMocks();
 });

it('submits changed geography and requirements and labels a new search explicitly', async () => {
  const request = vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (path, options) => {
    if (options?.method === 'POST') {
      const body = JSON.parse(String(options.body));
      return { config: body.config, approval: { action_id: 'new-approval' }, credit_quote: { total_max: 30 }, creates_new_search: true };
    }
    return { enabled: true, items: [task] };
  });
  render(<OutreachContinuation businessId="b" />);
  await userEvent.click(await screen.findByRole('button', { name: 'Изменить условия поиска' }));
  await userEvent.clear(screen.getByLabelText('Кого ищем'));
  await userEvent.type(screen.getByLabelText('Кого ищем'), 'Сантехники');
  await userEvent.clear(screen.getByLabelText('Где ищем'));
  await userEvent.type(screen.getByLabelText('Где ищем'), 'Москва');
  await userEvent.type(screen.getByLabelText('Требования'), 'Выезжают на дом');
  await userEvent.click(screen.getByRole('button', { name: 'Проверить план' }));
  expect(await screen.findByText(/Будет создан новый поиск/)).toBeVisible();
  const calls = request.mock.calls.filter(([, options]) => options?.method === 'POST');
  const body = JSON.parse(String(calls[0][1]?.body));
  expect(body.config.search_geography).toEqual(['Москва']);
  expect(body.config.requirements).toEqual(['Выезжают на дом']);
  expect(body.config.queries).toEqual([]);
  expect(screen.getByRole('button', { name: 'Начать новый поиск' })).toBeVisible();
  vi.restoreAllMocks();
});
