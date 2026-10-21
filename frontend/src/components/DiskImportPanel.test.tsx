import '@testing-library/jest-dom/vitest';
import type { ReactNode } from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { LanguageContext, type Language } from '@/i18n/LanguageContext.logic';
import { en } from '@/i18n/locales/en';
import { DiskImportPanel } from './DiskImportPanel';
import { ExternalDriveVideos } from './ExternalDriveVideos';
import { GoogleDriveReaderSettings } from './GoogleDriveReaderSettings';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const source = { id: 's', provider: 'google', root_name: 'Работы', root_url: 'https://drive.google.com/drive/folders/f', version: 2, state: 'ready', counts: [] };
const withLanguage = (element: ReactNode, language: Language = 'ru') => <LanguageContext.Provider value={{ language, setLanguage: vi.fn(), t: en }}>{element}</LanguageContext.Provider>;
it('lets an owner prepare a public Yandex folder without an OAuth connection or a send', async () => {
  const fetcher = vi.fn((_url: RequestInfo | URL, options?: RequestInit) => Promise.resolve(new Response(JSON.stringify(options?.method === 'POST' ? {} : { enabled: true, can_configure: true, sources: [] }))));
  vi.stubGlobal('fetch', fetcher);
  render(withLanguage(<DiskImportPanel businessId="b" />));
  await userEvent.type(await screen.findByLabelText('Ссылка на папку Яндекс Диска'), 'https://disk.360.yandex.ru/d/example');
  await userEvent.click(screen.getByRole('button', { name: 'Подготовить папку' }));
  const call = fetcher.mock.calls.find(candidate => candidate[1]?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ business_id: 'b', provider: 'yandex', folder_url: 'https://disk.360.yandex.ru/d/example' });
  expect(fetcher.mock.calls.every(candidate => !String(candidate[0]).includes('/publish') && !String(candidate[0]).includes('/send'))).toBe(true);
});
it('stays hidden when the backend route is not deployed yet', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ error: 'Not Found' }), { status: 404 }))));
  render(withLanguage(<DiskImportPanel businessId="b" />));
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByRole('region', { name: 'Материалы с Диска' })).not.toBeInTheDocument();
  expect(screen.queryByText('Not Found')).not.toBeInTheDocument();
});
it('shows one explicit enable action after folder verification', async () => {
  const fetcher = vi.fn((_url: RequestInfo | URL, options?: RequestInit) => Promise.resolve(new Response(JSON.stringify(options?.method === 'POST' ? source : { can_configure: true, sources: [source] }))));
  vi.stubGlobal('fetch', fetcher); render(withLanguage(<DiskImportPanel businessId="b" />));
  await userEvent.click(await screen.findByRole('button', { name: 'Включить автоматическое добавление' }));
  const call = fetcher.mock.calls.find(candidate => candidate[1]?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ business_id: 'b', source_id: 's', version: 2, action: 'enable' });
});
it('participants can see state without source configuration controls', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ can_configure: false, sources: [{ ...source, state: 'active' }] })))));
  render(withLanguage(<DiskImportPanel businessId="b" />)); await screen.findByText('Импорт включён');
  expect(screen.queryByText('Подключить папку')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Отключить' })).not.toBeInTheDocument();
});
it('does not leak a previous business response after navigation', async () => {
  let resolveOld: (value: Response) => void = () => {};
  vi.stubGlobal('fetch', vi.fn((url: RequestInfo | URL) => String(url).includes('business_id=old') ? new Promise<Response>(resolve => { resolveOld = resolve; }) : Promise.resolve(new Response(JSON.stringify({ can_configure: false, sources: [] })))));
  const view = render(withLanguage(<DiskImportPanel businessId="old" />)); view.rerender(withLanguage(<DiskImportPanel businessId="new" />));
  resolveOld(new Response(JSON.stringify({ can_configure: true, sources: [source] })));
  await screen.findByText('Материалы с Диска'); expect(screen.queryByText('Google Диск · Работы')).not.toBeInTheDocument();
});
it('selects external video with a version and a manual path only', async () => {
  const video = { id: 'v', name: 'Работа.mp4', original_url: 'https://drive.google.com/file/d/v/view', available: true };
  const fetcher = vi.fn((_url: RequestInfo | URL, options?: RequestInit) => Promise.resolve(new Response(JSON.stringify({ videos: [video], selected: options?.method === 'POST' ? [video] : [], item_version: 'v1' }))));
  vi.stubGlobal('fetch', fetcher); render(withLanguage(<ExternalDriveVideos businessId="b" itemId="item" />));
  await userEvent.click(await screen.findByRole('checkbox')); await userEvent.click(screen.getByRole('button', { name: 'Сохранить выбор видео' }));
  await waitFor(() => expect(fetcher.mock.calls.some(call => call[1]?.method === 'POST')).toBe(true));
  const call = fetcher.mock.calls.find(candidate => candidate[1]?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ item_version: 'v1', video_ids: ['v'], business_id: 'b' });
  expect(screen.getByText(/Выбранные видео публикуются вручную/)).toBeInTheDocument();
  expect(fetcher.mock.calls.every(call => !String(call[0]).includes('/publish'))).toBe(true);
});
it('shows the active disk import and adjacent video sections in Armenian', async () => {
  const activeSource = { ...source, provider: 'yandex', root_name: 'Աշխատանքներ', state: 'active', error_code: 'retry_pending', last_checked_at: '2026-10-12T12:01:40Z', counts: [{ status: 'imported', count: 10 }, { status: 'pending', count: 1 }] };
  const fetcher = vi.fn((url: RequestInfo | URL) => Promise.resolve(new Response(JSON.stringify(String(url).includes('/videos')
    ? { videos: [], selected: [], item_version: '', warnings: [] }
    : { enabled: true, can_configure: true, sources: [activeSource] }))));
  vi.stubGlobal('fetch', fetcher);
  render(withLanguage(<><DiskImportPanel businessId="b" /><ExternalDriveVideos businessId="b" /></>, 'hy'));
  const panel = await screen.findByRole('region', { name: 'Նյութեր Դիսկից' });
  expect(panel).toHaveTextContent('Ներմուծումը միացված է');
  expect(panel).toHaveTextContent('Ժամանակավոր սխալ․ ստուգումը կկրկնենք');
  expect(panel).toHaveTextContent('Ավելացվել է: 10');
  expect(panel).toHaveTextContent('Սպասում է մշակման: 1');
  expect(screen.getByRole('button', { name: 'Ստուգել հիմա' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Դադարեցնել' })).toBeInTheDocument();
  expect(await screen.findByText('Տեսանյութեր Դիսկից')).toBeInTheDocument();
  expect(screen.getByText(/Բնօրինակները պահվում են Դիսկում/)).toBeInTheDocument();
  expect(panel.textContent).not.toMatch(/[А-Яа-яЁё]/);
});
it('keeps the Yandex folder connection actionable in Armenian', async () => {
  const fetcher = vi.fn(() => Promise.resolve(new Response(JSON.stringify({ enabled: true, can_configure: true, sources: [] }))));
  vi.stubGlobal('fetch', fetcher);
  render(withLanguage(<DiskImportPanel businessId="b" />, 'hy'));
  expect(await screen.findByLabelText('Յանդեքս Դիսկի պանակի հղումը')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Պատրաստել պանակը' })).toBeInTheDocument();
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

it('shows a readable error and retries an incomplete video listing', async () => {
  let broken = true;
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify(broken ? {} : { videos: [], selected: [], item_version: '' }), { status: 200 }))));
  render(withLanguage(<ExternalDriveVideos businessId="b" itemId="item" />));
  expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось выполнить действие');
  expect(screen.getByRole('alert')).not.toHaveTextContent('Cannot read');
  broken = false;
  await userEvent.click(screen.getByRole('button', { name: 'Обновить список видео' }));
  await screen.findByText('Пока нет видео. Добавьте MP4, MOV или WebM в подключённую папку.');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

it('hides the optional video section when the server reports the feature unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ error: 'not_found' }), { status: 404 }))));
  await act(async () => { render(withLanguage(<ExternalDriveVideos businessId="b" itemId="item" />)); });
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.queryByText('Видео с Диска')).not.toBeInTheDocument();
});
