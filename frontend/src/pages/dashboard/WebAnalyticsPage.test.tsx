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
    sections: [{ hostname: 'example.com', path: '/', key: 'services', label: 'Услуги и цены', position: 2, views: 4, visitors: 3, sessions: 3, reach_percent: 60, average_engagement_seconds: 18, exits: 1 }],
    funnel: { sessions: 5, target_actions: 3, requires_page_groups: true },
    funnel_v2: { configured: true, stages: [{ key: 'sessions', label: 'Сессии', sessions: 5 }, { key: 'service', label: 'Услуги', sessions: 4 }, { key: 'target', label: 'Целевые действия', sessions: 3 }] },
    cta_performance: [{ cta_id: 'booking_hero', label: 'Записаться', impressions: 20, clicks: 5, ctr_percent: 25 }],
    form_funnels: [{ form_id: 'main_booking', starts: 5, validation_errors: 1, attempts: 4, successes: 3, submit_errors: 0 }],
    confirmed_outcomes: [{ event_type: 'booking_confirmed', count: 2, attributed: 2, revenue: 0, currency: null }],
    devices: [{ device_type: 'mobile', sessions: 4, visitors: 3 }],
    visitor_cohorts: { new_visitors: 3, returning_visitors: 1 },
    recommendations: [],
  },
};

const configurationResponse = {
  page_groups: [{ id: 'group-1', name: 'Услуги', group_type: 'service', match_type: 'prefix', include_patterns: ['/services'], exclude_patterns: [], status: 'receiving', matched_paths: 2, matched_sessions: 4 }],
  goals: [{ id: 'goal-1', name: 'Просмотр услуги', goal_type: 'page_view', matcher: { page_group_id: 'group-1' }, status: 'receiving', count: 4 }],
  annotations: [],
  campaign_costs: [],
  conversion_key: { configured: false, created_at: null },
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
    vi.mocked(newAuth.makeRequest).mockImplementation((endpoint) => {
      if (endpoint.includes('web-page-groups/preview')) return Promise.resolve({ preview: { matched_paths: 2, matched_sessions: 4, available_paths: 5, sample: [{ path: '/services', sessions: 4 }] } });
      if (endpoint.includes('web-analytics/configuration')) return Promise.resolve(configurationResponse);
      if (endpoint.endsWith('web-tracking')) return Promise.resolve(trackerResponse);
      return Promise.resolve(metricsResponse);
    });
  });

  it('shows installation state, privacy boundary, and aggregated analytics', async () => {
    renderPage();

    expect(await screen.findByText('Сбор данных работает')).toBeInTheDocument();
    expect(screen.getByText('Приватность по умолчанию')).toBeInTheDocument();
    expect(screen.getAllByText('Услуги').length).toBeGreaterThan(0);
    expect(screen.getByText('Google')).toBeInTheDocument();
    expect(screen.getByText('Форма')).toBeInTheDocument();
    expect(screen.getByText('Услуги и цены')).toBeInTheDocument();
    expect(screen.getAllByText('60%').length).toBeGreaterThan(0);
    expect(screen.getByText('Записаться')).toBeInTheDocument();
    expect(screen.getByText('Подтверждённые записи')).toBeInTheDocument();
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

  it('opens the owner setup flow and previews URL rules before save', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Сбор данных работает');

    await user.click(screen.getByRole('button', { name: 'Цели сайта' }));
    expect(await screen.findByText('1. Объедините страницы по смыслу')).toBeInTheDocument();
    expect(screen.getAllByText('Получает данные').length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: 'Добавить группу' }));
    await user.type(screen.getByLabelText('Название'), 'Цены');
    await user.type(screen.getByLabelText('URL — по одному на строку'), '/prices');
    await user.click(screen.getByRole('button', { name: 'Проверить правило' }));

    expect(await screen.findByText('Найдено 2 из 5 страниц')).toBeInTheDocument();
    expect(newAuth.makeRequest).toHaveBeenCalledWith('/business/business-1/web-page-groups/preview', expect.objectContaining({ method: 'POST' }));
  });
});
