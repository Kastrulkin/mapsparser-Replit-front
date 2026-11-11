import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { PartnershipsMobileModule } from './PartnershipsMobileModule';

const response = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
const workspace = { items: [{ id: 'reply-1', lead_name: 'Компания один', business_name: 'Первый бизнес', channel: 'email', reply_text: 'Готовы обсудить сотрудничество' }], searches: [], senders: [], cursor: 'reply-1', readiness: { search_enabled: true, web_enabled: true, yandex_enabled: false, sync_enabled: true } };
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

it('opens all-business outreach directly and loads the next page without selecting a business', async () => {
  const fetch = vi.fn((input: RequestInfo | URL) => String(input).includes('?cursor=') ? response({ ...workspace, cursor: null, items: [{ id: 'reply-2', business_name: 'Второй бизнес', channel: 'vk', reply_text: 'Пришлите условия' }] }) : response(workspace));
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<PartnershipsMobileModule scope={{ kind: 'platform' }} />);
  expect(await screen.findByText('Готовы обсудить сотрудничество')).toBeInTheDocument();
  expect(screen.queryByText(/сначала выберите конкретный бизнес/)).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Ещё ответы' }));
  expect(await screen.findByText('Пришлите условия')).toBeInTheDocument();
  expect(screen.getByText('Готовы обсудить сотрудничество')).toBeInTheDocument();
  expect(fetch.mock.calls.every(([url]) => String(url).startsWith('/api/operator/mobile/platform/outreach'))).toBe(true);
});

it('shows exact search terms before confirming through the existing action endpoint', async () => {
  let started = false;
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/actions/approval-1/confirm')) { started = true; return response({ operator_result: { status: 'completed', job_id: 'search-1', chat_response: 'Поиск запущен.' } }); }
    if (init?.method === 'POST') return response({ business_id: 'system-localos', operator_result: { status: 'approval_required', chat_response: 'Пафос · 10 компаний · до 53 кредитов. Поиск ещё не запущен.', approval: { action_id: 'approval-1' } } });
    return response({ ...workspace, searches: started ? [{ id: 'search-1', business_id: 'system-localos', audience: 'Салоны красоты', stage: 'Ищем компании', status: 'queued' }] : [] });
  });
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<PartnershipsMobileModule scope={{ kind: 'platform' }} />);
  await user.click(await screen.findByRole('button', { name: 'Новый поиск' }));
  await user.type(screen.getByLabelText('Кого ищем'), 'Салоны красоты');
  await user.type(screen.getByLabelText('Где ищем'), 'Пафос');
  await user.click(screen.getByRole('button', { name: 'Показать условия и стоимость' }));
  expect(await screen.findByText(/до 53 кредитов/)).toBeInTheDocument();
  expect(started).toBe(false);
  const prepare = fetch.mock.calls.find(([, init]) => init?.body && String(init.body).includes('search_preview'));
  expect(JSON.parse(String(prepare?.[1]?.body))).toMatchObject({ audience: 'Салоны красоты', search_geography: ['Пафос'], target_count: 10 });
  await user.click(screen.getByRole('button', { name: 'Подтвердить запуск поиска' }));
  expect(await screen.findByText('Ищем компании')).toBeInTheDocument();
  const confirm = fetch.mock.calls.find(([url]) => String(url).endsWith('/actions/approval-1/confirm'));
  expect(JSON.parse(String(confirm?.[1]?.body))).toEqual({ business_id: 'system-localos' });
});

it('queues reply collection and reports a partial channel failure', async () => {
  vi.useFakeTimers();
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).includes('/mobile/jobs/')) return response({ job: { id: 'sync-1', terminal: true, status: 'completed', result: { sync_status: 'partial' } } });
    if (init?.method === 'POST') return response({ job: { id: 'sync-1', terminal: false, status: 'queued' } });
    return response(workspace);
  });
  vi.stubGlobal('fetch', fetch);
  render(<PartnershipsMobileModule scope={{ kind: 'platform' }} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  await act(async () => { screen.getByRole('button', { name: 'Проверить входящие' }).click(); });
  expect(screen.getByRole('button', { name: 'Проверяем входящие…' })).toBeDisabled();
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect(screen.getByText('Часть каналов не удалось обновить. Доступные ответы показаны ниже.')).toBeInTheDocument();
  expect(screen.getByText('Готовы обсудить сотрудничество')).toBeInTheDocument();
});

it('removes private replies when an update is forbidden', async () => {
  const fetch = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => init?.method === 'POST' ? response({ success: false, error: 'Доступ отозван' }, 403) : response(workspace));
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<PartnershipsMobileModule scope={{ kind: 'platform' }} />);
  expect(await screen.findByText('Готовы обсудить сотрудничество')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Проверить входящие' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Доступ отозван');
  expect(screen.queryByText('Готовы обсудить сотрудничество')).not.toBeInTheDocument();
});
