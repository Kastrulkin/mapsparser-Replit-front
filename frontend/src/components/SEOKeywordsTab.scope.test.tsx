import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { LanguageProvider } from '@/i18n/LanguageContext';
import SEOKeywordsTab from './SEOKeywordsTab';

const ContextRoute = () => <Outlet context={{ user: { id: 'test-user' } }} />;
const app = (businessId: string | null) => (
  <MemoryRouter initialEntries={['/?lang=ru']}>
    <LanguageProvider>
      <Routes>
        <Route element={<ContextRoute />}>
          <Route index element={<SEOKeywordsTab businessId={businessId} />} />
        </Route>
      </Routes>
    </LanguageProvider>
  </MemoryRouter>
);

const json = (body: object) => Response.json(body);
const keywordList = (keyword: string) => {
  const item = { keyword, category: 'ключи', views: 30, updated_at: '2026-11-22' };
  return json({ success: true, items: [item], grouped: { ключи: [item] } });
};

beforeEach(() => window.localStorage.setItem('language', 'ru'));
afterEach(() => {
  window.localStorage.removeItem('language');
  vi.unstubAllGlobals();
});

it('keeps the selected business after an older response arrives', async () => {
  let resolveOld: (response: Response) => void = () => {};
  const oldResponse = new Promise<Response>(resolve => { resolveOld = resolve; });
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith('/negative-keywords')) return Promise.resolve(json({ success: true, items: [] }));
    if (url.searchParams.get('business_id') === 'old-business') return oldResponse;
    return Promise.resolve(keywordList('Новые данные'));
  });
  vi.stubGlobal('fetch', fetchMock);

  const { rerender } = render(app('old-business'));
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/keywords?business_id=old-business'))).toBe(true));
  rerender(app('new-business'));
  expect(await screen.findByRole('cell', { name: 'Новые данные' })).toBeInTheDocument();
  await act(async () => { resolveOld(keywordList('Старые данные')); });
  expect(screen.getByRole('cell', { name: 'Новые данные' })).toBeInTheDocument();
  expect(screen.queryByRole('cell', { name: 'Старые данные' })).not.toBeInTheDocument();
});

it('does not request or display business keywords without a selected business', async () => {
  const fetchMock = vi.fn(() => Promise.resolve(keywordList('Старые данные')));
  vi.stubGlobal('fetch', fetchMock);
  const { rerender } = render(app('old-business'));
  expect(await screen.findByRole('cell', { name: 'Старые данные' })).toBeInTheDocument();
  fetchMock.mockClear();

  rerender(app(null));
  expect(fetchMock).not.toHaveBeenCalled();
  const table = screen.getByRole('table');
  expect(within(table).queryByRole('cell', { name: 'Старые данные' })).not.toBeInTheDocument();
  expect(within(table).getByText('Выберите бизнес')).toBeInTheDocument();
});

it('applies only the last filter change and reuses the loaded negative keywords', async () => {
  let resolveFiltered: (response: Response) => void = () => {};
  const filteredResponse = new Promise<Response>(resolve => { resolveFiltered = resolve; });
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), window.location.origin);
    if (url.pathname.endsWith('/negative-keywords')) return Promise.resolve(json({ success: true, items: [] }));
    if (url.searchParams.get('include_blocked') === '1') return filteredResponse;
    return Promise.resolve(keywordList('Актуальные запросы'));
  });
  vi.stubGlobal('fetch', fetchMock);

  render(app('test-business'));
  expect(await screen.findByRole('cell', { name: 'Актуальные запросы' })).toBeInTheDocument();
  const filter = screen.getByLabelText('Показать исключённые минус-словами');
  fireEvent.click(filter);
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes('include_blocked=1'))).toBe(true));
  fireEvent.click(filter);
  await act(async () => { resolveFiltered(keywordList('Устаревшая выборка')); });
  expect(await screen.findByRole('cell', { name: 'Актуальные запросы' })).toBeInTheDocument();
  expect(screen.queryByRole('cell', { name: 'Устаревшая выборка' })).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/negative-keywords'))).toHaveLength(1);
});
