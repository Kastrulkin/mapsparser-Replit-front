import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { ProgressPage } from './ProgressPage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

const overview = {
  summary: {
    completed_milestones: 11,
    total_milestones: 17,
    active_areas: 4,
    needs_attention: 1,
    completed_last_30_days: 6,
    locations_count: 1,
  },
  focus_action: {
    id: 'growth:finance',
    title: 'Обновите финансовые данные',
    reason: 'Финансовые данные давно не обновлялись.',
    expected_outcome: 'LocalOS сможет показать актуальную финансовую картину и точки роста.',
    cta_label: 'Загрузить данные',
    screen: 'finance',
  },
  data_health: { status: 'stale', source: 'demo_grooming_network', reason: 'Загрузите свежую выгрузку, чтобы открыть актуальную аналитику.' },
  analytics_level: { level: 'setup', label: 'Нужны данные', next_unlock: 'Загрузите первую финансовую сводку, чтобы открыть аналитику.' },
  analytics_modules: [
    { key: 'sales', label: 'Продажи и средний чек', status: 'available' },
    { key: 'trend', label: 'Динамика и доказательные рекомендации', status: 'locked' },
  ],
  rhythm: { status: 'forming', label: 'Ритм формируется' },
  areas: [
    {
      key: 'maps',
      label: 'Карты и репутация',
      status: 'needs_attention',
      summary: 'Карта подключена, аудит ещё не готов',
      problem: 'Карта подключена, но свежих данных и аудита ещё нет.',
      expected_outcome: 'Появится аудит с конкретными проблемами карточки.',
      action: {
        title: 'Получите данные карты',
        reason: 'Карта подключена, но свежих данных и аудита ещё нет.',
        expected_outcome: 'Появится аудит с конкретными проблемами карточки.',
        cta_label: 'Обновить карту',
        cta_url: '/dashboard/profile',
      },
      progress: { completed: 2, total: 4 },
      milestones: [
        { key: 'map_connected', label: 'Карта подключена', status: 'done', evidence: '6 из 6', achieved_at: '2026-06-24T12:00:00Z' },
        { key: 'map_audited', label: 'Данные и аудит получены', status: 'next' },
        { key: 'map_profile_complete', label: 'Основные данные заполнены', status: 'next' },
        { key: 'reputation_started', label: 'Начата работа с репутацией', status: 'done', evidence: 'Отзывов: 90', achieved_at: '2026-06-20T12:00:00Z' },
      ],
      metrics: [
        { label: 'Карты', value: '6 из 6' },
        { label: 'Отзывы', value: 90 },
        { label: 'Без ответа', value: 39 },
      ],
    },
  ],
  recent_achievements: [],
  scope: {
    business_id: 'demo-business',
    business_name: 'Рога и копыта',
    is_network: false,
    locations: [{ id: 'demo-business', name: 'Рога и копыта' }],
  },
  generated_at: '2026-08-04T12:00:00Z',
};

const ContextRoute = () => <Outlet context={{ currentBusinessId: 'demo-business' }} />;

describe('ProgressPage localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'tr');
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.startsWith('/operator/progress?')) return Promise.resolve(overview);
      return Promise.resolve({ success: true, status: 'idle' });
    });
  });

  it('renders Turkish system and structured growth copy when the API payload contains Russian labels', async () => {
    const { container } = render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<ProgressPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'İşletme ilerlemesi' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Haritalar ve itibar')).toBeInTheDocument());
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });

  it('renders Greek system and structured growth copy when the API payload contains Russian labels', async () => {
    window.localStorage.setItem('language', 'el');
    const { container } = render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<ProgressPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Πρόοδος επιχείρησης' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Χάρτες και φήμη')).toBeInTheDocument());
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });

  it('renders the empty recent-results state when the API omits recent achievements', async () => {
    const { recent_achievements: omittedRecentAchievements, ...overviewWithoutRecentAchievements } = overview;
    void omittedRecentAchievements;
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.startsWith('/operator/progress?')) return Promise.resolve(overviewWithoutRecentAchievements);
      return Promise.resolve({ success: true, status: 'idle' });
    });

    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<ProgressPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Doğrulanmış sonuçlar burada görünecek/)).toBeInTheDocument();
  });

  it('shows the data freshness action when the overview reports missing analytics inputs', async () => {
    window.localStorage.setItem('language', 'ru');
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.startsWith('/operator/progress?')) {
        return Promise.resolve({
          ...overview,
          data_health: {
            status: 'stale',
            source_label: 'unknown',
            missing: ['оплаты за текущий период'],
          },
        });
      }
      return Promise.resolve({ success: true, status: 'idle' });
    });

    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<ProgressPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: 'Загрузить файл из CRM' })).toBeInTheDocument();
    expect(screen.getByText(/Источник: не указан/)).toBeInTheDocument();
  });
});
