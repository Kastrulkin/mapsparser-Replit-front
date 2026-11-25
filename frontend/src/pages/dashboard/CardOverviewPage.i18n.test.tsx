import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { CardOverviewPage } from './CardOverviewPage';
import { getCardOverviewPageCopy } from './cardOverviewPageCopy';

const response = (data: Record<string, unknown>) => Promise.resolve(new Response(JSON.stringify(data), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}));

const ContextRoute = ({ demoMode = true }: { demoMode?: boolean }) => (
  <Outlet context={{
    user: { id: 'test-user', demo_mode: demoMode },
    currentBusinessId: 'demo-business',
    currentBusiness: { id: 'demo-business', name: 'Roga i Kopyta', subscription_tier: 'starter', subscription_status: 'active' },
    businesses: [],
    onBusinessChange: vi.fn(),
  }} />
);

const CurrentLocation = () => {
  const { pathname, search, hash } = useLocation();
  return <output>{pathname}{search}{hash}</output>;
};

describe('CardOverviewPage localization', () => {
  let finishYandexSummary: (() => void) | undefined;

  beforeEach(() => {
    finishYandexSummary = undefined;
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/external/summary')) {
        if (url.includes('source=yandex')) {
          return new Promise<Response>((resolve) => {
            finishYandexSummary = () => resolve(response({ success: true, rating: 3.9, reviews_total: 25, competitors: [] }));
          });
        }
        if (url.includes('source=google')) {
          return response({ success: true, rating: 4.8, reviews_total: 65, competitors: [] });
        }
        return response({ success: true, rating: 4.6, reviews_total: 90, last_parse_date: '2026-06-24T20:22:00Z', competitors: [] });
      }
      if (url.includes('/services/list')) return response({
        success: true,
        services: [{ id: 'demo-service', name: 'Стрижка собак', description: 'Аккуратная стрижка и уход за шерстью.', keywords: ['груминг собак'] }],
        external_services: [],
        last_parse_date: '2026-06-24T20:22:00Z',
      });
      if (url.includes('/external/posts')) return response({
        success: true,
        posts: [{ id: 'demo-post', title: 'Летний уход за питомцем', text: 'Как подготовить шерсть к жаркой погоде.', source: 'yandex' }],
      });
      if (url.includes('/parse-status')) return response({ success: true, status: 'idle', refresh_policy: { can_refresh: true } });
      if (url.includes('/competitors/manual')) return response({
        success: true,
        competitors: window.localStorage.getItem('language') === 'tr'
          ? [
            { id: 'competitor-1', name: 'Пушистый Стиль', url: 'https://yandex.example/competitor-1' },
            { id: 'competitor-2', name: 'Барбос & Мурка', url: 'https://yandex.example/competitor-2' },
          ]
          : [],
      });
      if (url.includes('/client-info')) return response({
        success: true,
        businessName: 'Roga i Kopyta',
        mapLinks: window.localStorage.getItem('language') === 'tr'
          ? [{ url: 'https://yandex.example/demo' }, { url: 'https://2gis.example/demo' }]
          : [{ url: 'https://yandex.example/demo' }, { url: 'https://www.google.com/maps/place/Demo' }],
      });
      if (url.includes('/network-locations')) return response({ success: true, locations: [] });
      return response({ success: true });
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders the services start screen in Greek without Cyrillic system copy', async () => {
    const { container } = render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<CardOverviewPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Βαθμολογία')).toBeInTheDocument();
    expect(await screen.findByText('90', { exact: true })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Υπηρεσίες' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Κριτικές' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Νέα' })).toBeInTheDocument();
    expect((await screen.findAllByText('Κούρεμα σκύλων')).length).toBeGreaterThan(0);
    expect(screen.getByText('Προσεκτικό κούρεμα και περιποίηση τριχώματος.')).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
    expect(container.textContent).not.toContain('LAST UPDATED');
    expect(container.textContent).not.toContain('Could not update card data');
  });

  it('renders Turkish map sources and demo competitors without Russian or English fallback copy', async () => {
    window.localStorage.setItem('language', 'tr');

    const { container } = render(
      <MemoryRouter initialEntries={['/?tab=competitors']}>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<CardOverviewPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('tab', { name: 'Rakipler' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText('Pofuduk Stil').length).toBeGreaterThan(0));
    expect(screen.getByRole('button', { name: '2GIS' })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);

    const copy = getCardOverviewPageCopy('tr');
    expect(copy.refreshAllHint).toBe('Eklenen tüm harita kayıtlarını yeniler. Kayıt verilerinin miktarına bağlı olarak yaklaşık 10 kredi tutar.');
    expect(copy.refreshAllHint).not.toContain('Refreshes all added map listings');
  });

  it('redirects an old map content-plan link to the calendar with its business and plan', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/card?tab=news&mode=plan&business_id=demo-business&plan_id=plan-1#calendar']}>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route path="/dashboard/card" element={<CardOverviewPage />} />
            </Route>
            <Route path="/dashboard/content" element={<CurrentLocation />} />
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('/dashboard/content?business_id=demo-business&plan_id=plan-1&section=calendar#calendar')).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('opens the reviews workspace with the unanswered filter from the route', async () => {
    window.localStorage.setItem('language', 'ru');

    render(
      <MemoryRouter initialEntries={['/?tab=reviews&review_filter=needs_reply']}>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute demoMode={false} />}>
              <Route index element={<CardOverviewPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('tab', { name: 'Отзывы' })).toHaveAttribute('data-state', 'active');
    expect(await screen.findByRole('button', { name: /Без ответа/ })).toHaveClass('bg-slate-900');
    expect(screen.queryByText('Как работать с данными карточки')).not.toBeInTheDocument();
  });

  it('keeps service settings without repeating the listing refresh timestamp', async () => {
    window.localStorage.setItem('language', 'ru');

    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<CardOverviewPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: 'Настройки' })).toBeInTheDocument();
    expect(screen.queryByText(/^Последнее обновление карточки:/)).not.toBeInTheDocument();
  });

  it('keeps the platform selector separate from section navigation and ignores an older platform response', async () => {
    window.localStorage.setItem('language', 'ru');

    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<CardOverviewPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    const platform = await screen.findByRole('group', { name: 'Площадка' });
    expect(screen.queryByText('Площадка', { exact: true })).not.toBeInTheDocument();
    const all = within(platform).getByRole('button', { name: 'Все карты' });
    const yandex = within(platform).getByRole('button', { name: 'Яндекс' });
    const google = within(platform).getByRole('button', { name: 'Google' });
    const sections = screen.getByRole('tablist', { name: 'Управление картами' });
    const services = within(sections).getByRole('tab', { name: 'Услуги' });

    expect(all).toHaveAttribute('aria-pressed', 'true');
    expect(services).toHaveAttribute('aria-selected', 'true');
    expect(platform.compareDocumentPosition(sections) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(await screen.findByText('4.6', { exact: true })).toBeInTheDocument();
    expect(screen.getAllByText('Рейтинг', { exact: true })).toHaveLength(1);

    fireEvent.click(yandex);
    expect(yandex).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByText('4.6', { exact: true })).not.toBeInTheDocument();
    await waitFor(() => expect(finishYandexSummary).toBeTypeOf('function'));

    fireEvent.click(google);
    expect(google).toHaveAttribute('aria-pressed', 'true');
    expect(yandex).toHaveAttribute('aria-pressed', 'false');
    expect(await screen.findByText('4.8', { exact: true })).toBeInTheDocument();
    await act(async () => { finishYandexSummary?.(); });
    expect(screen.getByText('4.8', { exact: true })).toBeInTheDocument();
    expect(screen.queryByText('3.9', { exact: true })).not.toBeInTheDocument();
    expect(services).toHaveAttribute('aria-selected', 'true');

    fireEvent.click(all);
    expect(all).toHaveAttribute('aria-pressed', 'true');
    expect(await screen.findByText('4.6', { exact: true })).toBeInTheDocument();
  });
});
