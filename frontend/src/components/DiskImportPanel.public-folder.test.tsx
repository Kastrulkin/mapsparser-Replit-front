import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { DiskImportPanel } from './DiskImportPanel';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('prepares a public Yandex folder for the selected business without sending or enabling it', async () => {
  const fetcher = vi.fn((_url: RequestInfo | URL, options?: RequestInit) => Promise.resolve(new Response(JSON.stringify(options?.method === 'POST' ? {} : { enabled: true, can_configure: true, sources: [] }))));
  vi.stubGlobal('fetch', fetcher);
  render(<DiskImportPanel businessId="client" />);
  await userEvent.type(await screen.findByLabelText('Ссылка на папку Яндекс Диска'), 'https://disk.360.yandex.ru/d/example');
  await userEvent.click(screen.getByRole('button', { name: 'Подготовить папку' }));
  const call = fetcher.mock.calls.find(candidate => candidate[1]?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ business_id: 'client', provider: 'yandex', folder_url: 'https://disk.360.yandex.ru/d/example' });
  expect(fetcher.mock.calls.filter(candidate => candidate[1]?.method === 'POST')).toHaveLength(1);
  expect(String(call?.[0]).endsWith('/prepare')).toBe(true);
});
it('does not expose setup for participants', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ enabled: true, can_configure: false, sources: [] })))));
  render(<DiskImportPanel businessId="client" />);
  await screen.findByText('Материалы с Диска');
  expect(screen.queryByLabelText('Ссылка на папку Яндекс Диска')).not.toBeInTheDocument();
});
it('does not leak a previous business after switching', async () => {
  let resolveOld: (value: Response) => void = () => {};
  vi.stubGlobal('fetch', vi.fn((url: RequestInfo | URL) => String(url).includes('business_id=old') ? new Promise<Response>(resolve => { resolveOld = resolve; }) : Promise.resolve(new Response(JSON.stringify({ enabled: true, can_configure: false, sources: [] })))));
  const view = render(<DiskImportPanel businessId="old" />);
  view.rerender(<DiskImportPanel businessId="new" />);
  resolveOld(new Response(JSON.stringify({ enabled: true, can_configure: true, sources: [] })));
  await waitFor(() => expect(screen.getByText('Материалы с Диска')).toBeInTheDocument());
  expect(screen.queryByLabelText('Ссылка на папку Яндекс Диска')).not.toBeInTheDocument();
});
