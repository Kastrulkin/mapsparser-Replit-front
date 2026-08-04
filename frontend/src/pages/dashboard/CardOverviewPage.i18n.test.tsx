import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { CardOverviewPage } from './CardOverviewPage';

const response = (data: Record<string, unknown>) => Promise.resolve(new Response(JSON.stringify(data), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}));

const ContextRoute = () => (
  <Outlet context={{
    user: { id: 'demo-user' },
    currentBusinessId: 'demo-business',
    currentBusiness: { id: 'demo-business', name: 'Roga i Kopyta', subscription_status: 'active' },
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
      if (url.includes('/services/list')) return response({ success: true, services: [], external_services: [], last_parse_date: '2026-06-24T20:22:00Z' });
      if (url.includes('/external/posts')) return response({ success: true, posts: [] });
      if (url.includes('/parse-status')) return response({ success: true, status: 'idle', refresh_policy: { can_refresh: true } });
      if (url.includes('/competitors/manual')) return response({ success: true, competitors: [] });
      if (url.includes('/client-info')) return response({ success: true, businessName: 'Roga i Kopyta', mapLinks: [{ url: 'https://yandex.example/demo' }] });
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
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });
});
