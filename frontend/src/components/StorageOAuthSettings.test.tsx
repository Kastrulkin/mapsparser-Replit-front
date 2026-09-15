import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { StorageOAuthSettings } from './StorageOAuthSettings';
const item = { provider: 'google', name: 'Google Диск', client_id: 'client', secret_saved: false, version: 0, redirect_uri: 'https://localos.pro/api/operator/google-drive/callback' };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('saves credentials, clears the secret, and keeps it masked on read', async () => {
  const fetcher = vi.fn((_url: RequestInfo | URL, options?: RequestInit) => Promise.resolve(new Response(JSON.stringify({ encryption_ready: true, items: [{ ...item, secret_saved: options?.method === 'POST', version: options?.method === 'POST' ? 1 : 0 }] }))));
  vi.stubGlobal('fetch', fetcher);
  render(<MemoryRouter><StorageOAuthSettings /></MemoryRouter>);
  const field = await screen.findByLabelText('Client Secret · Google Диск');
  await userEvent.type(field, 'private-secret');
  await userEvent.click(screen.getByRole('button', { name: 'Сохранить Google Диск' }));
  await waitFor(() => expect(field).toHaveValue(''));
  expect(field).toHaveAttribute('type', 'password');
  expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).toMatchObject({ client_secret: 'private-secret', version: 0 });
  expect(screen.getByText('Сохранено.', { exact: false })).toBeInTheDocument();
});
it('hides credential forms on permission failure', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ error: 'Только администратор' }), { status: 403 }))));
  render(<MemoryRouter><StorageOAuthSettings /></MemoryRouter>);
  await screen.findByRole('alert');
  expect(screen.queryByLabelText('Client Secret · Google Диск')).not.toBeInTheDocument();
});
