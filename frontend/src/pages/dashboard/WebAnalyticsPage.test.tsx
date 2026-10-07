import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WebAnalyticsPage } from './WebAnalyticsPage';
import { newAuth } from '@/lib/auth_new';


vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

vi.mock('@/i18n/LanguageContext', () => ({
  useLanguage: () => ({ language: 'ru' }),
}));

const trackerResponse = {
  tracker: {
    public_tracker_id: 'pub_demo',
    embed_code: '<script async src="https://localos.pro/tracker.js" data-business="pub_demo"></script>',
    status: 'working',
    last_event_at: '2026-08-16T12:00:00Z',
    enabled: true,
  },
};

const metricsResponse = {
  metrics: {
    totals: { visitors: 4, sessions: 5, page_views: 12, conversions: 3 },
    top_pages: [{ path: '/services', title: 'Услуги', visitors: 4, views: 7, conversions: 2, average_engagement_seconds: 42 }],
    traffic_sources: [{ source: 'Google', source_type: 'search', sessions: 5 }],
    conversions: [{ action: 'Форма отправлена', action_type: 'form', count: 2 }],
    top_paths: [{ path: '/ → /services', sessions: 3 }],
    funnel: { sessions: 5, target_actions: 3, requires_page_groups: true },
  },
};

const Context = () => <Outlet context={{ currentBusinessId: 'business-1', currentBusiness: { web_tracking_available: true } }} />;

const renderPage = () => render(
  <MemoryRouter initialEntries={['/dashboard/web-analytics']}>
    <Routes>
      <Route element={<Context />}>
        <Route path="/dashboard/web-analytics" element={<WebAnalyticsPage />} />
      </Route>
    </Routes>
  </MemoryRouter>,
);

describe('WebAnalyticsPage', () => {
  beforeEach(() => {
    vi.mocked(newAuth.makeRequest).mockImplementation((endpoint) => (
      Promise.resolve(endpoint.includes('web-tracking') ? trackerResponse : metricsResponse)
    ));
  });

  it('shows installation state, privacy boundary, and aggregated analytics', async () => {
    renderPage();

    expect(await screen.findByText('Сбор данных работает')).toBeInTheDocument();
    expect(screen.getByText('Приватность по умолчанию')).toBeInTheDocument();
    expect(screen.getByText('Услуги')).toBeInTheDocument();
    expect(screen.getByText('Google')).toBeInTheDocument();
    expect(screen.getByText('Форма')).toBeInTheDocument();
  });

  it('reloads analytics for a newly selected period', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Сбор данных работает');

    await user.click(screen.getByRole('button', { name: '7 дней' }));

    await waitFor(() => {
      expect(newAuth.makeRequest).toHaveBeenCalledWith('/business/business-1/web-analytics?period=7');
    });
  });
});
