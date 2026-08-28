import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { CardOverviewPage } from './CardOverviewPage';
import { getCardOverviewPageCopy } from './cardOverviewPageCopy';

const response = (data: Record<string, unknown>) => Promise.resolve(new Response(JSON.stringify(data), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}));

const ContextRoute = () => (
  <Outlet context={{
    user: { id: 'demo-user', demo_mode: true },
    currentBusinessId: 'demo-business',
    currentBusiness: { id: 'demo-business', name: 'Roga i Kopyta', subscription_tier: 'starter', subscription_status: 'active' },
    businesses: [],
    onBusinessChange: vi.fn(),
  }} />
);

describe('CardOverviewPage localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/external/summary')) return response({ success: true, rating: 4.6, reviews_total: 90, last_parse_date: '2026-06-24T20:22:00Z', competitors: [] });
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
          : [{ url: 'https://yandex.example/demo' }],
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

    expect(await screen.findByRole('heading', { name: 'Βαθμολογία' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('90 κριτικές')).toBeInTheDocument());
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

  it('opens the reviews workspace with the unanswered filter from the route', async () => {
    window.localStorage.setItem('language', 'ru');

    render(
      <MemoryRouter initialEntries={['/?tab=reviews&review_filter=needs_reply']}>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
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
});
