import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { DiskImportPanel } from './DiskImportPanel';
import { ExternalDriveVideos } from './ExternalDriveVideos';
import { GoogleDriveReaderSettings } from './GoogleDriveReaderSettings';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const source = { id: 's', provider: 'google', root_name: 'Работы', root_url: 'https://drive.google.com/drive/folders/f', version: 2, state: 'ready', counts: [] };
it('stays hidden when the backend route is not deployed yet', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ error: 'Not Found' }), { status: 404 }))));
  render(<DiskImportPanel businessId="b" />);
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByRole('region', { name: 'Материалы с Диска' })).not.toBeInTheDocument();
  expect(screen.queryByText('Not Found')).not.toBeInTheDocument();
});
it('shows one explicit enable action after folder verification', async () => {
  const fetcher = vi.fn((_url: RequestInfo | URL, options?: RequestInit) => Promise.resolve(new Response(JSON.stringify(options?.method === 'POST' ? source : { can_configure: true, sources: [source] }))));
  vi.stubGlobal('fetch', fetcher); render(<DiskImportPanel businessId="b" />);
  await userEvent.click(await screen.findByRole('button', { name: 'Включить автоматическое добавление' }));
  const call = fetcher.mock.calls.find(candidate => candidate[1]?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ business_id: 'b', source_id: 's', version: 2, action: 'enable' });
});
it('participants can see state without source configuration controls', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ can_configure: false, sources: [{ ...source, state: 'active' }] })))));
  render(<DiskImportPanel businessId="b" />); await screen.findByText('Импорт включён');
  expect(screen.queryByText('Подключить папку')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Отключить' })).not.toBeInTheDocument();
});
it('does not leak a previous business response after navigation', async () => {
  let resolveOld: (value: Response) => void = () => {};
  vi.stubGlobal('fetch', vi.fn((url: RequestInfo | URL) => String(url).includes('business_id=old') ? new Promise<Response>(resolve => { resolveOld = resolve; }) : Promise.resolve(new Response(JSON.stringify({ can_configure: false, sources: [] })))));
  const view = render(<DiskImportPanel businessId="old" />); view.rerender(<DiskImportPanel businessId="new" />);
  resolveOld(new Response(JSON.stringify({ can_configure: true, sources: [source] })));
  await screen.findByText('Материалы с Диска'); expect(screen.queryByText('Google Диск · Работы')).not.toBeInTheDocument();
});
it('selects external video with a version and a manual path only', async () => {
  const video = { id: 'v', name: 'Работа.mp4', original_url: 'https://drive.google.com/file/d/v/view', available: true };
  const fetcher = vi.fn((_url: RequestInfo | URL, options?: RequestInit) => Promise.resolve(new Response(JSON.stringify({ videos: [video], selected: options?.method === 'POST' ? [video] : [], item_version: 'v1' }))));
  vi.stubGlobal('fetch', fetcher); render(<ExternalDriveVideos businessId="b" itemId="item" />);
  await userEvent.click(await screen.findByRole('checkbox')); await userEvent.click(screen.getByRole('button', { name: 'Сохранить выбор видео' }));
  await waitFor(() => expect(fetcher.mock.calls.some(call => call[1]?.method === 'POST')).toBe(true));
  const call = fetcher.mock.calls.find(candidate => candidate[1]?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ item_version: 'v1', video_ids: ['v'], business_id: 'b' });
  expect(screen.getByText(/Выбранные видео публикуются вручную/)).toBeInTheDocument();
  expect(fetcher.mock.calls.every(call => !String(call[0]).includes('/publish'))).toBe(true);
});
it('clears uploaded service-account key after saving', async () => {
  vi.stubGlobal('fetch', vi.fn((_url: RequestInfo | URL, options?: RequestInit) => Promise.resolve(new Response(JSON.stringify({ configured: options?.method === 'POST', client_email: 'reader@test.iam.gserviceaccount.com', version: options?.method === 'POST' ? 1 : 0 })))));
  render(<GoogleDriveReaderSettings />);
  const input = await screen.findByLabelText('JSON-ключ служебного аккаунта');
  const file = new File(['{}'], 'reader.json', { type: 'application/json' });
  Object.defineProperty(file, 'text', { value: async () => '{}' });
  await userEvent.upload(input, file); await userEvent.click(screen.getByRole('button', { name: 'Сохранить служебный аккаунт' }));
  await screen.findByText(/Ключ сохранён зашифрованным/); expect(input).toHaveValue('');
});
