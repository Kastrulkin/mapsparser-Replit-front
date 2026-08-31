import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { ProgressPage } from './ProgressPage';
import { NetworkDashboardPage } from './network/NetworkDashboardPage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

type MapLocation = {
  id: string;
  name: string;
};

type NetworkMapMockProps = {
  locations: MapLocation[];
  onOpenDashboard?: (businessId: string) => void;
};

vi.mock('./network/components/NetworkMap', () => ({
  NetworkMap: ({ locations, onOpenDashboard }: NetworkMapMockProps) => (
    <section data-testid="network-map">
      <span>{locations.length} точки на карте</span>
      {locations.map((location) => (
        <button key={location.id} type="button" onClick={() => onOpenDashboard?.(location.id)}>
          Открыть {location.name}
        </button>
      ))}
    </section>
  ),
}));

const networkOverview = {
  summary: {
    completed_milestones: 4,
    total_milestones: 8,
    active_areas: 2,
    needs_attention: 1,
    completed_last_30_days: 2,
    locations_count: 2,
  },
  focus_action: null,
  areas: [{
    key: 'maps',
    label: 'Карты и репутация',
    status: 'healthy',
    summary: 'Карточки сети подключены',
    problem: null,
    expected_outcome: 'Данные сети остаются актуальными.',
    action: {
      title: 'Открыть карты',
      reason: 'Карточки подключены.',
      expected_outcome: 'Данные сети остаются актуальными.',
      cta_label: 'Открыть карты',
      screen: 'progress',
    },
    progress: { completed: 4, total: 4 },
    milestones: [{ key: 'map_audited', label: 'Аудит готов', status: 'done' }],
    metrics: [],
  }],
  recent_achievements: [],
  network_summary: {
    locations_count: 2,
    problem_locations_count: 1,
    healthy_locations_count: 1,
  },
  problem_locations: [],
  scope: {
    business_id: 'parent-business',
    business_name: 'Демо-сеть',
    is_network: true,
    locations: [
      { id: 'location-1', name: 'Точка на Невском' },
      { id: 'location-2', name: 'Точка на Литейном' },
    ],
  },
  generated_at: '2026-08-31T12:00:00Z',
};

const businessOverview = {
  ...networkOverview,
  network_summary: null,
  scope: {
    business_id: 'location-1',
    business_name: 'Точка на Невском',
    is_network: false,
    locations: [{ id: 'location-1', name: 'Точка на Невском' }],
  },
};

const jsonResponse = (payload: object) => ({
  json: () => Promise.resolve(payload),
});

describe('ProgressPage network map', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'ru');
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.startsWith('/operator/progress?')) return Promise.resolve(networkOverview);
      if (url.startsWith('/journey-actions?')) return Promise.resolve({ actions: [] });
      return Promise.resolve({ success: true, status: 'idle' });
    });
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/network-locations')) {
        return Promise.resolve(jsonResponse({
          success: true,
          network_id: 'network-1',
          locations: [
            { id: 'location-1', name: 'Точка на Невском', address: 'Невский проспект', geo_lat: '59.93', geo_lon: '30.31', rating: 4.8, reviews_count: 120 },
            { id: 'location-2', name: 'Точка на Литейном', address: 'Литейный проспект', geo_lat: '59.94', geo_lon: '30.35', rating: 4.6, reviews_count: 80 },
          ],
        }));
      }
      if (url.includes('/network/health')) {
        return Promise.resolve(jsonResponse({ success: true, data: { locations_count: 2, avg_rating: 4.7, total_reviews: 200, unanswered_reviews_count: 3 } }));
      }
      if (url.includes('/metrics-history')) {
        return Promise.resolve(jsonResponse({ history: [] }));
      }
      return Promise.resolve(jsonResponse({ success: true, data: { locations: [] } }));
    }));
  });

  it('shows the network map and opens a selected location in LocalOS', async () => {
    const onBusinessChange = vi.fn();
    const onControlScopeChange = vi.fn();
    const ContextRoute = () => (
      <Outlet context={{
        currentBusinessId: 'parent-business',
        controlScope: { kind: 'network', id: 'network-1', name: 'Демо-сеть' },
        onBusinessChange,
        onControlScopeChange,
      }} />
    );

    render(
      <MemoryRouter initialEntries={['/dashboard/progress']}>
        <LanguageProvider>
          <Routes>
            <Route path="/dashboard" element={<ContextRoute />}>
              <Route path="progress" element={<ProgressPage />} />
              <Route path="card" element={<div>Карточка выбранной точки</div>} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('network-map')).toBeInTheDocument();
    expect(await screen.findByText('2 точки на карте')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Открыть Точка на Литейном' }));

    expect(onBusinessChange).toHaveBeenCalledWith('location-2');
    expect(onControlScopeChange).toHaveBeenCalledWith({ kind: 'business', id: 'location-2', name: 'Точка на Литейном' });
    expect(await screen.findByText('Карточка выбранной точки')).toBeInTheDocument();
  });

  it('does not show the network map for a single business', async () => {
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.startsWith('/operator/progress?')) return Promise.resolve(businessOverview);
      return Promise.resolve({ success: true, status: 'idle' });
    });
    const ContextRoute = () => (
      <Outlet context={{
        currentBusinessId: 'location-1',
        controlScope: { kind: 'business', id: 'location-1', name: 'Точка на Невском' },
      }} />
    );

    render(
      <MemoryRouter initialEntries={['/dashboard/progress']}>
        <LanguageProvider>
          <Routes>
            <Route path="/dashboard" element={<ContextRoute />}>
              <Route path="progress" element={<ProgressPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Что уже сделано' })).toBeInTheDocument();
    expect(screen.queryByTestId('network-map')).not.toBeInTheDocument();
  });

  it('loads the network dashboard from the selected parent scope when no business prop is supplied', async () => {
    const ContextRoute = () => (
      <Outlet context={{
        currentBusinessId: 'parent-business',
        controlScope: { kind: 'network', id: 'network-1', name: 'Демо-сеть' },
      }} />
    );

    render(
      <MemoryRouter initialEntries={['/dashboard/network']}>
        <LanguageProvider>
          <Routes>
            <Route path="/dashboard" element={<ContextRoute />}>
              <Route path="network" element={<NetworkDashboardPage embedded />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('network-map')).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      '/api/business/parent-business/network-locations',
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });
});
