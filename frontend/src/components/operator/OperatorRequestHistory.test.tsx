import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { OperatorRequestHistory } from './OperatorRequestHistory';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const response = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));
const entry = { id: 'one', input_summary: 'Покажи следующий пост', output_summary: '', status: 'failed', reason_code: 'execution',
  metadata_json: { operator_channel: 'telegram', input_type: 'voice' }, created_at: '2026-09-13T10:00:00Z' };

it('shows a failed input and records feedback without executing chat', async () => {
  const calls = vi.fn((url: RequestInfo | URL) => String(url).endsWith('/feedback') ? response({ status: 'recorded' })
    : String(url).includes('/requests/one') ? response(entry) : response({ items: [entry], next_offset: null }));
  vi.stubGlobal('fetch', calls);
  const user = userEvent.setup();
  render(<OperatorRequestHistory businessId="b" />);
  await user.click(screen.getByText('История обращений'));
  await user.click(await screen.findByText('Покажи следующий пост'));
  expect(await screen.findByText(/Сохранённого ответа пока нет/)).toBeInTheDocument();
  await user.type(screen.getByLabelText('Оператор понял неправильно'), 'Нужен ближайший неопубликованный пост');
  await user.click(screen.getByText('Сохранить замечание'));
  expect(await screen.findByText(/Замечание сохранено/)).toBeInTheDocument();
  expect(calls.mock.calls.every(([url]) => !String(url).includes('/chat'))).toBe(true);
});

it('removes private content when access is revoked', async () => {
  let revoked = false;
  vi.stubGlobal('fetch', vi.fn(() => revoked ? response({ error: 'Нет доступа' }, 403) : response({ items: [entry], next_offset: null })));
  const user = userEvent.setup();
  render(<OperatorRequestHistory businessId="b" />);
  await user.click(screen.getByText('История обращений'));
  await screen.findByText('Покажи следующий пост');
  revoked = true;
  await user.click(screen.getByText('Обновить'));
  await waitFor(() => expect(screen.queryByText('Покажи следующий пост')).not.toBeInTheDocument());
  expect(await screen.findByRole('alert')).toHaveTextContent('Нет доступа');
});

it('uses English fallback for the expanded history in other languages', async () => {
  vi.stubGlobal('fetch', vi.fn(() => response({ items: [], next_offset: null })));
  const user = userEvent.setup();
  const { container } = render(<OperatorRequestHistory businessId="b" language="el" />);
  await user.click(screen.getByText('Ιστορικό αιτημάτων'));
  await screen.findByText(/No requests yet/);
  expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
});
