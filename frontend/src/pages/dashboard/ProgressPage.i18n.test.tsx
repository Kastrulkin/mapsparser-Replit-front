import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
const originalRequestAnimationFrame = window.requestAnimationFrame;
const originalCancelAnimationFrame = window.cancelAnimationFrame;

describe('ProgressPage localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'tr');
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.startsWith('/operator/progress?')) return Promise.resolve(overview);
      return Promise.resolve({ success: true, status: 'idle' });
    });
    HTMLElement.prototype.scrollIntoView = vi.fn();
    window.requestAnimationFrame = (callback) => {
      callback(0);
      return 1;
    };
    window.cancelAnimationFrame = vi.fn();
  });

  afterEach(() => {
    HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    window.requestAnimationFrame = originalRequestAnimationFrame;
    window.cancelAnimationFrame = originalCancelAnimationFrame;
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

  it('localizes managed-card system copy from stable codes while preserving business and provider names', async () => {
    window.localStorage.setItem('language', 'es');
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.startsWith('/operator/progress?')) {
        return Promise.resolve({
          ...overview,
          focus_action: {
            id: 'card-growth:demo-business:yandex:category',
            provider: 'yandex',
            provider_label: 'Яндекс',
            fact: 'contacts',
            gate: 2,
            gate_label: 'Можно обратиться',
            copy_code: 'contacts',
            copy_params: { goal: 'bookings' },
            title: 'Заполните контакты в Яндекс',
            reason: 'Клиент должен сразу понимать, как связаться с этой точкой.',
            expected_outcome: 'Больше записей после следующей проверки.',
            cta_label: 'Проверить контакты',
            cta_url: '/dashboard/card',
          },
          goal: {
            value: 'bookings',
            label: 'Больше записей',
            status: 'recommended',
            options: [{ value: 'bookings', label: 'Больше записей' }],
          },
          card_state: {
            status: 'needs_attention',
            locations: [{
              business_id: 'demo-business',
              business_name: 'Рога и копыта',
              critical: true,
              providers: [{
                provider: 'yandex',
                provider_label: 'Яндекс',
                source_state: 'observed',
                observed_at: '2026-09-11T08:00:00Z',
                facts: {
                  contacts: {
                    state: 'missing',
                    evidence: 'Контакты из профиля бизнеса не доказывают, что они опубликованы на площадке',
                    evidence_code: 'internal_contacts',
                  },
                },
                benchmark: {
                  sample_size: 12,
                  period_days: 90,
                  disclaimer_code: 'relative_benchmark',
                },
              }],
            }],
          },
          baseline: {
            status: 'observed',
            period: { start: '2026-08-01', end: '2026-08-28' },
            providers: { yandex: { views: 12, clicks: 3, actions: 1 } },
            disclaimer: 'Показы и нажатия не являются подтверждёнными клиентами или продажами.',
            disclaimer_code: 'views_not_sales',
          },
          measurement: {
            status: 'waiting_for_measurement',
            checkpoints: [{ days: 14, due_at: '2026-10-01T00:00:00Z', status: 'waiting' }],
            decision: 'adjust',
            decision_reason: 'На первой контрольной точке роста действий пока нет; проверим следующий период.',
            decision_reason_code: 'adjust',
            result: {
              deltas: { yandex: { goal_delta: 1 } },
              disclaimer: 'Платформенные действия не являются подтверждёнными клиентами, заказами или продажами.',
              disclaimer_code: 'platform_actions_not_sales',
            },
          },
          next_actions: [{
            id: 'card-growth:demo-business:yandex:photos',
            provider: 'yandex',
            fact: 'photos',
            gate: 5,
            gate_label: 'Есть доверие',
            copy_code: 'photos',
            copy_params: { goal: 'bookings' },
            title: 'Добавьте полезные фотографии в Яндекс',
            reason: 'Покажите вход и пространство.',
            expected_outcome: 'Больше записей после следующей проверки.',
            cta_label: 'Открыть фотографии',
            business_name: 'Рога и копыта',
          }],
        });
      }
      return Promise.resolve({ success: true, status: 'idle' });
    });

    render(
      <MemoryRouter initialEntries={['/?section=maps&audit=open']}>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<ProgressPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Objetivo y estado de las fichas' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('region', { name: 'Auditoría completa de la ficha' })).toHaveFocus());
    expect(screen.getByText('Más reservas')).toBeInTheDocument();
    expect(screen.getByText('Acción principal')).toBeInTheDocument();
    expect(screen.getByText('Рога и копыта')).toBeInTheDocument();
    expect(screen.getAllByText('Яндекс').length).toBeGreaterThan(0);
    expect(screen.getByText('Completa los contactos en Яндекс')).toBeInTheDocument();
    expect(screen.getByText('Aún no hay crecimiento en el primer control; se comprobará el siguiente periodo.')).toBeInTheDocument();
    const managedPanel = screen.getByRole('heading', { name: 'Objetivo y estado de las fichas' }).closest('section');
    if (!managedPanel) throw new Error('Managed card panel was not rendered');
    const providerSummary = within(managedPanel).getAllByText('Яндекс').map((element) => element.closest('summary')).find(Boolean);
    if (!providerSummary) throw new Error('Managed provider summary was not rendered');
    await userEvent.click(providerSummary);
    expect(screen.getByText('Los contactos internos no prueban que estén publicados en la plataforma')).toBeInTheDocument();
    expect(screen.queryByText('Больше записей')).not.toBeInTheDocument();
    expect(screen.queryByText('Заполните контакты в Яндекс')).not.toBeInTheDocument();
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
