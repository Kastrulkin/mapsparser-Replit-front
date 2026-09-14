import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { OperatorWorkdayInput } from './OperatorWorkdayInput';

const headers = () => ({ Authorization: 'Bearer test' });
const reply = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));
const config = { enabled: true, can_configure: true, version: 0, recipients: [{ id: 'owner', name: 'Александр' }] };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('uploads a file into the conversation without automatically executing a task', async () => {
  const user = userEvent.setup(); const selected = vi.fn();
  const fetcher = vi.fn((url: RequestInfo | URL, options?: RequestInit) => {
    if (String(url).includes('/workday/config')) return reply(config);
    if (String(url).includes('/disk/status')) return reply({ configured: false, connection: { status: 'disconnected' }, photos: [] });
    expect(String(url)).toBe('/api/operator/attachments');
    expect(options?.body).toBeInstanceOf(FormData);
    return reply({ attachment: { id: 'a' }, conversation_id: 'conversation' });
  });
  vi.stubGlobal('fetch', fetcher);
  render(<OperatorWorkdayInput businessId="b" channel="web" headers={headers} onConversation={selected} />);
  await screen.findByRole('button', { name: 'Фото или файл' });
  await user.upload(screen.getByLabelText('Фото или файл для Оператора'), new File(['time,service'], 'day.csv', { type: 'text/csv' }));
  await waitFor(() => expect(selected).toHaveBeenCalledWith('conversation'));
  expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/chat'))).toBe(false);
});

it('does not expose owner configuration to a manager', async () => {
  vi.stubGlobal('fetch', vi.fn((url: RequestInfo | URL) => String(url).includes('/workday/config') ? reply({ ...config, can_configure: false }) : reply({ configured: false, connection: { status: 'disconnected' }, photos: [] })));
  render(<OperatorWorkdayInput businessId="b" channel="web" headers={headers} onConversation={vi.fn()} />);
  await screen.findByRole('button', { name: 'Фото или файл' });
  expect(screen.queryByText('Настройки рабочего пилота')).not.toBeInTheDocument();
});

it('does not restore stale business settings after switching scope', async () => {
  let resolveOld: (value: Response) => void = () => {};
  vi.stubGlobal('fetch', vi.fn((url: RequestInfo | URL) => String(url).includes('business_id=old')
    ? new Promise<Response>(resolve => { resolveOld = resolve; }) : reply({ error: 'Нет доступа' }, 403)));
  const view = render(<OperatorWorkdayInput businessId="old" channel="web" headers={headers} onConversation={vi.fn()} />);
  view.rerender(<OperatorWorkdayInput businessId="new" channel="web" headers={headers} onConversation={vi.fn()} />);
  resolveOld(new Response(JSON.stringify(config)));
  await waitFor(() => expect(screen.queryByText('Настройки рабочего пилота')).not.toBeInTheDocument());
});
